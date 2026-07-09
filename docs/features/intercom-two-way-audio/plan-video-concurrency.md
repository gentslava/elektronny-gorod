# Видео-конкурентность вызова — Implementation Plan (A-88 / A-89)

> **For agentic workers:** этот план — единый источник контекста для ветки
> `feat/intercom-video-concurrency`. Задачи размечены чекбоксами (`- [ ]` /
> `- [x]`). Источник findings — [`project-audit.md`](../../audit/project-audit.md)
> A-88 / A-89; строки плана — [`roadmap.md`](../../roadmap.md) Итерация 4.

**Ветка:** `feat/intercom-video-concurrency`. Master подтянут (PR #68 merged + docs-sync).

**Scope = Phase A (A-88, видео anti-churn) + Phase B (A-89, мульти-вызов).**
Фаза B — отдельная, начинается только после стабильной A.

---

## Контекст: как устроено видео вызова (проверено в коде + прод 2026-07-08)

- Видео вызова = **copy c общей forpost-камеры домофона**: `eg_intercom_call`
  **вложен** в `rtsp://127.0.0.1:8554/eg_<id>#video=copy` + аудио-мост (downlink
  G.711 → ffmpeg → mpegts/aac → go2rtc). SIP от панели несёт **только аудио**;
  видео берётся из camera-API оператора (одноразовый forpost-URL).
- `call_camera.py` (`camera.intercom_call`) — HA-native entity активного вызова:
  `available` только во время звонка, `stream_source()` строит `eg_intercom_call`,
  `_warm_up()` на `CALL_STATE_ACTIVE` прогревает продюсер (keyframe).
- go2rtc серверно **отдаёт валидный кадр** (`frame.jpeg` = 65 КБ, `ff d8 ff`,
  H264) — серверный пайплайн исправен.

## Проблема (A-88, P1)

Видео вызова нестабильно у пользователя: «на ноуте нет — на телефоне есть»,
задержка 3/5/иногда 20 с, иногда только картинка без видео.

**Root cause:** при нескольких консьюмерах (ноут + телефон, ringing-превью +
стрим вызова) каждое открытие камеры **пере-фетчит одноразовый operator-URL и
пере-собирает продюсер** → `eg_<id>` `Error opening (Invalid data)` / `Operation
timed out`, у части клиентов WebRTC не успевает декодировать keyframe (браузерный
хук: `frames=0 0x0`). После звонка HA Stream worker `camera.*_intercom_call`
**не гасится** → `404 eg_intercom_call` каждые ~60–90 с в течение 9+ минут.

## Проблема (A-89, P2 — UX)

Пока 1-й вызов held (ещё не отвечен), `ring` со 2-го домофона **игнорируется**
(`handle_signal` ring-guard: `if self._manager is not None`). Требование
пользователя: НЕ одновременные разговоры, а **смена активного звонящего** — если
курьер позвонил в один домофон, потом в другой (пока не открыли), экран должен
**переключиться** на новый.

---

## Проблема (A-90, P1 — авто-сброс принятого вызова)

Оператор при ответе **снимает ring-уведомление со всех устройств** → шлёт FCM
`ended` (`reason=answered_elsewhere`) через ~0.7 с после «Принять», хотя SIP-диалог
ещё жив (реальный BYE — на несколько секунд позже). `handle_signal("ended")`
принимал этот push за hangup и гасил `sensor.*_call_state` → карта «Вызов
завершён» на живом разговоре (домофон продолжает разговор).

**Evidence (прод 2026-07-08 20:57, ac=35604, call_id=`R.rgCE…`):**
```
20:57:39.297 вызов ПРИНЯТ, active_call_media OK cam=5593592
20:57:39.298 call-camera available False -> True
20:57:39.965 SIP signal ended: call_id=R.rgCE… (active call_id=R.rgCE…)  ← FCM, +0.67с
20:57:45.827 SIP: вызов завершён (BYE)                                    ← реальный SIP, +6с
```
Cross-call guard (fix 3) не ловит — это тот же `call_id`/`ac`, не чужой вызов.

## Что уже сделано (в этой ветке)

- [x] **A-90: игнор FCM `ended` для принятого вызова** — в `handle_signal` (ветка
  `ended`, после cross-call guard) при `self._manager.in_call` событие игнорируется:
  завершение отвеченного вызова приходит по SIP (BYE→`_schedule_audio_cleanup`,
  CANCEL→`_on_ring_cancelled`, `hangup`, страховка `_MAX_CALL_SEC`). Для
  неотвеченного (`holding`/`ringing`, `in_call=False`) FCM `ended` по-прежнему
  завершает (ответ не в HA). `event.*` doorbell-сущность не затронута — сырые FCM
  события стреляют как раньше. Тесты в `tests/test_sip_call_controller.py`.
- [x] **anti-churn dedup** — `call_camera.stream_source` кэширует
  `(id(bridge), rtsp_url)` активного вызова: повторные открытия камеры отдают
  готовый URL без повторного upsert в go2rtc. Кэш сбрасывается при `media is
  None` (конец звонка) и на новом `bridge`. Тесты в `tests/test_call_camera.py`.
  _(commit `feat(call-camera): anti-churn … (A-88)`)_
- [x] **shared producer (A3)** — `camera.async_go2rtc_video_rtsp()`: reuse
  `eg_<id>` RTSP без второго operator-pull; bootstrap только если producer пуст.
  _(Phase A Task A3)_
- [x] **teardown на ended** — `call_camera._teardown_call_stream()` по
  `CALL_STATE_ENDED`/`error`: `remove_audio_stream(eg_intercom_call)` + сброс кэша.
  _(Phase A Task A1)_
- [x] **warm-up на answer** — `_warm_up()` строит стрим один раз на
  `CALL_STATE_ACTIVE` и пробит `frame.jpeg`, чтобы keyframe был готов к моменту
  открытия клиентами (anti-delay). _(перенесено из UI-ветки, commit `75fe655`)_
- [x] **dedup конкурентных первых открытий (review-driven)** — `call_camera.stream_source`
  получил in-flight future (зеркало A-68 из `camera`): warm-up + открытие карточки
  фронтендом одновременно больше не пере-собирают стрим (double upsert). Ключ
  anti-churn кэша заменён с `id(bridge)` на объект `bridge` (сравнение `is`) —
  устраняет теоретический id-reuse footgun. Тест `test_stream_source_concurrent_opens_deduped`.
- [x] **reuse продюсера только по живости (review-driven)** — `async_go2rtc_video_rtsp`
  переиспользует `eg_<id>` только если `bytes_recv > 0` (не пустой/handshake/мёртвая
  operator-сессия A-71); иначе честный bootstrap. Тесты в `test_camera_call_video_rtsp.py`.
- [x] **чистка hot-path (review-driven)** — `active_call_media` возвращён к чистой
  guard-цепочке (убран eager f-string reason-аккумулятор и `_acm_last`); property
  `available` очищен от side-effect (`_last_available`). DIAG-лог `handle_signal`
  ring/ended оставлен осознанно (low-freq, полезен для Phase B).

---

## Phase A — A-88 остаток

### Task A1: Teardown стрима + остановка HA Stream worker на `ended`
**Files:** `custom_components/elektronny_gorod/call_camera.py`,
`custom_components/elektronny_gorod/sip/call_controller.py` (событие фазы),
`tests/test_call_camera.py`.

Цель — убрать вечные `404 eg_intercom_call` после завершения вызова.

- [x] На `CALL_STATE_ENDED`/`error`: `remove_audio_stream(eg_intercom_call)` из go2rtc
      (`call_camera._teardown_call_stream`), сброс `_call_stream_cache`.
- [x] `available`→False на конце вызова (уже было); teardown go2rtc снимает 404-ретраи
      worker'а (фронт после `ended` скрывает карточку ~2.5с — отдельный UX, не блокер).
- [x] Тест: после `ended` `stream_source()` → `None`, `remove_audio_stream`
      вызван, повторный teardown идемпотентен (`tests/test_call_camera.py`).

### Task A2: PATCH-only обновления (не PUT) — не убивать живой продюсер (A-71)
**Files:** `go2rtc.py` (`upsert_audio_stream`), `tests/test_go2rtc_audio.py`.

- [x] Upsert стрима вызова — **PATCH-first**, PUT только fallback на 4xx/ClientError
      (см. `go2rtc.py:upsert_audio_stream`, A-71).
- [x] Тест: повторный upsert того же src не шлёт PUT при успешном PATCH
      (`test_upsert_audio_stream_patch_first`).

### Task A3: Не давать вызову второй operator-pull
**Files:** `call_camera.py`, `camera.py` (общий `eg_<id>`).

- [x] Вызов делит **единый продюсер** камеры домофона (`eg_<id>`): `call_camera`
      зовёт `ElektronnyGorodCamera.async_go2rtc_video_rtsp()` — локальный RTSP
      если producer уже в go2rtc; иначе один bootstrap через `stream_source()`.
- [ ] Проверить на проде: ноут + телефон одновременно во время звонка → оба видят
      видео, `frames>0` в обоих браузерах.

### Verification A
- [ ] Прод-сценарий: звонок, открыть карту на 2 устройствах → видео на обоих,
      без `Invalid data` / `Operation timed out` в go2rtc-логах.
- [ ] После `ended` — нет `404 eg_intercom_call` в HA-логе.
- [ ] `PYTHONPATH=. .venv/bin/pytest tests/test_call_camera.py tests/test_go2rtc.py -q` зелёные.

---

## Phase B — A-89 мульти-вызов (смена звонящего)

### Task B1: Ветвление ring-guard holding vs in_call
**Files:** `sip/call_controller.py` (`handle_signal` на `ring`),
`tests/test_sip_call_controller.py`.

- [ ] Различать **holding** (ещё не ответили) vs **in_call** (идёт разговор).
- [ ] holding + новый `ring` с другого домофона → снять старый held (release
      SIP/RTP-порты) и захватить новый вызов (переключение звонящего домофона).
- [ ] in_call + новый `ring` → оставить текущий (одновременный разговор вне scope;
      возможно — очередь/индикатор «ещё звонок»).
- [ ] Обновить `sensor.*_call_state` / `EVENT_CALL_STATE` так, чтобы карта
      переключилась на новый звонящий домофон.
- [ ] Тесты: held→release+re-hold нового; in_call не прерывается.

### Verification B
- [ ] Прод: звонок в домофон №1 (не отвечать) → звонок в №2 → карта показывает №2,
      №1 корректно снят; принять №2 → разговор идёт.

---

## Rollback

Всё в git-коммитах; прод-файлы восстанавливаются из git + `docker cp`. Каждая
задача — отдельный коммит, откат по одному.

## Связанные документы

- [`project-audit.md`](../../audit/project-audit.md) — A-88 / A-89 (findings,
  evidence, severity).
- [`roadmap.md`](../../roadmap.md) — Итерация 4, фазы A/B.
- [ADR-0009](../../decisions/0009-camera-stream-auto-recovery.md) — go2rtc
  stream lifecycle / auto-recovery (контекст PUT vs PATCH, A-71).
