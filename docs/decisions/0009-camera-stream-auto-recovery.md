# ADR-0009: Camera stream auto-recovery при истечении operator session

- **Status:** accepted
- **Date:** 2026-05-27
- **Owner:** Architecture + HA Expert Agent
- **Closes:** [audit A-71](../audit/project-audit.md)

## Context

Operator forpost live-stream имеет серверный TTL **~30 минут** (см.
[A-71](../audit/project-audit.md), подтверждено логами 2026-05-27 + HAR). По
истечении бэкенд закрывает сессию `forpost-N.../rtsp/a<NNNNNN>/<token>/d=1`:

- go2rtc ffmpeg producer ловит `error=EOF`;
- HA Stream worker ([`stream/__init__.py:_run_worker`](../../custom_components/elektronny_gorod/camera.py)) **ретраит тот же `self.source`** с backoff (`STREAM_RESTART_INCREMENT=10s`), **никогда не перевызывая `stream_source()`**;
- наш единственный refresh-источника (`_ensure_go2rtc_stream` + `Stream.update_source()`, см. [ADR-0006 mirror](0006-mirror-app-behavior.md) / A-66) вызывается **только** из `stream_source()`;
- → видео заморожено до ручного reopen карточки.

**Важно:** оригинальное приложение «Мой Дом» зависает идентично — это
by-design лимит бэкенда (пользователь не смотрит лайв >30 мин). Поэтому это
**не баг**, а решение об осознанной мягкой deviation ради HA-UX (wall-panel,
долгий просмотр), где лимит бьёт сильнее, чем в мобильном приложении.

### Что HA уже делает

- **WebRTC** ([`go2rtc/__init__.py:_update_stream_source`](../../custom_components/elektronny_gorod/camera.py)) перевызывает `camera.stream_source()` **на каждый offer** → переподключение WebRTC уже даёт свежий URL.
- **Legacy Stream** (HLS / `preload_stream` / recording) — НЕ перевызывает; именно он в логах фейлил по камере «Подъезд» (20:34→20:54).
- Базовый `Camera` вешает `stream.set_update_callback(self.async_write_ha_state)`; worker при отказе зовёт `_set_state(False)` → callback срабатывает. **Это готовый event-driven сигнал stall.**

## Decision

**Event-driven auto-recovery**: обернуть HA Stream update-callback. При
переходе `stream.available → False` (worker сигналит отказ) запустить
**throttled** re-fetch свежего operator URL и перенаправить источник — те же
API-вызовы, что HA делает на WebRTC re-offer и пользователь при reopen.

### Изменения ([camera.py](../../custom_components/elektronny_gorod/camera.py))

```python
STREAM_RECOVERY_COOLDOWN = 30.0  # сек между авто-recovery попытками

async def async_create_stream(self) -> Stream | None:
    stream = await super().async_create_stream()
    if stream is not None:
        # Оборачиваем callback: сохраняем write_ha_state + детект stall.
        stream.set_update_callback(self._on_stream_state_change)
    return stream

@callback
def _on_stream_state_change(self) -> None:
    self.async_write_ha_state()
    stream = self.stream
    if stream is not None and not stream.available:
        self._maybe_schedule_stream_recovery()

@callback
def _maybe_schedule_stream_recovery(self) -> None:
    now = time.monotonic()
    if now - self._last_recovery_monotonic < STREAM_RECOVERY_COOLDOWN:
        return
    self._last_recovery_monotonic = now
    self.hass.async_create_task(self._async_recover_stream())

async def _async_recover_stream(self) -> None:
    # guard = CoordinatorEntity.available (coordinator up) И камера в
    # coordinator.data; НЕ stream-availability (она перекрыта).
    if not self.available:
        return
    stream_url = await self.coordinator.get_camera_stream(self._id)  # fresh

    if not stream_url:
        return
    if self._use_go2rtc:
        await self._ensure_go2rtc_stream(stream_url)   # PATCH go2rtc + update_source (A-66)
    elif self.stream is not None:
        self.stream.update_source(stream_url)
```

### Throttle (защита от шторма)

