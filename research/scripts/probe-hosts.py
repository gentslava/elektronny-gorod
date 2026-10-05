#!/usr/bin/env python3
"""Живая проверка: отвечают ли хосты «Мой Дом» и «Электронного города» на пути друг друга.

    python3 research/scripts/probe-hosts.py research/api/<сессия-эмулятора>.har

Токен и заголовки берутся из указанного HAR (gitignored) — из последнего
успешного запроса к `myhome.proptech.ru` с Bearer. Файл задаётся явно:
автовыбор «самого свежего» однажды взял бы HAR с чужого устройства.
Запросы только читающие, редиректы не выполняются — иначе `urllib`
перенёс бы `Authorization` на чужой хост. В вывод идут код ответа, длина
и форма тела; цифры и токеноподобные строки маскируются, токен не
печатается (ADR-0006, «Область действия»; S-25).

Что значат ответы, записано в `research/apk/eg-3.7.2-analysis.md`.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.request

PROPTECH = "https://myhome.proptech.ru"
EG = "https://my.2090000.ru"
GUESTS = "/api/ntk-guests/v1/rpc/getGuestsByOwner"


def research_headers(path: str) -> dict[str, str]:
    with open(path) as fh:
        har = json.load(fh)
    for entry in reversed(har["log"]["entries"]):
        req = entry["request"]
        if "myhome.proptech.ru" not in req["url"] or entry["response"]["status"] != 200:
            continue
        headers = {h["name"].lower(): h["value"] for h in req["headers"]}
        if headers.get("authorization", "").startswith("Bearer "):
            keep = ("authorization", "user-agent", "operator", "accept-encoding")
            picked = {k: v for k, v in headers.items() if k in keep}
            account = re.search(r"\| (\d+) \| (?:\d+|null) \|", picked.get("user-agent", ""))
            if account:
                picked["accountid"] = account.group(1)
            return picked
    raise SystemExit("в HAR нет успешного запроса к myhome.proptech.ru с Bearer")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 — 3xx печатается как есть
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


def mask(text: str) -> str:
    return re.sub(r"\d", "#", text)


def mask_body(text: str) -> str:
    # Из содержимого ответа сначала вырезаются токеноподобные строки —
    # сервер мог бы вернуть заголовок авторизации в теле, — потом цифры.
    return mask(re.sub(r"[A-Za-z0-9._~+/=-]{16,}", "<redacted>", text))


def shape(value: object) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(sorted(value)) + "}"
    if isinstance(value, list):
        return f"list[{len(value)}]" + (" of " + shape(value[0]) if value else "")
    return type(value).__name__


def probe(url: str, headers: dict[str, str], label: str) -> None:
    request = urllib.request.Request(url, headers=headers)
    try:
        response = OPENER.open(request, timeout=20)
        status, meta, body = response.status, response.headers, response.read()
    except urllib.error.HTTPError as err:
        status, meta, body = err.code, err.headers, err.read()
    except OSError as err:
        print(f"{mask(url)} [{label}] -> {type(err).__name__}")
        return
    if meta.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)
    try:
        info = "json " + shape(json.loads(body))
    except ValueError:
        title = re.search(rb"<title>(.*?)</title>", body, re.S)
        # Маскировка до обрезки: иначе кусок токена у границы прошёл бы
        # короче порога `mask_body`.
        info = "title " + (mask_body(title.group(1).decode("utf-8", "replace"))[:60] if title else "-")
    print(f"{mask(url)} [{label}] -> {status} len={len(body)} {mask_body(info)}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    token = research_headers(sys.argv[1])
    print("HAR:", os.path.basename(sys.argv[1]))
    no_auth = {k: v for k, v in token.items() if k != "authorization"}
    garbage = {**token, "authorization": "Bearer garbage.garbage.garbage"}
    probe(f"{PROPTECH}/rest/v3/subscriber-places", token, "token")      # контроль
    probe(f"{PROPTECH}/api/zz-nonexistent/v1/x", token, "token")        # базовый 404
    probe(f"{PROPTECH}{GUESTS}", token, "token")
    probe(f"{EG}/api/zz-nonexistent/v1/x", token, "token")              # базовый 403
    probe(f"{EG}/rest/v3/subscriber-places", token, "token")
    probe(f"{EG}/rest/v3/subscriber-places", no_auth, "no-auth")
    probe(f"{EG}{GUESTS}", no_auth, "no-auth")
    probe(f"{EG}{GUESTS}", garbage, "garbage")
    probe(f"{EG}{GUESTS}", token, "token")


if __name__ == "__main__":
    main()
