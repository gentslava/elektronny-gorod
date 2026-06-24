# Экран вызова через HA-native (camera.intercom_call) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) или superpowers:executing-plans. Шаги — checkbox (`- [ ]`).

**Goal:** Показать вызов домофона (видео + звук гостя инлайн) в HA-дашборде, работая на 4G без экспозиции go2rtc, через одну camera-сущность `camera.intercom_call` + HA-native WebRTC.

**Architecture:** Новая `Camera`-сущность `camera.intercom_call`. Её `stream_source()` при активном вызове пересобирает go2rtc-стрим `eg_intercom_call` (СВЕЖИЙ video-RTSP домофона + аудио-мост) и возвращает RTSP — рефреш-на-открытии убирает EOF; вне вызова → `None`. Создание `eg_intercom_call` переезжает из `accept` (B) в `stream_source()`. HA-native отдаёт video+audio за HA-логином (4G ok, go2rtc в LAN). Узкий интерфейс к `DoorbellCallController`. `camera.py` stream-lifecycle не трогаем.

**Tech Stack:** HA custom integration, Python 3.13 asyncio, `homeassistant.components.camera.Camera`, go2rtc REST, pytest-homeassistant-custom-component.

**Дизайн:** [`call-screen-display-design.md`](call-screen-display-design.md).

---

## File Structure

| Файл | Ответственность | Действие |
|---|---|---|
| `custom_components/elektronny_gorod/sip/call_controller.py` | + `active_call_media()` (узкий интерфейс: активный вызов → camera_id + bridge); `_setup_audio_bridge` перестаёт upsert'ить стрим (только поднимает мост) | модифицируется (Task 1) |
| `custom_components/elektronny_gorod/call_camera.py` | **новый** — `ElektronnyGorodCallCamera`: `stream_source()` собирает свежий `eg_intercom_call`, отдаёт RTSP | создаётся (Task 2) |
| `custom_components/elektronny_gorod/camera.py` | + регистрация `ElektronnyGorodCallCamera` в `async_setup_entry` (одна сущность на entry). stream-lifecycle камер НЕ трогаем | модифицируется (Task 2) |
| `tests/test_sip_call_controller.py` | тест `active_call_media` | модифицируется (Task 1) |
| `tests/test_call_camera.py` | **новый** — тесты `stream_source` (активный/нет вызова, рефреш) | создаётся (Task 2) |
| дашборд `doorbell-call` (HA storage) | карточка вызова → `webrtc-camera` `entity: camera.intercom_call` (инлайн-звук); fallback advanced-camera-card | Task 3 (live) |

---

## Task 1: Контроллер — узкий интерфейс активного вызова + мост без upsert

**Files:**
- Modify: `custom_components/elektronny_gorod/sip/call_controller.py`
- Test: `tests/test_sip_call_controller.py`

**Контекст:** Сейчас (B) `_setup_audio_bridge(call)` поднимает мост И сразу `upsert_audio_stream(CALL_STREAM_NAME, _call_stream_srcs(...))`. Переносим upsert в camera-сущность (рефреш-на-открытии). Контроллер теперь только поднимает мост и **отдаёт** «активный вызов: camera_id + bridge».

- [ ] **Step 1: Падающий тест `active_call_media`**

```python
# tests/test_sip_call_controller.py
async def test_active_call_media_returns_camera_and_bridge():
    api = MagicMock()
    api.mint_sip_device = AsyncMock(return_value={"login": "l", "password": "p", "realm": "r"})
    c = DoorbellCallController(
        _hass(), api, lambda: "TOK",
        go2rtc=Go2RtcConfig("http://g:1984", {}, "127.0.0.1"),
        camera_resolver=lambda ac: "5593590" if ac == "AC" else None,
    )
    c.handle_signal(_ring(ac="AC"))
    bridge = MagicMock()
    c._manager = MagicMock(); c._manager.in_call = True
    c._bridge = bridge
    cam_id, br = c.active_call_media()
    assert cam_id == "5593590" and br is bridge


def test_active_call_media_none_when_no_call():
    c = DoorbellCallController(_hass(), MagicMock(), lambda: "TOK")
    assert c.active_call_media() is None
```

- [ ] **Step 2: Прогон — FAIL** `PYTHONPATH=. .venv/bin/pytest tests/test_sip_call_controller.py::test_active_call_media_returns_camera_and_bridge -q` → AttributeError `active_call_media`.

- [ ] **Step 3: Реализация `active_call_media` + мост без upsert**

