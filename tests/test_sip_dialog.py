"""Unit-тесты dialog-state + build 200 OK / BYE (sip/dialog.py).

Критично (FINDINGS + спайк): 200 OK эхо-ит ВСЕ Via/Record-Route дословно + To-tag,
иначе Kazoo SBC игнорит ответ (нет ACK). BYE адресован remote Contact с Route из
Record-Route.
"""
from __future__ import annotations

from custom_components.elektronny_gorod.sip.dialog import (
    build_200_ok,
    build_bye,
    extract_dialog,
)
from custom_components.elektronny_gorod.sip.message import parse_sip

_INVITE = (
    "INVITE sip:000@1.2.3.4 SIP/2.0\r\n"
    "v: SIP/2.0/UDP 1.1.1.1;branch=z1\r\n"
    "Via: SIP/2.0/UDP 2.2.2.2;branch=z2\r\n"
    "Record-Route: <sip:1.1.1.1;lr>\r\n"
    "Record-Route: <sip:2.2.2.2;lr>\r\n"
    "f: <sip:panel@realm>;tag=abc\r\n"
    "t: <sip:000@realm>\r\n"
    "i: call-xyz\r\n"
    "m: <sip:panel@2.2.2.2:5060>\r\n"
    "CSeq: 1 INVITE\r\n"
    "\r\n"
    "v=0\r\n"
)

_SDP = "v=0\r\nm=audio 40016 RTP/AVP 8\r\n"


def test_build_200_ok_echoes_all_via_and_record_route() -> None:
    ok = build_200_ok(parse_sip(_INVITE), _SDP, local_tag="mytag", contact="<sip:ha@local>", ua="EG")
    # оба Via дословно (включая компактный v:)
    assert "v: SIP/2.0/UDP 1.1.1.1;branch=z1" in ok
    assert "Via: SIP/2.0/UDP 2.2.2.2;branch=z2" in ok
    # оба Record-Route дословно
    assert "Record-Route: <sip:1.1.1.1;lr>" in ok
    assert "Record-Route: <sip:2.2.2.2;lr>" in ok
    assert ok.startswith("SIP/2.0 200 OK\r\n")


def test_build_200_ok_adds_to_tag_and_sdp() -> None:
    ok = build_200_ok(parse_sip(_INVITE), _SDP, local_tag="mytag", contact="<sip:ha@local>", ua="EG")
    assert "t: <sip:000@realm>;tag=mytag" in ok  # To получил наш tag
    assert "Content-Type: application/sdp" in ok
    assert f"Content-Length: {len(_SDP.encode())}" in ok
    assert ok.endswith(_SDP)


def test_extract_dialog_fields() -> None:
    d = extract_dialog(parse_sip(_INVITE), local_tag="mytag")
    assert d.call_id == "call-xyz"
    assert d.remote == "<sip:panel@realm>;tag=abc"  # From
    assert d.local == "<sip:000@realm>;tag=mytag"  # To + наш tag
    assert d.target == "sip:panel@2.2.2.2:5060"  # Contact URI без <>
    assert d.route == ["<sip:1.1.1.1;lr>", "<sip:2.2.2.2;lr>"]


def test_build_bye_targets_remote_contact_with_route() -> None:
    d = extract_dialog(parse_sip(_INVITE), local_tag="mytag")
    bye = build_bye(d, local_ip="9.9.9.9", local_port=5066, ua="EG", cseq=2, branch="zbye")
    assert bye.startswith("BYE sip:panel@2.2.2.2:5060 SIP/2.0\r\n")
    assert "Route: <sip:1.1.1.1;lr>" in bye
    assert "Route: <sip:2.2.2.2;lr>" in bye
    assert "From: <sip:000@realm>;tag=mytag" in bye  # наша сторона
    assert "To: <sip:panel@realm>;tag=abc" in bye  # удалённая
    assert "Call-ID: call-xyz" in bye
    assert "CSeq: 2 BYE" in bye