Worker фейлит каждые 10/20/30с и на каждый отказ зовёт callback. Без cooldown
мы бы забили operator API. `STREAM_RECOVERY_COOLDOWN=30s` + recovery идёт через
`hass.async_create_background_task` (не блокирует callback, авто-отмена при
shutdown). Если свежий URL тоже мёртвый (operator реально down) → падаем в
штатный backoff HA, повторная попытка не раньше чем через cooldown.

### v2 — go2rtc producer-health poll (go2rtc/WebRTC-only путь)

**Прод-проверка v1 (лог 2026-05-27 23:39)** подтвердила: event-driven recovery
сработал для **домофонов** (есть legacy HA Stream worker → `available → False`),
но **лифты зависли** — они обслуживаются **только** через go2rtc consumer
(WebRTC), legacy Stream worker отсутствует → сигнала `available=False` нет.

**Диагностика go2rtc `/api/streams` (live, тот же момент)** дала health-сигнал:

| go2rtc stream | bytes_recv за 5с | consumers | |
|---|---|---|---|
| eg_5593590/92/94 (домофоны) | +750–800 КБ | 1 | живые (recovered v1) |
| eg_5595470/71/72 (лифты) | **+0 (заморожен)** | 1 | мёртвый producer |

Живой forpost-producer непрерывно принимает байты (~150 КБ/с). `bytes_recv`,
**не изменившийся за интервал при наличии `consumers`**, = producer мёртв
(operator EOF), но go2rtc держит stale-producer.

**Решение v2:** per-camera poll `GET /api/streams?src=eg_<id>` каждые
`GO2RTC_HEALTH_POLL_INTERVAL=30s` (только `use_go2rtc`, регистрируется в
`async_added_to_hass`, снимается в `async_will_remove_from_hass`). Если
`bytes_recv` заморожен с прошлого опроса при `consumers>0` → тот же
`_maybe_schedule_stream_recovery()` (общий cooldown с event-driven путём).
`consumers==0` → сброс baseline (idle producer легитимен, не трогаем).

Recovery-действие для лифтов идентично: `_ensure_go2rtc_stream` делает PUT/PATCH
go2rtc с свежим URL; `update_source` пропускается (legacy Stream у лифтов нет —
и не нужен, go2rtc сам переподключит producer к consumer). Прод-факт: домофоны
с `consumers=1` после PUT свежего URL льют байты → PUT-resume-consumer доказан.

### v3 + v3.2 — Proactive keep-alive refresh (ROOT CAUSE FIX)

**Прод-DIAG (T20-08, 17h):** v1/v2 не покрывают реальный кейс. `consumers`
падает с >0 до 0 ВНУТРИ 30с poll-окна (мы никогда не видим
`frozen+consumers>0`), session-level cutoff бэкенда бьёт ВСЕ потоки
синхронно независимо от наблюдателей.

**v3 решение:** PROACTIVE refresh каждые 28:30 (95% от observed
min TTL 30 мин) **только** для streams с активными consumers — не нагружаем
сеть для idle камер. Первое открытие после idle → HA go2rtc дёрнет
`stream_source()` → fresh fetch автоматически.

**ROOT CAUSE найден через прод-эксперимент с go2rtc API (2026-05-30):**

| Метод | На existing stream | Эффект |
|---|---|---|
| **PUT** | DESTROY + RECREATE | producer killed, consumers=0, catastrophe |
| **PATCH** | UPDATE config only | producer survives, consumers сохраняются |

`_go2rtc_upsert_stream` исторически использовал PUT-first (PATCH был
fallback при PUT exception, который никогда не выполнялся). Каждый refresh
УБИВАЛ running producer → consumers падали → пользователь видел чёрный
экран. Это объясняет ВСЕ предыдущие проблемы:

