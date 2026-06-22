"""Общий слой для проб входящего вызова домофона (research, throwaway).

Standalone-зеркало HTTP/UA/login-флоу интеграции `elektronny_gorod`
(см. custom_components/elektronny_gorod/{api,http,user_agent,const}.py).
БЕЗ зависимости от Home Assistant — чистый aiohttp/asyncio, чтобы пробу
можно было гонять локально и на home.server в обычном venv/контейнере.

Назначение: эксперимент — определить, по какому каналу
(STOMP-WS / SIP / FCM) приходит событие «звонят в домофон».

Секреты (токены, SIP-пароли) НЕ логируем — правило no-secret-logs.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from random import choice
from typing import Any

import aiohttp

BASE_API_URL = "myhome.proptech.ru"
APP_VERSION = {"name": "9.7.0", "code": "90700000"}
ANDROID_OS_VER = "16"
ANDROID_DEVICES = [
    {"manufacturer": "Google", "model": "Pixel 8"},
    {"manufacturer": "Google", "model": "Pixel 9"},
    {"manufacturer": "Google", "model": "Pixel 7a"},
]


def build_user_agent(
    account_id: str = "",
    operator_id: str = "null",
    place_id: str = "null",
    device_uuid: str | None = None,
) -> str:
    """User-Agent байт-в-байт как user_agent.py интеграции."""
    dev = choice(ANDROID_DEVICES)
    u = device_uuid or str(uuid.uuid4())
    return (
        f"{dev['manufacturer']} {dev['model']} | Android {ANDROID_OS_VER} | ntk | "
        f"{APP_VERSION['name']} ({APP_VERSION['code']}) | "
        f"{account_id} | {operator_id} | {u} | {place_id}"
    )


@dataclass
class Session:
    """То, что нужно пробам после логина. Сохраняется в session.json."""

    access_token: str
    refresh_token: str | None
    operator_id: str
    account_id: str
    subscriber_id: str
    phone: str
    user_agent: str
    install_id: str           # стабильный installationId аккаунта (UA uuid)
    place_id: str = ""
    # список домофонов с поддержкой звонка на мобильное:
    # [{"placeId","accessControlId","name","realm?"}...]
    intercoms: list[dict[str, Any]] | None = None

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path: str) -> "Session":
        with open(path, encoding="utf-8") as f:
            return Session(**json.load(f))


class Api:
    """Минимальный HTTP-клиент, зеркалящий http.py интеграции."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        user_agent: str,
        access_token: str | None = None,
        operator: str | None = None,
    ) -> None:
        self._s = session
        self._base = f"https://{BASE_API_URL}"
        self._ua = user_agent
        self.access_token = access_token
        self._operator = operator

    def _headers(self, post: bool) -> dict[str, str]:
        h = {"accept-encoding": "gzip", "user-agent": self._ua}
        if self._operator is not None:
            h["operator"] = self._operator
        if post:
            h["content-type"] = "application/json; charset=UTF-8"
        # Bearer — только на post-auth путях (как в http.py).
        if self.access_token and not str.startswith(self._last_path or "", "/auth/"):
            h["authorization"] = f"Bearer {self.access_token}"
        return h

    _last_path: str | None = None

    async def get(self, path: str) -> aiohttp.ClientResponse:
        self._last_path = path
        return await self._s.get(self._base + path, headers=self._headers(False))

    async def post(self, path: str, payload: Any) -> aiohttp.ClientResponse:
        self._last_path = path
        return await self._s.post(
            self._base + path,
            data=json.dumps(payload),
            headers=self._headers(True),
        )


# ----------------------- login (SMS-флоу) ----------------------- #


async def login_sms_step1_contracts(api: Api, phone: str) -> list[dict[str, Any]]:
    """GET /auth/v2/login/{phone} → contracts (300) | password(200) | unreg(204)."""
    r = await api.get(f"/auth/v2/login/{phone}")
    if r.status == 300:
        return await r.json()
    if r.status == 200:
        raise RuntimeError("account requires PASSWORD login (200), SMS-флоу не подходит")
    if r.status == 204:
        raise RuntimeError("phone unregistered (204)")
    raise RuntimeError(f"unexpected login status {r.status}")


async def login_sms_step2_request_code(api: Api, phone: str, contract: dict[str, Any]) -> None:
    """POST /auth/v2/confirmation/{phone} → отправка SMS."""
    payload = {
        "accountId": contract["accountId"],
        "address": contract["address"],
        "operatorId": contract["operatorId"],
        "subscriberId": str(contract["subscriberId"]),
        "placeId": contract["placeId"],
    }
    r = await api.post(f"/auth/v2/confirmation/{phone}", payload)
    if r.status == 429:
        raise RuntimeError("limit_exceeded (429): слишком часто, подожди")
    if not r.ok:
        raise RuntimeError(f"request SMS failed: {r.status}")


async def login_sms_step3_verify(
    api: Api, phone: str, contract: dict[str, Any], code: str
) -> dict[str, Any]:
    """POST /auth/v3/auth/{phone}/confirmation → {accessToken, refreshToken, ...}."""
    payload = {
        "accountId": contract["accountId"],
        "confirm1": code,
        "confirm2": code,
        "login": phone,
        "operatorId": contract["operatorId"],
        "subscriberId": str(contract["subscriberId"]),
    }
    r = await api.post(f"/auth/v3/auth/{phone}/confirmation", payload)
    if r.status == 406:
        raise RuntimeError("invalid SMS code format (406)")
    if not r.ok:
        raise RuntimeError(f"verify SMS failed: {r.status}")
    return await r.json()


# ----------------------- discovery (places / intercoms) ----------------------- #


async def fetch_intercoms(api: Api) -> tuple[str, list[dict[str, Any]]]:
    """Возвращает (place_id, intercoms[]) — домофоны с allowCallMobile."""
    r = await api.get("/rest/v3/subscriber-places")
    places = (await r.json()).get("data") or []
    intercoms: list[dict[str, Any]] = []
    first_place = ""
    for sp in places:
        place = sp.get("place") or {}
        pid = str(place.get("id") or "")
        if not pid:
            continue
        first_place = first_place or pid
        ra = await api.get(f"/rest/v1/places/{pid}/accesscontrols")
        acs = (await ra.json()).get("data") or []
        for ac in acs:
            if ac.get("allowCallMobile") or ac.get("type") == "SIP":
                intercoms.append(
                    {
                        "placeId": pid,
                        "accessControlId": str(ac.get("id")),
                        "name": ac.get("name"),
                        "type": ac.get("type"),
                        "externalCameraId": ac.get("externalCameraId"),
                    }
                )
    return first_place, intercoms
