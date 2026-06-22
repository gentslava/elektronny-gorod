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
| `research-spike.md` | (будет, Task 1) результаты спайка: voip-utils API, тайминг, audioop |

## Краткая суть

После события вызова (FCM, фича `feat/doorbell-fcm-event`) — ответить на вызов из HA
и **говорить с гостем у двери** (двусторонний звук), как приложение. SIP/RTP-медиа
**доказаны рабочими** (`probe_sip_media.py`, live 2026-06-22). Не хватает только
интеграции медиа-пути в HA.

## Ключевые решения (brainstorming 2026-06-22)

1. **SIP-стек — в интеграции** (go2rtc не умеет SIP: нет пакета `sip`,
   [issue #1750](https://github.com/AlexxIT/go2rtc/issues/1750) open). База —
   **`voip-utils`** (SIP-клиент из HA core, Apache-2.0, уже UAS), дописываем
   G.711/REGISTER/STUN из доказанного `probe`. Без тяжёлых нативных deps → работает
   в HA Container. Готового end-to-end решения нет (3 research-прохода) — наш `probe`
   уже закрыл SIP-gap на Python.
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
