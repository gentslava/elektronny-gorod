"""The Elektronny Gorod integration."""

from __future__ import annotations
import json
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr, entity_registry as er
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
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.EVENT,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
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

    # One-time migration: legacy state (disabled_by на entities/devices от
    # старых версий integration) → None. Применяется один раз per entry.
    migration_changed = _migrate_legacy_disabled_state(hass, entry)

    # Visibility sync: hidden в /settings/screens → entity.hidden_by=INTEGRATION.
    # `hidden_by` (НЕ disabled_by) — state machine продолжает работать
    # (automations доступны), entity не показывается в default UI views.
    # Пользователь может easily Show через Settings → Entities → filter Hidden.
    # Sync не требует reload — registry update подхватывается HA core напрямую.
    _sync_visibility(hass, entry, coordinator.data or {})

    # Reload только если migration реально сбросила disabled_by markers — entity
    # требуют re-init платформ для применения. Sync visibility update в registry
    # — это live operation, не нужен reload (см. A-64).
    if migration_changed:
        hass.async_create_task(
            hass.config_entries.async_reload(entry.entry_id),
            name=f"{DOMAIN}_migration_reload",
        )

    return True


_MIGRATION_FLAG_KEY = "visibility_migration_v2"


def _migrate_legacy_disabled_state(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """One-time cleanup legacy disabled_by markers (entity + device).

    Применяется один раз per entry, флаг в `entry.data` (НЕ options) — чтобы
    запись flag-а не триггерила `async_update_options` listener → reload cascade
    (см. A-64). Backward-compat: если flag уже в options от старой версии,
    считаем migration выполненной и переносим в data.

    Background: до перехода на hidden_by-based visibility sync интеграция
    использовала disabled_by:
    - entity.disabled_by=INTEGRATION/DEVICE (от cascade)
    - device.disabled_by=INTEGRATION (от device-level sync)
    - entity.disabled_by=USER (от bulk-disable пользователем в HA UI до bi-dir sync)

    Все эти markers надо сбросить — новая модель использует только hidden_by,
    который потом устанавливается _sync_visibility согласно current API state.

    Returns True если что-то реально изменилось в registry (caller schedule
    reload — entity нужны re-init платформ для применения disabled_by сброса).
    """
    if entry.data.get(_MIGRATION_FLAG_KEY) or entry.options.get(_MIGRATION_FLAG_KEY):
        # Backward-compat: если flag в options от прошлой версии, перенесём в data
        # без re-running миграции (registry уже cleaned).
        if entry.options.get(_MIGRATION_FLAG_KEY) and not entry.data.get(_MIGRATION_FLAG_KEY):
            new_options = {k: v for k, v in entry.options.items() if k != _MIGRATION_FLAG_KEY}
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, _MIGRATION_FLAG_KEY: True},
                options=new_options,
            )
        return False

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    changed = False
    reset_count = 0

    # 1. Entities: disabled_by INTEGRATION/DEVICE/USER → None.
    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if entity.disabled_by in (
            er.RegistryEntryDisabler.INTEGRATION,
            er.RegistryEntryDisabler.DEVICE,
            er.RegistryEntryDisabler.USER,
        ):
            ent_reg.async_update_entity(entity.entity_id, disabled_by=None)
            reset_count += 1
            changed = True

    # 2. Devices: disabled_by INTEGRATION/USER → None (CONFIG_ENTRY HA сам).
    for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        if device.disabled_by in (
            dr.DeviceEntryDisabler.INTEGRATION,
            dr.DeviceEntryDisabler.USER,
        ):
            dev_reg.async_update_device(device.id, disabled_by=None)
            reset_count += 1
            changed = True

    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, _MIGRATION_FLAG_KEY: True},
    )

    if reset_count:
        LOGGER.info(
            "One-time visibility migration: reset %d disabled_by markers "
            "(entity + device). Sync будет использовать hidden_by вместо disabled_by.",
            reset_count,
        )

    return changed


