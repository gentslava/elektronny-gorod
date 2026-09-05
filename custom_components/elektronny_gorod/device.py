"""Иерархия устройств: адрес (place) — родитель домофонов и камер подъезда.

HA 2026.8 объявил `via_device` устаревшим, а 2026.9 убрал его из `DeviceInfo`
(в `async_get_or_create` поле пока принимается — до 2027.8). Прежнее поле
адресовало родителя по `identifiers` и допускало ссылку на ещё не созданное
устройство, резолвя её позже. Пришедший на замену `via_device_id` принимает
**готовый** `device_id`, поэтому адрес обязан существовать раньше, чем на него
сошлётся первая платформа, — иначе связь теряется, а устройства выстраиваются
плоским списком (A-100).
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .history import place_display_name

MANUFACTURER = "Электронный город"


def place_identifier(place_id: str) -> tuple[str, str]:
    """Стабильный identifier устройства адреса."""
    return (DOMAIN, f"place_{place_id}")


@callback
def async_register_place_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    data: dict[str, Any] | None,
) -> None:
    """Создать устройства адресов до forward-а платформ.

    Порядок платформ тут против нас: `camera` идёт раньше `sensor`, который
    исторически создавал адрес попутно.
    """
    device_registry = dr.async_get(hass)
    for subscriber_place in (data or {}).get("places") or []:
        place = subscriber_place.get("place") or {}
        place_id = str(place.get("id") or "")
        if not place_id:
            continue
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={place_identifier(place_id)},
            name=place_display_name(data, place_id),
            manufacturer=MANUFACTURER,
            model="Place",
        )


@callback
def place_device_id(hass: HomeAssistant, entry_id: str, place_id: str) -> str | None:
    """Вернуть `device_id` адреса этого config entry, если он уже создан.

    Читаем реестр напрямую, а не собственную карту в `hass.data`: ядро даёт
    для этого штатную обёртку, а `identifiers` уникальны внутри записи, так
    что связь не может уйти в чужой аккаунт. `None` означает, что адрес ещё
    не зарегистрирован — связь появится на следующем setup.
    """
    try:
        return dr.async_get_device_id_by_identifier(
            hass, place_identifier(place_id), config_entry_id=entry_id
        )
    except ValueError:
        return None


def linked_to_place(device_info: DeviceInfo, via_device_id: str | None) -> DeviceInfo:
    """Привязать устройство к адресу, если его `device_id` уже известен.

    `DeviceInfo.via_device_id` объявлен как `str`, а не `str | None`: ключ либо
    есть, либо отсутствует. Разница существенная — явный `None` ядро понимает
    как «отвязать», а пропуск ключа оставляет существующую связь нетронутой.
    Благодаря этому установки с прежней плоской версией получают иерархию на
    первом же старте, без отдельной миграции.
    """
    if via_device_id:
        device_info["via_device_id"] = via_device_id
    return device_info
