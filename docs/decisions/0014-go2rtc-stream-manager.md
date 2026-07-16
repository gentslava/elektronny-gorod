# ADR-0014: Единый lifecycle go2rtc streams для внешнего RTSP

- **Status:** accepted
- **Date:** 2026-07-16
- **Owner:** project owner + Codex
- **Extends:** [ADR-0009](0009-camera-stream-auto-recovery.md)
- **Tracks:** [audit A-96](../audit/project-audit.md#a-96-внешний-rtsp-после-простоя-требует-предварительного-открытия-камеры-в-ha)

## Context

Интеграция публикует камеры в go2rtc под стабильными именами
`eg_<camera_id>`, но operator URL одноразовый и истекает примерно через
30 минут. Lazy registration без активного consumer после простоя давала
внешнему RTSP `404/500/EOF` до предварительного открытия камеры в HA.

Live-проверки показали связанные требования к одному lifecycle:

- внешний opt-in RTSP должен работать после простоя без HA-open;
- initial operator URL нужно немедленно потребить активным go2rtc preload;
- PATCH refresh не должен обрывать producer/viewers;
- go2rtc restart и inactive producer должны восстанавливаться;
- выключение publication удаляет preload и idle registration, но сохраняет
  активного viewer;
- disabled никогда не публикуется;
- hidden background publication требует отдельной галочки, но явное открытие
  hidden-but-enabled камеры в HA должно работать, пока её смотрят;
- сохранение publication options не должно reload-ить всю интеграцию или
  обнулять существующих producers;
- operator URL, credentials и raw producer source не должны попадать в state,
  diagnostics или логи.

## Decision

Создать один `CameraStreamManager` на config entry и сделать его единственным
владельцем operator-camera записей `eg_<camera_id>`.

### Transport and refresh ownership

1. `Go2RtcClient` владеет sanitized list/get/PATCH/DELETE, preload API и
   credential-aware RTSP URL. Operator-camera source записывается только PATCH;
   destructive streams PUT fallback запрещён.
2. Manager дедуплицирует по camera ID полную цепочку
   `operator mint → PATCH → optional preload`. Concurrent background, HA-open и
   recovery callers разделяют одну HA-managed task.
3. Первый background refresh после PATCH включает go2rtc preload, немедленно
   потребляя одноразовый URL. Следующий успешный refresh через 28:30 обновляет
   source PATCH-ом без замены активного preload consumer.
4. Ошибки получают backoff 15/30/60/120/240/300 секунд. Reconcile раз в минуту
   сравнивает complete stream/preload snapshot, восстанавливает missing stream,
   missing preload, inactive producer и go2rtc restart.
5. Cold config-entry startup распределяет initial work deterministic jitter
   `0..60s`. Ручное включение publication в уже loaded entry запускает missing
   cameras коротким async ramp `0s, 0.5s, 1.0s, ...` и не ждёт сетевые операции
   в options callback.

### Registry policy

```text
enabled(camera) =
  correct config entry AND registry_entry.disabled_by is None

background_publishable(camera) =
  enabled(camera)
  AND (
    registry_entry.hidden_by is None
    OR (go2rtc_keep_warm AND go2rtc_keep_warm_hidden)
  )

eligible(camera) =
  go2rtc_keep_warm AND background_publishable(camera)
```

6. `background_due` и `reconcile` могут mint/PATCH только
   `background_publishable` camera. Только `eligible` camera получает manager
   preload, periodic scheduling и считается eligible в diagnostics.
7. После manager startup явные `ha_open`, `active_consumer` и `recovery` могут
   mint/PATCH любую enabled camera, включая hidden. Background-ineligible hidden
   camera не получает preload; reconcile сохраняет registration с viewer и
   удаляет её после ухода consumer.
8. До manager startup coordinator `hidden=true` используется как conservative
   hint для всех reasons, потому что HA может запросить `stream_source()` до
   visibility sync. Persistent user-shown override или обе publication options
   могут разрешить source; иначе setup делает zero mint/PATCH/preload.
9. Disabled camera запрещена в background и on-demand manager paths.

### Cleanup and options lifecycle

10. Cleanup сначала снимает manager preload. Затем получает актуальное число
    consumers: active viewer сохраняет registration с `cleanup_pending`, zero
    consumers приводит к DELETE. Unload снимает owned preloads и отменяет все
    listeners/timers/tasks.
11. `go2rtc_keep_warm` и `go2rtc_keep_warm_hidden` default-off. Main-off
    выполняет cleanup in place, но не запрещает обычный HA on-demand playback.
12. Publication-only options применяются к existing started manager без
    config-entry reload, если normalized API URL, RTSP host и credentials не
    изменились. Transport/auth change, disable go2rtc или missing manager
    сохраняют normal reload fallback.
13. Late background mint повторно проверяет policy до PATCH. Если policy
    меняется во время already-started PATCH, consumer-aware cleanup выполняется
    сразу после ответа, не оставляя late zero-consumer registration.

### HA and security boundary

14. `ElektronnyGorodCamera` сохраняет проверенные ADR-0009 recovery triggers,
    но делегирует manager'у operator-camera writes.
15. Source URL живёт только внутри refresh coroutine/result. Detached state и
    diagnostic sensor содержат только credential-free имя/RTSP URL, sanitized
    status, producer/preload/consumer observations и freshness.

## Consequences

### Positive

- Один writer устраняет конкурирующие mint/PATCH и duplicate config writes.
- Active preload делает внешний RTSP действительно keep-warm после простоя.
- PATCH refresh сохраняет producer/viewers; restart recovery ограничен минутой.
- Background hidden inventory соответствует opt-in policy, а hidden HA playback
  остаётся совместимым со старым “работает пока смотрят” контрактом.
- Publication toggles сохраняют existing producers и не переинициализируют
  coordinator/platform/history/FCM/SIP.
- Default-off ограничивает постоянный operator traffic.

### Negative

- Каждая eligible camera постоянно держит operator producer и обновляет session
  раз в 28:30 — это цена always-addressable external RTSP.
- Reconcile делает локальные go2rtc list-запросы раз в минуту.
- Hidden `eg_<id>` может появиться при явном просмотре в HA даже с выключенной
  hidden background publication; после viewer registration cleanup-ится.
- Реальный idle/playback path нельзя полностью доказать mocked suite.

### Mitigation

- Registry policy, short interactive ramp, cold-start jitter и capped backoff
  ограничивают нагрузку.
- Consumer-aware cleanup не обрывает активных viewers.
- Pre-visibility API hint закрывает setup race без запрета post-start HA-open.
- Live QA остаётся merge gate для idle, restart, consumer preservation и
  hidden/on-demand lifecycle.

## Alternatives considered

1. **Per-entity keep-warm timers.** Отклонено: несколько writers и нет единого
   restart/cleanup ownership.
2. **PATCH-only lazy registration без preload.** Отклонено live: одноразовый URL
   истекал до первого viewer и внешний RTSP возвращал 404/EOF.
3. **Destructive PUT fallback.** Отклонено: production evidence ADR-0009
   показало разрыв existing producer/consumers.
4. **Запретить hidden HA playback вместе с background publication.** Отклонено:
   `hidden_by` не означает disabled, а HA WebRTC получал RTSP 404.
5. **Full config-entry reload на каждую галочку.** Отклонено: producers падали в
   zero и повторно инициализировалась вся интеграция.
6. **Никогда не удалять registrations/preloads.** Отклонено: нарушает opt-in
   traffic и unload lifecycle.

## Supersedes / Superseded by

- supersedes: нет; расширяет ADR-0009, не меняя active-consumer recovery
- superseded by: none

## Notes

- Design: [`../features/go2rtc-stream-manager/design.md`](../features/go2rtc-stream-manager/design.md)
- Implementation plan: [`../features/go2rtc-stream-manager/plan.md`](../features/go2rtc-stream-manager/plan.md)
- Origin: unmerged PR #61 / `feat/go2rtc-keep-warm`; идея, option keys,
  translations и diagnostic concept сохранены и переработаны в PR #71.
