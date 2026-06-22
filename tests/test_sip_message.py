"""Unit-тесты парсинга SIP-сообщения (sip/message.py).

Ключевой урок спайка: voip-utils теряет множественные Via/Record-Route (dict
headers). Наш парсер сохраняет их списком + дословные строки для эхо в 200 OK/BYE.
"""
from __future__ import annotations

from custom_components.elektronny_gorod.sip.message import parse_sip

# INVITE с компактными заголовками (как шлёт Kazoo) + 2x Via + 2x Record-Route.
_INVITE = (
    "INVITE sip:000@1.2.3.4 SIP/2.0\r\n"
    "v: SIP/2.0/UDP 1.1.1.1;branch=z1\r\n"
    "Via: SIP/2.0/UDP 2.2.2.2;branch=z2\r\n"
    "Record-Route: <sip:1.1.1.1;lr>\r\n"
    "Record-Route: <sip:2.2.2.2;lr>\r\n"
    "f: <sip:panel@realm>;tag=abc\r\n"
    "t: <sip:000@realm>\r\n"
    "i: call-xyz\r\n"
    "m: <sip:panel@2.2.2.2>\r\n"
    "CSeq: 1 INVITE\r\n"
    "\r\n"
    "v=0\r\no=- 1 1 IN IP4 10.0.0.1\r\n"
)


def test_parse_preserves_multiple_via_and_record_route() -> None:
    msg = parse_sip(_INVITE)
    # оба Via сохранены (включая компактный v:), дословно — для эхо.
    assert msg.raw_lines("via") == [
        "v: SIP/2.0/UDP 1.1.1.1;branch=z1",
        "Via: SIP/2.0/UDP 2.2.2.2;branch=z2",
    ]
    assert len(msg.raw_lines("record-route")) == 2
    assert msg.raw_lines("record-route")[1] == "Record-Route: <sip:2.2.2.2;lr>"


def test_compact_header_names_normalized() -> None:
    msg = parse_sip(_INVITE)
    assert msg.first("from") == "<sip:panel@realm>;tag=abc"  # f: -> from
    assert msg.first("to") == "<sip:000@realm>"  # t: -> to
    assert msg.first("call-id") == "call-xyz"  # i: -> call-id
    assert msg.first("contact") == "<sip:panel@2.2.2.2>"  # m: -> contact


def test_start_line_and_body() -> None:
    msg = parse_sip(_INVITE)
    assert msg.start_line == "INVITE sip:000@1.2.3.4 SIP/2.0"
    assert msg.body.startswith("v=0")


def test_missing_header_returns_empty() -> None:
    msg = parse_sip(_INVITE)
    assert msg.first("nonexistent") is None
    assert msg.raw_lines("nonexistent") == []
