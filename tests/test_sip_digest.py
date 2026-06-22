"""Unit-тесты SIP Digest MD5 аутентификации (sip/digest.py)."""
from __future__ import annotations

from custom_components.elektronny_gorod.sip.digest import (
    build_authorization,
    digest_response,
    md5,
)


def test_md5_ha1_rfc2617() -> None:
    # RFC 2617 §3.5: HA1 = MD5(user:realm:password).
    assert md5("Mufasa:testrealm@host.com:Circle Of Life") == (
        "939e7578ed9e3c518a452acee763bce9"
    )


def test_digest_response_rfc2617_qop_golden() -> None:
    # RFC 2617 §3.5 канонический пример (qop=auth).
    assert (
        digest_response(
            "Mufasa",
            "Circle Of Life",
            "testrealm@host.com",
            "dcd98b7102dd2f0e8b11d0f600bfb0c093",
            "GET",
            "/dir/index.html",
            qop="auth",
            cnonce="0a4f113b",
            nc="00000001",
        )
        == "6629fae49393a05397450978507c4ef1"
    )


def test_digest_response_without_qop_golden() -> None:
    # non-qop: MD5(HA1:nonce:HA2). Golden вычислен независимо (hashlib).
    assert (
        digest_response("alice", "secret", "sip.test", "NONCE123", "REGISTER", "sip:sip.test")
        == "931f7009cd4da0c9312391d3df56d22f"
    )


def test_build_authorization_qop_includes_all_fields() -> None:
    auth = build_authorization(
        "alice", "sip.test", "N", "sip:sip.test", "RESP",
        qop="auth", cnonce="C", nc="00000001",
    )
    assert auth.startswith("Digest ")
    assert 'username="alice"' in auth
    assert "algorithm=MD5" in auth
    assert "qop=auth" in auth
    assert "nc=00000001" in auth
    assert 'cnonce="C"' in auth


def test_build_authorization_without_qop_omits_qop_fields() -> None:
    auth = build_authorization("alice", "sip.test", "N", "sip:sip.test", "RESP")
    assert "qop" not in auth
    assert "cnonce" not in auth
