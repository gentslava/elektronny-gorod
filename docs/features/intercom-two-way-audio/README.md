# Feature: Two-way talk по домофону (SIP-аудио)

- **Status:** IMPLEMENTED IN MASTER — SIP-фундамент, downlink, uplink-микрофон,
  экран вызова, multi-call switching и video anti-churn реализованы.
- **Feature-id:** `intercom-two-way-audio`
- **Branch:** `master` (актуальная реализация после PR #69)
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

**Текущее состояние (`master`):**
- Приём вызова по SIP — **работает live** (register-on-ring, ADR-0012: FCM `ring`
  → mint → REGISTER → held-INVITE → `100 Trying`; по «Ответить» `200 OK` → RTP-latching).
- Сброс с панели → SIP `CANCEL` → мгновенный dismiss экрана вызова в HA.
- Звук гостя (downlink) — **выводится** через `AudioBridge` → go2rtc → HA-native WebRTC.
- Экран вызова (`camera.intercom_call`) — видео домофона + звук гостя инлайн на дашборде, работает на 4G без экспозиции go2rtc.
- Микрофон (uplink, говорить гостю) — **реализован и live-подтверждён** через
  HA WebSocket binary-audio → `UplinkSink` → RTP (ADR-0013).
- Несколько клиентов делят один video producer вызова; новый неотвеченный ring
  переключает карточку на нового звонящего (A-88/A-89, PR #69).

## Использование: экран вызова `/doorbell-call/call`

Интеграция даёт сервисы `elektronny_gorod.answer` / `elektronny_gorod.hangup`,
`event`-сущность вызова и сущность активного вызова `camera.<...>_intercom_call`.
Поверх них собирается **экран вызова**: пуш будит телефон и одним тапом открывает
в HA экран с видео, звуком гостя и кнопками. Канон — прод-модель «лёгкий пуш →
экран» (idiomatic HA: интеграция = entity+сервисы, UI строит пользователь).

| Blueprint | Роль | Сколько |
|---|---|---|
| [`doorbell_call_notify.yaml`](../../../blueprints/automation/elektronny_gorod/doorbell_call_notify.yaml) | пуш со снимком + активная дверь + «Открыть» из пуша | по 1× на дверь |
| [`doorbell_screen_controller.yaml`](../../../blueprints/automation/elektronny_gorod/doorbell_screen_controller.yaml) | SIP-состояние + «Открыть» + сброс при старте | 1× на систему |

Полная пошаговая сборка (хелперы → blueprint-ы → дашборд → микрофон → pro-tip
авто-звука), поток состояний и ограничения — в [`call-screen-setup.md`](call-screen-setup.md).

> Требуется Companion App (actionable-уведомления). Ответить нужно в окне `~30с`
> (`CallInvalidated`) — иначе домофон сбросит вызов сам. Альтернатива без телефона:
> кнопка на дашборде, вызывающая `elektronny_gorod.answer`.

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
- Audit: [A-81/A-85/A-88/A-89/A-90/A-91](../../audit/project-audit.md) — resolved в master

## Quality gates

- [x] SPEC_READY
- [x] PLAN_APPROVED (Slice 0–1)
- [x] TESTS_PASS (suite 392 passed на merge PR #69; SIP/FCM/camera/go2rtc regressions покрыты)
- [x] SECURITY_OK (SIP realm/login/password в SENSITIVE_KEYS; no-secret-logs соблюдён)
- [x] DOCS_UPDATED (project-map, overview, audit A-81, roadmap, ADR-0012)
- [x] MERGED (PR #69)
- [ ] READY_FOR_RELEASE (нужна обычная release-проверка и релизный артефакт)

**Оставшийся polish:** DTMF и дальнейшие UX/reliability улучшения ведутся отдельно;
они не блокируют уже реализованный two-way audio.
