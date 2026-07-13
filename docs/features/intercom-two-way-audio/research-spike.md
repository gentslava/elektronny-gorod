# Spike: voip-utils API + audioop + тайминг

- **Date:** 2026-06-23
- **Task:** [plan.md](plan.md) Task 1 (спайк). Снять 3 развилки до SIP-UAS lifecycle.
- **Статус:** D1 ✅ решён, D3 ✅ решён, D2 ✅ повторно верифицирован полным
  Android PCAP 2026-07-13; итоговая модель — register-on-ring + `100 Trying`.

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

> 🔑 **ФИНАЛЬНЫЙ ИТОГ после полного PCAP 2026-07-13:** штатное приложение на ring
> выполняет `REGISTER → INVITE → 100 Trying`, держит INVITE до ответа/завершения
> и шлёт `200 OK` только по явному ответу. Вывод 2026-06-23 о register-on-answer
> был сделан по неполному окну захвата и отменён. Полная картина —
> [call-answer-model.md](call-answer-model.md). Текст ниже сохраняет историю
> промежуточных live-экспериментов и не является текущей архитектурой.

✅ **Замерено (live 2026-06-23, `home.server`, fcm+media пробы параллельно).**

**Результат замера:** `SIP INVITE` пришёл на **~107 мс РАНЬШЕ** `FCM CALL_INCOMING`
(общие часы контейнеров; единичный звонок, но дельта недвусмысленно отрицательная).

**Промежуточный результат D2 (3 live-теста 2026-06-23):** были найдены два
рабочих экспериментальных пути. Их трактовка как «точного mirror» и вывод,
что «Занято» бывает только от автоответа, позднее опровергнуты полным PCAP.

| Тест | Конфигурация | Результат |
|---|---|---|
| **1. push-to-register** (без pre-bind) | НЕ держим рег.; по FCM → transient `REGISTER` (154мс) → ждём INVITE | ❌ **INVITE не пришёл** — forking прошёл без нас |
| **2. held без авто-ответа** | держим рег.; на INVITE → `180 Ringing` (не `200 OK`) | ✅ **INVITE пришёл**; **телефон принял штатно**; панель НЕ «занято» |
| **3. экспериментальный push-wake** | REGISTER с **RFC 8599 push-параметрами** (`pn-provider=fcm; pn-prid=<токен>`, `Expires=3600`) ДО вызова → «сон» (close) → по FCM re-register | ✅ **INVITE пришёл за 68мс**; позднее PCAP показал, что это рабочий эксперимент, но не точный профиль приложения |

**Выводы:**
- 🎯 **Экспериментальный push-wake ВЫПОЛНИМ** (тест 3): ключ — **предварительный
  RFC 8599 push-binding** (REGISTER с pn-параметрами ДО вызова). Тогда Kazoo при вызове
  будит push-устройство и доставляет INVITE на re-register (68мс). Без pre-bind (тест 1)
  не работает. Утверждение, что приложение делает именно так, снято полным PCAP.
- Промежуточно «Занято» было приписано автоответу. Полный PCAP и изоляция
  2026-07-13 показали, что связанная панель воспроизводит его и со штатным
  `REGISTER → INVITE → 100 Trying`, без участия HA; прежняя причинная атрибуция неверна.

**→ Два пути к финальной стратегии (выбор — этап дизайна сетевого слоя):**

| | **App-scheme (push-wake)** | **Held (запасной)** |
|---|---|---|
| Регистрация | pre-bind с push-параметрами, re-register по FCM, сокет может «спать» | постоянная (re-REGISTER keep-alive) |
| Mirror приложения | ✅ точный | ⚠️ нет (приложение так не делает) |
| Риск «Занято» | нет (не держим активный сокет) | нет (доказано тест 2, без авто-ответа) |
| Сложность | выше (pre-bind + push-параметры + re-register на FCM + обновление binding) | ниже |
| Латентность ответа | +68мс на re-register после FCM | мгновенно (рег. уже есть) |

