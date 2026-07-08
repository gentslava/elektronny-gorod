"""Config-flow tests (A-73 — Bronze IQS gate).

Покрывают три ветки аутентификации + go2rtc-меню + abort/reauth-кейсы.
API мокается на уровне namespace `config_flow.ElektronnyGorodAPI` (ленивый
`@property api` создаёт инстанс при первом обращении в step), поэтому сетевых
запросов к оператору нет.
"""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elektronny_gorod.const import (
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_CONTRACT,
    CONF_OPERATOR_ID,
    CONF_PHONE,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_SMS,
    CONF_SUBSCRIBER_ID,
    CONF_USER_AGENT,
    CONF_USE_GO2RTC,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_RTSP_HOST,
    CONF_GO2RTC_USERNAME,
    CONF_GO2RTC_PASSWORD,
)
from custom_components.elektronny_gorod.go2rtc import Go2RtcValidationResult


_PROFILE = {"subscriber": {"name": "Ivan", "accountId": "1131686", "id": 2104659}}
_AUTH = {"accessToken": "AT", "refreshToken": "RT", "operatorId": 1}
_CONTRACT = {"subscriberId": 2104659, "address": "Some St 1", "accountId": "1131686"}


@pytest.fixture
def mock_api() -> Generator[MagicMock, None, None]:
    """Мок ElektronnyGorodAPI в namespace config_flow (ленивый инстанс из @property)."""
    with patch(
        "custom_components.elektronny_gorod.config_flow.ElektronnyGorodAPI"
    ) as cls:
        api = cls.return_value
        api.query_contracts = AsyncMock()
        api.verify_password = AsyncMock(return_value=_AUTH)
        api.verify_sms_code = AsyncMock(return_value=_AUTH)
        api.request_sms_code = AsyncMock(return_value=None)
        api.query_profile = AsyncMock(return_value=_PROFILE)
        yield api


@pytest.fixture
def _mock_clientsession() -> Generator[None, None, None]:
    """Не создавать реальную aiohttp-сессию в go2rtc-step (см. test_options_flow)."""
    with patch(
        "custom_components.elektronny_gorod.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ):
        yield


def _existing_entry(hass: HomeAssistant, **overrides) -> MockConfigEntry:
    data = {
        CONF_NAME: "Ivan (1131686)",
        CONF_ACCOUNT_ID: "1131686",
        CONF_SUBSCRIBER_ID: 2104659,
        CONF_ACCESS_TOKEN: "OLD_AT",
        CONF_REFRESH_TOKEN: "OLD_RT",
        CONF_OPERATOR_ID: "1",
        CONF_USER_AGENT: '{"a":"b"}',
    }
    data.update(overrides)
    entry = MockConfigEntry(domain=DOMAIN, version=3, title=data[CONF_NAME], data=data)
    entry.add_to_hass(hass)
    return entry


async def test_user_phone_sms_happy(
    hass: HomeAssistant, mock_api: MagicMock, mock_setup_entry
) -> None:
    """phone → contract → sms → go2rtc-menu → skip → CREATE_ENTRY."""
    mock_api.query_contracts.return_value = {"password": False, "contracts": [_CONTRACT]}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PHONE: "+79990000000"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "contract"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CONTRACT: "2104659"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "sms"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SMS: "1234"}
    )
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "go2rtc_menu"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "skip_go2rtc"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Ivan (1131686)"
    assert result["data"][CONF_ACCESS_TOKEN] == "AT"
    assert result["data"][CONF_USE_GO2RTC] is False
    mock_api.request_sms_code.assert_awaited_once()
    mock_api.verify_sms_code.assert_awaited_once()


async def test_user_phone_password_happy(
    hass: HomeAssistant, mock_api: MagicMock, mock_setup_entry
) -> None:
    """phone (password=True) → password → go2rtc-menu → skip → CREATE_ENTRY."""
    mock_api.query_contracts.return_value = {"password": True}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PHONE: "+79990000000"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "password"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "hunter2"}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "skip_go2rtc"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ACCESS_TOKEN] == "AT"
    mock_api.verify_password.assert_awaited_once()


async def test_user_access_token_advanced(
    hass: HomeAssistant, mock_api: MagicMock, mock_setup_entry
) -> None:
    """advanced mode: paste access_token → go2rtc-menu → skip → CREATE_ENTRY."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "PASTED_TOKEN"}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "skip_go2rtc"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_ACCESS_TOKEN] == "PASTED_TOKEN"


async def test_go2rtc_setup_valid(
    hass: HomeAssistant, mock_api: MagicMock, mock_setup_entry, _mock_clientsession
) -> None:
    """advanced token → go2rtc → validate ok → CREATE_ENTRY с go2rtc-данными."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "PASTED_TOKEN"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "go2rtc"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "go2rtc"

    with patch(
        "custom_components.elektronny_gorod.config_flow.validate_go2rtc",
        new=AsyncMock(
            return_value=Go2RtcValidationResult(ok=True, error="", rtsp_host="127.0.0.1")
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984",
                CONF_GO2RTC_USERNAME: "admin",
                CONF_GO2RTC_PASSWORD: "secret",
            },
        )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USE_GO2RTC] is True
    assert result["data"][CONF_GO2RTC_RTSP_HOST] == "127.0.0.1"
    assert result["data"][CONF_GO2RTC_USERNAME] == "admin"


async def test_invalid_phone_shows_error(hass: HomeAssistant, mock_api: MagicMock) -> None:
    """Пустой phone → форма с error invalid_phone, без обращения к API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PHONE: "   "}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_PHONE: "invalid_phone"}
    mock_api.query_contracts.assert_not_awaited()


async def test_abort_already_configured(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Повтор по совпадающему access_token → abort already_configured."""
    _existing_entry(hass, access_token="PASTED_TOKEN")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "PASTED_TOKEN"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_entry_and_aborts(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Совпадение name+account+subscriber (но иной токен) → обновление data + abort reauth_successful."""
    entry = _existing_entry(hass, access_token="OLD_AT")

    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock(return_value=True)
    ) as reload:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER, "show_advanced_options": True}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ACCESS_TOKEN: "NEW_AT"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    # data обновлена свежим токеном.
    assert entry.data[CONF_ACCESS_TOKEN] == "NEW_AT"
    reload.assert_awaited_once()
