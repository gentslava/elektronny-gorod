"""SIP REGISTER build + Digest auth для модели register-on-ring (ADR-0012).

Мы НЕ держим долгую регистрацию: REGISTER шлётся в момент FCM-ring (а не «ответить»)
и триггерит forked `INVITE` от Kazoo, который держим в `100 Trying` до ответа
пользователя (см. call-answer-model.md, ADR-0012). Зеркалируем формат приложения:
FCM Call-ID в push-params Contact, Expires=30, `Accept: application/sdp`,
`Supported: outbound/gruu/path`.
"""
from __future__ import annotations

import uuid

from .digest import build_authorization, digest_response

# push-params приложения оператора (call-answer-model.md §4) — зеркалируем формат.
PUSH_APP_ID = "com.novotelecom.domophone"
_CRLF = "\r\n"
REGISTER_EXPIRES = 30  # короткий, как приложение (свежесть регистрации)


def build_contact(
    login: str,
    host: str,
    port: int,
    fcm_token: str,
    *,
    fcm_call_id: str | None = None,
    include_transport: bool = True,
) -> str:
    """Contact с проприетарными push-params приложения (триггерит push-aware флоу)."""
    call_param = f";Call-Id:%20{fcm_call_id}" if fcm_call_id else ""
    transport_param = ";transport=udp" if include_transport else ""
    return (
        f"<sip:{login}@{host}:{port}{transport_param}"
        f";app-id={PUSH_APP_ID};pn-type=google{call_param};pn-tok={fcm_token}>"
    )


def build_register(
    login: str,
    realm: str,
    host: str,
    port: int,
    call_id: str,
    from_tag: str,
    cseq: int,
    contact: str,
    branch: str,
    user_agent: str,
    expires: int = REGISTER_EXPIRES,
    auth: str | None = None,
    *,
    accept_sdp: bool = False,
) -> str:
    """Сформировать REGISTER-запрос (с опц. Authorization после 401-challenge)."""
    lines = [
        f"REGISTER sip:{realm} SIP/2.0",
        f"Via: SIP/2.0/UDP {host}:{port};branch={branch};rport",
        "Max-Forwards: 70",
        f"From: <sip:{login}@{realm}>;tag={from_tag}",
        f"To: <sip:{login}@{realm}>",
        f"Call-ID: {call_id}",
        f"CSeq: {cseq} REGISTER",
        f"Contact: {contact}",
        f"Expires: {expires}",
        "Supported: replaces, outbound, gruu, path",
    ]
    if accept_sdp:
        lines.append("Accept: application/sdp")
    lines.append(f"User-Agent: {user_agent}")
    if auth:
        lines.append(f"Authorization: {auth}")
    lines += ["Content-Length: 0", "", ""]
    return _CRLF.join(lines)


def build_register_authorization(
    login: str,
    password: str,
    realm: str,
    nonce: str,
    reg_uri: str,
    qop: str | None = None,
) -> str:
    """Authorization для REGISTER из 401-challenge (Digest MD5, qop=auth или non-qop).

    Регистратор оператора (FreeSWITCH/Kamailio) обычно шлёт challenge с
    `qop="auth"` — тогда обязательны `cnonce`/`nc`, иначе сервер отвергает
    REGISTER (нет 200 OK → нет форка INVITE на нашу регистрацию). Без qop —
    legacy non-qop. cnonce рандомный, nc=00000001 (одна попытка на nonce).
    """
    cnonce = nc = None
    if qop:
        cnonce = uuid.uuid4().hex[:16]
        nc = "00000001"
    resp = digest_response(login, password, realm, nonce, "REGISTER", reg_uri, qop, cnonce, nc)
    return build_authorization(login, realm, nonce, reg_uri, resp, qop, cnonce, nc)
