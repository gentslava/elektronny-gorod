"""Утилиты безопасного логирования. См. ADR-0004 (token redaction).

🔴 Категорически нельзя логировать (см. также .claude/rules/no-secret-logs.md):
- access_token / refresh_token (в любом регистре);
- headers целиком (там Bearer);
- password / SMS-код;
- entry.data / entry.options целиком;
- тело auth-ответов;
- go2rtc_username / go2rtc_password;
- phone / contract_id / account_id в auth URL path.

Используй redact(data) для dict/headers, попадающих в логи.
Используй redact_path(url) для URL/path попадающих в логи.
"""
from __future__ import annotations

import re
from typing import Any

REDACTED = "***"

# Источник правды по списку — ADR-0004 (Token redaction strategy).
# При добавлении ключа сюда — обновить также TO_REDACT в diagnostics.py (когда появится).
SENSITIVE_KEYS: frozenset[str] = frozenset({
    "access_token",
    "refresh_token",
    "accesstoken",
    "refreshtoken",
    "password",
    "go2rtc_password",
    "go2rtc_username",
    "user_agent",
    "authorization",
    "sms",
    "confirm1",
    "confirm2",
    "hash1",
    "hash2",
    "fcm_credentials",
    "pushtoken",
    "realm",  # SIP realm минта sipdevices — содержит acId (PII), парный к SIP password
})


def _normalize_key(name: object) -> str:
    """Нормализовать имя ключа: lowercase + дефис → подчёркивание.

    Это критично для HTTP-headers: aiohttp хранит их в форме `User-Agent`,
    а в SENSITIVE_KEYS — `user_agent`. Без нормализации `User-Agent` бы не
    редактился и значение (содержащее account_id) попадало бы в логи.
    """
    return str(name).lower().replace("-", "_")


def redact(value: Any, keys: frozenset[str] = SENSITIVE_KEYS) -> Any:
    """Рекурсивно маскировать значения для sensitive-ключей.

    Сравнение ключей — case-insensitive **и** dash-insensitive:
    `Authorization` == `authorization`; `User-Agent` == `user_agent`.

    Возвращает новую структуру; исходную не модифицирует.
    """
    if isinstance(value, dict):
        return {
            k: REDACTED if _normalize_key(k) in keys else redact(v, keys)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        kind = type(value)
        return kind(redact(v, keys) for v in value)
    return value


# Auth-эндпоинты, на которых запрещено логировать request body или response body
# (там приходят / отправляются токены, пароли, SMS).
AUTH_PATH_MARKERS: tuple[str, ...] = (
    "/auth/",
)


def is_auth_path(url_or_path: str) -> bool:
    """True, если URL/path относится к auth-flow и body не должно попадать в логи."""
    return any(marker in url_or_path for marker in AUTH_PATH_MARKERS)


# Заменяет numeric identifier (phone, contract_id, account_id) внутри auth-URL
# на REDACTED. Применяется ТОЛЬКО к auth-paths — обычные REST URL (с place_id,
# camera_id и т.д.) не маскируются, т.к. это не PII, а internal references.
#
# Примеры:
#   /auth/v2/login/1131686                  → /auth/v2/login/***
#   /auth/v2/auth/+79991234567/password     → /auth/v2/auth/***/password
#   /auth/v3/auth/79991234567/confirmation  → /auth/v3/auth/***/confirmation
_AUTH_PATH_ID_PATTERN = re.compile(r"(/auth/v\d+/[a-z]+/)\+?\d+", re.IGNORECASE)


def redact_path(url_or_path: str) -> str:
    """Маскировать PII identifier в auth-URL path.

    Для non-auth path — возвращает строку без изменений.
    """
    if not is_auth_path(url_or_path):
        return url_or_path
    return _AUTH_PATH_ID_PATTERN.sub(r"\1***", url_or_path)