```python
# call_controller.py — добавить метод
@callback
def active_call_media(self) -> tuple[str, AudioBridge] | None:
    """Активный отвеченный вызов → (camera_id, bridge) для camera.intercom_call.

    None, если нет активного разговора / нет моста / камера не разрешилась."""
    if self._bridge is None or self._manager is None or not self._manager.in_call:
        return None
    call = self.current_call()
    if call is None:
        return None
    cam_id = (
        self._camera_resolver(call.access_control_id)
        if self._camera_resolver else None
    )
    if not cam_id:
        return None
    return cam_id, self._bridge
```

В `_setup_audio_bridge` **убрать** upsert стрима (его теперь делает camera-сущность), оставить подъём моста:

```python
        try:
            await bridge.start()
        except Exception:  # noqa: BLE001 — degrade
            LOGGER.warning("Аудио-мост не поднялся — медиа недоступно (degrade)")
            await bridge.stop()
            return None, self._on_downlink
        LOGGER.info("Аудио-мост поднят (стрим вызова соберёт camera.intercom_call)")
        return bridge, bridge.feed_downlink
```

(Удалить из `_setup_audio_bridge` блок `await upsert_audio_stream(...)`. `_teardown_audio_bridge` — оставить `remove_audio_stream(CALL_STREAM_NAME, ...)` как есть: контроллер снимает стрим на конце вызова.)

- [ ] **Step 4: Обновить существующие B-тесты** — `test_answer_with_go2rtc_sets_up_bridge` больше не проверяет `upsert.assert_awaited_once()` (upsert ушёл из accept). Заменить на проверку, что `bridge.start` вызван и `on_downlink == bridge.feed_downlink`:

```python
    assert ok is True
    bridge.start.assert_awaited_once()
    assert mgr.async_answer.await_args.kwargs["on_downlink"] is bridge.feed_downlink
    # upsert на accept больше НЕ происходит (его делает camera.intercom_call)
    upsert.assert_not_awaited()
```

- [ ] **Step 5: Прогон — PASS** `PYTHONPATH=. .venv/bin/pytest tests/test_sip_call_controller.py -q` → all pass.

- [ ] **Step 6: Commit**

```bash
git add custom_components/elektronny_gorod/sip/call_controller.py tests/test_sip_call_controller.py
git commit -m "refactor(sip): контроллер отдаёт active_call_media; upsert стрима уходит из accept"
```

---

## Task 2: Сущность `camera.intercom_call` (stream_source с рефреш-на-открытии)

**Files:**
- Create: `custom_components/elektronny_gorod/call_camera.py`
- Modify: `custom_components/elektronny_gorod/camera.py` (регистрация в `async_setup_entry`)
- Test: `tests/test_call_camera.py`

**Контекст:** `stream_source()` зовётся HA при открытии плеера. При активном вызове: берём camera_id+bridge у контроллера, **рефрешим** видео домофона (через `stream_source()` doorbell-камеры → свежий `rtsp://…/eg_<camera>`), собираем `eg_intercom_call` = [свежее видео `#video=copy`, аудио моста], upsert, возвращаем RTSP. Иначе `None`.

- [ ] **Step 1: Падающий тест**

```python
# tests/test_call_camera.py
from unittest.mock import AsyncMock, MagicMock, patch
from custom_components.elektronny_gorod.call_camera import ElektronnyGorodCallCamera

_CC = "custom_components.elektronny_gorod.call_camera"


def _cam(controller, doorbell_lookup):
    return ElektronnyGorodCallCamera(
        controller=controller, go2rtc_base_url="http://g:1984",
        go2rtc_headers={}, rtsp_host="127.0.0.1", doorbell_lookup=doorbell_lookup,
    )


async def test_stream_source_none_without_active_call():
    c = MagicMock(); c.active_call_media.return_value = None
    cam = _cam(c, lambda cid: None)
    assert await cam.stream_source() is None


async def test_stream_source_builds_fresh_combined_and_returns_rtsp():
    bridge = MagicMock(); bridge.go2rtc_src = "ffmpeg:http://1.2.3.4:40020#audio=aac#audio=opus"
    c = MagicMock(); c.active_call_media.return_value = ("5593590", bridge)
    doorbell = MagicMock()
    doorbell.stream_source = AsyncMock(return_value="rtsp://127.0.0.1:8554/eg_5593590")
    upsert = AsyncMock()
    cam = _cam(c, lambda cid: doorbell if cid == "5593590" else None)
    with patch(f"{_CC}.upsert_audio_stream", new=upsert), patch(
        f"{_CC}.async_get_clientsession", return_value=MagicMock()
    ):
        cam.hass = MagicMock()
        url = await cam.stream_source()
    doorbell.stream_source.assert_awaited_once()  # рефреш видео-источника
    # eg_intercom_call собран: свежее видео (copy) + аудио моста
    srcs = upsert.await_args.args[2]
    assert srcs == [
        "rtsp://127.0.0.1:8554/eg_5593590#video=copy",
        "ffmpeg:http://1.2.3.4:40020#audio=aac#audio=opus",
    ]
    assert url == "rtsp://127.0.0.1:8554/eg_intercom_call"
```

