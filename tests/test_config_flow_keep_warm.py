"""Config-flow contract for opt-in external RTSP publishing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCOUNT_ID,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_KEEP_WARM,
    CONF_GO2RTC_KEEP_WARM_HIDDEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_SUBSCRIBER_ID,
    CONF_USE_GO2RTC,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.go2rtc import Go2RtcValidationResult


_PROFILE = {
    "subscriber": {"name": "Ivan", "accountId": "1131686", "id": 2104659}
}


@pytest.fixture(autouse=True)
def _mock_boundaries():
    """Keep config-flow tests off the network and operator API."""
    with (
        patch(
            "custom_components.elektronny_gorod.config_flow.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.elektronny_gorod.config_flow.ElektronnyGorodAPI"
        ) as api_cls,
    ):
        api_cls.return_value.query_profile = AsyncMock(return_value=_PROFILE)
        yield


async def _open_initial_go2rtc_form(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "PASTED_TOKEN"}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "go2rtc"}
    )


def _entry(hass: HomeAssistant, *, data_flags: tuple[bool, bool]) -> ConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        title="Test",
        data={
            CONF_NAME: "Test",
            CONF_ACCOUNT_ID: "1131686",
            CONF_SUBSCRIBER_ID: 2104659,
            CONF_ACCESS_TOKEN: "AT",
            CONF_REFRESH_TOKEN: "RT",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: '{"a":"b"}',
            CONF_USE_GO2RTC: True,
            CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984",
            CONF_GO2RTC_KEEP_WARM: data_flags[0],
            CONF_GO2RTC_KEEP_WARM_HIDDEN: data_flags[1],
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_initial_go2rtc_form_defaults_keep_warm_off(
    hass: HomeAssistant,
) -> None:
    """Both publishing switches are explicit opt-ins on first setup."""
    result = await _open_initial_go2rtc_form(hass)

    assert result["type"] == FlowResultType.FORM
    values = result["data_schema"]({CONF_GO2RTC_BASE_URL: "http://go2rtc:1984"})
    assert values[CONF_GO2RTC_KEEP_WARM] is False
    assert values[CONF_GO2RTC_KEEP_WARM_HIDDEN] is False


async def test_options_flow_persists_keep_warm_flags(
    hass: HomeAssistant,
) -> None:
    """The options flow persists both switches independently."""
    entry = _entry(hass, data_flags=(False, False))
    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch(
        "custom_components.elektronny_gorod.config_flow.validate_go2rtc",
        new=AsyncMock(
            return_value=Go2RtcValidationResult(
                ok=True, error="", rtsp_host="127.0.0.1"
            )
        ),
    ):
        finish = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_USE_GO2RTC: True,
                CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984",
                CONF_GO2RTC_KEEP_WARM: True,
                CONF_GO2RTC_KEEP_WARM_HIDDEN: True,
            },
        )

    assert finish["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_GO2RTC_KEEP_WARM] is True
    assert entry.options[CONF_GO2RTC_KEEP_WARM_HIDDEN] is True


async def test_initial_go2rtc_persists_keep_warm_flags(
    hass: HomeAssistant,
    mock_setup_entry,
) -> None:
    """Initial setup stores both opt-ins in config-entry data."""
    result = await _open_initial_go2rtc_form(hass)

    with patch(
        "custom_components.elektronny_gorod.config_flow.validate_go2rtc",
        new=AsyncMock(
            return_value=Go2RtcValidationResult(
                ok=True, error="", rtsp_host="127.0.0.1"
            )
        ),
    ):
        finish = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984",
                CONF_GO2RTC_KEEP_WARM: True,
                CONF_GO2RTC_KEEP_WARM_HIDDEN: True,
            },
        )

    assert finish["type"] == FlowResultType.CREATE_ENTRY
    assert finish["data"][CONF_GO2RTC_KEEP_WARM] is True
    assert finish["data"][CONF_GO2RTC_KEEP_WARM_HIDDEN] is True


async def test_skip_go2rtc_persists_keep_warm_off(
    hass: HomeAssistant,
    mock_setup_entry,
) -> None:
    """Skipping go2rtc cannot leave background publishing enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "PASTED_TOKEN"}
    )
    finish = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "skip_go2rtc"}
    )

    assert finish["type"] == FlowResultType.CREATE_ENTRY
    assert finish["data"][CONF_GO2RTC_KEEP_WARM] is False
    assert finish["data"][CONF_GO2RTC_KEEP_WARM_HIDDEN] is False


async def test_options_flow_defaults_from_entry_data(
    hass: HomeAssistant,
) -> None:
    """Absent option overrides fall back to the values stored in entry data."""
    entry = _entry(hass, data_flags=(True, True))
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    values = result["data_schema"]({})
    assert values[CONF_GO2RTC_KEEP_WARM] is True
    assert values[CONF_GO2RTC_KEEP_WARM_HIDDEN] is True


def test_keep_warm_keys_are_public_constants() -> None:
    """Policy/config consumers share one spelling for both option keys."""
    assert CONF_GO2RTC_KEEP_WARM == "go2rtc_keep_warm"
    assert CONF_GO2RTC_KEEP_WARM_HIDDEN == "go2rtc_keep_warm_hidden"
