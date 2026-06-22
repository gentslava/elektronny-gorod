"""Проба канала STOMP-over-WebSocket `wss://myhome.proptech.ru/events`.

Зеркалит приложение: handshake с Sec-WebSocket-Protocol: v12.stomp +
Authorization: Bearer, затем STOMP CONNECT → SUBSCRIBE /user/queue.
Логирует ВСЕ входящие STOMP-кадры (особенно MESSAGE) с таймстампами.

Цель эксперимента: прилетит ли при звонке в домофон MESSAGE с типом
вызова (call/incomingCall/intercom/…), а не только availableFeatures.

Запуск:  python probe_stomp.py
Лог:     logs/stomp.log  (+ stdout)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import uuid

import aiohttp

import common

LOG_PATH = "logs/stomp.log"
WS_URL = f"wss://{common.BASE_API_URL}/events"
STOMP_PROTOCOLS = ("v12.stomp", "v11.stomp", "v10.stomp")
NUL = "\x00"


def _ts() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def log(line: str) -> None:
    os.makedirs("logs", exist_ok=True)
    msg = f"{_ts()}  {line}"
    print(msg, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def stomp_frame(command: str, headers: dict[str, str], body: str = "") -> str:
    head = "\n".join(f"{k}:{v}" for k, v in headers.items())
    return f"{command}\n{head}\n\n{body}{NUL}"


def parse_stomp(raw: str):
    """raw STOMP frame → (command, headers, body). Может содержать heartbeat '\\n'."""
    raw = raw.rstrip(NUL)
    if not raw.strip("\n"):
        return ("HEARTBEAT", {}, "")
    head, _, body = raw.partition("\n\n")
    lines = head.split("\n")
    command = lines[0]
    headers = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, _, v = ln.partition(":")
            headers[k] = v
    return (command, headers, body)


async def main() -> None:
    sess = common.Session.load("session.json")
    log(f"=== STOMP probe start (place={sess.place_id}, intercoms={len(sess.intercoms or [])}) ===")

    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(
            WS_URL,
            protocols=STOMP_PROTOCOLS,
            headers={
                "authorization": f"Bearer {sess.access_token}",
                "user-agent": sess.user_agent,
            },
            heartbeat=10.0,  # WS PING/PONG каждые 10с — как приложение
        ) as ws:
            log(f"WS connected (subprotocol={ws.protocol!r})")

            # CONNECT (heart-beat:0,0 — полагаемся на WS ping, как приложение)
            await ws.send_str(
                stomp_frame(
                    "CONNECT",
                    {
                        "accept-version": "1.2,1.1,1.0",
                        "host": common.BASE_API_URL,
                        "heart-beat": "0,0",
                    },
                )
            )

            # SUBSCRIBE /user/queue (как приложение)
            await ws.send_str(
                stomp_frame(
                    "SUBSCRIBE",
                    {
                        "id": str(uuid.uuid4()),
                        "destination": "/user/queue",
                        "content-length": "0",
                    },
                )
            )
            log("→ sent CONNECT + SUBSCRIBE /user/queue. Жду события. ЗВОНИ В ДОМОФОН.")

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    command, headers, body = parse_stomp(msg.data)
                    if command == "HEARTBEAT":
                        continue
                    log(f"[STOMP {command}] headers={headers}")
                    if body:
                        log(f"           body={body}")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log(f"WS ERROR: {ws.exception()!r}")
                    break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                    log("WS closed by server")
                    break

    log("=== STOMP probe end ===")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
