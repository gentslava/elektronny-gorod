"""Tests for A-57: balance-related entities из /finance response.

Архитектура:

| Entity | Платформа | Источник из coordinator.data["balances"] |
|---|---|---|
| sensor.{addr}_account_balance | sensor (existing) | balance |
| binary_sensor.{addr}_blocked | binary_sensor (new) | blocked |
| sensor.{addr}_days_to_block | sensor (new) | days_to_block |

Note: `payment_link` остаётся как attribute у `sensor.balance` (поле
"Payment link" в extra_state_attributes). Button entity для оплаты убран —
HA не имеет server-side browser-launch, redirect делается через client-side
(Lovelace card `tap_action: url` или mobile_app push с OPEN_URL action).
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.user_agent import UserAgent

PLACE_ID = "1000000"


def _finance_response(
    balance: float = 1234.56,
    blocked: bool = False,
    days_to_block: int = 14,
    days_to_warning: int = 7,
    payment_link: str = "https://pay.example/abc",
) -> dict[str, Any]:
    """Полный shape ответа /finance."""
    return {
        "balance": balance,
        "blockType": "warning" if blocked else "normal",
        "blocked": blocked,
        "amountSum": 500.0,
        "targetDate": "2026-06-01T00:00:00+07:00",
        "paymentLink": payment_link,
        "daysToBlock": days_to_block,
        "daysToWarning": days_to_warning,
        "company": "Test Operator LLC",
    }


@pytest.fixture
def mock_api(monkeypatch):
    """API mock with one place + finance response."""
    finance = _finance_response()

    def _fixture(**overrides):
        nonlocal finance
        if overrides:
            finance = _finance_response(**overrides)

    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.http = AsyncMock()
        instance.http.user_agent = AsyncMock()
        instance.query_places = AsyncMock(return_value=[{
            "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
            "place": {"id": PLACE_ID, "address": "addr"},
        }])
        instance.query_access_controls = AsyncMock(return_value=[])
        instance.query_cameras = AsyncMock(return_value=[])
        instance.query_public_cameras = AsyncMock(return_value=[])
        instance.query_screens_settings = AsyncMock(return_value={})
        instance.query_dnd_settings = AsyncMock(return_value=[])
        # Делает callable, чтобы кадый вызов отдавал текущий finance dict.
        instance.query_balance = AsyncMock(side_effect=lambda place_id: finance)
        yield mock_cls, _fixture


def _make_config_entry() -> MockConfigEntry:
    ua = UserAgent()
    ua.operator_id = "1"
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="test_unique_subscriber_S1",
        title="Test",
        data={
            CONF_ACCESS_TOKEN: "T1",
            CONF_REFRESH_TOKEN: "R1",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(ua.json()),
            "account_id": "A1",
            "subscriber_id": "S1",
            "use_go2rtc": False,
            "go2rtc_base_url": "http://127.0.0.1:1984",
            "go2rtc_rtsp_host": "127.0.0.1",
        },
    )


# ─── binary_sensor.blocked ──────────────────────────────────────────────────


async def test_binary_sensor_blocked_off_when_api_not_blocked(
    hass: HomeAssistant, mock_api
):
    """blocked=False в API → binary_sensor.state = off."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    uid = f"{DOMAIN}_{PLACE_ID}_blocked"
    eid = registry.async_get_entity_id("binary_sensor", DOMAIN, uid)
    assert eid is not None, f"Expected binary_sensor with unique_id={uid}"
    assert hass.states.get(eid).state == "off"


async def test_binary_sensor_blocked_on_when_api_blocked(
    hass: HomeAssistant, mock_api
):
    """blocked=True в API → binary_sensor.state = on."""
    _, set_finance = mock_api
    set_finance(blocked=True)

    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    uid = f"{DOMAIN}_{PLACE_ID}_blocked"
    eid = registry.async_get_entity_id("binary_sensor", DOMAIN, uid)
    assert hass.states.get(eid).state == "on"


# ─── sensor.days_to_block ───────────────────────────────────────────────────


async def test_days_to_block_sensor_native_value(
    hass: HomeAssistant, mock_api
):
    """days_to_block=14 в API → sensor.native_value = 14."""
    _, set_finance = mock_api
    set_finance(days_to_block=14)

    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    uid = f"{DOMAIN}_{PLACE_ID}_days_to_block"
    eid = registry.async_get_entity_id("sensor", DOMAIN, uid)
    assert eid is not None
    assert hass.states.get(eid).state == "14"


async def test_days_to_block_has_duration_device_class(
    hass: HomeAssistant, mock_api
):
    """sensor.days_to_block должен иметь device_class=duration + unit=days."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    uid = f"{DOMAIN}_{PLACE_ID}_days_to_block"
    eid = registry.async_get_entity_id("sensor", DOMAIN, uid)
    state = hass.states.get(eid)
    assert state.attributes.get("device_class") == "duration"
    assert state.attributes.get("unit_of_measurement") == "d"


# ─── payment_link остаётся как attribute у sensor.balance ─────────────────


async def test_payment_link_available_as_balance_sensor_attribute(
    hass: HomeAssistant, mock_api
):
    """payment_link доступен в `sensor.balance.attributes["Payment link"]`.

    Пользователь использует через Lovelace `tap_action: url` (с template на
    attribute) или automation с mobile_app.notify (action OPEN_URL).
    """
    _, set_finance = mock_api
    set_finance(payment_link="https://pay.example/xyz")

    entry = _make_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    uid = f"{DOMAIN}_{PLACE_ID}_balance"
    eid = registry.async_get_entity_id("sensor", DOMAIN, uid)
    assert eid is not None
    state = hass.states.get(eid)
    assert state.attributes.get("Payment link") == "https://pay.example/xyz"
