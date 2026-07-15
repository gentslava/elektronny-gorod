"""Tests for the read-only WebSocket history browser."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import entity_registry as er

from custom_components.elektronny_gorod.api import HistoryEvent, HistoryPage
from custom_components.elektronny_gorod.const import DOMAIN


_UNIQUE_ID = "elektronny_gorod_event_history_access_1001_2001"
_ENTITY_ID = "event.test_intercom_call_history"


def _history_module():
    return importlib.import_module(
        "custom_components.elektronny_gorod.history_ws"
    )


def _connection(*, can_read: bool = True) -> MagicMock:
    connection = MagicMock()
    connection.user = MagicMock(is_admin=False)
    connection.user.permissions.check_entity.return_value = can_read
    return connection


def _setup_target(hass) -> tuple[MockConfigEntry, SimpleNamespace]:
    entry = MockConfigEntry(domain=DOMAIN, title="Test")
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "event",
        DOMAIN,
        _UNIQUE_ID,
        suggested_object_id="test_intercom_call_history",
        config_entry=entry,
    )
    target = registry.async_get(_ENTITY_ID)
    assert target is not None

    page = HistoryPage(
        events=(
            HistoryEvent(
                id="event-target",
                place_id="1001",
                event_type="accessControlCallMissed",
                timestamp=1770000100,
                source_type="accessControl",
                source_id="2001",
            ),
            HistoryEvent(
                id="event-other-access-control",
                place_id="1001",
                event_type="accessControlCallAccepted",
                timestamp=1770000000,
                source_type="accessControl",
                source_id="9999",
            ),
            HistoryEvent(
                id="event-unknown",
                place_id="1001",
                event_type="notRuntimeVerified",
                timestamp=1769999900,
                source_type="accessControl",
                source_id="2001",
            ),
        ),
        number=2,
        last=False,
    )
    coordinator = SimpleNamespace(
        api=SimpleNamespace(query_events=AsyncMock(return_value=page)),
        data={
            "locks": [
                {
                    "place_id": "1001",
                    "access_control_id": "2001",
                    "entrance_id": "20",
                    "name": "Подъезд 2",
                },
                {
                    "place_id": "1001",
                    "access_control_id": "2001",
                    "entrance_id": "10",
                    "name": "Подъезд 1",
                },
            ]
        },
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    return entry, coordinator


@pytest.mark.asyncio
async def test_history_ws_returns_previous_sanitized_page(hass) -> None:
    """Old rows are browse data, not EventEntity triggers."""
    history_ws = _history_module()
    _entry, coordinator = _setup_target(hass)
    connection = _connection()

    await history_ws.async_handle_history(
        hass,
        connection,
        {"id": 7, "entity_id": _ENTITY_ID, "page": 2},
    )

    coordinator.api.query_events.assert_awaited_once_with([1001], page=2)
    connection.send_result.assert_called_once_with(7, {
        "entity_id": _ENTITY_ID,
        "source_name": "Подъезд 1",
        "events": [{
            "event_id": "event-target",
            "event_type": "call_missed",
            "occurred_at": 1770000100,
        }],
        "page": 2,
        "last": False,
    })
    serialized = str(connection.send_result.call_args.args[1])
    assert "message" not in serialized.lower()


@pytest.mark.asyncio
async def test_history_ws_rejects_user_without_entity_read_permission(hass) -> None:
    """Restricted HA users cannot use the card to bypass entity permissions."""
    history_ws = _history_module()
    _setup_target(hass)
    connection = _connection(can_read=False)

    with pytest.raises(Unauthorized):
        await history_ws.async_handle_history(
            hass,
            connection,
            {"id": 8, "entity_id": _ENTITY_ID, "page": 0},
        )


@pytest.mark.asyncio
async def test_history_ws_returns_safe_error_without_operator_details(
    hass, caplog
) -> None:
    """Operator failures do not expose a response body or exception message."""
    history_ws = _history_module()
    _entry, coordinator = _setup_target(hass)
    coordinator.api.query_events.side_effect = RuntimeError("PII-SENTINEL")
    connection = _connection()
    caplog.set_level("DEBUG")

    await history_ws.async_handle_history(
        hass,
        connection,
        {"id": 9, "entity_id": _ENTITY_ID, "page": 0},
    )

    connection.send_error.assert_called_once_with(
        9,
        "history_unavailable",
        "History is temporarily unavailable",
    )
    connection.send_result.assert_not_called()
    assert "PII-SENTINEL" not in caplog.text


def test_history_ws_schema_bounds_page_number() -> None:
    """Untrusted card input cannot request unbounded or negative pages."""
    import voluptuous as vol

    history_ws = _history_module()
    schema = history_ws.ws_history._ws_schema
    base = {
        "id": 1,
        "type": "elektronny_gorod/history",
        "entity_id": _ENTITY_ID,
    }

    assert schema(base)["page"] == 0
    assert schema({**base, "page": 100})["page"] == 100
    with pytest.raises(vol.Invalid):
        schema({**base, "page": -1})
    with pytest.raises(vol.Invalid):
        schema({**base, "page": 101})


def test_history_ws_registration_is_idempotent() -> None:
    """Multiple config entries register the global command only once."""
    history_ws = _history_module()
    hass = MagicMock()
    hass.data = {}

    with patch.object(history_ws.websocket_api, "async_register_command") as reg:
        history_ws.async_register_history_ws_command(hass)
        history_ws.async_register_history_ws_command(hass)

    reg.assert_called_once_with(hass, history_ws.ws_history)
