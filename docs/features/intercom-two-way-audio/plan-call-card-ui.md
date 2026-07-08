# План реализации: Call UI (Slice 3) — `call_state` + карточка `eg-intercom-call-card`

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development
> или superpowers:executing-plans. Шаги — checkbox (`- [ ]`). TDD обязателен для backend
> (Slice 3a). Перед push — `.claude/rules/pre-pr-checklist.md`.

**Goal:** Дать (а) единый backend-источник состояния вызова `sensor.<intercom>_call_state`
для DIY-сборки и автоматизаций, и (б) готовую «из коробки» карточку
`eg-intercom-call-card` (Lit+TS), повторяющую UX приложения в родном HA-облике.

**Дизайн:** [`call-card-ux-spec.md`](call-card-ux-spec.md) (решения владельца 2026-06-24).

**Architecture (заземлено в коде):**
- `DoorbellCallController` (один на entry, `hass.data[SIP_DATA][entry_id]`) уже —
  единственный оркестратор вызова: `handle_signal` (ring/ended), `current_call()`,
  `_manager.in_call`, `async_answer`/`async_hangup`, `_on_cancelled`/`_release`.
  → Делаем его **единственным автором** состояния: новый сигнал `SIGNAL_CALL_STATE`,
  испускается в каждой точке перехода. Сейчас контроллер гоняет `input_boolean`
  (dismiss) — **не трогаем его в 3a** (карточка/дашборд продолжают работать),
  депрекация helper'а — отдельный поздний cleanup.
- `sensor.<intercom>_call_state` — **по домофону** (dedup `(place_id, access_control_id)`,
  как `event.py`), тот же device. Подписывается **только** на `SIGNAL_CALL_STATE`,
  отражает state если AC совпал, иначе `idle`. Имя берёт из своего `lock_info`.
- Карточка читает `call_state` + камеры + lock, встраивает HA-native WebRTC,
  адаптивный open-control, микрофон (логика из текущей `eg-intercom-mic-card.js`).

**Tech Stack:** HA custom integration (Python 3.13 asyncio, enum SensorEntity,
dispatcher); фронтенд — **Lit + TypeScript** + Rollup/Vite (бандл → статик-ресурс).

---

## Слайсы

| Slice | Что | Риск | Статус (2026-06-25) |
|---|---|---|---|
| **3a** | backend `sensor.*_call_state` + `EVENT_CALL_STATE` | низкий | ✅ сделано (тесты+review) |
| **3b** | Lit-карточка `eg-intercom-call-card` (поглощает mic-card) | средний | ✅ собрано (typecheck+25 unit+smoke); ⏳ дизайн на согласовании + live-проверка видео/микрофона |
| **3c** (опц.) | fullscreen на панели (auto-view / browser_mod) | низкий | ⏳ позже |

Каждый слайс — отдельный PR (pre-PR checklist). 3a мерджится самостоятельно
(полезен для DIY даже без карточки).

---

## Slice 3a — backend: `sensor.<intercom>_call_state`

**Files:**
- Modify: `const.py` (+`SIGNAL_CALL_STATE`, enum-значения), `sip/call_controller.py`
  (`_set_call_state()` + emit в переходах), `sensor.py` (+entity), `strings.json`,
  `translations/ru.json`/`en.json`.
- Test: `tests/test_sensor_call_state.py` (new), `tests/test_sip_call_controller.py` (+).

**Контракт состояния (enum):**
`idle | ringing | connecting | active | ended | error`. Атрибуты сенсора:
`call_id`, `intercom_name` (из своего lock_info), `started_at` (момент `active`),
`access_control_id`, `place_id`. Длительность считает карточка от `started_at`
(отдельный duration-сенсор не делаем — решение §17).

### Task 1: Сигнал + переходы в контроллере

- [ ] **Step 1: const** — добавить в `const.py`:
```python
SIGNAL_CALL_STATE = f"{DOMAIN}_call_state"   # payload: {place_id, access_control_id, state, call_id, started_at}
# enum-значения (используются и сенсором, и контроллером):
CALL_STATE_IDLE = "idle"
CALL_STATE_RINGING = "ringing"
CALL_STATE_CONNECTING = "connecting"
CALL_STATE_ACTIVE = "active"
CALL_STATE_ENDED = "ended"
CALL_STATE_ERROR = "error"
```

