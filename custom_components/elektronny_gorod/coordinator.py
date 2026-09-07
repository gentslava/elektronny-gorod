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
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ElektronnyGorodAPI
from .http import is_unauthorized
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


# Запись с уже разобранным координатором. Состояние снимает ядро, поэтому
# забыть подчистить его невозможно — в отличие от `hass.data[DOMAIN][entry_id]`,
# который снимался вручную.
type ElektronnyGorodConfigEntry = ConfigEntry[ElektronnyGorodUpdateCoordinator]


@callback
def async_get_coordinator(
    hass: HomeAssistant, entry_id: str
) -> "ElektronnyGorodUpdateCoordinator | None":
    """Координатор загруженной записи, либо None.

    Проверка состояния обязательна: после успешной выгрузки ядро удаляет
    `runtime_data`, и обращение к нему у выгруженной записи упало бы.
    """
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        # Реестр записей глобальный. Раньше домен проверялся неявно — поиск шёл
        # по нашему словарю, — и чужой идентификатор просто не находился. Без
        # этой строки он доходит до `runtime_data` чужой интеграции: у media
        # source идентификатор приходит из пользовательского `media-source://`.
        return None
    if entry.state is not ConfigEntryState.LOADED:
        return None
    return entry.runtime_data


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

        # Виды данных, по которым оператор сейчас молчит: `(что, place_id)`.
        # Нужны, чтобы сообщить об отказе один раз, а не каждый цикл.
        self._failing: set[tuple[str, str]] = set()

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

    @property
    def api(self) -> ElektronnyGorodAPI:
        """Read-only доступ к API-обёртке (для FCM push-registration в fcm.py)."""
        return self._api

    # ------------------------------------------------------------------ #
    # Public service methods (вызываются entity-слоем)                   #
    # ------------------------------------------------------------------ #

    async def async_set_dnd(
        self,
        place_id: str,
        items: list[dict[str, Any]],
    ) -> bool:
        """Update DND settings for a place.

        Caller (switch entity) формирует полный payload (3 items с обновлёнными
        `status`).

        ⚠️ Inter-task race с `_async_update_data` теоретически возможен (оба
        мутируют shared `user_agent.place_id`), но **не affecting корректность**:
        backend идентифицирует место по `place_id` в URL `.../places/{id}/...`,
        UA-поле — лишь metadata о клиенте. Worst case — UA содержит чужой
        place_id в момент DND POST; backend всё равно обрабатывает запрос
        корректно по URL. Полноценный `asyncio.Lock` — overengineering для
        этой semantics.

        Returns True если backend принял.
        """
        self._api.http.user_agent.place_id = place_id
        if not await self._api.post_dnd_settings(place_id, items):
            return False
        # Принятый payload — и есть новое состояние. Без записи в снимок
        # следующий переключатель того же адреса построит свой payload из
        # старых данных и вернёт назад только что включённое.
        #
        # Дебаунсер `async_request_refresh` первый вызов в окне выполняет
        # немедленно (`REQUEST_REFRESH_DEFAULT_IMMEDIATE`), поэтому после
        # первого переключения снимок и так перечитывается у оператора — эта
        # запись нужна для всех последующих, которые дебаунсер уже отложил на
        # десять секунд. Вторая половина защиты — сериализация действий
        # (`PARALLEL_UPDATES = 1` в `switch.py`): без неё переключатели
        # строят payload одновременно, и записывать в снимок уже поздно.
        if isinstance(self.data, dict):
            self.data.setdefault("dnd", {})[str(place_id)] = [dict(i) for i in items]
            # Без этого снимок и состояние в Home Assistant расходятся до
            # следующего отложенного обновления: тумблер на глазах
            # отскакивает назад, а сценарий, читающий соседний переключатель
            # сразу после переключения, видит доизменённое значение.
            self.async_update_listeners()
        return True

    # ------------------------------------------------------------------ #
    # Periodic refresh (`_async_update_data`)                            #
    # ------------------------------------------------------------------ #

    async def _async_update_data(self) -> dict[str, Any]:
        """Обновить весь снапшот данных за один тик.

        Возвращает dict:
            {
                "places":   list[dict],            # subscriber places
                "balances": list[dict],            # per-place balance info
                "cameras":  list[dict],            # уникальные камеры (по id)
                "locks":    list[dict],            # по entrance (или AC, если нет entrances)
                "dnd":      dict[str, list[dict]], # do_not_disturb per place_id
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
            # 401 повтором не лечится: токен отозван, и ждать нечего. Home
            # Assistant по этому исключению сам предложит войти заново, а
            # раньше запись просто уходила в «недоступна» без объяснения.
            if is_unauthorized(ex):
                LOGGER.warning("Оператор отверг токен — нужна повторная авторизация")
                raise ConfigEntryAuthFailed("token rejected by operator") from ex
            # Своего лога здесь быть не должно: ядро само пишет об отказе
            # один раз на переходе и о возвращении данных
            # (`Error fetching … data` / `Fetching … data recovered` в
            # `update_coordinator.py`). Прежний `LOGGER.exception` дублировал
            # его трейсбеком на КАЖДОМ цикле — под три сотни за сутки молчания
            # оператора, ровно против правила Silver `log-when-unavailable`.
            # Тип, а не текст: в тексте оператора может быть адрес или id.
            raise UpdateFailed(f"places: {type(ex).__name__}") from ex

        if not places:
            # Тоже один раз: у заблокированного аккаунта список пуст сутками.
            self._note_failure("Список адресов", None, "оператор вернул пустой список")
            return {"places": [], "balances": [], "cameras": [], "locks": [], "dnd": {}}

        self._note_success("Список адресов", None)

        balances: list[dict[str, Any]] = []
        cameras: list[dict[str, Any]] = []
        locks: list[dict[str, Any]] = []
        dnd: dict[str, list[dict[str, Any]]] = {}

        for _, place_id in self._iter_place_ids(places):
            # Установка `place_id` в shared UA — критично сделать ДО любого
            # запроса для этого place. Поскольку refresh serial — race нет.
            self._api.http.user_agent.place_id = place_id

            try:
                balance = await self._fetch_balance(place_id)
            except Exception as ex:  # noqa: BLE001
                self._note_failure("Баланс", place_id, ex)
            else:
                self._note_success("Баланс", place_id)
                if balance:
                    balances.append(balance)

            # Pre-fetch shared per-place data (A-61): screens + access_controls
            # нужны и для cameras (для hidden), и для locks. Раньше каждый
            # collector делал свой fetch — двойной HTTP. Теперь один раз per
            # place, передаём в collectors как параметры.
            try:
                screens = await self._api.query_screens_settings(place_id)
            except Exception as ex:  # noqa: BLE001
                self._note_failure("Настройки экранов", place_id, ex)
                screens = {}
            else:
                self._note_success("Настройки экранов", place_id)
            try:
                access_controls = await self._api.query_access_controls(place_id)
            except Exception as ex:  # noqa: BLE001
                self._note_failure("Домофоны", place_id, ex)
                access_controls = []
            else:
                self._note_success("Домофоны", place_id)

            hidden_cam_ids = self._extract_hidden_ids(screens, "PUBLIC_CAMERAS")
            hidden_entrance_ids = self._extract_hidden_ids(screens, "ACCESS_CONTROLS")

            try:
                cameras.extend(await self._collect_cameras_for_place(
                    place_id, access_controls, hidden_cam_ids, hidden_entrance_ids
                ))
            except Exception as ex:  # noqa: BLE001
                self._note_failure("Камеры", place_id, ex)
            else:
                self._note_success("Камеры", place_id)

            try:
                locks.extend(self._collect_locks_for_place(
                    place_id, access_controls, hidden_entrance_ids
                ))
            except Exception as ex:  # noqa: BLE001
                self._note_failure("Замки", place_id, ex)
            else:
                self._note_success("Замки", place_id)

            try:
                dnd_items = await self._api.query_dnd_settings(place_id)
            except Exception as ex:  # noqa: BLE001
                self._note_failure("Режим «не беспокоить»", place_id, ex)
            else:
                self._note_success("Режим «не беспокоить»", place_id)
                if dnd_items:
                    dnd[str(place_id)] = dnd_items

        cameras = dedupe_by_id(cameras) if cameras else []

        LOGGER.debug(
            "Coordinator refresh: %d places, %d balances, %d cameras, %d locks, %d dnd",
            len(places), len(balances), len(cameras), len(locks), len(dnd),
        )

        return {
            "places": places,
            "balances": balances,
            "cameras": cameras,
            "locks": locks,
            "dnd": dnd,
        }

    @callback
    def _note_failure(
        self, what: str, place_id: str | None, err: Exception | str
    ) -> None:
        """Сообщить об отказе один раз, а не на каждом цикле обновления.

        Отказ отдельного подзапроса устойчив: оператор молчит про баланс или
        камеры сутками. Прежний `warning` на каждом цикле давал под три сотни
        одинаковых строк в сутки на каждый отказавший вид данных — правило
        Silver `log-when-unavailable` требует обратного: сказать о пропаже
        один раз и один раз о возвращении. Пишем тип исключения, а не текст:
        в тексте оператора может оказаться адрес или идентификатор.
        """
        key = (what, str(place_id or ""))
        if key in self._failing:
            return
        self._failing.add(key)
        # Строкой — когда причина не исключение: иначе пришлось бы сочинять
        # его, и лог утверждал бы поломку там, где оператор просто ничего не
        # прислал.
        reason = err if isinstance(err, str) else type(err).__name__
        if place_id is None:
            LOGGER.warning("%s: нет данных (%s)", what, reason)
            return
        LOGGER.warning("%s: нет данных для place_id=%s (%s)", what, place_id, reason)

    @callback
    def _note_success(self, what: str, place_id: str | None) -> None:
        """Сообщить о возвращении данных, если до этого был отказ."""
        key = (what, str(place_id or ""))
        if key not in self._failing:
            return
        self._failing.discard(key)
        if place_id is None:
            LOGGER.info("%s: данные снова приходят", what)
            return
        LOGGER.info("%s: данные снова приходят для place_id=%s", what, place_id)

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
            "days_to_block": finance.get("daysToBlock"),
            "days_to_warning": finance.get("daysToWarning"),
            "company": finance.get("company"),
        }

    async def _collect_cameras_for_place(
        self,
        place_id: str,
        access_controls: list[dict[str, Any]],
        hidden_cam_ids: set[str],
        hidden_entrance_ids: set[str],
    ) -> list[dict[str, Any]]:
        """Камеры одного place — три источника (access_controls + public + cameras).

        Args:
            place_id: ID места.
            access_controls: pre-fetched access controls (общий результат с
                _collect_locks_for_place; раньше каждый делал свой запрос —
                A-61).
            hidden_cam_ids: pre-extracted из `/settings/screens` PUBLIC_CAMERAS
                раздел (общий с locks для ACCESS_CONTROLS hidden — A-61).
            hidden_entrance_ids: pre-extracted из ACCESS_CONTROLS раздел.

        ⚠️ **Структура API** (см. api-reference §Access controls):
        `externalCameraId` существует на ДВУХ уровнях:
        - `access_control.externalCameraId` — общая камера домофона;
        - `access_control.entrances[*].externalCameraId` — камера конкретного
          entrance (подъезд/калитка). Это **разные** камеры — у каждой entrance
          обычно своя.

        Поэтому для intercom-камер группировка идёт **по entrance**, не по ac.
        Coordinator передаёт `place_id` + `access_control_id` + `entrance_id`
        в camera dict — entity-слой делает device identifier
        `entrance_{place}_{ac}_{entrance_id|main}`, общий с lock того же entrance.

        Категоризация по `source`:
        - intercom — от access_controls (домофоны);
        - place — от `/rest/v1/.../cameras` (личные подписочные камеры);
        - public — от `/rest/v2/.../public/cameras` (общедомовые + городские —
          API не различает, оба идут одним списком).

        Пользовательская видимость из `/settings/screens` прокидывается флагом
        `hidden`: entity получит `_attr_entity_registry_enabled_default = False`
        (uses user app preference как дефолт для новых установок).
        """
        cameras: list[dict[str, Any]] = []

        # 1. Access controls (домофоны).
        # hidden для intercom-камеры берётся из ACCESS_CONTROLS.hidden — если
        # user скрыл entrance в приложении, и lock и camera этого entrance
        # получат `enabled_default=False`.
        for ac in access_controls:
            ac_id = ac.get("id")
            entrances = ac.get("entrances") or []
            if entrances:
                # Каждая entrance со своим externalCameraId → отдельная intercom-камера.
                for entrance in entrances:
                    eid = entrance.get("externalCameraId")
                    if not eid:
                        continue
                    entrance_id = entrance.get("id")
                    cameras.append({
                        "id": eid,
                        "name": entrance.get("name"),
                        "place_id": place_id,
                        "access_control_id": ac_id,
                        "entrance_id": entrance_id,
                        "source": "intercom",
                        "hidden": str(entrance_id) in hidden_entrance_ids,
                    })
            else:
                # AC без entrances — сам по себе door. Используем ac.externalCameraId.
                cid = ac.get("externalCameraId")
                if cid:
                    cameras.append({
                        "id": cid,
                        "name": ac.get("name"),
                        "place_id": place_id,
                        "access_control_id": ac_id,
                        "entrance_id": None,
                        "source": "intercom",
                        "hidden": False,  # AC без entrance не отображается в screens
                    })

        # 2. Place-cameras (личные подписочные камеры).
        # Идут ВТОРЫМИ чтобы dedupe_by_id отдал приоритет intercom > place > public.
        # Каждый источник — под своим фронтом: отказ одного не должен уносить
        # камеры остальных. Домофонные уже собраны выше и от этого запроса не
        # зависят.
        try:
            place_cameras = await self._api.query_cameras(place_id)
        except Exception as ex:  # noqa: BLE001
            self._note_failure("Камеры места", place_id, ex)
            place_cameras = []
        else:
            self._note_success("Камеры места", place_id)
        for cam in place_cameras:
            cid = cam.get("externalCameraId") or cam.get("id")
            cameras.append({
                "id": cid,
                "name": cam.get("name"),
                "place_id": place_id,
                "source": "place",
                "hidden": False,  # личные камеры всегда видимы по дефолту
            })

        # 3. Public cameras (общедомовые + городские, API не разделяет).
        # Видимость берётся из /settings/screens — user в приложении сам решает
        # какие camera ему интересны, какие скрыть.
        try:
            public_cameras = await self._api.query_public_cameras(place_id)
        except Exception as ex:  # noqa: BLE001
            self._note_failure("Общедомовые камеры", place_id, ex)
            public_cameras = []
        else:
            self._note_success("Общедомовые камеры", place_id)
        for cam in public_cameras:
            cid = cam.get("externalCameraId") or cam.get("id")
            cameras.append({
                "id": cid,
                "name": cam.get("name"),
                "place_id": place_id,
                "source": "public",
                "hidden": str(cid) in hidden_cam_ids,
            })

        return cameras

    @staticmethod
    def _extract_hidden_ids(screens: Any, screen_type: str) -> set[str]:
        """Из ответа `/settings/screens` достать id-шки скрытых entities.

        Возвращает set строковых id. Если screen-тип не найден — пустой set
        (значит ничего не скрыто).

        `screens` намеренно `Any`, а не `dict`: это разобранный JSON от
        оператора, и обещать его форму в аннотации значит выдать желаемое за
        действительное — проверка формы ниже стала бы «недостижимым кодом».
        """
        result: set[str] = set()
        if not isinstance(screens, dict):
            # Форму ответа задаёт оператор, а разбор идёт вне `try` цикла
            # обновления: массив вместо объекта ронял бы `AttributeError`
            # наружу, и ядро писало бы трейсбек на КАЖДОМ цикле — этот его
            # обработчик не ограничен фронтом. Нет настроек — ничего не
            # скрыто, это и есть безопасное умолчание.
            return result
        for screen in screens.get("screens") or []:
            if not isinstance(screen, dict) or screen.get("type") != screen_type:
                continue
            for item in screen.get("hidden") or []:
                iid = item.get("id") if isinstance(item, dict) else None
                if iid is not None:
                    result.add(str(iid))
        return result

    def _collect_locks_for_place(
        self,
        place_id: str,
        access_controls: list[dict[str, Any]],
        hidden_entrance_ids: set[str],
    ) -> list[dict[str, Any]]:
        """Locks одного place (один per entrance, либо per AC если без entrances).

        Args:
            place_id: ID места.
            access_controls: pre-fetched (общий результат с
                _collect_cameras_for_place; раньше каждый делал свой запрос —
                A-61).
            hidden_entrance_ids: pre-extracted из `/settings/screens`
                ACCESS_CONTROLS раздел.

        `name` — entrance.name (для UI entity, чтобы различать "Подъезд 1" /
        "Калитка 2"). `ac_name` — имя access_control (физического домофона),
        используется как `device_info.name` — общее для всех entrances + camera
        этого домофона. `hidden` — из ACCESS_CONTROLS.hidden в `/settings/screens`
        (user в приложении скрыл entrance) → entity получит enabled_default=False.
        """
        locks: list[dict[str, Any]] = []
        for ac in access_controls:
            ac_name = ac.get("name")
            entrances = ac.get("entrances") or []
            if entrances:
                for entrance in entrances:
                    eid = entrance.get("id")
                    locks.append({
                        "place_id": place_id,
                        "access_control_id": ac.get("id"),
                        "entrance_id": eid,
                        "name": entrance.get("name"),
                        "ac_name": ac_name,
                        "openable": entrance.get("allowOpen"),
                        "hidden": str(eid) in hidden_entrance_ids,
                    })
            else:
                locks.append({
                    "place_id": place_id,
                    "access_control_id": ac.get("id"),
                    "entrance_id": None,
                    "name": ac_name,
                    "ac_name": ac_name,
                    "openable": ac.get("allowOpen"),
                    "hidden": False,
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
