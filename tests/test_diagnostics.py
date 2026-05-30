"""Тесты diagnostics redaction (S-08 / S-16 / A-23).

Гарантируют, что выгрузка diagnostics через HA UI НЕ содержит секретов
(access_token, refresh_token, go2rtc creds, user_agent с account_id) и PII.
См. ADR-0004 (token redaction), docs/audit/security.md#S-08.
"""
from __future__ import annotations

import json

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import REDACTED
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.elektronny_gorod.const import DOMAIN
from custom_components.elektronny_gorod.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)

_SECRET_MARKERS = (
    "supersecret-access",
    "supersecret-refresh",
    "go2rtc-pass-secret",
    "go2rtc-user-secret",
    "Pixel 7; account=1131686",  # user_agent несёт account_id
)


def _make_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Электронный город",
        data={
            "access_token": "supersecret-access",
            "refresh_token": "supersecret-refresh",
            "user_agent": "Pixel 7; account=1131686",
            "operator_id": 42,
            "account_id": 1131686,
            "subscriber_id": 999,
            "use_go2rtc": True,
            "go2rtc_base_url": "http://127.0.0.1:1984",
            "go2rtc_username": "go2rtc-user-secret",
            "go2rtc_password": "go2rtc-pass-secret",
        },
        options={
            "go2rtc_username": "go2rtc-user-secret",
            "go2rtc_password": "go2rtc-pass-secret",
        },
    )


async def test_diagnostics_redacts_all_secrets(hass: HomeAssistant) -> None:
    """Ни один секрет/креденшл не должен попасть в выгрузку (даже как substring)."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    blob = json.dumps(diag, default=str, ensure_ascii=False)

    for marker in _SECRET_MARKERS:
        assert marker not in blob, f"Секрет утёк в diagnostics: {marker!r}"

    data = diag["entry"]["data"]
    assert data["access_token"] == REDACTED
    assert data["refresh_token"] == REDACTED
    assert data["user_agent"] == REDACTED
    assert data["go2rtc_username"] == REDACTED
    assert data["go2rtc_password"] == REDACTED


async def test_diagnostics_redacts_options(hass: HomeAssistant) -> None:
    """go2rtc creds из entry.options тоже редактятся (S-16)."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    options = diag["entry"]["options"]
    assert options["go2rtc_password"] == REDACTED
    assert options["go2rtc_username"] == REDACTED


async def test_diagnostics_keeps_non_sensitive(hass: HomeAssistant) -> None:
    """Несекретные поля сохраняются — diagnostics должна быть полезной."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    data = diag["entry"]["data"]
    assert data["use_go2rtc"] is True
    assert data["go2rtc_base_url"] == "http://127.0.0.1:1984"


async def test_diagnostics_coordinator_snapshot_is_counts_only(
    hass: HomeAssistant,
) -> None:
    """Если coordinator есть — отдаём только счётчики, без PII/значений."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    class _FakeCoordinator:
        data = {
            "places": [{"id": 1}, {"id": 2}],
            "cameras": {"c1": {}, "c2": {}, "c3": {}},
            "locks": {"l1": {}},
            "balances": {"b1": {}},
            "dnd": {"root": True},
        }

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _FakeCoordinator()

    diag = await async_get_config_entry_diagnostics(hass, entry)
    snap = diag["coordinator"]
    assert snap == {
        "places": 2,
        "cameras": 3,
        "locks": 1,
        "balances": 1,
        "dnd": True,
    }


async def test_diagnostics_without_coordinator(hass: HomeAssistant) -> None:
    """Без coordinator в hass.data — diagnostics не падает, секция отсутствует."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert "coordinator" not in diag


def test_to_redact_covers_sensitive_keys() -> None:
    """TO_REDACT должен покрывать все SENSITIVE_KEYS (синхронизация с _logging.py)."""
    from custom_components.elektronny_gorod._logging import SENSITIVE_KEYS

    assert SENSITIVE_KEYS <= TO_REDACT
