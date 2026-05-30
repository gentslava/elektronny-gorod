"""Diagnostics для Elektronny Gorod (S-08 / S-16 / A-23, ADR-0004).

HA по умолчанию при экспорте diagnostics дампит `entry.data`/`entry.options`
целиком — там access_token / refresh_token / go2rtc creds / user_agent
(с account_id). Этот модуль маскирует их через `async_redact_data`, чтобы
пользователь мог безопасно поделиться диагностикой.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from ._logging import SENSITIVE_KEYS
from .const import (
    CONF_ACCOUNT_ID,
    CONF_CONTRACT,
    CONF_OPERATOR_ID,
    CONF_PHONE,
    CONF_SUBSCRIBER_ID,
    DOMAIN,
)

# Источник правды по секретам — SENSITIVE_KEYS из _logging.py (ADR-0004).
# Дополняем PII-идентификаторами, которые не секреты, но не должны утекать в
# публично расшаренную diagnostics-выгрузку.
TO_REDACT: frozenset[str] = SENSITIVE_KEYS | {
    CONF_PHONE,
    CONF_CONTRACT,
    CONF_OPERATOR_ID,
    CONF_ACCOUNT_ID,
    CONF_SUBSCRIBER_ID,
    "name",
    "address",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Вернуть redact-нутую диагностику config entry."""
    diagnostics: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
    }

    # Снимок coordinator — только счётчики (без значений/PII).
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    data = getattr(coordinator, "data", None)
    if isinstance(data, dict):
        diagnostics["coordinator"] = {
            "places": len(data.get("places") or []),
            "cameras": len(data.get("cameras") or {}),
            "locks": len(data.get("locks") or {}),
            "balances": len(data.get("balances") or {}),
            "dnd": bool(data.get("dnd")),
        }

    return diagnostics
