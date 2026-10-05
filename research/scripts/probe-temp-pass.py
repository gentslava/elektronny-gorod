#!/usr/bin/env python3
"""Живая проба `mh-temp-pass` (временный доступ, A-118) исследовательским аккаунтом.

    python3 research/scripts/probe-temp-pass.py research/api/<сессия-эмулятора>.har

    python3 research/scripts/probe-temp-pass.py <har> --create-and-revoke

Токен, заголовки и `placeId` берутся из указанного HAR (gitignored) —
из последнего успешного запроса к `myhome.proptech.ru` с Bearer; `placeId`
— из User-Agent того же запроса. Редиректы не выполняются.

Без флага — только чтение (GET). С `--create-and-revoke` — пишущая
проба с согласия владельца аккаунта: создаётся пропуск на минимальный
срок к одной двери, читается список, пропуск сразу удаляется, и список
перечитывается — отзыв подтверждается чтением, а не одним кодом 200.
Ссылка и текст сообщения не печатаются: только их наличие и длина.

Что печатается — только то, что не персональные данные (S-25):
* код ответа, длина, форма тела;
* значения `time-to-life` — это допустимые сроки, константы сервера;
* множество значений `status` у выданных пропусков;
* у объектов доступа — число и имена полей, но не названия дверей.
Цифры в URL и прочем маскируются, токен не печатается (ADR-0006,
«Область действия»).
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
import urllib.error
import urllib.request

HOST = "https://myhome.proptech.ru"
BASE = "/api/mh-temp-pass/mobile/v1/rest/v1/temp-passes"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # 3xx печатается как есть
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


def research_headers(path: str) -> tuple[dict[str, str], str]:
    with open(path) as fh:
        har = json.load(fh)
    for entry in reversed(har["log"]["entries"]):
        req = entry["request"]
        if "myhome.proptech.ru" not in req["url"] or entry["response"]["status"] != 200:
            continue
        headers = {h["name"].lower(): h["value"] for h in req["headers"]}
        if not headers.get("authorization", "").startswith("Bearer "):
            continue
        keep = ("authorization", "user-agent", "operator", "accept-encoding")
        picked = {k: v for k, v in headers.items() if k in keep}
        # UA: «… | account_id | operator_id | uuid | place_id»
        place = picked.get("user-agent", "").rsplit("|", 1)[-1].strip()
        if place.isdigit():
            return picked, place
    raise SystemExit("в HAR нет успешного запроса с Bearer и placeId в User-Agent")


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


def get(path: str, headers: dict[str, str]) -> tuple[int, object]:
    return call("GET", path, headers)


def call(method: str, path: str, headers: dict[str, str],
         body: object | None = None) -> tuple[int, object]:
    data = None
    sent = dict(headers)
    if body is not None:
        data = json.dumps(body).encode()
        sent["content-type"] = "application/json; charset=UTF-8"
    request = urllib.request.Request(HOST + path, data=data, headers=sent, method=method)
    try:
        response = OPENER.open(request, timeout=20)
        status, meta, body = response.status, response.headers, response.read()
    except urllib.error.HTTPError as err:
        status, meta, body = err.code, err.headers, err.read()
    if meta.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)
    raw = body
    try:
        payload: object = json.loads(body)
        info = "json " + shape(payload)
    except ValueError:
        payload = None
        title = re.search(rb"<title>(.*?)</title>", body, re.S)
        info = "title " + (mask_body(title.group(1).decode("utf-8", "replace"))[:60] if title else "-")
    print(f"{method} {mask(path)} -> {status} len={len(raw)} {mask_body(info)}")
    if status != 200 and isinstance(payload, dict):
        # Код и текст отказа — то, ради чего проба: как сервер отвечает
        # адресу без услуги. Значения маскируются, как и всё прочее.
        print("   refusal:", {k: mask_body(str(v))[:80] for k, v in payload.items()})
    return status, payload


def unwrap(payload: object) -> object:
    return payload.get("data", payload) if isinstance(payload, dict) else payload


def describe_pass(item: object) -> None:
    if not isinstance(item, dict):
        return
    link = str(item.get("sharedLinkMessage") or "")
    print(f"   pass fields {sorted(item)}; status={item.get('status')!r}; "
          f"expiredAt={mask(str(item.get('expiredAt')))}; "
          f"sharedLinkMessage: {len(link)} chars, has url: {'http' in link}; "
          f"availableAccessControl: {shape(item.get('availableAccessControl'))}")


def create_and_revoke(headers: dict[str, str], place: str) -> None:
    _, payload = get(f"{BASE}/time-to-life?placeId={place}", headers)
    ttls = unwrap(payload)
    _, payload = get(f"{BASE}/access-controls?placeId={place}", headers)
    controls = unwrap(payload)
    if not (isinstance(ttls, list) and ttls and isinstance(controls, list) and controls):
        raise SystemExit("нет сроков или объектов доступа — создавать не из чего")
    ttl = min(ttls)
    door = controls[0]["id"]
    print(f"-- create: ttl={ttl}s, 1 access control")
    status, payload = call("POST", BASE, headers,
                           {"placeId": int(place), "ttl": ttl, "accessControlIds": [door]})
    created = unwrap(payload)
    describe_pass(created)
    if status not in (200, 201) or not isinstance(created, dict) or "id" not in created:
        print("-- create refused or unexpected; nothing to revoke")
        return
    pass_id = created["id"]
    try:
        _, payload = get(f"{BASE}?placeId={place}", headers)
        listed = unwrap(payload)
        if isinstance(listed, list):
            print(f"   list after create: {len(listed)} item(s)")
            for item in listed:
                describe_pass(item)
    finally:
        print("-- revoke")
        for attempt in (1, 2):
            status, _ = call("DELETE", f"{BASE}/{pass_id}", headers, {"placeId": int(place)})
            if status in (200, 204):
                break
        _, payload = get(f"{BASE}?placeId={place}", headers)
        left = unwrap(payload)
        still = [p for p in left if isinstance(p, dict) and p.get("id") == pass_id] if isinstance(left, list) else None
        print(f"   list after revoke: {len(left) if isinstance(left, list) else '?'} item(s); "
              f"created pass still listed: {bool(still)}")
        describe_pass(still[0] if still else None)


def main() -> None:
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != "--create-and-revoke"):
        raise SystemExit(__doc__)
    headers, place = research_headers(sys.argv[1])
    print("HAR:", os.path.basename(sys.argv[1]))
    if len(sys.argv) == 3:
        create_and_revoke(headers, place)
        return

    status, payload = get(f"{BASE}/time-to-life?placeId={place}", headers)
    ttl = unwrap(payload)
    if status == 200 and isinstance(ttl, list) and all(isinstance(x, (int, float)) for x in ttl):
        print("   time-to-life values:", ttl)   # константы сервера, не PII

    status, payload = get(f"{BASE}/access-controls?placeId={place}", headers)
    controls = unwrap(payload)
    if status == 200 and isinstance(controls, list):
        keys = sorted({k for c in controls if isinstance(c, dict) for k in c})
        print(f"   access-controls: {len(controls)} item(s), fields {keys}")

    status, payload = get(f"{BASE}?placeId={place}", headers)
    passes = unwrap(payload)
    if status == 200 and isinstance(passes, list):
        statuses = sorted({str(p.get("status")) for p in passes if isinstance(p, dict)})
        print(f"   temp-passes: {len(passes)} item(s), status values {statuses}")


if __name__ == "__main__":
    main()
