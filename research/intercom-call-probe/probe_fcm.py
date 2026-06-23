"""Проба канала FCM — серверный приём пуша без Android-устройства.

Регистрирует СВОЙ FCM-токен под Firebase-проектом приложения (ntk-myhome,
конфиг в firebase_config.json), привязывает его к аккаунту оператора через
device-installations + subscriberNotifications, держит MTalk-сокет и логирует
входящие пуши. Цель — поймать пуш `PushType=CALL_INCOMING` при звонке.

Используем ОТДЕЛЬНЫЙ installationId/deviceId (не телефона) → телефон
продолжает получать пуши, мы получаем дубль.

Persistence: fcm_credentials.json (gitignored) — чтобы FCM-токен был
стабильным между перезапусками (иначе придётся перепривязывать).

⚠️ Цепочка опирается на приватные API Google (checkin/register/MTalk) —
может не сработать; это и проверяем.

Запуск:  python probe_fcm.py
Лог:     logs/fcm.log
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import uuid

import aiohttp

import common

LOG_PATH = "logs/fcm.log"
CRED_FILE = "fcm_credentials.json"
FB_CFG_FILE = "firebase_config.json"


def _ts() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="milliseconds")


def log(line: str) -> None:
    os.makedirs("logs", exist_ok=True)
    msg = f"{_ts()}  {line}"
    print(msg, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def _load_creds() -> dict | None:
    # Терпим к отсутствующему/пустому/битому файлу (docker bind-mount создаёт
    # пустой файл на первом запуске) — тогда регистрируемся заново.
    try:
        with open(CRED_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data or None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_creds(creds: dict, *_) -> None:
    with open(CRED_FILE, "w", encoding="utf-8") as f:
        json.dump(creds, f)
    log("FCM credentials persisted")


# device-id для оператора: стабильный 16-hex, привязан к install_id сессии
def _device_id(install_id: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_DNS, "fcm-probe-" + install_id).hex[:16]


async def bind_token(sess: common.Session, fcm_token: str) -> None:
    """Регистрируем наш FCM-токен у оператора (как приложение после auth)."""
    body = {
        "appVersionCode": int(common.APP_VERSION["code"]),
        "installationId": sess.install_id,
        "appId": 2,
        "appVersion": common.APP_VERSION["name"],
        "platform": "google",
        "pushToken": fcm_token,
        "isDevelop": False,
        "deviceManufacturer": "Google",
        "deviceModelName": "Pixel 8",
        "osVersion": common.ANDROID_OS_VER,
        "deviceId": _device_id(sess.install_id),
        "deviceType": "MOBILE_APPLICATION",
    }
    async with aiohttp.ClientSession() as s:
        api = common.Api(s, sess.user_agent, access_token=sess.access_token, operator=sess.operator_id)
        r1 = await api.post(
            "/api/mh-customer-device/mobile/public/v1/customers/device-installations", body
        )
        log(f"device-installations → {r1.status}")
        r2 = await api.post("/rest/v1/subscriberNotifications", body)
        log(f"subscriberNotifications → {r2.status}")
        if not (r1.ok and r2.ok):
            log("⚠️ привязка токена не полностью успешна — пуши могут не прийти")


def on_push(notification, persistent_id, *_):
    """Callback firebase-messaging. Логируем всё, особо — CALL_INCOMING."""
    log(f"📩 FCM push (persistent_id={persistent_id})")
    log(f"   {json.dumps(notification, ensure_ascii=False)}")
    data = (notification or {}).get("data") or notification or {}
    ptype = data.get("PushType") or data.get("google.c.a.m_l")
    if ptype == "CALL_INCOMING":
        log("🔔🔔🔔 CALL_INCOMING — ЗВОНОК С ДОМОФОНА (FCM)!")
        for k in ("GateName", "PlaceId", "AccessControlId", "Call-ID", "Apartment", "AllowOpen", "CallStarted"):
            if k in data:
                log(f"        {k}={data[k]}")


async def main() -> None:
    from firebase_messaging import FcmPushClient, FcmRegisterConfig

    sess = common.Session.load("session.json")
    with open(FB_CFG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    log(f"=== FCM probe start (project={cfg['project_id']}, account={sess.account_id}) ===")

    fcm_config = FcmRegisterConfig(
        project_id=cfg["project_id"],
        app_id=cfg["app_id"],
        api_key=cfg["api_key"],
        messaging_sender_id=cfg["messaging_sender_id"],
        bundle_id=cfg.get("bundle_id"),
    )
    client = FcmPushClient(
        on_push,
        fcm_config,
        _load_creds(),
        _save_creds,
    )

    log("→ checkin_or_register (приватные API Google)…")
    fcm_token = await client.checkin_or_register()
    log(f"FCM token получен (len={len(fcm_token)}, …{fcm_token[-8:]})")

    log("→ привязываю токен у оператора…")
    await bind_token(sess, fcm_token)

    log("→ start MTalk listener. ЗВОНИ В ДОМОФОН.")
    await client.start()
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await client.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
