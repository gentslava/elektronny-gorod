"""Tests for _logging.redact() helper (ADR-0004)."""
from __future__ import annotations

import pytest

from custom_components.elektronny_gorod._logging import (
    REDACTED,
    SENSITIVE_KEYS,
    AUTH_PATH_MARKERS,
    is_auth_path,
    redact,
    redact_path,
)


def test_redact_passes_through_scalars():
    assert redact(None) is None
    assert redact(42) == 42
    assert redact("hello") == "hello"
    assert redact(True) is True


def test_redact_dict_masks_sensitive_keys():
    src = {
        "access_token": "MHAT-secret",
        "refresh_token": "rt-secret",
        "operator_id": "1",
        "place_id": "12345",
    }
    out = redact(src)
    assert out["access_token"] == REDACTED
    assert out["refresh_token"] == REDACTED
    assert out["operator_id"] == "1"
    assert out["place_id"] == "12345"


def test_redact_case_insensitive():
    """Authorization header (любой регистр) должен маскироваться."""
    src = {"Authorization": "Bearer xxx", "AccessToken": "yyy", "REFRESHTOKEN": "zzz"}
    out = redact(src)
    assert out["Authorization"] == REDACTED
    assert out["AccessToken"] == REDACTED
    assert out["REFRESHTOKEN"] == REDACTED


def test_redact_dash_to_underscore_normalization():
    """`User-Agent` (как в HTTP headers) и `user_agent` — эквивалентны.

    Регрессия из code review: aiohttp хранит headers с дефисом, без нормализации
    `User-Agent` value (содержащее account_id) утекало бы в логи.
    """
    src = {
        "User-Agent": "leaky-agent-value",
        "user-agent": "leaky-too",
        "USER-AGENT": "loud-leak",
        "user_agent": "underscore-form",
    }
    out = redact(src)
    for k in src:
        assert out[k] == REDACTED, f"key {k!r} not redacted"


def test_redact_non_sensitive_dashed_key_not_affected():
    """Только ключи из SENSITIVE_KEYS маскируются; случайные `X-User-Agent` — нет."""
    src = {"X-User-Agent": "ok", "X-Custom": "ok"}
    out = redact(src)
    assert out["X-User-Agent"] == "ok"
    assert out["X-Custom"] == "ok"


def test_redact_recursive_into_nested_dicts():
    src = {
        "outer": {
            "headers": {
                "authorization": "Bearer xxx",
                "user-agent": "Test",  # дефис — должен маскироваться через нормализацию
            },
            "safe_key": "value",
        },
    }
    out = redact(src)
    assert out["outer"]["headers"]["authorization"] == REDACTED
    assert out["outer"]["headers"]["user-agent"] == REDACTED
    assert out["outer"]["safe_key"] == "value"


def test_redact_recursive_into_lists():
    src = [
        {"password": "p1"},
        {"safe": "ok"},
        {"password": "p2"},
    ]
    out = redact(src)
    assert out[0]["password"] == REDACTED
    assert out[1]["safe"] == "ok"
    assert out[2]["password"] == REDACTED


def test_redact_preserves_tuple_type():
    src = ({"hash1": "x"}, {"hash2": "y"})
    out = redact(src)
    assert isinstance(out, tuple)
    assert out[0]["hash1"] == REDACTED
    assert out[1]["hash2"] == REDACTED


def test_redact_does_not_modify_source():
    src = {"access_token": "secret"}
    redact(src)
    assert src["access_token"] == "secret"


def test_redact_empty_dict():
    assert redact({}) == {}


def test_redact_empty_list():
    assert redact([]) == []


@pytest.mark.parametrize(
    "key",
    sorted(SENSITIVE_KEYS),
)
def test_each_sensitive_key_is_redacted(key: str):
    """Все ключи из SENSITIVE_KEYS должны маскироваться."""
    src = {key: "any-value"}
    assert redact(src)[key] == REDACTED


def test_is_auth_path_positive():
    assert is_auth_path("/auth/v2/login/+79991112233") is True
    assert is_auth_path("/auth/v3/auth/+79991112233/confirmation") is True
    assert is_auth_path("https://myhome.proptech.ru/auth/v2/confirmation/+79991112233") is True


def test_is_auth_path_negative():
    assert is_auth_path("/rest/v3/subscriber-places") is False
    assert is_auth_path("/api/mh-payment/mobile/v1/finance") is False
    assert is_auth_path("/rest/v1/places/12345/accesscontrols") is False


def test_auth_path_markers_contains_auth():
    """Sanity check: маркеры покрывают auth/-paths."""
    assert any("/auth/" in m for m in AUTH_PATH_MARKERS)


@pytest.mark.parametrize("path,expected", [
    # numeric identifier (phone / contract / account)
    ("/auth/v2/login/1131686", "/auth/v2/login/***"),
    ("/auth/v2/login/79991234567", "/auth/v2/login/***"),
    ("/auth/v2/login/+79991234567", "/auth/v2/login/***"),
    ("/auth/v2/auth/79991234567/password", "/auth/v2/auth/***/password"),
    ("/auth/v3/auth/+79991234567/confirmation", "/auth/v3/auth/***/confirmation"),
    ("/auth/v2/confirmation/79991234567", "/auth/v2/confirmation/***"),
    # full URL
    ("https://myhome.proptech.ru/auth/v2/login/1131686",
     "https://myhome.proptech.ru/auth/v2/login/***"),
])
def test_redact_path_masks_auth_identifiers(path, expected):
    assert redact_path(path) == expected


@pytest.mark.parametrize("path", [
    "/rest/v3/subscriber-places",
    "/rest/v1/places/12345/accesscontrols",
    "/api/mh-payment/mobile/v1/finance",
    "/rest/v1/forpost/cameras/5593590/video",
])
def test_redact_path_passes_non_auth_unchanged(path):
    """Не-auth URLs не маскируются: place_id, camera_id и т.д. — internal
    references, не PII клиента."""
    assert redact_path(path) == path
