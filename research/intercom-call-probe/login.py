"""Свежий логин по SMS → session.json (research, throwaway).

Запуск:
    python login.py

Спросит телефон и SMS-код, выполнит auth-флоу оператора (зеркало интеграции),
получит токен, найдёт домофоны с поддержкой звонка и сохранит всё в session.json.
Пробы (probe_stomp/sip/fcm) читают session.json.

session.json содержит токен — он в .gitignore, НЕ коммитить.
"""

from __future__ import annotations

import asyncio
import uuid

import aiohttp

import common

SESSION_FILE = "session.json"


async def main() -> None:
    phone = input("Телефон (например 79991234567): ").strip().lstrip("+")
    device_uuid = str(uuid.uuid4())  # стабильный installationId для этой сессии
    ua = common.build_user_agent(device_uuid=device_uuid)

    async with aiohttp.ClientSession() as s:
        api = common.Api(s, ua)

        print("→ запрашиваю контракты…")
        contracts = await common.login_sms_step1_contracts(api, phone)
        if not contracts:
            raise SystemExit("нет контрактов для этого телефона")

        if len(contracts) == 1:
            contract = contracts[0]
        else:
            print("Найдено несколько контрактов:")
            for i, c in enumerate(contracts):
                print(f"  [{i}] {c.get('address')}  (placeId={c.get('placeId')})")
            contract = contracts[int(input("Выбери индекс: ").strip())]

        print("→ отправляю SMS…")
        await common.login_sms_step2_request_code(api, phone, contract)

        code = input("SMS-код: ").strip()
        print("→ подтверждаю…")
        tokens = await common.login_sms_step3_verify(api, phone, contract, code)

        operator_id = str(tokens.get("operatorId") or contract.get("operatorId") or "")
        account_id = str(contract.get("accountId") or "")
        subscriber_id = str(contract.get("subscriberId") or "")

        # UA для post-auth запросов — теперь с account/operator.
        ua_authed = common.build_user_agent(
            account_id=account_id,
            operator_id=operator_id,
            device_uuid=device_uuid,
        )
        api2 = common.Api(
            s,
            ua_authed,
            access_token=tokens["accessToken"],
            operator=operator_id,
        )

        print("→ ищу домофоны…")
        place_id, intercoms = await common.fetch_intercoms(api2)

        sess = common.Session(
            access_token=tokens["accessToken"],
            refresh_token=tokens.get("refreshToken"),
            operator_id=operator_id,
            account_id=account_id,
            subscriber_id=subscriber_id,
            phone=phone,
            user_agent=ua_authed,
            install_id=device_uuid,
            place_id=place_id,
            intercoms=intercoms,
        )
        sess.save(SESSION_FILE)

    print(f"\n✅ session.json сохранён. Домофонов найдено: {len(intercoms)}")
    for ic in intercoms:
        print(f"   • {ic['name']}  place={ic['placeId']} ac={ic['accessControlId']} type={ic['type']}")
    print("\nДалее: запусти пробы (probe_stomp.py / probe_sip.py / probe_fcm.py) и позвони в домофон.")


if __name__ == "__main__":
    asyncio.run(main())
