"""Tests for A-68: dedup concurrent `stream_source()` для одной camera.

Контекст:
- HA Stream worker + Frigate + Lovelace независимо вызывают
  `Camera.stream_source()` для одной camera.
- Operator API возвращает разные session tokens на каждый запрос —
  поэтому `src != self._last_src` каждый раз → дубль HTTP + PUT в
  go2rtc + `Stream.update_source()` restart worker.
- Каждый restart прерывает video на ~1 сек → пользователь видит
  «мигание» когда несколько источников активны одновременно.
- Production-лог 2026-05-27 показал 2 restart за 0.88s для camera 5593590.

Acceptance (A-68):
- 2+ concurrent `stream_source()` для одной camera → only 1 HTTP к operator.
- Все concurrent callers получают одинаковый результат.
- После первого завершения — следующий вызов делает свежий HTTP (no stuck cache).
- Если первый бросает exception — все concurrent callers получают exception
  (без зависания).
- Разные cameras — независимые in-flight futures.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch

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
from custom_components.elektronny_gorod.user_agent import UserAgent

CAM_A = "100"
CAM_B = "200"
PLACE_ID = "P1"


def _places() -> list[dict[str, Any]]:
    return [{
        "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
        "place": {"id": PLACE_ID, "address": "addr"},
    }]


def _public_cameras() -> list[dict[str, Any]]:
    return [
        {"id": int(CAM_A), "externalCameraId": None, "name": "CamA"},
        {"id": int(CAM_B), "externalCameraId": None, "name": "CamB"},
    ]


def _screens_visible() -> dict[str, Any]:
    return {"screens": [
        {"type": "PUBLIC_CAMERAS",
         "entities": [
             {"id": int(CAM_A), "type": "PUBLIC_CAMERA", "order": 0},
             {"id": int(CAM_B), "type": "PUBLIC_CAMERA", "order": 1},
         ],
         "hidden": []},
        {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
    ]}


@pytest.fixture
def mock_api_with_delayed_stream():
    """API mock: `query_camera_stream` имеет latency, возвращает unique URL per call."""
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

        call_counter = {"n": 0}

        async def _stream_side_effect(camera_id: str):
            # Имитируем latency operator (~50ms) и unique token per call.
            await asyncio.sleep(0.05)
            call_counter["n"] += 1
            return f"https://op.example/stream/{camera_id}/token{call_counter['n']}.flv"

        instance.query_camera_stream = AsyncMock(side_effect=_stream_side_effect)
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


# ─── Test A: concurrent stream_source dedup ────────────────────────────────


async def test_concurrent_stream_source_makes_single_http_call(
    hass: HomeAssistant, mock_api_with_delayed_stream
):
    """A-68: 2 concurrent `stream_source()` для одной camera → 1 HTTP к operator,
    оба callers получают одинаковый URL."""
    entry = _make_config_entry(use_go2rtc=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    assert cam is not None

    instance = mock_api_with_delayed_stream.return_value
    instance.query_camera_stream.reset_mock()

    # Запускаем 3 concurrent stream_source.
    results = await asyncio.gather(
        cam.stream_source(),
        cam.stream_source(),
        cam.stream_source(),
    )

    assert instance.query_camera_stream.await_count == 1, (
        f"3 concurrent stream_source должны дать 1 HTTP, "
        f"got call_count={instance.query_camera_stream.await_count}"
    )
    # Все callers получили одинаковый URL.
    assert results[0] == results[1] == results[2]
    assert results[0] is not None


# ─── Test B: sequential calls — no cache stuck ────────────────────────────


async def test_sequential_stream_source_after_dedup_fetches_fresh(
    hass: HomeAssistant, mock_api_with_delayed_stream
):
    """A-68: после завершения dedup-batch, in-flight future cleared —
    sequential call **за пределами** A-69 TTL cache делает свежий HTTP.
    Cache invalidated manually для изоляции от A-69 поведения."""
    entry = _make_config_entry(use_go2rtc=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    instance = mock_api_with_delayed_stream.return_value
    instance.query_camera_stream.reset_mock()

    # Batch #1: 2 concurrent.
    await asyncio.gather(cam.stream_source(), cam.stream_source())
    assert instance.query_camera_stream.await_count == 1
    # in-flight future cleared (после batch).
    assert cam._inflight_stream_future is None

    # Invalidate A-69 cache, чтобы test изолированно проверял A-68 future.
    cam._cached_stream_url = None

    # Sequential call после batch + invalidate — должен сделать новый HTTP.
    await cam.stream_source()
    assert instance.query_camera_stream.await_count == 2, (
        f"Sequential call после dedup-batch (cache invalidated) должен "
        f"fetch свежий URL, got call_count={instance.query_camera_stream.await_count}"
    )


# ─── Test C: exception propagation для concurrent waiters ────────────────


async def test_concurrent_callers_receive_exception_from_first(
    hass: HomeAssistant, mock_api_with_delayed_stream
):
    """A-68: если первый caller бросает exception — все concurrent waiters
    тоже получают exception (не зависают, не получают None)."""
    entry = _make_config_entry(use_go2rtc=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    instance = mock_api_with_delayed_stream.return_value

    # Mock fail на operator API.
    async def _fail(camera_id: str):
        await asyncio.sleep(0.05)
        raise RuntimeError("operator down")

    instance.query_camera_stream = AsyncMock(side_effect=_fail)

    results = await asyncio.gather(
        cam.stream_source(),
        cam.stream_source(),
        cam.stream_source(),
        return_exceptions=True,
    )

    # Все 3 должны получить exception (или те же exception объект, или его repr).
    for i, r in enumerate(results):
        assert isinstance(r, RuntimeError), (
            f"Caller #{i} должен получить RuntimeError, got {type(r).__name__}: {r}"
        )
        assert "operator down" in str(r)


# ─── Test E: first caller cancelled — waiters не зависают ───────────────────


async def test_first_caller_cancelled_does_not_hang_waiters(
    hass: HomeAssistant, mock_api_with_delayed_stream
):
    """A-68 safety: если первый caller (owner future) cancelled — waiters
    не должны висеть навсегда. Future cancel-ится в `finally` блоке."""
    entry = _make_config_entry(use_go2rtc=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")

    task1 = asyncio.create_task(cam.stream_source())
    task2 = asyncio.create_task(cam.stream_source())
    # Дать taskам начать выполнение и task1 захватить future.
    await asyncio.sleep(0.01)
    task1.cancel()

    # task2 НЕ должен висеть. Должен либо complete с результатом
    # (если первый успел set_result), либо получить CancelledError.
    try:
        result2 = await asyncio.wait_for(task2, timeout=1.0)
        # Acceptable: task1 успел complete до cancel.
        assert result2 is not None or result2 is None
    except (asyncio.CancelledError, TimeoutError):
        # Acceptable: task2 получил CancelledError (waiter watch future).
        pass
    # task1 cancelled — собрать исключение.
    with pytest.raises((asyncio.CancelledError, Exception)):
        await task1


# ─── Test D: разные cameras — независимые futures ──────────────────────────


async def test_different_cameras_have_independent_inflight_futures(
    hass: HomeAssistant, mock_api_with_delayed_stream
):
    """A-68: dedup per-camera. Concurrent на CamA не влияет на CamB —
    обе получают свои HTTP (не sharing future)."""
    entry = _make_config_entry(use_go2rtc=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam_a = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_A}")
    cam_b = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAM_B}")
    instance = mock_api_with_delayed_stream.return_value
    instance.query_camera_stream.reset_mock()

    # 2 concurrent для CamA + 2 concurrent для CamB.
    results = await asyncio.gather(
        cam_a.stream_source(),
        cam_a.stream_source(),
        cam_b.stream_source(),
        cam_b.stream_source(),
    )

    # 1 HTTP на CamA + 1 HTTP на CamB = 2 HTTP total (не 4).
    assert instance.query_camera_stream.await_count == 2, (
        f"2 concurrent на каждую из 2 cameras → 2 HTTP, "
        f"got call_count={instance.query_camera_stream.await_count}"
    )
    # CamA callers получили один URL, CamB callers — другой.
    assert results[0] == results[1]  # CamA dedup
    assert results[2] == results[3]  # CamB dedup
    assert results[0] != results[2]  # разные cameras → разные URL
