# ADR-0014: Единый go2rtc stream manager для внешнего RTSP

- **Status:** accepted
- **Date:** 2026-07-16
- **Owner:** Architecture Agent + project owner
- **Extends:** [ADR-0009](0009-camera-stream-auto-recovery.md)
- **Tracks:** [audit A-96](../audit/project-audit.md#a-96-внешний-rtsp-после-простоя-требует-предварительного-открытия-камеры-в-ha)

## Context

Интеграция публикует камеры в go2rtc под стабильными именами
`eg_<camera_id>`, но operator URL является сессией с наблюдаемым TTL около
30 минут. A-71/ADR-0009 восстановили уже открытые HA-потоки, однако внешний
RTSP после долгого простоя мог отвечать `500/EOF`, пока пользователь сначала
не откроет ту же камеру в Home Assistant.

Экспериментальная ветка `feat/go2rtc-keep-warm` добавляла фоновые таймеры в
camera entity, но production acceptance не доказала полный путь
`operator mint -> go2rtc registration -> external RTSP`. Запись потоков также
оставалась разделена между `camera.py` и `go2rtc.py`, а PUT fallback мог
разрушить работающего producer'а.

Требования к замене:

- функция строго opt-in и выключена по умолчанию;
- disabled entity никогда не публикуется;
- hidden entity публикуется только отдельным sub-option;
- активный consumer не обрывается при refresh;
- go2rtc restart восстанавливается без открытия камеры в HA;
- operator URL и credentials не попадают в state, diagnostics или логи.

## Decision

Создавать один `CameraStreamManager` на config entry и сделать его
единственным владельцем записей `eg_<camera_id>`.

1. `Go2RtcClient` в `go2rtc.py` владеет list/get/PATCH/DELETE и построением
   RTSP URL. Запись operator-camera stream выполняется только PATCH; PUT
   fallback запрещён.
2. Manager дедуплицирует полную цепочку mint+PATCH по camera ID. Одновременные
   background, HA-open и recovery callers разделяют одну HA-managed task.
3. Eligibility берётся из HA entity registry:
   `disabled_by is None` и (`hidden_by is None` или включён hidden sub-option).
4. `go2rtc_keep_warm` и `go2rtc_keep_warm_hidden` имеют default `false`.
   При выключенном main-option manager обслуживает обычный HA on-demand/A-71,
   но не запускает фоновые mint/list/delete операции.
5. Успешный refresh планируется снова через 28:30. Ошибки получают backoff
   15/30/60/120/240/300 секунд. Startup имеет детерминированный jitter <60с.
6. Reconcile раз в минуту восстанавливает отсутствующие eligible streams
   после рестарта go2rtc. Ineligible stream удаляется только после ухода
   consumers.
7. `ElektronnyGorodCamera` сохраняет проверенные A-71 triggers, но делегирует
   manager'у все operator-camera writes.
8. Diagnostic sensor читает только detached manager state и отдаёт
   credential-free RTSP URL. Свежим считается успешный present/eligible stream
   не старше 28:30.

Production acceptance из семи сценариев остаётся merge gate: автоматические
тесты не доказывают доступность внешнего клиента после часа реального простоя.

## Consequences

### Positive

- Один writer и один dedup boundary устраняют конкурирующие operator mint/PATCH.
- Disabled/hidden policy соответствует фактическому HA registry state.
- PATCH-only не разрушает действующего producer/consumers.
- go2rtc restart обнаруживается максимум за минуту.
- Existing users не получают фонового трафика без явного opt-in.
- Диагностика показывает фактическую свежесть, а не желаемую конфигурацию.

### Negative

- Для каждой eligible камеры появляется operator mint раз в 28:30 даже без
  viewers; это осознанная цена внешнего always-addressable RTSP.
- Reconcile делает локальный list-запрос к go2rtc раз в минуту.
- Реальный idle/playback path нельзя полностью воспроизвести mocked suite.
- A-71 triggers пока остаются в `camera.py`; полное выделение state machine
  (A-83) не входит в решение.

### Mitigation

- Default-off options и явная registry eligibility ограничивают нагрузку.
- Jitter распределяет startup mint, backoff ограничивает ошибки.
- Source URL живёт только внутри refresh coroutine/result и не сохраняется в
  manager state.
- Live QA report обязателен до merge/закрытия старого PR #61.

## Alternatives considered

1. **Оставить per-entity keep-warm timers.** Отклонено: несколько владельцев
   записи и тестируется scheduling, а не полный lifecycle/restart/cleanup.
2. **Сохранить PUT fallback.** Отклонено: production evidence A-71 показало,
   что PUT уничтожает existing producer и отключает consumers.
3. **Использовать go2rtc preload/постоянно держать producer подключённым.**
   Отклонено: лишний трафик и другая семантика; достаточно своевременно
   обновлять зарегистрированный source.
4. **Отказаться от внешнего RTSP.** Отклонено владельцем: стабильный RTSP без
   предварительного открытия HA является требуемым opt-in use case.

## Supersedes / Superseded by

- supersedes: нет; расширяет ADR-0009, не меняя его active-consumer recovery
- superseded by: пусто на момент принятия

## Notes

- Design: [`../features/go2rtc-stream-manager/design.md`](../features/go2rtc-stream-manager/design.md)
- Implementation plan: [`../features/go2rtc-stream-manager/plan.md`](../features/go2rtc-stream-manager/plan.md)
- Related findings: [A-82](../audit/project-audit.md#a-82-go2rtc-transport-в-elektronnygorodcamera-не-вынесен-в-go2rtc-клиент),
  [A-83](../audit/project-audit.md#a-83-auto-recovery-state-machine-a-71-не-выделена-в-отдельный-helper),
  [A-84](../audit/project-audit.md#a-84-go2rtc-config-bloat--стрим-дописывается-а-не-мёржится-unbounded)
- Origin: unmerged PR #61 / `feat/go2rtc-keep-warm`; option keys,
  translations and diagnostic concept were retained, implementation was not.

---

## Когда писать новое ADR взамен этого

- Если writer ownership уходит из per-entry manager.
- Если operator-camera writes снова требуют другой HTTP verb.
- Если eligibility перестаёт определяться HA entity registry.
- Если live evidence опровергнет 28:30 refresh/reconcile модель.
