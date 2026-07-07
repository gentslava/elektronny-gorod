"""helpers.py tests — golden vectors + list utils (A-74).

Крипто-функции (`hash_password`, `hash_password_timestamp`) — reverse-engineered
формат оператора. Golden vectors пиннят текущую формулу: любая правка порядка
конкатенации / prefix / secret / алгоритма молча ломает login, и этот тест —
единственный регрессионный guard (см. audit A-74).

Эталонные значения посчитаны независимой реализацией (hashlib напрямую), не
через `helpers`, — иначе тест был бы циклическим. Значения — детерминированы для
фиксированных входов.
"""
from __future__ import annotations

import base64
import hashlib

import pytest

from custom_components.elektronny_gorod.helpers import (
    append_unique,
    contains,
    dedupe_by_id,
    find,
    hash_password,
    hash_password_timestamp,
)


# --- Golden vectors: hash_password (SHA1 → base64) ------------------------- #


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("password123", "y/2sYAj5yrQIN4TL0YdPdmGNKpc="),
        ("", "2jmj7l5rSw0yVb/vlWAYkK/YBwk="),
        ("Пароль!", "t6fUQ0YP3j7aNGLaPdw96pe2vb8="),  # UTF-8 encoding guard
    ],
)
def test_hash_password_golden(password: str, expected: str) -> None:
    """hash_password фиксирован: SHA1(utf-8) → base64."""
    assert hash_password(password) == expected


def test_hash_password_matches_reference_algorithm() -> None:
    """Двойной guard: совпадает с независимой SHA1→base64 реализацией."""
    password = "another-secret"
    reference = base64.b64encode(
        hashlib.sha1(password.encode("utf-8")).digest()
    ).decode("utf-8")
    assert hash_password(password) == reference


# --- Golden vector: hash_password_timestamp (MD5 of concat) ---------------- #


def test_hash_password_timestamp_golden() -> None:
    """hash_password_timestamp фиксирован: MD5(prefix+login+password+time+secret).

    Пиннит порядок конкатенации и захардкоженные prefix/secret — их изменение
    молча сломало бы auth.
    """
    result = hash_password_timestamp("+79990000000", "password123", "20260101120000")
    assert result == "3c522969fcbfc59b17273139c404d8c1"


def test_hash_password_timestamp_varies_with_time() -> None:
    """Разный timestamp → разный хеш (time реально участвует в формуле)."""
    a = hash_password_timestamp("+79990000000", "password123", "20260101120000")
    b = hash_password_timestamp("+79990000000", "password123", "20260101120001")
    assert a != b


# --- List utils ------------------------------------------------------------ #


def test_find_returns_first_match_or_none() -> None:
    items = [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}, {"id": 2, "v": "c"}]
    assert find(items, lambda x: x["id"] == 2) == {"id": 2, "v": "b"}
    assert find(items, lambda x: x["id"] == 99) is None
    assert find([], lambda x: True) is None


def test_contains() -> None:
    items = [{"id": 1}, {"id": 2}]
    assert contains(items, lambda x: x["id"] == 2) is True
    assert contains(items, lambda x: x["id"] == 3) is False
    assert contains([], lambda x: True) is False


def test_dedupe_by_id_keeps_first_occurrence() -> None:
    items = [
        {"id": 1, "v": "first"},
        {"id": 2, "v": "x"},
        {"id": 1, "v": "dup"},
        {"id": "1", "v": "str-dup"},  # str vs int → тот же ключ (str(id))
    ]
    result = dedupe_by_id(items)
    assert [r["v"] for r in result] == ["first", "x"]


def test_append_unique_skips_existing_id() -> None:
    target = [{"id": 1}, {"id": 2}]
    append_unique(target, {"id": 2})  # уже есть — no-op
    append_unique(target, {"id": 3})  # новый — добавится
    assert [d["id"] for d in target] == [1, 2, 3]