- [ ] **Step 2: падающий тест контроллера** — emit на ring/answer/hangup:
```python
# tests/test_sip_call_controller.py — добавить
async def test_call_state_signal_lifecycle():
    sent = []
    hass = _hass()
    with patch(f"{_CC}.async_dispatcher_send", side_effect=lambda h, sig, p: sent.append((sig, p))):
        c = DoorbellCallController(hass, _api_ok(), lambda: "TOK",
                                   go2rtc=_go2rtc(), camera_resolver=lambda ac: "CAM")
        c.handle_signal(_ring(ac="AC", call_id="CID"))         # → ringing
        # answer → connecting → active (мок manager.async_answer успешен, in_call=True)
        c._manager = _mgr_in_call()
        await c.async_answer()
        await c.async_hangup()                                 # → ended
    states = [p["state"] for _, p in sent if _ == SIGNAL_CALL_STATE]
    assert states[0] == CALL_STATE_RINGING
    assert CALL_STATE_CONNECTING in states and CALL_STATE_ACTIVE in states
    assert states[-1] == CALL_STATE_ENDED
    assert all(p["access_control_id"] == "AC" for s, p in sent if s == SIGNAL_CALL_STATE)
```

- [ ] **Step 3: реализация `_set_call_state`** в `call_controller.py`:
```python
@callback
def _set_call_state(self, state: str, *, call: ActiveCall | None = None) -> None:
    """Единственная точка публикации состояния вызова (SIGNAL_CALL_STATE)."""
    call = call or self.current_call()
    ac = call.access_control_id if call else self._last_ac
    self._last_ac = ac  # кешируем — на `ended` current_call уже может быть None
    async_dispatcher_send(self.hass, SIGNAL_CALL_STATE, {
        "place_id": call.place_id if call else self._last_place_id,
        "access_control_id": ac,
        "state": state,
        "call_id": call.call_id if call else self._last_call_id,
        "started_at": self._started_at,  # set при active
    })
```
Вызвать `_set_call_state(...)` в точках перехода (заземлено в текущих хуках):
- `handle_signal` ветка `ring` (после запоминания call) → `CALL_STATE_RINGING`
  (+ `self._last_ac/_last_place_id/_last_call_id = ...`).
- `handle_signal` ветка `ended` / `_on_fcm_ended` / `_on_cancelled` / `_release` /
  таймаут окна → `CALL_STATE_ENDED`.
- `async_answer`: в начале → `CALL_STATE_CONNECTING`; после успешного
  `manager.async_answer(...)` (200 OK, `in_call=True`) → `self._started_at = utcnow()`,
  `CALL_STATE_ACTIVE`; в `except` → `CALL_STATE_ERROR` затем `CALL_STATE_ENDED`.
- `async_hangup` (BYE) → `CALL_STATE_ENDED`.

> ⚠️ **Реализатору:** `_last_ac/_last_place_id/_last_call_id/_started_at` — новые
> инстанс-поля (init `None`). Свериться с точными именами полей `ActiveCall`
> (`access_control_id`, `place_id`, `call_id`) и хуками сброса — не плодить новые
> состояния, только публиковать существующие переходы. `input_boolean`-логику
> dismiss **оставить как есть** (параллельно), её снимем отдельным cleanup.

- [ ] **Step 4: прогон** `PYTHONPATH=. .venv/bin/pytest tests/test_sip_call_controller.py -q` → PASS.
- [ ] **Step 5: commit** — `feat(sip): контроллер публикует SIGNAL_CALL_STATE на переходах вызова`.

### Task 2: Сущность `sensor.<intercom>_call_state`

- [ ] **Step 1: падающий тест** `tests/test_sensor_call_state.py`:
```python
async def test_call_state_reflects_matching_ac_and_resets_others():
    # две сущности (AC1, AC2); SIGNAL_CALL_STATE по AC1 → AC1=ringing, AC2 остаётся idle
    ...
async def test_call_state_attributes_started_at_and_call_id(): ...
async def test_default_idle_on_add(): ...
```

