"""Tests for A-57: balance-related entities из /finance response.

Архитектура:

| Entity | Платформа | Источник из coordinator.data["balances"] |
|---|---|---|
| sensor.{addr}_account_balance | sensor (existing) | balance |
| binary_sensor.{addr}_blocked | binary_sensor (new) | blocked |
| sensor.{addr}_days_to_block | sensor (new) | days_to_block |

Note: `payment_link` остаётся как attribute у `sensor.balance` (поле
`payment_link` в extra_state_attributes). Button entity для оплаты убран —
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
    """payment_link доступен в `sensor.balance.attributes["payment_link"]`.

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
    assert state.attributes.get("payment_link") == "https://pay.example/xyz"


async def test_attribute_keys_are_snake_case_and_translated(
    hass: HomeAssistant, mock_api
):
    """Ключи атрибутов — snake_case, и у каждого есть перевод имени.

    Title Case выглядел прилично только по-английски: в русском интерфейсе
    имена атрибутов оставались английскими, потому что переводить их HA
    может лишь по `state_attributes` из `strings.json`. А в шаблоне такой
    ключ читался как `state_attr(..., 'Payment link')` — с пробелом и
    заглавной, чего не делает ни одна интеграция.
    """
    import json
    import pathlib
    import re

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

    # Атрибуты самого ядра (friendly_name, device_class, …) не наши.
    core_attrs = {
        "friendly_name", "device_class", "state_class", "icon",
        "unit_of_measurement", "supported_features", "attribution",
        "entity_picture", "assumed_state",
    }
    ours = {k for k in state.attributes if k not in core_attrs}
    assert ours, "сенсор баланса потерял свои атрибуты"

    snake = re.compile(r"^[a-z][a-z0-9_]*$")
    bad = sorted(k for k in ours if not snake.match(k))
    assert not bad, f"ключи не snake_case: {bad}"

    base = pathlib.Path(__file__).resolve().parent.parent / "custom_components/elektronny_gorod"
    for name in ("strings.json", "translations/ru.json", "translations/en.json"):
        data = json.loads((base / name).read_text(encoding="utf-8"))
        translated = data["entity"]["sensor"]["balance"].get("state_attributes", {})
        missing = sorted(ours - set(translated))
        assert not missing, f"{name}: нет перевода имени для {missing}"


# ─── Имя адреса и разбор даты ───────────────────────────────────────────────


def _balance_sensor(place: dict, finance: dict | None = None):
    """Сенсор баланса поверх заданного места, без поднятия платформы."""
    from unittest.mock import MagicMock

    from custom_components.elektronny_gorod.sensor import ElektronnyGorodBalanceSensor

    coordinator = MagicMock()
    coordinator.data = {
        "places": [{"place": place}],
        "balances": [{"place_id": PLACE_ID, **(finance or {})}],
    }
    return ElektronnyGorodBalanceSensor(coordinator, PLACE_ID)


@pytest.mark.parametrize(
    ("place", "expected"),
    [
        ({"id": PLACE_ID, "address": {"visibleAddress": "Улица 1"}}, "Улица 1"),
        ({"id": PLACE_ID, "address": "Улица 2"}, "Улица 2"),
        ({"id": PLACE_ID, "address": {}, "name": "Дача"}, "Дача"),
        ({"id": PLACE_ID}, f"Place {PLACE_ID}"),
        ({"id": "другое"}, f"Place {PLACE_ID}"),
    ],
)
def test_place_name_falls_back_through_what_the_operator_gave(place, expected) -> None:
    """Имя адреса берётся по убыванию точности, до запасного варианта.

    Оператор отдаёт адрес в трёх разных формах в зависимости от типа места;
    без запасного варианта сенсор остался бы без человекочитаемого имени.
    """
    assert _balance_sensor(place)._place_display_name() == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-06-01T00:00:00+07:00", "2026-06-01T00:00:00+07:00"),
        ("не дата вовсе", "не дата вовсе"),
        (None, None),
    ],
)
def test_payment_date_is_passed_through_or_kept_as_is(raw, expected) -> None:
    """Неразобранная дата отдаётся как есть, а не теряется.

    Формат у оператора менялся; терять значение хуже, чем отдать сырое.
    """
    sensor = _balance_sensor({"id": PLACE_ID}, {"payment_date": raw})
    assert sensor.extra_state_attributes["target_date"] == expected


def test_blocked_sensor_without_data_is_unknown() -> None:
    """Пока баланс не загружен, признак блокировки не выдумывается."""
    from unittest.mock import MagicMock

    from custom_components.elektronny_gorod.binary_sensor import (
        ElektronnyGorodBlockedBinarySensor,
    )

    coordinator = MagicMock()
    coordinator.data = {"balances": []}
    sensor = ElektronnyGorodBlockedBinarySensor(coordinator, PLACE_ID)

    assert sensor._balance_info is None
    assert sensor.is_on is None
    assert sensor.available is False
