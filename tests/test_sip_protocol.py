"""Focused tests for the stock-app SIP registration profile."""
from __future__ import annotations

from custom_components.elektronny_gorod.sip.protocol import SipProtocol


class RecordingTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple | None]] = []

    def get_extra_info(self, name: str):
        return ("10.0.0.2", 5066) if name == "sockname" else None

    def sendto(self, data: bytes, addr: tuple | None = None) -> None:
        self.sent.append((data, addr))


def test_protocol_builds_official_registration_profile() -> None:
    protocol = SipProtocol(
        {"login": "000", "password": "secret", "realm": "r.example"},
        "10.0.0.2",
        "FCM",
        "Myhome/Myhome-android",
        fcm_call_id="FCM-CALL-42",
        accept_sdp=True,
        include_contact_transport=False,
    )
    transport = RecordingTransport()
    protocol.connection_made(transport)  # type: ignore[arg-type]

    register = transport.sent[0][0].decode()
    assert "Call-Id:%20FCM-CALL-42" in register
    assert "Accept: application/sdp" in register
    assert ";transport=udp" not in register
