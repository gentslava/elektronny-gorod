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
`hass.async_create_task` (не блокирует callback). Если свежий URL тоже мёртвый
(operator реально down) → падаем в штатный backoff HA, повторная попытка не
раньше чем через cooldown.

## Consequences

### Positive

- Закрывает [A-71](../audit/project-audit.md) для наблюдаемого кейса (legacy
  Stream / preload — именно он в логах).
- Не выдумывает новых эндпоинтов: recovery = `get_camera_stream` +
  `_ensure_go2rtc_stream` — те же вызовы, что reopen в приложении. Минимальная
  deviation от [mirror-app-behavior](0006-mirror-app-behavior.md).
- Event-driven, без polling — нулевой overhead в нормальном режиме.

### Negative / Limitations

- **Не покрывает непрерывный WebRTC-only просмотр** без переподключения: там
  legacy Stream может быть idle, его callback не сработает. Для этого
  понадобился бы poll go2rtc `/api/streams` producer-health (тяжелее, ближе к
  keep-alive) — **осознанно отложено** до репорта такого кейса.
- Лишние HTTP к operator при recovery (1 на эпизод stall, throttled) —
  приемлемо (operator без rate-limit, частота ≤ 1/30с).

### Mitigation

- Cooldown ограничивает частоту.
- `_async_recover_stream` ловит исключения fetch (не валит callback-цепочку).

## Alternatives considered

1. **Proactive keep-alive** (фоновый refresh каждые ~10-15 мин). Отклонено
   как primary: паттерн, которого нет в приложении (сильнее нарушает mirror),
   + постоянные HTTP. Зафиксирован как «Вариант 2» в A-71.
2. **go2rtc `/api/streams` producer-health polling.** Отклонено как primary:
   надёжнее (покрывает WebRTC), но polling-overhead и сложность; ближе к
   keep-alive. Возможное будущее расширение.
3. **Pure mirror — ничего не делать**, задокументировать лимит. Отклонено
   пользователем (нужен HA-UX для долгого просмотра).

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
