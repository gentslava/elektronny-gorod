#!/usr/bin/env python3
"""chlz-to-har — конвертирует Charles 5+ .chlz session в HAR 1.2.

`.chlz` — это ZIP-архив с JSON-файлами вида:
- `N-meta.json` — метаданные запроса/ответа
- `N-req.json` / `N-req.dat` / `N-req.txt` — тело запроса (опционально)
- `N-res.json` / `N-res.dat` / `N-res.txt` — тело ответа (опционально)

Использование:
    chlz-to-har.py <input.chlz> [output.har] [--host-filter HOST_SUBSTR]
    chlz-to-har.py session.chlz                       # → session.har (все хосты)
    chlz-to-har.py session.chlz --host-filter proptech.ru
    chlz-to-har.py session.chlz out.har --host-filter proptech.ru

--host-filter оставляет только entries, host которых содержит указанный substring.
Полезно, чтобы отфильтровать «шум» (taobao, google, FCM) и оставить только
трафик нашего оператора.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import zipfile
from pathlib import Path


def _decode_body(body: bytes | None) -> dict | None:
    """Body → HAR-friendly dict (text или base64-encoded)."""
    if body is None or len(body) == 0:
        return None
    try:
        text = body.decode("utf-8")
        return {"text": text, "size": len(body)}
    except UnicodeDecodeError:
        return {
            "text": base64.b64encode(body).decode("ascii"),
            "encoding": "base64",
            "size": len(body),
        }


def _parse_headers(raw) -> list[dict]:
    """Charles headers structure: meta.request.header.headers (list of {name, value}).

    Для HTTP/2 первые headers — pseudo-headers (`:method`, `:path`, `:authority`, `:scheme`).
    Они не должны попадать в HAR (это часть request-line). Фильтруем.
    """
    if not raw:
        return []
    if isinstance(raw, dict):
        # meta.request.header — это объект с полем headers
        if "headers" in raw:
            raw = raw["headers"]
    result = []
    if isinstance(raw, list):
        for h in raw:
            if isinstance(h, dict):
                name = h.get("name") or h.get("key") or ""
                value = h.get("value", "")
                if not name:
                    continue
                # Skip HTTP/2 pseudo-headers
                if name.startswith(":"):
                    continue
                result.append({"name": str(name), "value": str(value)})
    return result


def _ms_to_sec(value) -> float:
    """Charles durations — в микросекундах? миллисекундах? Эмпирически — мкс. HAR хочет ms."""
    if value is None:
        return 0
    try:
        # Charles даёт в микросекундах (видно из примеров: total ~989659 для CONNECTING-only).
        # HAR.timings — миллисекунды.
        return float(value) / 1000.0
    except (TypeError, ValueError):
        return 0


def to_har_entry(meta: dict, req_body: bytes | None, res_body: bytes | None) -> dict:
    times = meta.get("times") or {}
    durations = meta.get("durations") or {}

    scheme = meta.get("scheme") or "http"
    host = meta.get("host") or ""
    actual_port = meta.get("actualPort")
    path = meta.get("path") or "/"
    query = meta.get("query") or ""

    # Build URL. Port include if non-standard.
    if actual_port and not (
        (scheme == "http" and actual_port == 80)
        or (scheme == "https" and actual_port == 443)
    ):
        url = f"{scheme}://{host}:{actual_port}{path}"
    else:
        url = f"{scheme}://{host}{path}"
    if query:
        url += "?" + query

    method = meta.get("method") or "GET"
    http_version = meta.get("protocolVersion") or "HTTP/1.1"

    req = meta.get("request") or {}
    res = meta.get("response") or {}

    req_headers = _parse_headers(req.get("header"))
    res_headers = _parse_headers(res.get("header"))

    req_sizes = req.get("sizes") or {}
    res_sizes = res.get("sizes") or {}

    request: dict = {
        "method": method,
        "url": url,
        "httpVersion": http_version,
        "headers": req_headers,
        "queryString": [],
        "headersSize": req_sizes.get("headers", -1) or -1,
        "bodySize": req_sizes.get("body", -1) or -1,
    }
    rb = _decode_body(req_body)
    if rb:
        request["postData"] = {
            "mimeType": req.get("mimeType") or "application/octet-stream",
            "text": rb["text"],
        }
        if "encoding" in rb:
            request["postData"]["encoding"] = rb["encoding"]

    # HTTP status в response.status. Может отсутствовать (status=NO_RESPONSE / FAILED).
    raw_status = res.get("status")
    try:
        http_status = int(raw_status) if raw_status is not None else 0
    except (TypeError, ValueError):
        http_status = 0

    response: dict = {
        "status": http_status,
        "statusText": res.get("statusText") or "",
        "httpVersion": http_version,
        "headers": res_headers,
        "cookies": [],
        "content": {
            "size": res_sizes.get("body", -1) or -1,
            "mimeType": res.get("mimeType") or "",
        },
        "redirectURL": "",
        "headersSize": res_sizes.get("headers", -1) or -1,
        "bodySize": res_sizes.get("body", -1) or -1,
    }
    if res.get("contentEncoding"):
        response["content"]["compression"] = 0  # body уже decompressed Charles-ом

    sb = _decode_body(res_body)
    if sb:
        response["content"]["text"] = sb["text"]
        response["content"]["size"] = sb["size"]
        if "encoding" in sb:
            response["content"]["encoding"] = sb["encoding"]

    return {
        "startedDateTime": times.get("start") or "1970-01-01T00:00:00Z",
        "time": _ms_to_sec(durations.get("total")),
        "request": request,
        "response": response,
        "cache": {},
        "timings": {
            "send": _ms_to_sec(durations.get("request")),
            "wait": _ms_to_sec(durations.get("latency")),
            "receive": _ms_to_sec(durations.get("response")),
        },
        "_charles": {
            # Сохраняем оригинальные status / connection metadata для отладки.
            "status": meta.get("status"),
            "host": host,
            "clientAddress": meta.get("clientAddress"),
            "connection": meta.get("connection"),
            "tags": meta.get("tags"),
        },
    }


def convert(input_path: Path, output_path: Path, host_filter: str | None) -> tuple[int, int]:
    with zipfile.ZipFile(input_path, "r") as z:
        names = set(z.namelist())
        # Группируем по индексу префикса (0-, 1-, 2-, ...)
        indices = sorted(
            {n.split("-", 1)[0] for n in names if "-" in n and n.split("-", 1)[0].isdigit()},
            key=int,
        )

        entries: list[dict] = []
        skipped = 0
        for idx in indices:
            meta_name = f"{idx}-meta.json"
            if meta_name not in names:
                continue
            try:
                meta = json.loads(z.read(meta_name).decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"⚠️  skip {idx} (meta parse): {e}", file=sys.stderr)
                skipped += 1
                continue

            host = meta.get("host") or ""
            if host_filter and host_filter not in host:
                skipped += 1
                continue

            req_body = None
            res_body = None
            for suffix in (".json", ".dat", ".txt"):
                name = f"{idx}-req{suffix}"
                if name in names:
                    req_body = z.read(name)
                    break
            for suffix in (".json", ".dat", ".txt"):
                name = f"{idx}-res{suffix}"
                if name in names:
                    res_body = z.read(name)
                    break

            try:
                entries.append(to_har_entry(meta, req_body, res_body))
            except Exception as e:  # noqa: BLE001
                print(f"⚠️  skip {idx} (entry build): {e}", file=sys.stderr)
                skipped += 1

        har = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "elektronny-gorod chlz→har",
                    "version": "1.0",
                    # Не указываем имя исходного .chlz — не хочется иметь идентифицирующие
                    # метаданные на случай, если HAR куда-то попадёт.
                },
                "entries": entries,
            }
        }
        output_path.write_text(json.dumps(har, indent=2, ensure_ascii=False))
        return len(entries), skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert Charles .chlz session to HAR 1.2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", type=Path, help="input .chlz file")
    parser.add_argument("output", nargs="?", type=Path, help="output .har (default: input with .har)")
    parser.add_argument(
        "--host-filter",
        default=None,
        help="оставить только entries, host которых содержит substring (напр., proptech.ru)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"❌ {args.input} не найден", file=sys.stderr)
        return 1

    output = args.output or args.input.with_suffix(".har")
    n, skipped = convert(args.input, output, args.host_filter)
    print(f"✓ {output} — {n} entries, {skipped} skipped (filter='{args.host_filter or 'none'}')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
