# ADR-0011: Realtime-канал события «вызов с домофона» — приём FCM in-HA

- **Status:** accepted
- **Date:** 2026-06-22
- **Owner:** @gentslava + Claude

## Context

Давно запрашиваемая возможность — событие в HA о входящем вызове домофона
(показать камеру, уведомить, открыть дверь). До сих пор интеграция отдавала
камеры/замки/баланс, но события вызова не было.

Эмпирическим экспериментом (live-проверка на прод-аккаунте, реальные звонки;
harness и доказательства — `research/intercom-call-probe/`, `FINDINGS.md`)
установлено, по какому каналу приходит вызов:

- 🔴 **STOMP-over-WS** `wss://…/events` — НЕ несёт событие вызова (только
  `availableFeatures`); постоянное соединение молчит при звонке.
- 🟢 **FCM data-push** — основной канал. Типы `CALL_INCOMING` /
  `CALL_END_ANSWERED_MOBILE`, латентность ~0.5–1 c, богатый payload.
- 🟡 **SIP** — это медиа-канал (сам разговор), а не сигнал; тяжёлый
  (UDP/NAT/SIP-стек), вынесен в отдельную фичу «разговор по домофону».

Приложение «Мой Дом / NTK» принимает вызов через **FCM**: регистрирует
FCM-токен (Firebase project `ntk-myhome`) и привязывает его у оператора
(`POST /rest/v1/subscriberNotifications` + `device-installations`). Серверный
приём FCM **без Android-устройства** подтверждён рабочим (`firebase-messaging`:
checkin → register → MTalk-сокет).

## Decision

**Принимать FCM-пуш вызова внутри интеграции (in-HA), не отдельным sidecar'ом.**

1. **`event`-сущность** `EventDeviceClass.DOORBELL` на домофон, типы
   `ring` (`CALL_INCOMING`) и `ended` (`CALL_END_ANSWERED_MOBILE`).
   Открытие двери — существующий `lock` (`accessControlOpen`), видео — go2rtc.
2. **Изолированный модуль `fcm.py`** держит FCM-соединение (firebase-messaging),
   парсит push и рассылает `SIGNAL_DOORBELL` → event-сущность. Запуск —
   background-task в `async_setup_entry`, teardown — `async_on_unload`.
3. **Публичный Firebase-конфиг приложения** (`FCM_PROJECT_ID/APP_ID/SENDER_ID/
   API_KEY/BUNDLE_ID`) — в `const.py`, как `BASE_API_URL`. Это **не секреты и не
   привязаны к юзеру/устройству**: одинаковы у всех пользователей приложения,
   зашиты в APK (`google-services.json`). Google официально считает Firebase
   API key не-секретом (защита — package + SHA-1 restriction). Per-device/user
   данные (FCM-токен, FCM-creds, операторский токен) — генерятся в рантайме и
   хранятся в `entry.data`, НЕ хардкодятся.
4. **Graceful degradation.** Весь FCM-флоу под try/except: при сбое (Google
   сломал приватный API, нет сети, протух токен) — warning, остальная
   интеграция (polling) работает, событие просто не стреляет. `async_setup_entry`
   не падает.
5. **Scope v1** — только NTK/myhome-вариант (`myhome.proptech.ru`). Дом.ру
   (Huawei Push / HMS) и двусторонний звук (SIP) — отдельные будущие фичи.

### Почему in-HA, а не sidecar

- **Self-contained / HACS** — пользователю не нужен второй контейнер (огромный
  барьер; go2rtc уже есть в HAOS, а здесь — обычная установка интеграции).
- **Один процесс владеет и операторским токеном, и FCM-токеном** — привязку
  (`subscriberNotifications`) делает та же интеграция своим токеном, без шаринга
  секретов между процессами.
- **Вписывается в asyncio HA** — `firebase-messaging` async, MTalk-сокет =
  long-running task. Хрупкость изолирована в `fcm.py`.

## Consequences

### Positive
- Закрывает давний запрос: realtime-событие вызова в HA, одно-контейнерная установка.
- Богатый payload (gate/place/apartment/call-id/allow_open) + lifecycle (ring→ended).
- Reverse-инжиниринг как явная часть процесса (мирроринг приложения, ADR-0006).

### Negative
- **«Серая зона»:** эмуляция Android-устройства в FCM опирается на
  **недокументированные приватные API Google** (checkin/register/MTalk), которые
  Google ломал (20.06.2024) — тогда «умерли» старые версии всех библиотек.
  Долгосрочно гарантий нет: «работает, пока работает».
- Новая зависимость `firebase-messaging` (+ protobuf/http_ece/cryptography).
- ToS: эмуляция клиента — формально не «официально поддержано».

### Mitigation
- **Graceful degradation** — слом FCM не ломает интеграцию, только отключает событие.
- Логика изолирована в `fcm.py` за чётким интерфейсом (`SIGNAL_DOORBELL`) — замена
  механизма (другая библиотека, sidecar-bridge) не задевает event-сущность.
- `firebase-messaging` — поддерживаемая библиотека (линия Lemoine→sdb9696),
  переживает изменения приватного API через bump зависимости.

## Alternatives considered

1. **STOMP-WS `/events` in-HA** — самый чистый (aiohttp, без UDP, долгоживущий
   токен). Отклонено: эксперимент доказал, что канал **не несёт** событие вызова.
2. **SIP REGISTER → INVITE** — проверенный экосистемой domru путь. Отклонено как
   канал *сигнала*: тяжёлый (UDP/NAT/SIP-стек), per-домофон, бедные метаданные;
   его ценность — медиа (разговор), вынесено в отдельную фичу.
3. **Sidecar push-bridge** (как go2rtc) — изоляция/persistence. Отклонено для v1:
   барьер второго контейнера + шаринг операторского токена между процессами.
   Остаётся опцией для HMS-варианта / жёсткой изоляции (v2).
4. **microG + Android-эмулятор + logcat** (как в экосистеме domru) — отклонено:
   нужен живой Android 24/7, ловит «8 из 10», хрупкая цепочка. Костыль.

## iot_class

Оставлен `cloud_polling` (основная модель данных — periodic refresh; FCM-push —
supplementary realtime-слой поверх). Пересмотр на `cloud_push` — при следующей
оценке IQS, если событийный слой станет первичным.

## Supersedes / Superseded by

— (первый ADR про realtime push-канал)

## Notes

- Доказательства и payload — `research/intercom-call-probe/FINDINGS.md`,
  PRD — `PRD-doorbell-event.md`; следующая фича (разговор) — `PRD-two-way-audio.md`.
- Связано с [ADR-0006](0006-mirror-app-behavior.md) (mirror-app-behavior):
  привязка FCM-токена зеркалит приложение (`subscriberNotifications`).
- [memory: doorbell-call-channel](~/.claude/projects/-Users-gentslava-Developer-elektronny-gorod/memory/doorbell-call-channel.md).
