# Feature: Two-way talk по домофону (SIP-аудио)

- **Status:** PLAN — спека согласована, план Slice 0 написан.
- **Feature-id:** `intercom-two-way-audio`
- **Branch:** `feat/intercom-two-way-audio` (ответвлена от `feat/doorbell-fcm-event` — зависит от FCM-канала).
- **Owner:** Vyacheslav Scherbinin

## Что внутри

| Файл | Описание |
|---|---|
| [`design.md`](design.md) | дизайн-спека: целевая архитектура, фазирование, решения brainstorming |
| [`prd.md`](prd.md) → см. источник | PRD-источник: [`research/intercom-call-probe/PRD-two-way-audio.md`](../../../research/intercom-call-probe/PRD-two-way-audio.md) |
| [`research.md`](research.md) → см. источник | технические доказательства: [`research/intercom-call-probe/FINDINGS.md`](../../../research/intercom-call-probe/FINDINGS.md) |
| [`plan.md`](plan.md) | implementation plan: Slice 0 (спайк + G.711/STUN, TDD) + roadmap Slice 1–3 |
| [`research-spike.md`](research-spike.md) | результаты спайка: voip-utils, тайминг, audioop |
| [`call-answer-model.md`](call-answer-model.md) | 🔑 **модель приёма вызова** (pcap-доказано): REGISTER-on-answer, latching, окно 30с |

## Краткая суть

После события вызова (FCM, фича `feat/doorbell-fcm-event`) — ответить на вызов из HA
и **говорить с гостем у двери** (двусторонний звук), как приложение. SIP/RTP-медиа
**доказаны рабочими** (`probe_sip_media.py`, live 2026-06-22). Не хватает только
интеграции медиа-пути в HA.

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
- ADR (будет): `docs/decisions/0012-sip-two-way-audio.md`

## Quality gates (целевой)

- [x] SPEC_READY
- [ ] PLAN_APPROVED
- [ ] TESTS_PASS
- [ ] SECURITY_OK (SIP-пароль не логировать — [`no-secret-logs.md`](../../../.claude/rules/no-secret-logs.md))
- [ ] DOCS_UPDATED
- [ ] READY_FOR_RELEASE
