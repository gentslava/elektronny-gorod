"""Dialog-state + построение 200 OK / BYE. Из probe_sip_media.py `_answer`/`send_bye`.

🔴 Критично (FINDINGS §SIP-flow + спайк): валидный 200 OK обязан эхо-ить ВСЕ
Via/Record-Route дословно + From/To/Call-ID/CSeq, добавив To-tag. Иначе Kazoo SBC
игнорит ответ -> нет ACK -> «нет ответа». BYE (in-dialog) адресуется remote Contact,
Route берётся из Record-Route, From=наша сторона, To=удалённая.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .message import SipMessage

# Заголовки, которые 200 OK эхо-ит из INVITE дословно (порядок прихода сохраняется).
_ECHO_HEADERS = ("via", "record-route", "from", "to", "call-id", "cseq")
_CRLF = "\r\n"


@dataclass
class DialogState:
    """Состояние SIP-диалога для отправки in-dialog BYE."""

    call_id: str
    local: str  # наша сторона (To + наш tag) -> From в BYE
    remote: str  # удалённая сторона (From) -> To в BYE
    target: str  # remote Contact URI -> Request-URI BYE
    route: list[str]  # Record-Route values -> Route в BYE


def _with_to_tag(to_value: str, local_tag: str) -> str:
    """Добавить наш tag к To, если его ещё нет."""
    if ";tag=" in to_value.lower():
        return to_value
    return f"{to_value};tag={local_tag}"


def build_200_ok(
    invite: SipMessage,
    sdp_body: str,
    local_tag: str,
    contact: str,
    ua: str,
) -> str:
    """200 OK с SDP-answer: эхо всех Via/Record-Route/From/To(+tag)/Call-ID/CSeq."""
    lines = ["SIP/2.0 200 OK"]
    for hn, raw in invite.header_lines:
        if hn not in _ECHO_HEADERS:
            continue
        if hn == "to" and ";tag=" not in raw.lower():
            raw = f"{raw};tag={local_tag}"
        lines.append(raw)
    lines.append(f"Contact: {contact}")
    lines.append(f"User-Agent: {ua}")
    lines.append("Allow: INVITE, ACK, BYE, CANCEL, OPTIONS")
    if sdp_body:
        lines.append("Content-Type: application/sdp")
    lines.append(f"Content-Length: {len(sdp_body.encode())}")
    lines.append("")
    lines.append(sdp_body)
    return _CRLF.join(lines)


def extract_dialog(invite: SipMessage, local_tag: str) -> DialogState:
    """Снять состояние диалога из INVITE для последующего BYE."""
    contact = invite.first("contact") or ""
    m = re.search(r"<([^>]+)>", contact)
    target = m.group(1) if m else contact
    return DialogState(
        call_id=invite.first("call-id") or "",
        local=_with_to_tag(invite.first("to") or "", local_tag),
        remote=invite.first("from") or "",
        target=target,
        route=invite.values("record-route"),
    )


def build_bye(
    dialog: DialogState,
    local_ip: str,
    local_port: int,
    ua: str,
    cseq: int,
    branch: str,
) -> str:
    """In-dialog BYE: Request-URI=remote Contact, Route из Record-Route."""
    lines = [
        f"BYE {dialog.target} SIP/2.0",
        f"Via: SIP/2.0/UDP {local_ip}:{local_port};branch={branch};rport",
        *[f"Route: {rr}" for rr in dialog.route],
        "Max-Forwards: 70",
        f"From: {dialog.local}",
        f"To: {dialog.remote}",
        f"Call-ID: {dialog.call_id}",
        f"CSeq: {cseq} BYE",
        f"User-Agent: {ua}",
        "Content-Length: 0",
        "",
        "",
    ]
    return _CRLF.join(lines)
