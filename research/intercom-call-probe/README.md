# Эксперимент: канал события «вызов с домофона»

Цель — эмпирически определить, по какому каналу приходит событие входящего
вызова домофона в приложении «Мой Дом / NTK» (`myhome.proptech.ru`), чтобы
выбрать архитектуру для интеграции Home Assistant.

Три независимые пробы, по одному каналу каждая, запускаются одновременно и
ловят **один физический звонок**:

| Проба | Канал | Что проверяет |
|---|---|---|
| `probe_stomp.py` | STOMP-over-WebSocket `/events` | наш чистый in-HA путь (aiohttp, без UDP, долгоживущий токен) |
| `probe_sip.py` | SIP REGISTER → INVITE | проверенный экосистемой domru путь |
| `probe_fcm.py` | FCM data-push (headless, без Android) | богатый payload `CALL_INCOMING`, но хрупкий (приватный API Google) |

> Status проверок (offline + live smoke):
> STOMP — ✅ live-connect OK (CONNECTED получен);
> SIP — ✅ Digest по RFC 2617, структура верна (полный тест нужен на звонке/NAT);
> FCM — ✅ checkin/register к Google работает, реальный FCM-токен получен.

## Подготовка

```bash
cd research/intercom-call-probe
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp firebase_config.example.json firebase_config.json   # вставить api_key (для FCM)
```

`session.json`, `firebase_config.json`, `fcm_credentials.json`, `logs/` —
в `.gitignore` (содержат токен/секреты). **Не коммитить.**

## Шаг 1 — логин (один раз)

```bash
.venv/bin/python login.py
# вводишь телефон → SMS-код → выбираешь контракт
```
Создаёт `session.json` (токен + список домофонов с `allowCallMobile`).

## Шаг 2 — запуск проб + звонок

### Вариант A — локально, быстро (3 терминала)
```bash
.venv/bin/python probe_stomp.py     # терминал 1
.venv/bin/python probe_sip.py       # терминал 2  (за домашним NAT INVITE может не дойти — см. ниже)
.venv/bin/python probe_fcm.py       # терминал 3
```
Затем **позвонить в домофон** (лучше с закрытым приложением на телефоне —
тогда foreground-WS держит только наша проба, результат STOMP однозначен).

### Вариант B — home.server, изолированно (авторитетный прогон)
Скопировать папку на сервер, выполнить `login.py` на хосте, затем:
```bash
docker compose up --build           # 3 изолированных контейнера, network_mode: host
```
`network_mode: host` обязателен для SIP (входящий UDP-INVITE мимо docker-NAT).

## Шаг 3 — интерпретация (`logs/{stomp,sip,fcm}.log`)

- **STOMP** залогировал `MESSAGE` с `type` про вызов (не `availableFeatures`)
  → **идеал**: берём чистый in-HA STOMP-канал, без SIP/FCM.
- Только **SIP** поймал `INVITE` → канал события = SIP (как у domru).
- Только **FCM** поймал `CALL_INCOMING` → нужен push-приём (sidecar-bridge).
- Несколько сразу → выбираем по простоте/надёжности (приоритет STOMP > SIP > FCM).

Маркеры в логах: `🔔🔔🔔` = пойман вызов; для каждого канала рядом — сырой payload.

## Безопасность / чистота

- Пробы read-only по бэкенду; единственная запись — минт SIP-кредов
  (`sipdevices`) и привязка FCM-токена (`subscriberNotifications`), оба —
  с **отдельным** `installationId`/`deviceId`, телефон не затрагивается и
  продолжает звонить.
- Токены/SIP-пароли в логи не пишутся.
- Это throwaway-research, не трогает `custom_components/`.

## Что дальше

После эксперимента — зафиксировать выбранный канал, обновить
`docs/architecture/api-reference.md` (STOMP `/events`, push-flow, sipdevices,
FCM `CALL_INCOMING`-payload) и завести ADR по realtime-каналу, затем
Plan/Tasks по фиче `event`-сущности `EventDeviceClass.DOORBELL`.
