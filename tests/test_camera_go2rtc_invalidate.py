"""Tests for A-66: invalidate go2rtc cached source при hidden→visible transition.

Контекст:
- `_ensure_go2rtc_stream` оптимизация — skip PUT в go2rtc если `_last_src ==
  src` (operator FLV URL не изменился между вызовами).
- Operator FLV URL содержит session token с TTL (минуты). За время пока
  камера hidden, токен в кешированном go2rtc producer expired.
- При un-hide HA Stream worker подключается к go2rtc → ffmpeg producer
  пытается открыть upstream с просроченным URL → fail (`Invalid data`).
- HA Stream делает retry-with-backoff (10s → 30s → 1m), на retry зовётся
  `stream_source()` → `_ensure_go2rtc_stream`. Если operator вернёт ТОТ ЖЕ
  URL → `_last_src == src` → skip PUT → producer всё ещё с тухлым URL.
- UX: юзер ждёт 10-30 сек, видит «не грузится», иногда вообще не получает.

Fix: detection hidden→visible в `stream_source`/`async_camera_image` —
invalidate `_last_src=None`, forcing fresh PUT при следующем вызове.
"""
from __future__ import annotations

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

CAMERA_ID = "100"
PLACE_ID = "P1"


def _places() -> list[dict[str, Any]]:
    return [{
        "subscriber": {"id": "S1", "accountId": "A1", "name": "Test"},
        "place": {"id": PLACE_ID, "address": "addr"},
    }]


def _public_cameras() -> list[dict[str, Any]]:
    return [{"id": int(CAMERA_ID), "externalCameraId": None, "name": "Cam"}]


def _screens_visible() -> dict[str, Any]:
    return {"screens": [
        {"type": "PUBLIC_CAMERAS",
         "entities": [{"id": int(CAMERA_ID), "type": "PUBLIC_CAMERA", "order": 0}],
         "hidden": []},
        {"type": "ACCESS_CONTROLS", "entities": [], "hidden": []},
    ]}


@pytest.fixture
def mock_api_go2rtc():
    """API mock + stable stream URL (чтобы _last_src проверка работала)."""
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
        # СТАБИЛЬНЫЙ URL — operator вернёт тот же URL подряд (тогда `_last_src` skip срабатывает).
        instance.query_camera_stream = AsyncMock(return_value="https://op.example/stream/SAME-TOKEN.flv")
        instance.query_camera_snapshot = AsyncMock(return_value=b"\x89PNG\r\n")
        yield mock_cls


def _make_config_entry(*, use_go2rtc: bool) -> MockConfigEntry:
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


# ─── Test A: оптимизация _last_src работает (regression guard) ──────────────


async def test_repeated_stream_source_skips_go2rtc_put_when_url_same(
    hass: HomeAssistant, mock_api_go2rtc
):
    """Regression: повторный stream_source с тем же operator URL skip-нет
    PUT в go2rtc (оптимизация _last_src сохранена)."""
    entry = _make_config_entry(use_go2rtc=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAMERA_ID}")
    assert cam is not None

    with patch(
        "custom_components.elektronny_gorod.camera._go2rtc_upsert_stream",
        new_callable=AsyncMock,
    ) as mock_put:
        await cam.stream_source()
        assert mock_put.await_count == 1, "Первый stream_source делает PUT"

        await cam.stream_source()
        assert mock_put.await_count == 1, (
            f"Повторный stream_source с тем же URL должен skip PUT, "
            f"got call_count={mock_put.await_count}"
        )


# ─── Test B: hidden→visible — invalidate force fresh PUT ────────────────────


