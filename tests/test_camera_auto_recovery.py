"""Tests for A-71: auto-recovery стрима при истечении operator session (~30 мин).

Контекст (A-71 / ADR-0009):
- Operator forpost live-stream живёт ~30 мин, потом backend закрывает сессию
  → go2rtc producer EOF, HA Stream worker ретраит мёртвый `self.source` и
  `stream_source()` повторно НЕ зовётся → видео заморожено до ручного reopen.
- Fix: оборачиваем HA Stream update-callback. При переходе
  `stream.available → False` делаем throttled re-fetch свежего URL +
  `update_source()` — те же вызовы, что reopen в приложении / WebRTC re-offer.

Acceptance:
- available=False → recovery: fresh `get_camera_stream` + `update_source`.
- available=True → no recovery.
- cooldown: частые False-сигналы → не более 1 recovery в окне.
- entity unavailable (нет в coordinator.data) → no recovery.
- empty stream url → graceful (no `update_source`).
- go2rtc-path → recovery идёт через stream manager (PATCH + restart).
"""
from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.elektronny_gorod.const import (
    CONF_ACCESS_TOKEN,
    CONF_OPERATOR_ID,
    CONF_REFRESH_TOKEN,
    CONF_USER_AGENT,
    DOMAIN,
)
from custom_components.elektronny_gorod.go2rtc import Go2RtcStreamInfo
from custom_components.elektronny_gorod.user_agent import UserAgent

CAM_A = "100"
PLACE_ID = "P1"


def _places() -> list[dict[str, Any]]:
    return [{
        "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
        "place": {"id": PLACE_ID, "address": "addr"},
    }]


def _public_cameras() -> list[dict[str, Any]]:
    return [{"id": int(CAM_A), "externalCameraId": None, "name": "CamA"}]