- [ ] **Step 2: Прогон — FAIL** `PYTHONPATH=. .venv/bin/pytest tests/test_call_camera.py -q` → ModuleNotFound `call_camera`.

- [ ] **Step 3: Реализация `call_camera.py`**

```python
"""camera.intercom_call — экран вызова через HA-native (call-screen-display-design.md).

Одна сущность на entry. stream_source() при активном вызове пересобирает go2rtc-стрим
eg_intercom_call (СВЕЖИЙ video-RTSP домофона + аудио-мост) → RTSP. Рефреш-на-открытии
убирает EOF (как у камер). Вне вызова → None. HA-native отдаёт video+audio (4G, без
экспозиции go2rtc). camera.py stream-lifecycle не трогаем.
"""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, GO2RTC_RTSP_PORT, LOGGER
from .go2rtc import upsert_audio_stream
from .sip.call_controller import CALL_STREAM_NAME, DoorbellCallController


class ElektronnyGorodCallCamera(Camera):
    """Camera-сущность активного вызова (video домофона + downlink-аудио)."""

    _attr_has_entity_name = True
    _attr_translation_key = "intercom_call"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(
        self,
        controller: DoorbellCallController,
        go2rtc_base_url: str,
        go2rtc_headers: dict,
        rtsp_host: str,
        doorbell_lookup: Callable[[str], Camera | None],
    ) -> None:
        super().__init__()
        self._controller = controller
        self._base_url = go2rtc_base_url
        self._headers = go2rtc_headers
        self._rtsp_host = rtsp_host
        # camera_id → entity домофона (для рефреша её source); из camera-платформы.
        self._doorbell_lookup = doorbell_lookup
        self._attr_unique_id = f"{DOMAIN}_intercom_call"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "intercom_call")}, name="Вызов домофона"
        )

    async def stream_source(self) -> str | None:
        """Активный вызов → свежий combined-стрим eg_intercom_call → RTSP; иначе None."""
        media = self._controller.active_call_media()
        if media is None:
            return None
        camera_id, bridge = media
        doorbell = self._doorbell_lookup(camera_id)
        if doorbell is None:
            return None
        # рефреш видео-источника домофона (свежий operator-URL → свежий eg_<camera> RTSP)
        video_rtsp = await doorbell.stream_source()
        if not video_rtsp:
            return None
        srcs = [f"{video_rtsp}#video=copy", bridge.go2rtc_src]
        await upsert_audio_stream(
            self._base_url, CALL_STREAM_NAME, srcs,
            async_get_clientsession(self.hass), self._headers,
        )
        LOGGER.info("Стрим вызова собран (HA-native): %s", CALL_STREAM_NAME)
        return f"rtsp://{self._rtsp_host}:{GO2RTC_RTSP_PORT}/{CALL_STREAM_NAME}"
```

- [ ] **Step 4: Прогон — PASS** `PYTHONPATH=. .venv/bin/pytest tests/test_call_camera.py -q` → pass.

- [ ] **Step 5: Регистрация в `camera.py:async_setup_entry`** — добавить ОДНУ сущность; `doorbell_lookup` ищет doorbell-камеру по `unique_id` среди уже созданных сущностей платформы.

```python
# camera.py, в конце async_setup_entry (после async_add_entities(... cameras ...))
    from .call_camera import ElektronnyGorodCallCamera
    from .sip.call_controller import DoorbellCallController
    sip_data = hass.data.get("elektronny_gorod_sip", {})
    controller = sip_data.get(entry.entry_id)
    if use_go2rtc and base_url and controller is not None:
        created = {c._id: c for c in []}  # заполняется ниже через замыкание реестра

        def _doorbell_lookup(camera_id: str):
            comp = hass.data["camera"]
            uid = f"{DOMAIN}_camera_{camera_id}"
            for ent in comp.entities:
                if getattr(ent, "unique_id", None) == uid:
                    return ent
            return None

        async_add_entities([
            ElektronnyGorodCallCamera(
                controller=controller, go2rtc_base_url=base_url,
                go2rtc_headers=ElektronnyGorodCamera._noop_headers(go2rtc_username, go2rtc_password),
                rtsp_host=rtsp_host, doorbell_lookup=_doorbell_lookup,
            )
        ])
```

