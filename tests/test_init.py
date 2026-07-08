"""Config-entry migration tests (A-73 — async_migrate_entry v1→2→3).

Проверяют, что `async_migrate_entry` доводит старые entry до текущей VERSION=3
без потери данных: v1 добавляет `user_agent`, v2/v3 — go2rtc-дефолты.
"""
from __future__ import annotations

import json

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elektronny_gorod import async_migrate_entry
from custom_components.elektronny_gorod.const import (
    DOMAIN,
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    CONF_USE_GO2RTC,
    CONF_GO2RTC_BASE_URL,
    CONF_GO2RTC_RTSP_HOST,
    DEFAULT_GO2RTC_BASE_URL,
    DEFAULT_GO2RTC_RTSP_HOST,
)


async def test_migrate_v1_to_v3(hass: HomeAssistant) -> None:
    """v1 (без user_agent, без go2rtc) → v3: добавлены user_agent + go2rtc-дефолты."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_REFRESH_TOKEN: "RT",
            CONF_OPERATOR_ID: "1",
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 3
    # v1→2: user_agent появился и это валидный JSON с operator_id.
    assert CONF_USER_AGENT in entry.data
    ua = json.loads(entry.data[CONF_USER_AGENT])
    assert ua["operator_id"] == "1"
    # v2→3: go2rtc-дефолты.
    assert entry.data[CONF_USE_GO2RTC] is False
    assert entry.data[CONF_GO2RTC_BASE_URL] == DEFAULT_GO2RTC_BASE_URL
    assert entry.data[CONF_GO2RTC_RTSP_HOST] == DEFAULT_GO2RTC_RTSP_HOST
    # Исходные данные не потеряны.
    assert entry.data[CONF_ACCESS_TOKEN] == "AT"


async def test_migrate_v2_to_v3(hass: HomeAssistant) -> None:
    """v2 (user_agent есть, go2rtc нет) → v3: добавлены только go2rtc-дефолты."""
    existing_ua = json.dumps({"operator_id": "1", "marker": "kept"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_REFRESH_TOKEN: "RT",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: existing_ua,
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 3
    # user_agent не перезаписан миграцией.
    assert entry.data[CONF_USER_AGENT] == existing_ua
    assert entry.data[CONF_USE_GO2RTC] is False
    assert entry.data[CONF_GO2RTC_BASE_URL] == DEFAULT_GO2RTC_BASE_URL
    assert entry.data[CONF_GO2RTC_RTSP_HOST] == DEFAULT_GO2RTC_RTSP_HOST


async def test_migrate_v3_noop(hass: HomeAssistant) -> None:
    """v3 (актуальная) → миграция ничего не ломает, версия остаётся 3."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=3,
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps({"operator_id": "1"}),
            CONF_USE_GO2RTC: True,
            CONF_GO2RTC_BASE_URL: "http://example:1984",
            CONF_GO2RTC_RTSP_HOST: "example",
        },
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True

    assert entry.version == 3
    # Существующие go2rtc-значения не сброшены дефолтами.
    assert entry.data[CONF_USE_GO2RTC] is True
    assert entry.data[CONF_GO2RTC_BASE_URL] == "http://example:1984"
