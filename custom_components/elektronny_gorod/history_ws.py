"""Authenticated, read-only WebSocket browser for previous call history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, LOGGER
from .history import map_general_event_type


_WS_REGISTERED = f"{DOMAIN}_history_ws_registered"


@dataclass(frozen=True, slots=True)
class HistoryBrowseTarget:
    """Resolved entity-scoped history source."""

    coordinator: Any
    place_id: str
    access_control_id: str
    source_name: str


def _resolve_target(
    hass: HomeAssistant,
    entity_id: str,
) -> HistoryBrowseTarget | None:
    """Resolve a registered access-history entity without trusting its name."""
    registry_entry = er.async_get(hass).async_get(entity_id)
    if (
        registry_entry is None
        or registry_entry.platform != DOMAIN
        or not registry_entry.config_entry_id
    ):
        return None
    coordinator = hass.data.get(DOMAIN, {}).get(registry_entry.config_entry_id)
    if coordinator is None:
        return None
    matches = []
    for lock_info in (coordinator.data or {}).get("locks") or []:
        place_id = str(lock_info.get("place_id") or "")
        access_control_id = str(lock_info.get("access_control_id") or "")
        expected_unique_id = (
            f"{DOMAIN}_event_history_access_{place_id}_{access_control_id}"
        )
        if registry_entry.unique_id == expected_unique_id:
            matches.append(lock_info)
    if not matches:
        return None
    # event.py uses the same stable representative for a multi-entrance AC.
    lock_info = min(
        matches,
        key=lambda item: str(item.get("entrance_id") or ""),
    )
    place_id = str(lock_info.get("place_id") or "")
    access_control_id = str(lock_info.get("access_control_id") or "")
    return HistoryBrowseTarget(
        coordinator=coordinator,
        place_id=place_id,
        access_control_id=access_control_id,
        source_name=str(lock_info.get("name") or access_control_id),
    )


async def async_handle_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return one sanitized backend page for an authorized history entity."""
    entity_id = msg["entity_id"]
    user = connection.user
    if user is None or (
        not user.is_admin
        and not user.permissions.check_entity(entity_id, POLICY_READ)
    ):
        raise Unauthorized

    target = _resolve_target(hass, entity_id)
    if target is None:
        connection.send_error(
            msg["id"],
            "history_entity_not_found",
            "History entity is not available",
        )
        return
    try:
        place_id = int(target.place_id)
    except ValueError:
        connection.send_error(
            msg["id"],
            "history_entity_invalid",
            "History entity has an invalid place identifier",
        )
        return

    try:
        page = await target.coordinator.api.query_events(
            [place_id],
            page=msg["page"],
        )
    except Exception as ex:  # noqa: BLE001 - optional feature degradation
        LOGGER.debug("History browse fetch failed (%s)", type(ex).__name__)
        connection.send_error(
            msg["id"],
            "history_unavailable",
            "History is temporarily unavailable",
        )
        return

    events = []
    for event in page.events:
        event_type = map_general_event_type(event.event_type)
        if (
            event_type is None
            or event.source_type != "accessControl"
            or event.place_id != target.place_id
            or event.source_id != target.access_control_id
        ):
            continue
        events.append(
            {
                "event_id": event.id,
                "event_type": event_type,
                "occurred_at": event.timestamp,
            }
        )

    connection.send_result(
        msg["id"],
        {
            "entity_id": entity_id,
            "source_name": target.source_name,
            "events": events,
            "page": page.number,
            "last": page.last,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/history",
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("page", default=0): vol.All(
            int,
            vol.Range(min=0, max=100),
        ),
    }
)
@websocket_api.async_response
async def ws_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle a browser request without mutating EventEntity state."""
    await async_handle_history(hass, connection, msg)


@callback
def async_register_history_ws_command(hass: HomeAssistant) -> None:
    """Register the global history command once for all config entries."""
    if hass.data.get(_WS_REGISTERED):
        return
    websocket_api.async_register_command(hass, ws_history)
    hass.data[_WS_REGISTERED] = True