> ⚠️ **План-уточнение реализатору:** `go2rtc_headers` — вычислить так же, как `_go2rtc_auth_headers()` в `camera.py` (Basic-auth из username/password). Если в `camera.py` это инстанс-метод — извлечь общий `go2rtc_auth_headers(user, pwd)` из `go2rtc.py` (он там уже есть как `go2rtc_auth_headers`) и переиспользовать (DRY, низкорисковый). Заменить `_noop_headers` на этот вызов. `hass.data["elektronny_gorod_sip"]` — проверить точный ключ (`_SIP_DATA` в `__init__.py`).

- [ ] **Step 6: Регресс-прогон** `PYTHONPATH=. .venv/bin/pytest tests/ -q` → all pass (camera.py stream-lifecycle не менялся).

- [ ] **Step 7: Translations** — добавить `intercom_call` в `strings.json` + `translations/ru.json`/`en.json` (`entity.camera.intercom_call.name`).

- [ ] **Step 8: Commit**

```bash
git add custom_components/elektronny_gorod/call_camera.py custom_components/elektronny_gorod/camera.py custom_components/elektronny_gorod/strings.json custom_components/elektronny_gorod/translations/ tests/test_call_camera.py
git commit -m "feat(camera): camera.intercom_call — экран вызова через HA-native (рефреш-на-открытии)"
```

---

## Task 3: Деплой + дашборд + live-проверка карточки инлайн-звука

**Files:**
- Deploy: `custom_components/elektronny_gorod/**` → прод (scp + docker restart, см. [[ha-deployment]]).
- Modify: дашборд `doorbell-call` (HA storage, через ha-mcp `ha_config_set_dashboard`).

- [ ] **Step 1: Деплой** скопировать изменённые файлы в `/opt/homeassistant/custom_components/elektronny_gorod/`, `docker restart`, дождаться `healthy`, проверить лог без ImportError + `FCM doorbell listener запущен`.

- [ ] **Step 2: Дашборд — заменить B-карточку (`webrtc-camera url: eg_intercom_call`) на entity-режим.** В каждом из 3 доменных блоков `doorbell-call`, карточка in-call (`input_boolean ... state: on`):

```yaml
type: custom:webrtc-camera
entity: camera.intercom_call
muted: false
```

(python_transform: найти `c.get("type") == "custom:webrtc-camera"` → заменить `{"type","url",...}` на `{"type":"custom:webrtc-camera","entity":"camera.intercom_call","muted":False}`.)

- [ ] **Step 3: Live на 4G — основной тест.** Позвонить → Ответить → на телефоне (4G) на экране вызова: **видео + звук гостя инлайн**, без «config error», без EOF; повторный вход в экран — снова работает (рефреш-на-открытии). go2rtc наружу не выставлен.

- [ ] **Step 4: Если `webrtc-camera entity` инлайн-звук не даёт на 4G** — fallback: установить `advanced-camera-card` (HACS) и карточку:

```yaml
type: custom:advanced-camera-card
cameras:
  - camera_entity: camera.intercom_call
    live_provider: ha
live:
  auto_play: true
  controls:
    builtin: true
```

Повторить Step 3.

- [ ] **Step 5: Commit дашборда-изменений** (если есть код-артефакты) + зафиксировать рабочий вариант карточки в [`call-screen-display-design.md`](call-screen-display-design.md) §«Показ инлайн».

---

## Self-Review

**Spec coverage:**
- ✅ camera.intercom_call + stream_source рефреш-на-открытии (Task 2).
- ✅ Узкий интерфейс к контроллеру `active_call_media` (Task 1).
- ✅ HA-native показ + инлайн-звук (Task 3, с fallback).
- ✅ EOF убран (рефреш видео-источника в stream_source).
- ✅ camera.py stream-lifecycle не тронут (только +регистрация сущности).
- ✅ Один go2rtc, без экспозиции — следствие HA-native (по дизайну).
- Микрофон (uplink) — вне плана (Slice 2, по дизайну §1.5). ✅ корректно исключён.

**Placeholder scan:** один помеченный план-уточнение в Task 2 Step 5 (`go2rtc_headers`/`_SIP_DATA` ключ) — это указание реализатору свериться с точными именами в `go2rtc.py`/`__init__.py`, не плейсхолдер логики.

**Type consistency:** `active_call_media() -> (camera_id:str, bridge)`; `CALL_STREAM_NAME="eg_intercom_call"` (импорт из call_controller); `GO2RTC_RTSP_PORT` (const); `upsert_audio_stream(base, name, srcs:list, session, headers)` — сигнатуры совпадают с реализованными в сессии.
