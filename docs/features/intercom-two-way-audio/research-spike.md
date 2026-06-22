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

⏳ **Ждёт живого звонка в домофон.** Требуется замерить дельту `FCM CALL_INCOMING` →
форк-`INVITE` (монотонные timestamps в harness `research/intercom-call-probe/`) и
проверить, успевает ли REGISTER, начатый **по** FCM-сигналу, к приходу INVITE, либо
нужно держать короткое окно регистрации. До замера стратегия регистрации
(`transient-by-FCM` vs `held-short-window`) **не фиксируется**.

## Влияние на спеку/план

- `design.md` §3.1 — переписан: primary = asyncio-модуль из probe; voip-utils —
  источник идей/`SipEndpoint`, не база; в manifest не добавляется.
- `plan.md` Roadmap Slice 0-lifecycle — убрать «voip-utils в manifest»; SIP-стек
  строим из probe.
