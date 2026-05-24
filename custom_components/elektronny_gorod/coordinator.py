"""DataUpdateCoordinator для Elektronny Gorod.

См. ADR-0002 (CoordinatorEntity + update_interval) и ADR-0003 (iot_class).

Slice 3a (текущий PR):
- `update_interval=timedelta(minutes=5)`.
- `_async_update_data` собирает все runtime-данные за один тик и возвращает
  dict `{places, balances, cameras, locks}`. HA-core кэширует это в
  `coordinator.data`.
- Старые методы (`get_*_info`, `update_*_state`) сохранены как shims над
  `self.data` — entities продолжают работать через них без изменений.
- Snapshot / stream / open_lock — on-demand actions (не data).

Slice 3b (будущий PR):
- Entities наследуют `CoordinatorEntity`, читают `self.coordinator.data` напрямую.
- Старые shim-методы удалить.

⚠️ Concurrency: `self._api.http.user_agent.place_id` — shared state, которое
читается в момент построения HTTP-headers (см. `mirror-app-behavior` memory:
UA — load-bearing fingerprint). Поэтому ВЕСЬ refresh идёт **последовательно**
по places. Race-free; параллелизация — отдельная задача, требующая
рефакторинга `HTTP` (передавать `place_id` per-request, не через state).
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import timedelta
import json
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ElektronnyGorodAPI
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DEFAULT_SNAPSHOT_WIDTH,
    DOMAIN,
    LOGGER,
)
from .helpers import dedupe_by_id
from .user_agent import UserAgent

UPDATE_INTERVAL = timedelta(minutes=5)


class ElektronnyGorodUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator: периодически опрашивает API, кэширует в self.data."""

    def __init__(self, hass: HomeAssistant, *, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        user_agent = UserAgent()
        user_agent.from_json(json.loads(entry.data[CONF_USER_AGENT]))

        self._api = ElektronnyGorodAPI(
            hass,
            user_agent,
            access_token=entry.data[CONF_ACCESS_TOKEN],
            refresh_token=entry.data[CONF_REFRESH_TOKEN],
            operator=str(entry.data[CONF_OPERATOR_ID]),
        )

        LOGGER.info("Integration loading entry %s", entry.entry_id)

        # Dispatcher listener (для будущих фич; сейчас no-op).
        self._unsub_notifications: Callable[[], None] = async_dispatcher_connect(
            hass,
            persistent_notification.SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED,
            self._notification_dismiss_listener,
        )

        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    @callback
    def _notification_dismiss_listener(self, _type: Any, _data: Any) -> None:
        """Hook для HA persistent notifications (placeholder)."""
        return

    # ------------------------------------------------------------------ #
    # Periodic refresh (`_async_update_data`)                            #
    # ------------------------------------------------------------------ #

    async def _async_update_data(self) -> dict[str, Any]:
        """Обновить весь снапшот данных за один тик.

        Возвращает dict:
            {
                "places":   list[dict],          # subscriber places
                "balances": list[dict],          # per-place balance info
                "cameras":  list[dict],          # уникальные камеры (по id)
                "locks":    list[dict],          # по entrance (или AC, если нет entrances)
            }

        Стратегия ошибок:
        - Если `query_places` упал — поднимаем `UpdateFailed` (без places никого
          не построить).
        - Per-place sub-задачи (balance/cameras/locks) ловятся индивидуально;
          partial data допустима. Логируется warning-ом, не tracebackом, чтобы
          не спамить лог при стабильном per-place failure.

        ⚠️ Race-safety: serial по places (см. module docstring).
        """
        try:
            places = await self._api.query_places()
        except Exception as ex:  # noqa: BLE001
            LOGGER.exception("Failed to load subscriber places")
            raise UpdateFailed(f"places: {ex}") from ex

        if not places:
            LOGGER.warning("No subscriber places returned by API")
            return {"places": [], "balances": [], "cameras": [], "locks": []}

        balances: list[dict[str, Any]] = []
        cameras: list[dict[str, Any]] = []
        locks: list[dict[str, Any]] = []

        for _, place_id in self._iter_place_ids(places):
            # Установка `place_id` в shared UA — критично сделать ДО любого
            # запроса для этого place. Поскольку refresh serial — race нет.
            self._api.http.user_agent.place_id = place_id

            try:
                balance = await self._fetch_balance(place_id)
            except Exception as ex:  # noqa: BLE001
                LOGGER.warning("Balance fetch failed for place_id=%s: %s", place_id, ex)
            else:
                if balance:
                    balances.append(balance)

            try:
                cameras.extend(await self._collect_cameras_for_place(place_id))
            except Exception as ex:  # noqa: BLE001
                LOGGER.warning("Cameras fetch failed for place_id=%s: %s", place_id, ex)

            try:
                locks.extend(await self._collect_locks_for_place(place_id))
            except Exception as ex:  # noqa: BLE001
                LOGGER.warning("Locks fetch failed for place_id=%s: %s", place_id, ex)

        cameras = dedupe_by_id(cameras) if cameras else []

        LOGGER.debug(
            "Coordinator refresh: %d places, %d balances, %d cameras, %d locks",
            len(places), len(balances), len(cameras), len(locks),
        )

        return {
            "places": places,
            "balances": balances,
            "cameras": cameras,
            "locks": locks,
        }

    @staticmethod
    def _iter_place_ids(
        places: list[dict[str, Any]],
    ) -> Iterator[tuple[dict[str, Any], str]]:
        """Yield `(subscriber_place, place_id)` для каждого валидного place."""
        for subscriber_place in places:
            place = subscriber_place.get("place") or {}
            place_id = place.get("id")
            if not place_id:
                continue
            yield subscriber_place, place_id

    # ------------------------------------------------------------------ #
    # Per-place collectors (вызываются сериально из `_async_update_data`)#
    # ------------------------------------------------------------------ #

    async def _fetch_balance(self, place_id: str) -> dict[str, Any] | None:
        """Балансовая запись для одного place."""
        finance = await self._api.query_balance(place_id)
        if not finance:
            return None
        return {
            "place_id": place_id,
            "balance": finance.get("balance"),
            "block_type": finance.get("blockType"),
            "blocked": finance.get("blocked"),
            "payment_date": finance.get("targetDate"),
            "payment_sum": finance.get("amountSum"),
            "payment_link": finance.get("paymentLink"),
        }

    async def _collect_cameras_for_place(self, place_id: str) -> list[dict[str, Any]]:
        """Камеры одного place — три источника (access_controls + public + cameras).

        Раньше дубликат логики был в `get_cameras_info` и `update_camera_state`
        (audit A-17). Теперь один helper.
        """
        cameras: list[dict[str, Any]] = []

        # 1. Access controls (домофоны с externalCameraId).
        access_controls = await self._api.query_access_controls(place_id)
        for ac in access_controls:
            if not ac.get("externalCameraId"):
                continue
            cameras.append({"id": ac.get("externalCameraId"), "name": ac.get("name")})

        # 2. Public cameras (дворовые).
        public_cameras = await self._api.query_public_cameras(place_id)
        for cam in public_cameras:
            cameras.append({
                "id": cam.get("externalCameraId") or cam.get("id"),
                "name": cam.get("name"),
            })

        # 3. Place-cameras.
        place_cameras = await self._api.query_cameras(place_id)
        for cam in place_cameras:
            cameras.append({
                "id": cam.get("externalCameraId") or cam.get("id"),
                "name": cam.get("name"),
            })

        return cameras

    async def _collect_locks_for_place(self, place_id: str) -> list[dict[str, Any]]:
        """Locks одного place (один per entrance, либо per AC если без entrances)."""
        locks: list[dict[str, Any]] = []
        access_controls = await self._api.query_access_controls(place_id)
        for ac in access_controls:
            entrances = ac.get("entrances") or []
            if entrances:
                for entrance in entrances:
                    locks.append({
                        "place_id": place_id,
                        "access_control_id": ac.get("id"),
                        "entrance_id": entrance.get("id"),
                        "name": entrance.get("name"),
                        "openable": entrance.get("allowOpen"),
                    })
            else:
                locks.append({
                    "place_id": place_id,
                    "access_control_id": ac.get("id"),
                    "entrance_id": None,
                    "name": ac.get("name"),
                    "openable": ac.get("allowOpen"),
                })
        return locks

    # ------------------------------------------------------------------ #
    # Lifecycle                                                          #
    # ------------------------------------------------------------------ #

    def async_unsubscribe(self) -> None:
        """Отписаться от dispatcher listener. Вызывается из async_unload_entry."""
        self._unsub_notifications()

    # ------------------------------------------------------------------ #
    # On-demand actions (не кэшируются в self.data)                      #
    # ------------------------------------------------------------------ #

    async def get_camera_stream(self, camera_id: str) -> str | None:
        """Fetch a single-use camera stream URL. On-demand action."""
        LOGGER.debug("Fetching camera %s stream URL", camera_id)
        return await self._api.query_camera_stream(camera_id)

    async def get_camera_snapshot(
        self,
        camera_id: str,
        width: int | None,
        height: int | None,
    ) -> bytes:
        """Fetch camera snapshot bytes. On-demand action."""
        w = width or DEFAULT_SNAPSHOT_WIDTH
        h = height or round(w / 16 * 9)
        LOGGER.debug("Fetching camera %s snapshot %sx%s", camera_id, w, h)
        return await self._api.query_camera_snapshot(camera_id, w, h)

    async def open_lock(
        self,
        place_id: str,
        access_control_id: str,
        entrance_id: str | None,
    ) -> None:
        """Send open lock command. On-demand action."""
        LOGGER.info(
            "Opening lock place_id=%s ac=%s entrance=%s",
            place_id, access_control_id, entrance_id,
        )
        await self._api.open_lock(place_id, access_control_id, entrance_id)