async def test_hidden_to_visible_invalidates_go2rtc_cache(
    hass: HomeAssistant, mock_api_go2rtc
):
    """A-66: после hidden→visible transition `_last_src` invalidated,
    следующий stream_source делает fresh PUT (даже если operator URL тот же)."""
    entry = _make_config_entry(use_go2rtc=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAMERA_ID}")
    assert cam is not None

    registry = er.async_get(hass)

    with patch(
        "custom_components.elektronny_gorod.camera._go2rtc_upsert_stream",
        new_callable=AsyncMock,
    ) as mock_put:
        # 1: visible call → PUT
        await cam.stream_source()
        assert mock_put.await_count == 1

        # 2: hide camera
        registry.async_update_entity(cam.entity_id, hidden_by=er.RegistryEntryHider.USER)

        # 3: hidden call → None, no PUT
        result = await cam.stream_source()
        assert result is None
        assert mock_put.await_count == 1, "Hidden камера не должна делать PUT"

        # 4: un-hide
        registry.async_update_entity(cam.entity_id, hidden_by=None)

        # 5: visible call → fresh PUT (even though operator URL unchanged)
        await cam.stream_source()
        assert mock_put.await_count == 2, (
            f"После hidden→visible transition fresh PUT должен произойти, "
            f"got call_count={mock_put.await_count}"
        )

        # 6: subsequent stable call → skip PUT (back to normal оптимизация)
        await cam.stream_source()
        assert mock_put.await_count == 2


# ─── Test C: snapshot path тоже tracks transition (symmetry) ────────────────


async def test_snapshot_followed_by_unhide_stream_invalidates(
    hass: HomeAssistant, mock_api_go2rtc
):
    """A-66: если предыдущий вызов skip был на async_camera_image (snapshot),
    последующий stream_source after un-hide тоже invalidate-нет."""
    entry = _make_config_entry(use_go2rtc=True)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAMERA_ID}")
    registry = er.async_get(hass)

    with patch(
        "custom_components.elektronny_gorod.camera._go2rtc_upsert_stream",
        new_callable=AsyncMock,
    ) as mock_put:
        # Setup _last_src через initial stream_source
        await cam.stream_source()
        assert mock_put.await_count == 1

        # Hide
        registry.async_update_entity(cam.entity_id, hidden_by=er.RegistryEntryHider.USER)

        # Hidden snapshot call → skip, set _was_hidden
        await cam.async_camera_image()

        # Un-hide
        registry.async_update_entity(cam.entity_id, hidden_by=None)

        # Stream_source — должен invalidate (transition detected)
        await cam.stream_source()
        assert mock_put.await_count == 2, (
            f"После hidden snapshot → un-hide → stream_source fresh PUT, "
            f"got call_count={mock_put.await_count}"
        )


# ─── Test D: no-op для случая когда go2rtc disabled ─────────────────────────


async def test_no_op_when_go2rtc_disabled(
    hass: HomeAssistant, mock_api_go2rtc
):
    """A-66: для use_go2rtc=False транзишн detection не делает ничего вредного
    (нет PUT в go2rtc вообще, просто stream_url напрямую)."""
    entry = _make_config_entry(use_go2rtc=False)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    cam = _get_camera_entity(hass, f"{DOMAIN}_camera_{CAMERA_ID}")
    registry = er.async_get(hass)

    with patch(
        "custom_components.elektronny_gorod.camera._go2rtc_upsert_stream",
        new_callable=AsyncMock,
    ) as mock_put:
        # Visible call
        result = await cam.stream_source()
        assert result == "https://op.example/stream/SAME-TOKEN.flv", (
            "С use_go2rtc=False stream_source возвращает direct URL"
        )
        assert mock_put.await_count == 0

        # Hide → Un-hide cycle
        registry.async_update_entity(cam.entity_id, hidden_by=er.RegistryEntryHider.USER)
        assert await cam.stream_source() is None
        registry.async_update_entity(cam.entity_id, hidden_by=None)

        # Visible again — всё ещё direct URL, no go2rtc
        result = await cam.stream_source()
        assert result == "https://op.example/stream/SAME-TOKEN.flv"
        assert mock_put.await_count == 0
