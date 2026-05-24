"""Утилиты безопасного логирования. См. ADR-0004 (token redaction).

🔴 Категорически нельзя логировать (см. также .claude/rules/no-secret-logs.md):
- access_token / refresh_token (в любом регистре);
- headers целиком (там Bearer);
- password / SMS-код;
- entry.data / entry.options целиком;
- тело auth-ответов;
- go2rtc_username / go2rtc_password.

Используй redact(data) для dict/headers, попадающих в логи.
"""
from __future__ import annotations

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