- [ ] **Step 2: реализация** в `sensor.py` (паттерн дедупа — копия `event.py`):
```python
class ElektronnyGorodCallStateSensor(CoordinatorEntity[...], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "call_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [CALL_STATE_IDLE, CALL_STATE_RINGING, CALL_STATE_CONNECTING,
                     CALL_STATE_ACTIVE, CALL_STATE_ENDED, CALL_STATE_ERROR]

    def __init__(self, coordinator, lock_info):
        super().__init__(coordinator)
        self._place_id = lock_info["place_id"]
        self._access_control_id = lock_info["access_control_id"]
        self._name = lock_info["name"]
        self._attr_native_value = CALL_STATE_IDLE
        self._attr_unique_id = f"{DOMAIN}_call_state_{self._place_id}_{self._access_control_id}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, <тот же device_uid, что event.py>)}, ...)
        self._extra = {}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_CALL_STATE, self._handle))

    @callback
    def _handle(self, payload):
        if str(payload.get("access_control_id")) != str(self._access_control_id):
            return  # вызов другого домофона — наш остаётся как есть (idle)
        self._attr_native_value = payload["state"]
        self._extra = {"call_id": payload.get("call_id"), "intercom_name": self._name,
                       "started_at": payload.get("started_at"),
                       "access_control_id": self._access_control_id, "place_id": self._place_id}
        if payload["state"] in (CALL_STATE_ENDED, CALL_STATE_ERROR):
            self._extra["started_at"] = None
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self): return self._extra
```
Регистрация в `sensor.py:async_setup_entry` — тем же дедупом `(place_id, ac_id)`, что
`event.py` (можно вынести общий helper `_dedup_doorbells(locks)` — низкорисковый
extract, опционально).

- [ ] **Step 3: прогон** `pytest tests/test_sensor_call_state.py -q` → PASS.
- [ ] **Step 4: translations** — `call_state` + перевод option-значений (`state.*` /
  `entity.sensor.call_state.state.{ringing,...}`) в `strings.json` + `ru.json`/`en.json`.
- [ ] **Step 5: регресс** `pytest tests/ -q` → all pass.
- [ ] **Step 6: commit** — `feat(sensor): sensor.*_call_state — единый источник состояния вызова`.

### Task 3: Docs sync (3a)
- [ ] CHANGELOG `[Unreleased]`, `project-map.md` (+sensor), `api-reference` если нужно,
  audit (A-NN при наличии), README фичи (статус Slice 3a).

**Self-review 3a:** контроллер — единственный автор; сенсор пассивно отражает;
`input_boolean` не тронут (dashboard работает); enum device_class → нативные графики/
history; per-doorbell симметрично `event.py`.

---

## Slice 3b — frontend: карточка `eg-intercom-call-card` (Lit + TS)

**Files (new):** `frontend/` (исходники TS) → сборка в
`custom_components/elektronny_gorod/www/eg-intercom-call-card.js`.
**Modify:** `www/` раздача (есть), README/`uplink-card-install.md` (инструкция),
`eg-intercom-mic-card.js` → помечается deprecated (логика мигрирует).

### Структура
```
frontend/
  src/
    eg-intercom-call-card.ts        # главный LitElement (config, hass, render по state)
    state-machine.ts                # маппинг sensor.call_state + lock/camera → ViewState
    components/
      call-video.ts                 # встроенный HA-native WebRTC-плеер (camera/webrtc/offer)
      open-control.ts               # адаптив: slide (тач) | hold | tap+confirm
      mic-controller.ts             # AudioWorklet + WS uplink (порт из eg-intercom-mic-card.js)
      call-actions.ts               # Принять/Отклонить/Завершить/Микрофон/Звук (ha-control-button)
      status-bar.ts                 # имя домофона + статус + таймер (опц.)
    util/pointer.ts                 # matchMedia('(pointer: coarse)') → tach vs desktop
  rollup.config.mjs · tsconfig.json · package.json
```

### Поведение (из UX-спеки)
- [ ] **Видео — HA-native WebRTC** (без обязательной `webrtc-camera`): `call-video.ts`
  использует WS `camera/webrtc/offer` для `camera.intercom_call` (in-call) и doorbell-
  камеры (ringing). Реюз `ha-camera-stream`/`ha-web-rtc-player`, если доступны в `hass`.
- [ ] **State-машина:** `sensor.*_call_state` → `idle/ringing/connecting/active/ended`;
  слои `opening_door` (по `lock`-state), `audio_unavailable`, `mic_permission`.
- [ ] **Сброс `error` (контракт из review P2 Slice 3a):** backend оставляет `error`
  терминальным (не авто-переходит в `ended`). Карточка показывает «Ошибка вызова»
  ~3–5с, затем сама гасит экран (локальный таймер) — чтобы `error` не «залипал» в UI
  до следующего вызова.
