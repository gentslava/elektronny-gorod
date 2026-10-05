#!/usr/bin/env python3
"""Живая проба гостевого доступа «Электронного города» (ЭГ, `my.2090000.ru`).

    python3 research/scripts/probe-eg-guests.py                 # чтение
    python3 research/scripts/probe-eg-guests.py --create-and-revoke

Проверяет гипотезу владельца: у «Мой Дом», «Умный Дом.ру» и ЭГ общий
бэкенд с разными точками входа и одной учётной записью. ЭГ авторизуется
через Keycloak (`api.novotelecom.ru`, grant password), а гостевой доступ
с выбором объектов живёт на `my.2090000.ru/api/ntk-guests/`.

Логин и пароль — из `research/scripts/auth.env` (gitignored), те же, что
владелец вводит во все три приложения. `client_secret` ЭГ — из
`research/scripts/eg.env` (gitignored, строка `EG_OAUTH_CLIENT_SECRET=`);
он есть в BuildConfig приложения и в код/вывод не попадает.

Без флага — только чтение (token, getAccount, getGuestsByOwner, findBy
devices). С `--create-and-revoke` — с согласия владельца: создать
приглашение на одну дверь и сразу удалить гостя, перечитав список. Отзыв
подтверждается чтением, а не кодом 200. Ссылка/QR не печатаются.

Токен не печатается; цифры и токеноподобные строки маскируются (S-25,
ADR-0006 «Область действия»). Редиректы не выполняются.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

OAUTH = "https://api.novotelecom.ru/auth/realms/weblk/protocol/openid-connect/token"
CLIENT_ID = "mlk:android"
USER = "https://my.2090000.ru/api/"
GUESTS = "https://my.2090000.ru/api/ntk-guests/"
EQUIP = "https://my.2090000.ru/api/ntk-video-equipment/"

OPENER = urllib.request.build_opener(
    type("NoRedirect", (urllib.request.HTTPRedirectHandler,),
         {"redirect_request": lambda *a, **k: None})()
)


def envvar(path: str, key: str) -> str:
    for line in open(path):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(f"{key} не найден в {path}")


def mask(text: str) -> str:
    return re.sub(r"\d", "#", text)


def mask_body(text: str) -> str:
    return mask(re.sub(r"[A-Za-z0-9._~+/=-]{16,}", "<redacted>", text))


def shape(value: object) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(sorted(value)) + "}"
    if isinstance(value, list):
        return f"list[{len(value)}]" + (" of " + shape(value[0]) if value else "")
    return type(value).__name__


def token() -> str:
    secret = envvar("research/scripts/eg.env", "EG_OAUTH_CLIENT_SECRET")
    form = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": CLIENT_ID,
        "client_secret": secret,
        "username": envvar("research/scripts/auth.env", "AUTH_LOGIN"),
        "password": envvar("research/scripts/auth.env", "AUTH_PASSWORD"),
    }).encode()
    req = urllib.request.Request(OAUTH, data=form,
                                 headers={"content-type": "application/x-www-form-urlencoded"})
    try:
        body = OPENER.open(req, timeout=20).read()
    except urllib.error.HTTPError as err:
        raise SystemExit(f"OAuth {err.code}: {mask_body(err.read()[:200].decode('utf-8', 'replace'))}")
    tok = json.loads(body).get("access_token")
    if not tok:
        raise SystemExit("OAuth ответил без access_token")
    print("OAuth: получен access_token")   # само значение не печатаем
    return tok


def call(method: str, url: str, tok: str, headers: dict[str, str] | None = None,
         body: object | None = None) -> tuple[int, object]:
    sent = {"authorization": f"Bearer {tok}", "accept-encoding": "gzip", **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        sent["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=sent, method=method)
    try:
        resp = OPENER.open(req, timeout=20)
        status, meta, raw = resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as err:
        status, meta, raw = err.code, err.headers, err.read()
    if meta.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    try:
        payload: object = json.loads(raw)
        info = "json " + shape(payload)
    except ValueError:
        payload = None
        info = "text " + mask_body(raw[:80].decode("utf-8", "replace"))
    path = urllib.parse.urlparse(url).path
    print(f"{method} {mask(path)} -> {status} len={len(raw)} {mask_body(info)}")
    return status, payload


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--create-and-revoke"
    if len(sys.argv) > 1 and not write:
        raise SystemExit(__doc__)
    tok = token()

    status, acc = call("GET", USER + "user/v2/accounts/getAccount", tok)
    contract = acc.get("contractId") if isinstance(acc, dict) else None
    if not isinstance(contract, int):
        raise SystemExit("getAccount не отдал числовой contractId")
    print(f"   account fields: {shape(acc)}; contractId: numeric")

    hdr = {"accountid": str(contract)}
    status, guests = call("GET", GUESTS + "v1/rpc/getGuestsByOwner", tok, hdr)
    if status == 200 and isinstance(guests, list):
        print(f"   guests: {len(guests)} item(s)")

    status, devices = call("GET", EQUIP + "rpc/devices/v1/findBy?category=ACCESS&isMain=false", tok)
    doors = devices if isinstance(devices, list) else []
    if status == 200:
        keys = sorted({k for d in doors if isinstance(d, dict) for k in d})
        print(f"   access devices: {len(doors)} item(s), fields {keys}")

    if not write:
        return
    if not doors:
        raise SystemExit("нет устройств категории ACCESS — создавать не из чего")
    door = doors[0].get("id")
    print(f"-- create invite for 1 access device")
    status, created = call("POST", GUESTS + "v1/rpc/createInvite", tok, hdr,
                           {"accountId": contract, "devices": [door]})
    if status not in (200, 201) or not isinstance(created, dict):
        print("-- create refused; nothing to revoke")
        return
    print(f"   invite fields: {shape(created)}")
    _, after = call("GET", GUESTS + "v1/rpc/getGuestsByOwner", tok, hdr)
    new = [g for g in after if isinstance(g, dict)] if isinstance(after, list) else []
    guest_id = new[-1].get("id") if new else None
    if guest_id is None:
        print("-- created invite not found in list; leaving as is")
        return
    print(f"   guests after create: {len(new)}")
    call("PATCH", GUESTS + f"v1/rpc/disableGuest/{guest_id}", tok, hdr)
    _, final = call("GET", GUESTS + "v1/rpc/getGuestsByOwner", tok, hdr)
    left = [g for g in final if isinstance(g, dict) and g.get("id") == guest_id] if isinstance(final, list) else []
    print(f"   guest still listed after revoke: {bool(left)}")


if __name__ == "__main__":
    main()
