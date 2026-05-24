"""Миграция `unique_id` для entity-records (A-12, slice 3c).

Закрывает audit A-12: старые формат unique_id включали `name`, который
динамически меняется в приложении оператора. После миграции (slice 3c):

- camera: `{id}_{name}` → `{DOMAIN}_camera_{id}`
- lock:   `{place}_{ac}_{eid}_{name}` → `{DOMAIN}_lock_{place}_{ac}_{eid|main}`

Sensor (`{DOMAIN}_{place_id}_balance`) уже стабилен — не мигрируется.

Вызывается из `async_setup_entry` после `coordinator.async_config_entry_first_refresh`
и до `async_forward_entry_setups`, чтобы HA не создал дубли (старый
unique_id остаётся в registry, новый ему сопоставляется, entity повторно
не регистрируется).

⚠️ Модуль НЕ должен импортировать `lock` / `camera` / `sensor` (которые тянут
HA), кроме точек, защищённых от import-time (`async def` тело). Иначе чистые
unit-тесты на `_camera_new_uid`/`_lock_new_uid` перестанут собираться без
HA-окружения. Поэтому канонический `lock_unique_id` определён здесь же.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def lock_unique_id(place_id: str, ac_id: str, entrance_id: str | None) -> str:
    """Канонический stable `unique_id` для lock-entity (A-12).

    Не зависит от user-facing `name` — переименование подъезда в приложении
    не приводит к появлению дубликата entity.
    """
    return f"{DOMAIN}_lock_{place_id}_{ac_id}_{entrance_id or 'main'}"


def _camera_new_uid(old_uid: str, cameras: list[dict[str, Any]]) -> str | None:
    """Если `old_uid` — legacy camera UID, вернуть новый stable формат.

    Возвращает None, если:
    - `old_uid` уже в новом формате,
    - запись camera для него не найдена в coordinator.data.
    """
    if old_uid.startswith(f"{DOMAIN}_camera_"):
        return None
    for cam in cameras:
        cid = cam.get("id")
        if not cid:
            continue
        cname = cam.get("name") or cid
        # Legacy: __init__ строил `f"{id}_{name}"` где name = api_name || id.
        if old_uid == f"{cid}_{cname}":
            return f"{DOMAIN}_camera_{cid}"
    return None


def _lock_new_uid(old_uid: str, locks: list[dict[str, Any]]) -> str | None:
    """Если `old_uid` — legacy lock UID, вернуть новый stable формат."""
    if old_uid.startswith(f"{DOMAIN}_lock_"):
        return None
    for lk in locks:
        pid = lk.get("place_id")
        ac = lk.get("access_control_id")
        eid = lk.get("entrance_id")
        name = lk.get("name")
        if pid is None or ac is None:
            continue
        # Legacy: `f"{place_id}_{access_control_id}_{entrance_id}_{name}"`.
        # entrance_id мог быть None → "None" в f-string.
        if old_uid == f"{pid}_{ac}_{eid}_{name}":
            return lock_unique_id(pid, ac, eid)
    return None


async def async_migrate_entity_unique_ids(
    hass: "HomeAssistant",
    entry: "ConfigEntry",
    coordinator_data: dict[str, Any],
) -> None:
    """Пройти по entity_registry конкретного entry и переименовать legacy UIDs.

    `coordinator_data` — снапшот свежий после `async_config_entry_first_refresh`.
    Используется только для resolve legacy → new UID (нужно знать актуальные
    `name` камер/локов).

    Коллизии: если несколько legacy записей мапятся в один новый UID (например,
    у camera id=X есть две записи с разными `name` — старая и переименованная),
    мигрируется ТОЛЬКО первая. Остальные остаются с legacy UID; HA сообщит про
    них «entity not provided by integration», пользователь удалит вручную в UI.
    Это лучше, чем `ValueError` посреди setup, который ломает всю интеграцию.
    """
    # Локальный import: HA-зависимости тянутся только при реальном вызове, а
    # модуль остаётся импортируемым в unit-тестах без HA-окружения.
    from homeassistant.core import callback
    from homeassistant.helpers import entity_registry as er

    cameras = coordinator_data.get("cameras") or []
    locks = coordinator_data.get("locks") or []

    registry = er.async_get(hass)
    # Снимок UIDs нашего entry на старте миграции — для детекта коллизий.
    # Обновляется при каждом успешном rename, так что повторный legacy с тем
    # же target UID будет пропущен.
    taken_uids: set[str] = {
        e.unique_id
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.platform == DOMAIN
    }

    @callback
    def _migrate(entity_entry: "er.RegistryEntry") -> dict[str, Any] | None:
        if entity_entry.platform != DOMAIN:
            return None

        new_uid: str | None = None
        if entity_entry.domain == "camera":
            new_uid = _camera_new_uid(entity_entry.unique_id, cameras)
        elif entity_entry.domain == "lock":
            new_uid = _lock_new_uid(entity_entry.unique_id, locks)

        if new_uid is None or new_uid == entity_entry.unique_id:
            return None

        if new_uid in taken_uids:
            LOGGER.warning(
                "Skip migration of %s unique_id %r: target %r already in use "
                "(likely a duplicate from a renamed device). Remove the orphan "
                "entity manually in Settings → Devices & Services → Entities.",
                entity_entry.domain,
                entity_entry.unique_id,
                new_uid,
            )
            return None

        LOGGER.info(
            "Migrating %s unique_id: %s -> %s",
            entity_entry.domain,
            entity_entry.unique_id,
            new_uid,
        )
        taken_uids.add(new_uid)
        taken_uids.discard(entity_entry.unique_id)
        return {"new_unique_id": new_uid}

    await er.async_migrate_entries(hass, entry.entry_id, _migrate)
