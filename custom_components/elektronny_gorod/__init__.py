"""The Elektronny Gorod integration."""

from __future__ import annotations
import json
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    LOGGER,
    CONF_OPERATOR_ID,
    CONF_USER_AGENT,
    CONF_USE_GO2RTC,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_RTSP_HOST,
    DEFAULT_GO2RTC_BASE_URL,
    DEFAULT_GO2RTC_RTSP_HOST,
)
from .coordinator import ElektronnyGorodUpdateCoordinator
from .entity_migration import async_migrate_entity_unique_ids, lock_unique_id
from .user_agent import UserAgent

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.LOCK,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Elektronny Gorod from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = ElektronnyGorodUpdateCoordinator(hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Slice 3c (A-12): legacy unique_id содержали динамический `name`.
    # Мигрируем ДО forward_entry_setups, чтобы entity повторно регистрировались
    # с новыми UID без появления дублей.
    await async_migrate_entity_unique_ids(hass, entry, coordinator.data or {})

    # HA-core гарантированно вызовет эти cleanup-функции на unload entry,
    # независимо от успешности platform unload. См. audit A-16.
    entry.async_on_unload(coordinator.async_unsubscribe)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Visibility sync (см. PR #35 follow-up): на re-add HA восстанавливает
    # entity из `deleted_entities` с сохранённым `disabled_by`,
    # игнорируя `_attr_entity_registry_enabled_default`. После того как
    # platforms зарегистрировали entity — синхронно подгоняем disabled_by
    # для entities, скрытых в /settings/screens.
    _sync_hidden_entities_disabled_by(hass, entry, coordinator.data or {})

    return True


def _sync_hidden_entities_disabled_by(
    hass: HomeAssistant,
    entry: ConfigEntry,
    data: dict[str, Any],
) -> None:
    """Single source of truth для entity visibility на основе /settings/screens.

    Запускается на каждом setup_entry (включая re-add после remove). Покрывает
    оба сценария — first add (entity ещё нет в registry) и re-add (HA восстановил
    из `deleted_entities` с прежним `disabled_by`).

    Стратегия:
    - Собираем `unique_id` всех hidden-камер и hidden-locks из coordinator.data.
    - Для каждой entity нашего config_entry с unique_id в этом множестве и
      `disabled_by is None` → устанавливаем `disabled_by=INTEGRATION`.
      `INTEGRATION` (не `CONFIG_ENTRY`) — `CONFIG_ENTRY` сбрасывается HA-core
      при restore из `deleted_entities`, см. entity_registry.py.
    - **One-way**: НЕ enable обратно visible-в-API entities — это перетёрло бы
      явный user choice (если человек целенаправленно отключил видимую entity).
    - Никогда не трогаем `disabled_by=USER` — пользователь явно решил.
    """
    hidden_uids: set[str] = set()

    for cam in data.get("cameras") or []:
        if cam.get("hidden") and cam.get("id"):
            hidden_uids.add(f"{DOMAIN}_camera_{cam['id']}")

    for lk in data.get("locks") or []:
        if lk.get("hidden"):
            hidden_uids.add(
                lock_unique_id(
                    lk.get("place_id"),
                    lk.get("access_control_id"),
                    lk.get("entrance_id"),
                )
            )

    if not hidden_uids:
        return

    ent_reg = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if entity.unique_id not in hidden_uids:
            continue
        if entity.disabled_by is not None:
            # USER / DEVICE / CONFIG_ENTRY / HASS / INTEGRATION — не трогаем.
            continue
        LOGGER.debug(
            "Disabling entity %s (unique_id=%s) — hidden in user app",
            entity.entity_id,
            entity.unique_id,
        )
        ent_reg.async_update_entity(
            entity.entity_id,
            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        )


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    version = config_entry.version
    new_data: ConfigType = {**config_entry.data}
    options: ConfigType = {**config_entry.options}

    LOGGER.debug("Migrating from version %s", version)

    # Migration to version 2: add user_agent field
    if version == 1:
        user_agent = UserAgent()
        user_agent.operator_id = new_data[CONF_OPERATOR_ID]
        new_data[CONF_USER_AGENT] = json.dumps(user_agent.json())

        version = 2
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=options, version=version
        )
        LOGGER.debug("Migration to version %s successful", version)

    # Migration to version 3: add go2rtc configuration
    if version == 2:
        new_data[CONF_USE_GO2RTC] = False
        new_data[CONF_GO2RTC_BASE_URL] = DEFAULT_GO2RTC_BASE_URL
        new_data[CONF_GO2RTC_RTSP_HOST] = DEFAULT_GO2RTC_RTSP_HOST

        version = 3
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, options=options, version=version
        )
        LOGGER.debug("Migration to version %s successful", version)

    LOGGER.debug("Migration to config version %s successful", config_entry.version)

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options for entry that was configured via user interface."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Разрешить пользователю удалить device через UI / WS-API.

    Возвращаем True безусловно — orphan devices (после переименований в
    приложении оператора или смены device-identifier между релизами)
    должны удаляться. На следующем тике coordinator пересоздаст актуальные
    devices, а удалённые останутся удалёнными.
    """
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Cleanup-функции coordinator-а (dispatcher listener, options listener)
    зарегистрированы через `entry.async_on_unload` в `async_setup_entry` —
    HA-core вызовет их автоматически независимо от исхода platform unload
    (см. audit A-16).
    """
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
