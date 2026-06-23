"""Открыть дверь домофона по событию вызова (демо полного цикла, research).

Зеркалит api.py: POST /rest/v1/places/{placeId}/accesscontrols/{acId}/actions
с телом {"name":"accessControlOpen"} — ровно тот вызов, которым приложение
(и интеграция) открывает дверь. AllowOpen=true в FCM-пуше CALL_INCOMING.

Запуск:  python open_door.py <placeId> <accessControlId>
"""

from __future__ import annotations

import asyncio
import sys

import aiohttp

import common


async def main() -> None:
    place_id, ac_id = sys.argv[1], sys.argv[2]
    sess = common.Session.load("session.json")
    async with aiohttp.ClientSession() as s:
        api = common.Api(s, sess.user_agent, access_token=sess.access_token, operator=sess.operator_id)
        r = await api.post(
            f"/rest/v1/places/{place_id}/accesscontrols/{ac_id}/actions",
            {"name": "accessControlOpen"},
        )
        body = await r.text()
        print(f"open accesscontrol {ac_id} @ place {place_id} → HTTP {r.status} {body[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