- [ ] **Open-control адаптивный** (`open_action: auto`): тач → slide (на стиле
  `ha-control-slider`); десктоп → hold(`lock.unlock` по удержанию) или tap+confirm.
  Прогресс/успех(`mdi:lock-open-check`)/ошибка(`mdi:lock-alert`) — overlay.
- [ ] **Микрофон:** при `active` авто-`getUserMedia`, **если** `permissions=granted` +
  `isSecureContext`; иначе CTA «Разрешить микрофон». Тогл выкл. Логика AudioWorklet+WS —
  перенос из `eg-intercom-mic-card.js` (slot-leak guard сохранить).
- [ ] **Звук гостя:** автоплей muted → оверлей «Включить звук»; тап «Принять» = жест
  (снимает mute). 
- [ ] **Действия:** Принять→`elektronny_gorod.answer`; Отклонить/Завершить→`...hangup`;
  Открыть→`lock.unlock`. На `active` «Принять» исчезает.
- [ ] **Таймер:** `timer: auto` — секундомер от `started_at`, по умолчанию ненавязчивый;
  поведение финализировать live (§17 п.6).
- [ ] **Тема:** только theme-токены (§12); адаптив по ширине контейнера (`ResizeObserver`).
- [ ] **Конфиг + auto-discovery** (см. Приложение B спеки): `call_state`, `camera`,
  `doorbell_camera`, `lock`, `open_action`, `mic`, `mic_autostart`, `timer`.

### Сборка / установка
- [ ] `npm i` (lit, rollup/vite, typescript) → `npm run build` → один бандл в `www/`.
- [ ] Lovelace-ресурс `/elektronny_gorod_static/eg-intercom-call-card.js` (как mic-card).
- [ ] `window.customCards.push({type:"eg-intercom-call-card", ...})`.

### Тестирование 3b
- [ ] **Unit (vitest + @open-wc/testing):** state-machine (call_state→ViewState),
  open-control (slide-порог/hold-таймер/confirm), pointer-детект, mic permission-gate.
- [ ] **Live (прод, 4G):** звонок → ringing видео (без звука) → Принять → connecting →
  active видео+звук (1 тап unmute) → микрофон авто (если granted) → Открыть (slide на
  телефоне / hold на десктопе) → Завершить. Повторный вход. go2rtc наружу не торчит.
- [ ] **Desktop:** проверить, что slide НЕ используется (hold/tap), всё без прокрутки.

- [ ] **Commits (порядок):** `chore(frontend): scaffold Lit+TS сборки карточки` →
  `feat(card): eg-intercom-call-card — экран вызова (state/video/actions)` →
  `feat(card): open-control адаптив + микрофон (порт mic-card)` →
  `docs: инструкция установки карточки; mic-card → deprecated`.

---

## Slice 3c (опционально) — fullscreen на панели

- [ ] **Базово (zero-dep):** пример automation в README — по `sensor.*_call_state ==
  ringing` `navigate`/`lovelace`-переход на выделенный fullscreen-view с карточкой.
- [ ] **Опц. `browser_mod`:** пример `browser_mod.popup` поверх всего на конкретных
  панелях (документируем как опциональную зависимость, не из коробки).
- [ ] Не блокирует 3a/3b; чистые docs + примеры.

---

## Quality gates (на каждый PR — `.claude/rules/pre-pr-checklist.md`)
- TDD: backend-тесты зелёные (3a). Карточка — unit + live.
- code-reviewer (subagent) до push; P0/P1 применить.
- Docs sync (CHANGELOG, project-map, README, audit).
- git-historian `HISTORY_CLEAN` перед merge.
- SECURITY: no-secret-logs (mic WS не логирует аудио/токены); diagnostics redaction не затронут.

## Связь
- [`call-card-ux-spec.md`](call-card-ux-spec.md) — UX-решения.
- [`call-answer-model.md`](call-answer-model.md) — окно 30с/лимит ~1мин, Call-ID.
- [`call-screen-display-design.md`](call-screen-display-design.md) — `camera.intercom_call`, autoplay-policy.
- ADR-0012 (register-on-ring), ADR-0013 (uplink mic).
- memory `frontend-card-framework` — Lit+TS.
