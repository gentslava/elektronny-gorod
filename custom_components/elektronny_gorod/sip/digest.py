"""SIP Digest MD5 аутентификация (RFC 2617) для REGISTER к realm оператора.

REGISTER шлётся на FCM-ring (register-on-ring, ADR-0012) — challenge приходит на
него же. Из probe_sip.py. voip-utils Digest не реализует (design.md §3.1) — наш слой.
Поддержка qop=auth и legacy non-qop (Kazoo шлёт challenge с nonce/realm).
"""
from __future__ import annotations

import hashlib


def md5(s: str) -> str:
    """MD5 hex-digest UTF-8 строки."""
    return hashlib.md5(s.encode()).hexdigest()


def digest_response(
    user: str,
    password: str,
    realm: str,
    nonce: str,
    method: str,
    uri: str,
    qop: str | None = None,
    cnonce: str | None = None,
    nc: str | None = None,
) -> str:
    """Digest response (RFC 2617): MD5(HA1:nonce:[nc:cnonce:qop:]HA2)."""
    ha1 = md5(f"{user}:{realm}:{password}")
    ha2 = md5(f"{method}:{uri}")
    if qop:
        return md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")
    return md5(f"{ha1}:{nonce}:{ha2}")


def build_authorization(
    user: str,
    realm: str,
    nonce: str,
    uri: str,
    response: str,
    qop: str | None = None,
    cnonce: str | None = None,
    nc: str | None = None,
) -> str:
    """Собрать значение заголовка Authorization для REGISTER."""
    auth = (
        f'Digest username="{user}", realm="{realm}", nonce="{nonce}", '
        f'uri="{uri}", response="{response}", algorithm=MD5'
    )
    if qop:
        auth += f', qop={qop}, nc={nc}, cnonce="{cnonce}"'
    return auth