def _sync_visibility(
    hass: HomeAssistant,
    entry: ConfigEntry,
    data: dict[str, Any],
) -> bool:
    """Two-way visibility sync `hidden_by` ↔ /settings/screens с user-override tracking.

    Базовая логика:
    - hidden в API + hidden_by=None + НЕТ user override → set INTEGRATION.
    - visible в API + hidden_by=INTEGRATION → set None.
    - hidden_by=USER → НЕ trogaem (явный user Hide через HA UI).

    User-override tracking (A-64): хранится в `entity.options[DOMAIN]`
    (entity_registry, persistent, НЕ триггерит config_entry listener):
    - `we_set_integration: True` — мы пометили эту entity hidden_by=INTEGRATION.
      Сбрасывается когда API возвращает visible.
    - `user_shown: True` — юзер включил «Показывать на панели» (мы видим
      `we_set_integration=True` но `hidden_by=None`). С этого момента не
      восстанавливаем INTEGRATION даже если API hidden. Сбрасывается когда
      приложение тоже разрешит показ.

    Когда вызывается: только в `async_setup_entry` (cold start, reload,
    reauth, любой options change). НЕ на каждом coordinator-tick — это
    осознанно, чтобы избежать постоянного registry write activity. Изменения
    `/settings/screens` в приложении подхватятся при следующем reload entry
    или рестарте HA.

    Почему `hidden_by`, а не `disabled_by`:
    - disabled_by INTEGRATION блокирует UI override («устройство деактивировано»).
    - hidden_by — entity скрыта из default UI views, state machine работает,
      юзер easily Show через toggle «Показывать на панели».

    Returns True если что-то реально изменилось в hidden_by. Caller использует
    для logging — reload НЕ требуется (registry update live).
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

    ent_reg = er.async_get(hass)
    registry_changed = False
    hid = 0
    shown = 0

    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if entity.domain not in ("camera", "lock"):
            continue

        uid = entity.unique_id
        api_hidden = uid in hidden_uids
        current = entity.hidden_by
        opts = dict(entity.options.get(DOMAIN) or {})
        we_set_integration = bool(opts.get("we_set_integration"))
        user_shown = bool(opts.get("user_shown"))
        new_opts = dict(opts)

        # Detect user-shown override: мы ранее set INTEGRATION, но registry уже None.
        # Юзер кликнул «Показывать на панели» — сохраняем флаг.
        if we_set_integration and current is None and not user_shown:
            new_opts["user_shown"] = True
            user_shown = True
            LOGGER.info(
                "User override saved: %s (unique_id=%s) — пользователь включил "
                "«Показывать на панели», не восстанавливаем INTEGRATION",
                entity.entity_id, uid,
            )

        # Auto-clear user override если приложение тоже разрешило показ.
        if not api_hidden and user_shown:
            new_opts.pop("user_shown", None)
            user_shown = False

        if api_hidden and not user_shown:
            # Должна быть скрыта по API и юзер не override.
            if current is None:
                LOGGER.debug(
                    "Hiding entity %s (unique_id=%s) — hidden in user app",
                    entity.entity_id, uid,
                )
                ent_reg.async_update_entity(
                    entity.entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
                )
                hid += 1
                registry_changed = True
                new_opts["we_set_integration"] = True
            elif current == er.RegistryEntryHider.INTEGRATION:
                # Уже скрыто нами — поддерживаем флаг (важно для restart).
                new_opts["we_set_integration"] = True
        elif not api_hidden and current == er.RegistryEntryHider.INTEGRATION:
            # API разрешил показ — снимаем INTEGRATION.
            LOGGER.debug(
                "Showing entity %s (unique_id=%s) — visible in user app",
                entity.entity_id, uid,
            )
            ent_reg.async_update_entity(entity.entity_id, hidden_by=None)
            shown += 1
            registry_changed = True
            new_opts.pop("we_set_integration", None)
        elif not api_hidden:
            # API visible и hidden_by не INTEGRATION — наш marker неактуален.
            new_opts.pop("we_set_integration", None)

        # Persist options только если изменились (не триггерит config_entry listener).
        if new_opts != opts:
            ent_reg.async_update_entity_options(entity.entity_id, DOMAIN, new_opts)

    if hid or shown:
        LOGGER.info(
            "Visibility sync: hidden_uids=%d, hid=%d, shown=%d (entry %s)",
            len(hidden_uids), hid, shown, entry.entry_id,
        )
    return registry_changed


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
