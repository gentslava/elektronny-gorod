"""Отзыв токена должен приводить к предложению войти заново.

Раньше 401 от оператора поднимался как `UpdateFailed` — то есть «повторим
позже». Повтором это не лечится: токен отозван, и сколько ни ждать, ответ
будет тот же. Запись просто уходила в «недоступна», а пользователю оставалось
догадываться, что делать.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientError, ClientResponse
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.http import is_unauthorized
from custom_components.elektronny_gorod.user_agent import UserAgent


def _response(status: int) -> MagicMock:
    response = MagicMock(spec=ClientResponse)
    response.status = status
    return response


def _make_config_entry() -> MockConfigEntry:
    ua = UserAgent()
    ua.operator_id = "1"
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="test_unique_subscriber_S1",
        title="Test",
        data={
            CONF_ACCESS_TOKEN: "STALE",
            CONF_REFRESH_TOKEN: "R1",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(ua.json()),
            "account_id": "A1",
            "subscriber_id": "S1",
            "use_go2rtc": False,
        },
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ClientError(_response(401)), True),
        (ClientError(_response(500)), False),
        (ClientError(_response(531)), False),
        (ClientError("нет ответа вовсе"), False),
        (TimeoutError(), False),
    ],
)
def test_only_401_counts_as_revoked_token(error, expected) -> None:
    """Отзыв токена отличается от временной ошибки оператора.

    Оператор регулярно отдаёт `531` и `500` — по ним звать пользователя
    заново вводить пароль нельзя.
    """
    assert is_unauthorized(error) is expected


async def test_revoked_token_starts_reauth(hass: HomeAssistant) -> None:
    """401 при загрузке — запись просит повторный вход, а не «недоступна»."""
    entry = _make_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as cls:
        api = cls.return_value
        api.http = AsyncMock()
        api.http.user_agent = AsyncMock()
        api.query_places = AsyncMock(side_effect=ClientError(_response(401)))

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1, "Home Assistant не предложил войти заново"
    assert flows[0]["context"]["source"] == "reauth"


async def test_operator_outage_does_not_ask_for_credentials(
    hass: HomeAssistant,
) -> None:
    """Временный отказ оператора повторный вход не запускает.

    Иначе каждое падение на стороне оператора выглядело бы как «ваш пароль
    больше не подходит».
    """
    entry = _make_config_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as cls:
        api = cls.return_value
        api.http = AsyncMock()
        api.http.user_agent = AsyncMock()
        api.query_places = AsyncMock(side_effect=ClientError(_response(500)))

        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