- v3 с `force_restart=True`: PUT destroy + `update_source()` мог частично
  спасти через worker restart, но WebRTC peers терялись (особенно у камер
  без preload — нет backup-consumer'а)
- v3.1 c `force_restart=False`: PUT destroy без координации = catastrophe

**v3.2 фикс:** переключение порядка → **PATCH-first**, PUT fallback (для
старых версий go2rtc). PATCH идемпотентен — обновляет только config
metadata, текущий ffmpeg-producer продолжает работать со старым URL до
natural EOF, затем go2rtc применит новый. Consumers выживают.

С PATCH-first proactive снова использует `force_restart=False` —
координация с HA Stream worker через `update_source()` не нужна.

**Прод-верификация v3.2 (2026-05-30 02:58→04:18):**

- 4 successful proactive cycles (02:58, 03:23, 03:48, 04:13)
- Все cycles **peaceful** — `bytes_recv` растут НЕПРЕРЫВНО (producer не
  restarted), consumers сохраняются между циклами
- Timestamp discontinuity errors: только 1 раз на cold-start (03:04),
  после стабилизации pipeline — natural EOF transitions проходят smoothly

**Known limitation:** при первом natural EOF после cold start HA Stream
worker может выдать `Timestamp discontinuity detected` ошибку (DTS jump
между producers). v1 reactive recovery ловит и фиксит (~5с gap). После
первого transition pipeline стабилизируется и последующие EOF проходят
без discontinuity. Зафиксировано в
[A-77](../audit/project-audit.md#a-77-ha-stream-worker-dts-discontinuity-при-producer-restart)
с возможными вариантами фиксации (ffmpeg flags / proactive restart).

## Consequences

### Positive

- Закрывает [A-71](../audit/project-audit.md) для наблюдаемого кейса (legacy
  Stream / preload — именно он в логах).
- Не выдумывает новых эндпоинтов: recovery = `get_camera_stream` +
  `_ensure_go2rtc_stream` — те же вызовы, что reopen в приложении. Минимальная
  deviation от [mirror-app-behavior](0006-mirror-app-behavior.md).
- **v1** event-driven — нулевой overhead в нормальном режиме (домофоны).
- **v2** poll покрывает go2rtc/WebRTC-only камеры (лифты), которых v1 не достаёт.

### Negative / Limitations

- v2 poll = `GET /api/streams?src=eg_<id>` каждые 30с на `use_go2rtc` камеру.
  Это localhost-запрос к go2rtc; overhead незначителен (N камер / 30с). Для
  растущих (живых) потоков poll лишь сверяет счётчик — recovery не триггерит.
- Детект stall имеет задержку ≤ интервала poll (~30–60с) + до ~30с на av-timeout
  при event-пути. Видео восстанавливается не мгновенно, но автоматически.
- Лишние HTTP к operator при recovery (1 на эпизод stall, throttled) —
  приемлемо (operator без rate-limit, частота ≤ 1/30с).
- Признак stall — `bytes_recv` заморожен за интервал; формат поля подтверждён
  на go2rtc этого инстанса. При смене схемы go2rtc API (маловероятно) poll
  деградирует gracefully (нет `bytes_recv` int → no-op), event-путь не зависит.

### Mitigation

- Общий cooldown (`STREAM_RECOVERY_COOLDOWN`) для обоих путей — нет двойного
  recovery если event и poll совпали.
- `_async_recover_stream` и `_fetch_go2rtc_stream_info` ловят исключения
  (не валят callback/таймер-цепочку).

## Alternatives considered

1. **Proactive keep-alive** (фоновый refresh каждые ~10-15 мин вслепую).
   Отклонено: re-mint даже healthy потоков (лишние HTTP), паттерн, которого нет
   в приложении. Producer-health poll действует только на реальный stall.
2. **Pure mirror — ничего не делать**, задокументировать лимит. Отклонено
   пользователем (нужен HA-UX для долгого просмотра).
3. **Только v1 event-driven** (без poll). Отклонено после прод-проверки: не
   покрывает go2rtc/WebRTC-only камеры (лифты зависли).

## Supersedes / Superseded by

—

## Notes

- Связано с A-66 (`Stream.update_source()` force restart) — этот ADR
  переиспользует A-66 механизм, добавляя **триггер** (stall-сигнал), которого
  раньше не было.
- Ортогонально A-68 (dedup concurrent `stream_source()`).
- Min HA: `set_update_callback` / `Stream.available` / `update_source`
  присутствуют с ≥ 2024.10 (целевой минимум проекта).
- Recovery-путь наследует отсутствие `ClientTimeout` ([A-21](../audit/project-audit.md),
  не закрыт) на `query_camera_stream` — закрывается в рамках A-21, не этим ADR.
- `available`-guard в `_async_recover_stream` опирается на
  `CoordinatorEntity.available` (она перекрывает `Camera.available`
  stream-check) — это осознанно: entity НЕ становится `unavailable` в UI при
  stall до recovery (pre-existing UX, см. coordinator-pattern).