def _screens_visible() -> dict[str, Any]:
    return {"screens": [
        {"type": "PUBLIC_CAMERAS",
         "entities": [{"id": int(CAM_A), "type": "PUBLIC_CAMERA", "order": 0}],
         "hidden": []},
        {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
    ]}


@pytest.fixture
def mock_api():
    """API mock: `query_camera_stream` возвращает unique URL per call."""
    with patch(
        "custom_components.elektronny_gorod.coordinator.ElektronnyGorodAPI"
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.http = AsyncMock()
        instance.http.user_agent = AsyncMock()
        instance.query_places = AsyncMock(return_value=_places())
        instance.query_balance = AsyncMock(return_value={})
        instance.query_access_controls = AsyncMock(return_value=[])
        instance.query_cameras = AsyncMock(return_value=[])
        instance.query_public_cameras = AsyncMock(return_value=_public_cameras())
        instance.query_screens_settings = AsyncMock(return_value=_screens_visible())
        instance.query_dnd_settings = AsyncMock(return_value=[])

        counter = {"n": 0}

        async def _stream(camera_id: str):
            counter["n"] += 1
            return f"https://op.example/stream/{camera_id}/token{counter['n']}.flv"

        instance.query_camera_stream = AsyncMock(side_effect=_stream)
        instance.query_camera_snapshot = AsyncMock(return_value=b"\x89PNG\r\n")
        yield mock_cls


def _make_config_entry(*, use_go2rtc: bool = False) -> MockConfigEntry:
    ua = UserAgent()
    ua.operator_id = "1"
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        unique_id="test_unique_subscriber_S1",
        title="Test",
        data={
            CONF_ACCESS_TOKEN: "T1",
            CONF_REFRESH_TOKEN: "R1",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(ua.json()),
            "account_id": "A1",
            "subscriber_id": "S1",
            "use_go2rtc": use_go2rtc,
            "go2rtc_base_url": "http://127.0.0.1:1984",
            "go2rtc_rtsp_host": "127.0.0.1",
        },
    )


def _get_camera_entity(hass: HomeAssistant, unique_id: str):
    from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
    component = hass.data.get(CAMERA_DOMAIN)
    if component is None:
        return None
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("camera", DOMAIN, unique_id)
    if entity_id is None:
        return None
    return component.get_entity(entity_id)


async def _setup_camera(hass: HomeAssistant, *, use_go2rtc: bool = False):
    entry = _make_config_entry(use_go2rtc=use_go2rtc)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    assert cam is not None
    return cam


def _fake_stream(available: bool) -> MagicMock:
    """Mock HA Stream объект: .available + .update_source()."""
    stream = MagicMock()
    stream.available = available
    return stream


# ─── Test A: unavailable → recovery (fresh fetch + update_source) ──────────


async def test_unavailable_stream_triggers_recovery(hass: HomeAssistant, mock_api):
    """available=False → fresh `get_camera_stream` + `update_source(fresh_url)`."""
    cam = await _setup_camera(hass, use_go2rtc=False)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()

    stream = _fake_stream(available=False)
    cam.stream = stream

    cam._on_stream_state_change()
    await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 1
    stream.update_source.assert_called_once()
    assert stream.update_source.call_args.args[0] is not None


# ─── Test B: available → no recovery ───────────────────────────────────────


async def test_available_stream_no_recovery(hass: HomeAssistant, mock_api):
    """available=True → recovery не запускается."""
    cam = await _setup_camera(hass, use_go2rtc=False)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()

    stream = _fake_stream(available=True)
    cam.stream = stream

    cam._on_stream_state_change()
    await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 0
    stream.update_source.assert_not_called()


# ─── Test C: cooldown — частые сигналы дают 1 recovery ─────────────────────


async def test_recovery_respects_cooldown(hass: HomeAssistant, mock_api):
    """Два быстрых available=False подряд → только 1 fetch (cooldown)."""
    cam = await _setup_camera(hass, use_go2rtc=False)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()

    stream = _fake_stream(available=False)
    cam.stream = stream

    cam._on_stream_state_change()
    cam._on_stream_state_change()  # сразу второй — внутри cooldown-окна
    await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 1


# ─── Test D: entity unavailable → no recovery ──────────────────────────────


async def test_no_recovery_when_entity_unavailable(hass: HomeAssistant, mock_api):
    """Камера отсутствует в coordinator.data (available=False у entity) →
    recovery не делает HTTP (нечего восстанавливать)."""
    cam = await _setup_camera(hass, use_go2rtc=False)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()

    # Убираем камеру из снапшота координатора → cam.available == False.
    cam.coordinator.data = {"cameras": [], "locks": [], "balances": [],
                            "places": _places(), "dnd": {}}
    assert cam.available is False

    stream = _fake_stream(available=False)
    cam.stream = stream

    cam._on_stream_state_change()
    await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 0
    stream.update_source.assert_not_called()


# ─── Test E: empty stream url → graceful ───────────────────────────────────


async def test_recovery_empty_url_graceful(hass: HomeAssistant, mock_api):
    """Operator вернул empty URL → recovery не зовёт `update_source` (no crash)."""
    cam = await _setup_camera(hass, use_go2rtc=False)
    instance = mock_api.return_value
    instance.query_camera_stream = AsyncMock(return_value=None)

    stream = _fake_stream(available=False)
    cam.stream = stream

    cam._on_stream_state_change()
    await hass.async_block_till_done()

    stream.update_source.assert_not_called()


# ─── Test F: go2rtc-path → recovery через stream manager ──────────


async def test_recovery_go2rtc_path_calls_manager(hass: HomeAssistant, mock_api):
    """use_go2rtc=True → manager mints, PATCHes and restarts HA Stream."""
    cam = await _setup_camera(hass, use_go2rtc=True)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()

    stream = _fake_stream(available=False)
    cam.stream = stream

    with patch.object(
        cam._stream_manager.client,
        "async_patch_stream",
        new=AsyncMock(),
    ) as mock_patch:
        cam._on_stream_state_change()
        await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 1
    mock_patch.assert_awaited_once()
    stream.update_source.assert_called_once_with(
        "rtsp://127.0.0.1:8554/eg_100"
    )


# ─── A-71 v2: go2rtc producer-health poll (go2rtc/WebRTC-only, лифты) ──────
#
# Контекст: камеры без legacy HA Stream worker (обслуживаются только через
# go2rtc/WebRTC — напр. лифты) не дают сигнала `stream.available → False`.
# Для них поллим go2rtc `/api/streams` producer `bytes_recv`: заморожен при
# наличии consumers → producer мёртв (operator EOF) → тот же recovery.


async def test_go2rtc_poll_frozen_triggers_recovery(hass: HomeAssistant, mock_api):
    """bytes_recv не растёт между опросами при consumers>0 → recovery."""
    cam = await _setup_camera(hass, use_go2rtc=True)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()
    cam._fetch_go2rtc_stream_info = AsyncMock(
        return_value=([{"bytes_recv": 1000}], [{}])
    )

    with patch.object(
        cam._stream_manager.client,
        "async_patch_stream",
        new=AsyncMock(),
    ) as mock_patch:
        await cam._async_poll_go2rtc_health()  # baseline (prev=None) — без recovery
        await cam._async_poll_go2rtc_health()  # тот же bytes_recv → frozen → recovery
        await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 1
    mock_patch.assert_awaited_once()


async def test_go2rtc_poll_first_call_only_baselines(hass: HomeAssistant, mock_api):
    """Первый опрос лишь ставит baseline — recovery не запускается."""
    cam = await _setup_camera(hass, use_go2rtc=True)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()
    cam._fetch_go2rtc_stream_info = AsyncMock(
        return_value=([{"bytes_recv": 1000}], [{}])
    )

    await cam._async_poll_go2rtc_health()
    await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 0
    assert cam._go2rtc_last_bytes_recv == 1000


async def test_go2rtc_poll_growing_no_recovery(hass: HomeAssistant, mock_api):
    """bytes_recv растёт (живой поток) → recovery не запускается."""
    cam = await _setup_camera(hass, use_go2rtc=True)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()
    cam._fetch_go2rtc_stream_info = AsyncMock(side_effect=[
        ([{"bytes_recv": 1000}], [{}]),
        ([{"bytes_recv": 2000}], [{}]),
        ([{"bytes_recv": 3000}], [{}]),
    ])

    for _ in range(3):
        await cam._async_poll_go2rtc_health()
    await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 0


async def test_go2rtc_poll_no_consumers_resets_baseline(hass: HomeAssistant, mock_api):
    """Нет consumers (никто не смотрит) → baseline сброшен, recovery нет даже
    при «замороженном» bytes_recv."""
    cam = await _setup_camera(hass, use_go2rtc=True)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()
    cam._fetch_go2rtc_stream_info = AsyncMock(
        return_value=([{"bytes_recv": 1000}], [])
    )

    await cam._async_poll_go2rtc_health()
    await cam._async_poll_go2rtc_health()
    await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 0
    assert cam._go2rtc_last_bytes_recv is None


async def test_go2rtc_poll_fetch_failure_graceful(hass: HomeAssistant, mock_api):
    """go2rtc недоступен / не-JSON (_fetch вернул None) → no-op, без падения."""
    cam = await _setup_camera(hass, use_go2rtc=True)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()
    cam._fetch_go2rtc_stream_info = AsyncMock(return_value=None)

    await cam._async_poll_go2rtc_health()
    await cam._async_poll_go2rtc_health()
    await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 0


async def test_health_poll_registered_only_for_go2rtc(hass: HomeAssistant, mock_api):
    """Таймер health-poll регистрируется для use_go2rtc, и НЕ для прямого FLV."""
    cam_go2rtc = await _setup_camera(hass, use_go2rtc=True)
    assert cam_go2rtc._unsub_health_poll is not None


async def test_health_poll_not_registered_without_go2rtc(
    hass: HomeAssistant, mock_api
):
    cam_direct = await _setup_camera(hass, use_go2rtc=False)
    assert cam_direct._unsub_health_poll is None


async def test_fetch_go2rtc_stream_info_parses_response(
    hass: HomeAssistant, mock_api
):
    """`_fetch_go2rtc_stream_info` парсит реальный shape go2rtc /api/streams.

    NB: используем прямой mock session.get вместо `aioresponses` — последний
    leak'ает aiohttp `_run_safe_shutdown_loop` thread на старых комбах
    HA/Python, что валит `verify_cleanup` фикстуру pytest-homeassistant.
    """
    cam = await _setup_camera(hass, use_go2rtc=True)

    cam._stream_manager.client.async_get_stream = AsyncMock(
        return_value=Go2RtcStreamInfo(
            producers=({"bytes_recv": 42},),
            consumer_count=1,
        )
    )

    info = await cam._fetch_go2rtc_stream_info()

    assert info is not None
    producers, consumers = info
    assert producers[0]["bytes_recv"] == 42
    assert isinstance(consumers, list) and len(consumers) == 1


# ─── A-71 v3: proactive keep-alive refresh (active streams only) ───────────
#
# DIAG (T20-08, 17ч): v1/v2 не покрывают реальный кейс — consumers падает с
# >0 до 0 ВНУТРИ 30с poll-окна, session-level cutoff операторского бэкенда
# бьёт ВСЕ потоки разом. Решение: proactive refresh ~25 мин, ТОЛЬКО для
# streams с активными consumers (не нагружаем сеть впустую).


async def test_proactive_refresh_active_consumers_triggers_recovery(
    hass: HomeAssistant, mock_api
):
    """consumers > 0 + cooldown прошёл → recovery scheduled."""
    cam = await _setup_camera(hass, use_go2rtc=True)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()
    # Cooldown давно прошёл. NB: используем relative offset от
    # `time.monotonic()`, а не 0.0 — в CI-контейнерах с малым uptime
    # `monotonic()-0.0` может быть < `min_age` (855s) → proactive skip.
    cam._last_recovery_monotonic = time.monotonic() - 10000.0
    cam._fetch_go2rtc_stream_info = AsyncMock(
        return_value=([{"bytes_recv": 100000}], [{}])
    )

    with patch.object(
        cam._stream_manager.client,
        "async_patch_stream",
        new=AsyncMock(),
    ) as mock_patch:
        await cam._async_proactive_refresh()
        await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 1
    mock_patch.assert_awaited_once()


async def test_proactive_refresh_no_consumers_skips(
    hass: HomeAssistant, mock_api
):
    """consumers == 0 → skip (нет смысла рефрешить кого никто не смотрит)."""
    cam = await _setup_camera(hass, use_go2rtc=True)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()
    cam._last_recovery_monotonic = time.monotonic() - 10000.0
    cam._fetch_go2rtc_stream_info = AsyncMock(
        return_value=([{"bytes_recv": 100000}], [])
    )

    await cam._async_proactive_refresh()
    await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 0


async def test_proactive_refresh_recent_cooldown_skips(
    hass: HomeAssistant, mock_api
):
    """Recent v1/v2 recovery → cooldown активен → skip."""
    cam = await _setup_camera(hass, use_go2rtc=True)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()
    # Только что было recovery (cooldown активен — refresh не нужен).
    cam._last_recovery_monotonic = time.monotonic()
    cam._fetch_go2rtc_stream_info = AsyncMock(
        return_value=([{"bytes_recv": 100000}], [{}])
    )

    await cam._async_proactive_refresh()
    await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 0


async def test_proactive_refresh_fetch_failure_graceful(
    hass: HomeAssistant, mock_api
):
    """go2rtc недоступен → skip без падений."""
    cam = await _setup_camera(hass, use_go2rtc=True)
    instance = mock_api.return_value
    instance.query_camera_stream.reset_mock()
    cam._last_recovery_monotonic = time.monotonic() - 10000.0
    cam._fetch_go2rtc_stream_info = AsyncMock(return_value=None)

    await cam._async_proactive_refresh()
    await hass.async_block_till_done()

    assert instance.query_camera_stream.await_count == 0


async def test_proactive_refresh_registered_only_for_go2rtc(
    hass: HomeAssistant, mock_api
):
    cam_go2rtc = await _setup_camera(hass, use_go2rtc=True)
    assert cam_go2rtc._unsub_proactive_refresh is not None


async def test_proactive_refresh_not_registered_without_go2rtc(
    hass: HomeAssistant, mock_api
):
    cam_direct = await _setup_camera(hass, use_go2rtc=False)
    assert cam_direct._unsub_proactive_refresh is None
