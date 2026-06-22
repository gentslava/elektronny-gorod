# Spike: voip-utils API + audioop + тайминг

- **Date:** 2026-06-23
- **Task:** [plan.md](plan.md) Task 1 (спайк). Снять 3 развилки до SIP-UAS lifecycle.
- **Статус:** D1 ✅ решён, D3 ✅ решён, D2 ⏳ ждёт живого звонка.

## D1 — SIP-база: `voip-utils` или ручной asyncio из probe?

**Решение: ручной `asyncio`-модуль на основе `probe_sip_media.py` (primary).
`voip-utils` как drop-in база НЕ подходит** под наш Kazoo-кейс.

Изучены исходники `voip_utils` (v на 2026-06): `sip.py`, `voip.py`, `const.py`,
`__init__.py`. Три **фатальных** для нашего кейса ограничения:

1. 🔴 **Множественные `Via`/`Record-Route` схлопываются.** `SipMessage.parse_sip`
   хранит заголовки в `dict[str, str]` (`sip.py:172-173` — `headers[key.lower()] =
   value`). При нескольких одноимённых заголовках остаётся **только последний**.
   `answer()` (`sip.py:890-901`) эхо-ит лишь один `Via` и **вообще не эхо-ит
   `Record-Route`**. Kazoo/Kamailio SBC требует **эхо всех `Via` + `Record-Route`
   дословно** (FINDINGS §«SIP-flow»), иначе `200 OK` игнорируется → нет `ACK` →
   «нет ответа». `probe` это делает специально (`probe_sip_media.py:265-285`).

2. 🔴 **Хардкод Opus.** `answer()` генерирует SDP только с `opus/48000/2`
   (`sip.py:861-862`); RTP-слой — `RtpOpusInput`/`RtpOpusOutput` (`voip.py:177-178`).
   Детектор кодека в INVITE ищет **только** `opus` в rtpmap (`sip.py:600-603`),
   для G.711 payload_type остаётся дефолтным 123. Домофон шлёт **только G.711**
   (PCMU/PCMA) — RTP-слой voip-utils не переиспользуем, `answer()` нужно
   полностью переопределять.

3. 🔴 **Нет REGISTER + Digest MD5; блокирующий `time.sleep`.** В `sip.py` нет
   REGISTER и Digest-аутентификации (наш слой в любом случае). `send_audio`
   (`voip.py:264,283`) использует **`time.sleep`** — неприемлемо в HA event loop.

**Вывод:** переопределить под Kazoo пришлось бы parse-заголовков, `answer()`,
RTP-слой, добавить REGISTER/Digest/STUN/latching — т.е. почти переписать `probe`.
`probe` уже **точнее под Kazoo** (эхо всех Via/Record-Route, G.711, Digest REGISTER,
STUN, latching, BYE — доказано live). Поэтому база — наш asyncio-модуль из `probe`.

**Что заимствуем из `voip-utils` (опционально, изолированно):**
- `SipEndpoint` (`sip.py:36-121`) — чистый regex-парсер SIP URI/заголовков (scheme,
  user, host, port, params). Переиспользуем для разбора `From`/`To`/`Contact`.
- Идея каркаса `SipDatagramProtocol` (`datagram_received` → `on_call`/`on_hangup`).

Заимствование — copy/адаптация отдельных функций, **не зависимость-база**. В manifest
`voip-utils` **не добавляем** (тащить пакет ради одного класса нерентабельно; парсер
URI у нас уже есть в probe). → плановый пункт «voip-utils в Slice 0-lifecycle»
снимается.

## D3 — `audioop` на Python 3.13

**Решение: `audioop-lts` ✅** (подтверждено в Task 2). `import audioop` падает на
чистом py3.13 (PEP 594), `audioop-lts` возвращает рабочий модуль; `lin2ulaw`/
`ulaw2lin`/`lin2alaw`/`alaw2lin` работают. Добавлен в `manifest.json` requirements.

## D2 — Тайминг FCM→INVITE + transient-register

🟡 **Частично (live 2026-06-23, на `home.server` через docker).** Медиа-путь
**подтверждён вживую с реальным аудио**, но точный тайминг transient-register — ещё нет.

**Что доказано (медиа-путь two-way):**
- `INVITE` доходит **только за пределами VPN**: локально на mac (за WARP-туннелем
  `utun4`, Contact `198.18.0.1`) — **0 INVITE**; на `home.server` (домашний IP +
  `network_mode: host`) — INVITE пришёл, `200 OK`→`ACK`, диалог установлен.
- Кодек домофона — **PCMU/8000 (µ-law, pt=0)**; probe взял `track.ulaw`.
- **Uplink:** наш G.711-трек («раз-два-три, проба») **слышно из панели** (подтверждено).
- **Downlink:** **3089 RTP-пакетов PCMU** от медиа-сервера оператора (`&lt;оператор-media-SBC&gt;`).
- Вердикт probe: «двусторонний звук РАБОТАЕТ». Вызов ~62с, завершён `BYE` оператора.
- → Валидирует вынесенные в `sip/` слои: G.711 (pt=0→ulaw), SDP-answer, RTP/STUN/latching, BYE.

**Что ещё НЕ замерено (собственно D2):**
- Дельта `FCM CALL_INCOMING` → форк-`INVITE` (нужен **параллельный** `probe_fcm` с
  монотонными timestamps — в этом прогоне FCM-проба не запускалась).
- Успевает ли REGISTER, начатый **по** FCM, к приходу INVITE (в прогоне регистрация
  держалась постоянно с 17:49:47, INVITE в 17:50:40 — ~53с спустя).
- → Стратегия (`transient-by-FCM` vs `held-short-window`) **остаётся открытой**;
  замер — отдельным прогоном (fcm + media probe вместе).

🔴 **Урок инфраструктуры:** приём входящего SIP-вызова **требует прямого сетевого
пути без VPN** (домашний NAT или сервер с публичным mapping) — за VPN-туннелем
forking-INVITE с медиа-SBC оператора не доходит. Для прода (HA в docker на сервере)
это естественно выполнено; для разработки за VPN — нет.

## Влияние на спеку/план

- `design.md` §3.1 — переписан: primary = asyncio-модуль из probe; voip-utils —
  источник идей/`SipEndpoint`, не база; в manifest не добавляется.
- `plan.md` Roadmap Slice 0-lifecycle — убрать «voip-utils в manifest»; SIP-стек
  строим из probe.
