"""Regression test for A-78: option flow must allow clearing go2rtc creds.

Until A-78 fix, `vol.Optional(KEY, default="old_value")` in OptionsFlow
schema meant HA frontend пустой submit вызывал voluptuous default →
старые creds back-fill'ились. Юзер «успешно сохранял» creds, но они
не менялись.

Fix: schema без default'а для username/password, текущие значения подаются
через `add_suggested_values_to_schema` (HA pattern).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elektronny_gorod.const import (
    DOMAIN,
    CONF_USE_GO2RTC,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_RTSP_HOST,
    CONF_GO2RTC_USERNAME,
    CONF_GO2RTC_PASSWORD,
)
from custom_components.elektronny_gorod.go2rtc import Go2RtcValidationResult


@pytest.fixture
def mock_entry_with_creds(hass: HomeAssistant) -> ConfigEntry:
    """Entry с уже сохранёнными go2rtc creds в options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test EG",
        data={
            "access_token": "tkn",
            "refresh_token": "ref",
            "account_id": "1131686",
            "operator_id": "1",
            "subscriber_id": 2104659,
            "user_agent": '{"a":"b"}',
            "name": "Test User",
            CONF_USE_GO2RTC: True,
            CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984",
            CONF_GO2RTC_RTSP_HOST: "127.0.0.1",
            CONF_GO2RTC_USERNAME: "",
            CONF_GO2RTC_PASSWORD: "",
        },
        options={
            CONF_USE_GO2RTC: True,
            CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984",
            CONF_GO2RTC_RTSP_HOST: "127.0.0.1",
            CONF_GO2RTC_USERNAME: "admin",
            CONF_GO2RTC_PASSWORD: "supersecret",
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_clear_creds_when_use_go2rtc_off(
    hass: HomeAssistant, mock_entry_with_creds: ConfigEntry
) -> None:
    """Snimaem галочку use_go2rtc, очищаем creds — должны сохраниться пустыми."""
    result = await hass.config_entries.options.async_init(
        mock_entry_with_creds.entry_id
    )
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    # Submit с очищенными creds и снятой галочкой use_go2rtc
    # (HA frontend омит пустые Optional поля — симулируем это: НЕ передаём ключи)
    finish = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_GO2RTC: False,
            CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984",
            # ↓ username/password НЕ передаём — симулируем cleared empty fields
        },
    )
    await hass.async_block_till_done()

    assert finish["type"] == "create_entry"
    # CRITICAL: до fix'а здесь были бы "admin" / "supersecret" — voluptuous
    # default подставил бы старое значение. После fix — пустые.
    assert mock_entry_with_creds.options.get(CONF_GO2RTC_USERNAME) == ""
    assert mock_entry_with_creds.options.get(CONF_GO2RTC_PASSWORD) == ""
    assert mock_entry_with_creds.options.get(CONF_USE_GO2RTC) is False


async def test_clear_creds_with_use_go2rtc_on_shows_auth_error(
    hass: HomeAssistant, mock_entry_with_creds: ConfigEntry
) -> None:
    """С use_go2rtc ON и cleared creds + go2rtc auth-required → понятная ошибка auth_failed.

    Это второй сценарий A-78: юзер хочет очистить creds но забыл снять
    галочку → validate_go2rtc вернёт 401 (если у юзера auth на сервере) →
    мы показываем go2rtc_auth_failed (а не generic unreachable).
    """
    result = await hass.config_entries.options.async_init(
        mock_entry_with_creds.entry_id
    )

    # Mock validate_go2rtc → returns auth_failed (как реальный server c auth on)
    with patch(
        "custom_components.elektronny_gorod.config_flow.validate_go2rtc",
        new=AsyncMock(
            return_value=Go2RtcValidationResult(
                ok=False, error="go2rtc_auth_failed", rtsp_host="127.0.0.1"
            )
        ),
    ):
        finish = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_USE_GO2RTC: True,  # ← НЕ снял галочку
                CONF_GO2RTC_BASE_URL: "http://127.0.0.1:1984",
                # username/password не передаём (cleared)
            },
        )

    assert finish["type"] == "form"
    assert finish["errors"] == {"base": "go2rtc_auth_failed"}
    # Options остались прежними — validation block'нул save
    assert mock_entry_with_creds.options.get(CONF_GO2RTC_USERNAME) == "admin"


async def test_change_creds_to_new_values(
    hass: HomeAssistant, mock_entry_with_creds: ConfigEntry
) -> None:
    """Юзер вводит НОВЫЕ creds — они должны попасть в options."""
    result = await hass.config_entries.options.async_init(
        mock_entry_with_creds.entry_id
    )

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
                CONF_GO2RTC_USERNAME: "newuser",
                CONF_GO2RTC_PASSWORD: "newpass",
            },
        )
    await hass.async_block_till_done()

    assert finish["type"] == "create_entry"
    assert mock_entry_with_creds.options.get(CONF_GO2RTC_USERNAME) == "newuser"
    assert mock_entry_with_creds.options.get(CONF_GO2RTC_PASSWORD) == "newpass"
