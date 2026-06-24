# Feature: Two-way talk по домофону (SIP-аудио)

- **Status:** IN PROGRESS — Slice 0 (SIP-фундамент) + Slice 1 (downlink + экран вызова) реализованы; Slice 2 (uplink/микрофон) в работе.
- **Feature-id:** `intercom-two-way-audio`
- **Branch:** `feat/intercom-two-way-audio` (pending merge → master)
- **Owner:** Vyacheslav Scherbinin

## Что внутри

| Файл | Описание |
|---|---|
| [`design.md`](design.md) | дизайн-спека: целевая архитектура, фазирование, решения brainstorming |
| [`call-answer-model.md`](call-answer-model.md) | 🔑 **модель приёма вызова** (pcap-доказано): register-on-ring, latching, окно 30с |
| [`audio-bridge-design.md`](audio-bridge-design.md) | дизайн аудио-моста (downlink): `sip/bridge.py` → go2rtc → HA-native WebRTC |
| [`call-screen-display-design.md`](call-screen-display-design.md) | дизайн экрана вызова: `call_camera.py` `camera.intercom_call` (видео+звук инлайн) |
| [`research-spike.md`](research-spike.md) | результаты спайков: voip-utils D1, тайминг D2, audioop D3, реверс APK D4 |
| [`plan.md`](plan.md) | Slice 0 (фундамент: G.711/STUN/SIP lifecycle) |
| [`plan-audio-downlink.md`](plan-audio-downlink.md) | Slice 1 plan: downlink PoC + `sip/bridge.py` + go2rtc audio upsert |
| [`plan-call-screen-display.md`](plan-call-screen-display.md) | Slice 1 plan: экран вызова через `call_camera.py` |

## Краткая суть

После события вызова (FCM, ADR-0011) — ответить на вызов из HA и **говорить с гостем
у двери** (двусторонний звук), как приложение. SIP/RTP-медиа **доказаны рабочими**
(`probe_sip_media.py`, live 2026-06-22).

**Текущее состояние (ветка `feat/intercom-two-way-audio`):**
- Приём вызова по SIP — **работает live** (register-on-ring, ADR-0012: FCM `ring` → mint → REGISTER → held-INVITE → по «Ответить» `200 OK` → RTP-latching).
- Сброс с панели → SIP `CANCEL` → мгновенный dismiss экрана вызова в HA.
- Звук гостя (downlink) — **выводится** через `AudioBridge` → go2rtc → HA-native WebRTC.
- Экран вызова (`camera.intercom_call`) — видео домофона + звук гостя инлайн на дашборде, работает на 4G без экспозиции go2rtc.
- Микрофон (uplink, говорить гостю) — **следующий слайс** (Slice 2).

## Использование: кнопка «Ответить» в уведомлении

Интеграция даёт сервисы `elektronny_gorod.answer` / `elektronny_gorod.hangup` и
`event`-сущность вызова. Кнопки в push-уведомлении удобно подключить готовым
**blueprint**-ом (idiomatic HA: интеграция = entity+сервисы, уведомление строит
пользователь под свой телефон). Два варианта:

| Blueprint | Кнопки | Когда |
|---|---|---|
| [`doorbell_two_way_answer.yaml`](../../../blueprints/automation/elektronny_gorod/doorbell_two_way_answer.yaml) | Ответить / Сбросить | минимальный — только аудио-ответ |
| [`doorbell_video_call.yaml`](../../../blueprints/automation/elektronny_gorod/doorbell_video_call.yaml) | **+ снимок камеры + Открыть дверь** | полный видеодомофонный UX |

Оба при `ring` шлют actionable-уведомление (Companion App) high-priority и снимают
его при действии/завершении. «Открыть дверь» — `lock.unlock` (accessControlOpen).

**Установка:**
1. Settings → Automations & Scenes → Blueprints → **Import Blueprint** → вставить
   raw-URL файла выше (или скопировать в `config/blueprints/automation/`).
2. Create Automation → выбрать blueprint → указать **сущность вызова домофона**
   и **телефон** (устройство с Home Assistant Companion App).
3. Требуется Companion App (actionable-уведомления). Ответить нужно в окне `~30с`
   (`CallInvalidated`) — иначе домофон сбросит вызов сам.

> Альтернатива без мобильного приложения: кнопка на Lovelace-дашборде, вызывающая
> `elektronny_gorod.answer` (actionable push для этого не нужен).

## Ключевые решения (brainstorming 2026-06-22)

1. **SIP-стек — в интеграции** (go2rtc не умеет SIP: нет пакета `sip`,
   [issue #1750](https://github.com/AlexxIT/go2rtc/issues/1750) open). База —
   **ручной `asyncio`-модуль на основе `probe`** (спайк [research-spike.md](research-spike.md)
   D1 показал: `voip-utils` не подходит под Kazoo — схлопывает multi-`Via`/`Record-Route`,
   хардкодит Opus, нет REGISTER/Digest). Из `voip-utils` берём лишь `SipEndpoint`.
   Без тяжёлых нативных deps → работает в HA Container. Готового end-to-end решения
   нет (3 research-прохода) — наш `probe` уже закрыл SIP-gap на Python.
2. **Целевая трубка — браузер HA через go2rtc** (вариант A: `exec`-backchannel +
   готовая карта `custom:webrtc-camera` AlexxIT/WebRTC). go2rtc как транспорт.
   ⚠️ uplink через `exec`-backchannel — известный риск go2rtc, PoC до Slice 2.
3. **Инкрементально:** фундамент (SIP-приём + downlink/прослушка) → полный two-way.
4. **go2rtc SIP-source на Go** — отдельная upstream-инициатива позже, наш `sip.py`
   как референс (мотивация: переиспользовать и для 2-way домашней камеры — вне scope).

## Связь

- PRD: [`research/intercom-call-probe/PRD-two-way-audio.md`](../../../research/intercom-call-probe/PRD-two-way-audio.md)
- FINDINGS: [`research/intercom-call-probe/FINDINGS.md`](../../../research/intercom-call-probe/FINDINGS.md)
- Эталон: [`research/intercom-call-probe/probe_sip_media.py`](../../../research/intercom-call-probe/probe_sip_media.py)
- Предшествующая фича: FCM-event ([ADR-0011](../../decisions/0011-doorbell-fcm-channel.md))
- ADR: [ADR-0012](../../decisions/0012-register-on-ring.md) — register-on-ring (held-short-window, CANCEL-dismiss)
- Audit: [A-81](../../audit/project-audit.md) — finding + resolved-in-branch статус

## Quality gates

- [x] SPEC_READY
- [x] PLAN_APPROVED (Slice 0–1)
- [x] TESTS_PASS (suite 234+ passed: test_sip_*.py + test_call_camera.py + test_api_sip.py + test_go2rtc_audio.py)
- [x] SECURITY_OK (SIP realm/login/password в SENSITIVE_KEYS; no-secret-logs соблюдён)
- [x] DOCS_UPDATED (project-map, overview, audit A-81, roadmap, ADR-0012)
- [ ] READY_FOR_RELEASE (pending merge + Slice 2 uplink)

**Slice 2 (uplink/микрофон):** PoC go2rtc backchannel с G.711 → `AudioBridge` обратная ветка → `SipManager.uplink_provider`.
