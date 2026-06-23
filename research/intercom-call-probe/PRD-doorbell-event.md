# PRD + план: событие «вызов с домофона» — FCM-event

> Статус: **в разработке (Фаза A)**. Источник фактов: эксперимент
> `research/intercom-call-probe/` + [FINDINGS.md](FINDINGS.md). Это первая
> (и базовая) фича; разговор по домофону — [PRD-two-way-audio.md](PRD-two-way-audio.md).

## 1. Проблема и цель

Пользователи хотят знать в HA, что **звонят в домофон**, чтобы строить
автоматизации (показать камеру go2rtc, уведомление, открыть дверь). Это
давно запрашиваемая возможность (несколько обращений в issues/обсуждениях),
а не разовый тикет. Сейчас интеграция отдаёт камеры/замки/баланс, но события
вызова нет.

**Success criteria:**
- В HA появляется `event`-сущность `EventDeviceClass.DOORBELL`, стреляющая
  `ring` в течение ~1–2 c после физического звонка, с метаданными вызова.
- Завершение вызова отражается событием `ended`.
- Переживает рестарт HA и обрыв связи (reconnect). Секреты не в логах.
- Телефон пользователя продолжает звонить (не перехватываем линию).

## 2. Доказанные факты (фундамент)

Live-проверка (FINDINGS §FCM):
- **Канал вызова = FCM data-push** (не STOMP `/events`, не SIP). Латентность ~0.5–1 c.
- Серверный приём FCM без Android **работает** (`firebase-messaging`, project
  `ntk-myhome`, sender `369367231553`, pkg `ru.inetra.intercom` — публичные id из APK).
- Привязка токена у оператора: `POST /rest/v1/subscriberNotifications` +
  `device-installations` (поле `pushToken`), рядом с auth.
- Таксономия (наблюдалось ровно 2 типа):
  - `CALL_INCOMING` — «Входящий вызов». Payload: `PlaceId`, `AccessControlId`,
    `GateName`, `Apartment`, `Call-ID`, `CallStarted`, `CallInvalidated`(окно ~30 c),
    `AllowOpen`, `PushTitle`.
  - `CALL_END_ANSWERED_MOBILE` — «принят на другом устройстве» (тот же `Call-ID`).
  - Сброс/таймаут/открытие отдельного end-пуша НЕ дают.
- Токены оператора долгоживущие; FCM-токен у пользователя стабилен.
- ⚠️ Риск «серой зоны»: эмуляция Android-устройства, приватные API Google
  ломались 20.06.2024 → нужна graceful degradation.

## 3. Требования

**Функциональные:**
- F1: `event`-сущность на домофон (`EventDeviceClass.DOORBELL`,
  `event_types: ["ring","ended"]`), сгруппирована с lock/camera того же домофона.
- F2: `CALL_INCOMING` → `ring` (+ атрибуты gate/place/apartment/call_id/allow_open/…).
- F3: `CALL_END_ANSWERED_MOBILE` → `ended` (reason: answered_elsewhere).
- F4: открытие двери — существующий `lock` (`accessControlOpen`); видео — go2rtc.

**Нефункциональные:**
- N1: реализация **in-HA** (self-contained/HACS), FCM-логика изолирована в модуль,
  graceful degradation при сбое Google-API (остальная интеграция жива).
- N2: FCM-creds персистятся (стабильный токен между рестартами).
- N3: `no-secret-logs` — токен/pushToken/тело не логировать.
- N4: только NTK/myhome-вариант в v1 (Дом.ру/HMS — future).

**Вне скоупа v1:** двусторонний звук/SIP (см. [PRD-two-way-audio.md](PRD-two-way-audio.md)),
push-to-talk (нет для домофонов), авто-ответ.

## 4. Архитектурное решение

**In-HA**, не sidecar. Причины: self-contained/HACS (нет барьера второго
контейнера), один процесс владеет и operator-токеном, и FCM-токеном (привязка
без шаринга между процессами), вписывается в asyncio HA. Хрупкая FCM-логика
изолирована в `fcm.py` за graceful degradation. (Подробный разбор in-HA vs
sidecar — в переписке; оформляется ADR.)

## 5. План реализации (слайсы, каждый — зелёные тесты)

**ADR (первым):** `docs/decisions/00NN-doorbell-fcm-channel.md` — канал FCM, in-HA
vs sidecar, риски серой зоны + graceful degradation, хардкод Firebase-конфига
(как `BASE_API_URL`), `iot_class`, scope NTK. Связь: FINDINGS, ADR-0006.

1. **event-платформа** — `event.py` (образец `lock.py`): `Platform.EVENT` в
   `PLATFORMS`; одна сущность на `(place_id, access_control_id)` из
   `coordinator.data["locks"]`; `device_info` = intercom-device (как lock/camera);
   подписка на dispatcher-сигнал `SIGNAL_DOORBELL` (const). `strings.json` +
   `translations/{ru,en}.json` блок `event.doorbell`. Тест `test_event.py` —
   через ручной `async_dispatcher_send` (без FCM).
2. **API-привязка** — `api.py`: `async_register_push_device(fcm_token)` (POST
   `subscriberNotifications` + `device-installations`, тело-зеркало приложения),
   `async_unregister_push_device()` (DELETE). Тест `test_api_push.py`.
3. **FCM-listener** — `fcm.py` (`firebase-messaging>=0.4`): `checkin_or_register`
   → FCM-token → привязка (слайс 2) → `start()` MTalk как
   `entry.async_create_background_task`; `creds_updated_cb` → `entry.data[CONF_FCM_CREDENTIALS]`;
   callback парсит `PushType` → `async_dispatcher_send(SIGNAL_DOORBELL, payload)`;
   try/except graceful degradation; гейт по оператору. `FCM_*` в `const.py`,
   `manifest.requirements`. Тест `test_fcm.py` (мок firebase-messaging).
4. **Docs sync + pre-PR** — CHANGELOG, audit (A-NN для фичи), api-reference (FCM-flow,
   универсальный тон), project-map, roadmap; code-reviewer + git-historian.

**Файлы:** новые `event.py`, `fcm.py`, `tests/test_{event,api_push,fcm}.py`,
`docs/decisions/00NN-*.md`; правки `__init__.py` (Platform.EVENT + wiring),
`const.py` (`SIGNAL_DOORBELL`, `FCM_*`, `CONF_FCM_CREDENTIALS`), `api.py`,
`manifest.json`, `strings.json`, `translations/*.json`.

## 6. Verification
- `PYTHONPATH=. .venv/bin/pytest tests/ -q` — зелёные на каждом слайсе.
- Hassfest/manifest валидны.
- E2E (опц., harness готов): ветка на home.server-HA → реальный звонок →
  `event.<домофон>_call` стрельнул `ring`; завершение → `ended`.
- `no-secret-logs` hook зелёный.

## Связь
- [FINDINGS.md](FINDINGS.md) — доказательства. Утв. план: `~/.claude/plans/` (локально).
- [PRD-two-way-audio.md](PRD-two-way-audio.md) — следующая фича (разговор).
