"""Unit-тесты SIP REGISTER build + Digest auth (sip/register.py).

Модель REGISTER-on-answer (call-answer-model.md): REGISTER с проприетарными
push-params приложения триггерит INVITE. Expires=30, Supported: outbound/gruu/path.
"""
from __future__ import annotations

from custom_components.elektronny_gorod.sip.register import (
    PUSH_APP_ID,
    build_contact,
    build_register,
    build_register_authorization,
)


def test_build_contact_has_app_push_params() -> None:
    c = build_contact("000", "1.2.3.4", 5066, "FCMTOKEN123")
    assert c.startswith("<sip:000@1.2.3.4:5066;transport=udp")
    assert f"app-id={PUSH_APP_ID}" in c
    assert "pn-type=google" in c
    assert "pn-tok=FCMTOKEN123" in c
    assert c.endswith(">")


def test_build_register_structure() -> None:
    reg = build_register(
        login="000", realm="ac.intercom.op.ru", host="1.2.3.4", port=5066,
        call_id="cid@host", from_tag="ftag", cseq=1,
        contact="<sip:000@1.2.3.4:5066;transport=udp>", branch="z9hG4bKtest",
        user_agent="Myhome/Myhome-android",
    )
    assert reg.startswith("REGISTER sip:ac.intercom.op.ru SIP/2.0\r\n")
    assert "Via: SIP/2.0/UDP 1.2.3.4:5066;branch=z9hG4bKtest;rport" in reg
    assert "From: <sip:000@ac.intercom.op.ru>;tag=ftag" in reg
    assert "CSeq: 1 REGISTER" in reg
    assert "Contact: <sip:000@1.2.3.4:5066;transport=udp>" in reg
    assert "Expires: 30" in reg  # как приложение (короткий)
    assert "Supported: replaces, outbound, gruu, path" in reg
    assert "User-Agent: Myhome/Myhome-android" in reg
    assert reg.endswith("\r\n\r\n")


def test_build_register_without_auth_has_no_authorization() -> None:
    reg = build_register(
        login="000", realm="r", host="h", port=1, call_id="c", from_tag="t",
        cseq=1, contact="<c>", branch="b", user_agent="ua",
    )
    assert "Authorization:" not in reg


def test_build_register_with_auth() -> None:
    reg = build_register(
        login="000", realm="r", host="h", port=1, call_id="c", from_tag="t",
        cseq=2, contact="<c>", branch="b", user_agent="ua",
        auth='Digest username="000", realm="r"',
    )
    assert 'Authorization: Digest username="000", realm="r"' in reg
    assert "CSeq: 2 REGISTER" in reg


def test_register_authorization_from_challenge() -> None:
    # 401 challenge (realm/nonce) → корректный Authorization c Digest MD5.
    auth = build_register_authorization(
        login="000", password="secret", realm="ac.intercom.op.ru",
        nonce="NONCE123", reg_uri="sip:ac.intercom.op.ru",
    )
    assert auth.startswith("Digest ")
    assert 'username="000"' in auth
    assert 'realm="ac.intercom.op.ru"' in auth
    assert 'nonce="NONCE123"' in auth
    assert "algorithm=MD5" in auth