Обе доказаны live. **App-scheme** предпочтительна по mirror-app-принципу; **held** —
проще и тоже валиден. На входящий `INVITE` в любом случае **НЕ авто-отвечаем**:
`200 OK` только по явному «ответить» (PRD F1).

---

### Дополнительно — медиа-путь (подтверждён вживую, та же серия)

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

## D4 — Реверс APK приложения (Linphone) — 2026-06-23

Декомпиляция APK `ru.inetra.intercom` / `com.ertelecom.smarthome` (myhome 9.7.0,
`base.apk` + `split_config.arm64_v8a.apk`) через jadx. Полная картина приёма вызова —
[call-answer-model.md](call-answer-model.md).

**SIP-стек:** Linphone / Belledonne SDK **5.4.42** (нативный `liblinphone.so` +
`libmediastreamer2.so`/`libortp.so`/`libbctoolbox.so`/`libsrtp2.so`). Java-обёртка
`org.linphone.core.*` (245 классов); драйвер приложения — `y60/*` (контроллер,
команды init/config/accept/hangup/iterate), `m9/c0` (Account/AuthInfo/AccountParams),
`l60/*` (Redux side-effects: SipManager/CallRingtone). Других SIP-стеков (PJSIP/Sofia/
JAIN/`android.net.sip`) в APK **нет**.

**Что приложение делает на приёме вызова (из кода):**
- Голый `currentCall.accept()` **по нажатию** пользователя (Redux side-effect) — НЕ авто.
- Авто-`180 Ringing` **ВЫКЛЮЧЕН** (`setAutoSendRingingEnabled(false)`).
- Авто-iterate выключен — ручной `core.iterate()` каждые **20мс** (Timer).
- **НЕТ** `183 Session Progress`/early-media, **НЕТ** session timers (RFC 4028),
  **НЕТ** periodic re-INVITE/UPDATE, **НЕТ** PRACK/100rel-required.

**REGISTER:**
- **Expires=30** (короткий) + re-REGISTER + iterate 20мс (держит свежесть).
- Contact push-params **проприетарные (НЕ RFC 8599)**:
  `app-id=<id>;pn-type=google;pn-tok=<FCM_TOKEN>` (`setContactUriParameters`).
- Встроенный Linphone RFC8599-push **выключен** (`setPushNotificationEnabled(false)`).
- SIP-креды (login/password/realm) минтятся REST-ом оператора (`SipDeviceRaw`).

**Media/SDP:**
- Только **UDP**; `MediaEncryption.None` (plain RTP, без SRTP несмотря на `libsrtp2`);
  AVPF **Disabled**; ICE/STUN/UPnP/IPv6 — всё **выключено**.
- Кодеки явно не задаются — дефолт Linphone (PCMU/PCMA/opus…); видео off (видео — go2rtc).
- micGain/playbackGain +2dB.
- SDP анонсирует **локальный адрес** → downlink через FreeSWITCH **RTP-latching**
  (подтверждено pcap).

**Кастомные заголовки бэкенда** (читает приложение): `Other-Leg-Call-ID` —
маркер Kazoo/FreeSWITCH.

**Ограничение реверса:** точные дефолты таймеров (progress/incoming/nortp) — в
нативном `.so`, из Java не извлекаются. Но вся **конфигурация, которой приложение
отличается от дефолта Linphone**, видна в Java — этого хватило для модели.

🔑 **Уточнённый вывод:** приложение не использует 180/183/session-timers для
удержания вызова. Полный PCAP показал точный порядок: register-on-ring →
`INVITE` → `100 Trying`; `200 OK` только по явному ответу
([call-answer-model.md](call-answer-model.md)).

## Влияние на спеку/план

- `design.md` §3.1 — переписан: primary = asyncio-модуль из probe; voip-utils —
  источник идей/`SipEndpoint`, не база; в manifest не добавляется.
- `design.md` §6.1 — **register-on-ring + 100 Trying** (полный PCAP 2026-07-13,
  см. call-answer-model.md).
- `plan.md` Roadmap Slice 0-lifecycle — убрать «voip-utils в manifest»; SIP-стек
  строим из probe.
