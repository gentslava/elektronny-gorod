"""Unit-тесты DoorbellCallController (sip/call_controller.py).

Чистая логика HA-glue: трекинг активного FCM-вызова (ring/ended/окно
CallInvalidated) + guard ответа (Call-ID binding, call-answer-model.md §6.5).
SIP-сеть (SipManager) замокана — её доказывает probe/живой звонок, не юнит.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.elektronny_gorod.sip.call_controller import (
    EVENT_SIP_CALL,
    DoorbellCallController,
)

_MGR_PATH = "custom_components.elektronny_gorod.sip.call_controller.SipManager"


def _hass() -> MagicMock:
    """hass-мок: async_create_task закрывает корутину (hold-таск не виснет в unit)."""
    hass = MagicMock()
    hass.async_create_task = lambda coro, *a, **k: coro.close()
    return hass


def _ring(call_id="c1", place="P", ac="A", invalidated=None) -> dict:
    attrs: dict = {"call_id": call_id}
    if invalidated:
        attrs["call_invalidated"] = invalidated
    return {
        "event_type": "ring",
        "place_id": place,
        "access_control_id": ac,
        "attributes": attrs,
    }


def _ended(call_id="c1", place="P", ac="A") -> dict:
    return {
        "event_type": "ended",
        "place_id": place,
        "access_control_id": ac,
        "attributes": {"call_id": call_id},
    }


@pytest.fixture
def controller() -> DoorbellCallController:
    api = MagicMock()
    api.mint_sip_device = AsyncMock(
        return_value={"login": "l", "password": "p", "realm": "r"}
    )
    return DoorbellCallController(_hass(), api, lambda: "FCMTOK")


def test_ring_tracked_then_ended_cleared(controller):
    controller.handle_signal(_ring())
    assert controller.current_call() is not None
    controller.handle_signal(_ended())
    assert controller.current_call() is None


def test_no_ring_no_active_call(controller):
    assert controller.current_call() is None


def test_call_expired_after_invalidated_deadline(controller):
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    controller.handle_signal(_ring(invalidated=past))
    # дедлайн в прошлом → не считается активным.
    assert controller.current_call() is None


def test_ended_for_other_call_id_does_not_clear(controller):
    controller.handle_signal(_ring(call_id="c1"))
    controller.handle_signal(_ended(call_id="OTHER"))
    assert controller.current_call() is not None


async def test_answer_refused_without_active_call(controller):
    assert await controller.async_answer() is False
    controller._api.mint_sip_device.assert_not_called()


async def test_answer_refused_without_fcm_token():
    api = MagicMock()
    api.mint_sip_device = AsyncMock()
    c = DoorbellCallController(_hass(), api, lambda: None)
    c.handle_signal(_ring())
    assert await c.async_answer() is False
    api.mint_sip_device.assert_not_called()


async def test_answer_mints_for_active_call_and_drives_manager(controller):
    controller.handle_signal(_ring(place="PLACE", ac="AC"))
    with patch(_MGR_PATH) as MgrCls:
        mgr = MgrCls.return_value
        mgr.in_call = False
        mgr.async_answer = AsyncMock(return_value=True)
        ok = await controller.async_answer()

    assert ok is True
    # SipManager сконструирован с FCM-токеном (для REGISTER push-params).
    assert MgrCls.call_args.args[0] == "FCMTOK"
    # mint привязан к ids активного вызова (Call-ID binding).
    creds_factory = mgr.async_answer.await_args.args[0]
    creds = await creds_factory()
    controller._api.mint_sip_device.assert_awaited_once_with("PLACE", "AC")
    assert creds == {"login": "l", "password": "p", "realm": "r"}


async def test_answer_refused_when_already_in_call(controller):
    controller.handle_signal(_ring())
    with patch(_MGR_PATH) as MgrCls:
        mgr = MgrCls.return_value
        mgr.in_call = False
        mgr.async_answer = AsyncMock(return_value=True)
        assert await controller.async_answer() is True
        # второй answer при активном разговоре → отказ, новый mint не вызывается.
        mgr.in_call = True
        controller._api.mint_sip_device.reset_mock()
        assert await controller.async_answer() is False
        controller._api.mint_sip_device.assert_not_called()


_CC = "custom_components.elektronny_gorod.sip.call_controller"


async def test_answer_with_go2rtc_sets_up_bridge():
    from custom_components.elektronny_gorod.sip.call_controller import (
        DoorbellCallController,
        Go2RtcConfig,
    )

    api = MagicMock()
    api.mint_sip_device = AsyncMock(return_value={"login": "l", "password": "p", "realm": "r"})
    c = DoorbellCallController(
        _hass(), api, lambda: "TOK", go2rtc=Go2RtcConfig("http://g:1984", {}, "127.0.0.1")
    )
    c.handle_signal(_ring())  # hold-таск закрыт (_hass) → answer идёт fallback-путём

    upsert = AsyncMock()
    with patch(_MGR_PATH) as MgrCls, patch(f"{_CC}.AudioBridge") as BridgeCls, patch(
        f"{_CC}.detect_lan_ip", return_value="1.2.3.4"
    ):
        bridge = BridgeCls.return_value
        bridge.start = AsyncMock()
        bridge.go2rtc_src = "ffmpeg:http://1.2.3.4:40020#audio=opus"
        mgr = MgrCls.return_value
        mgr.in_call = False
        mgr.async_answer = AsyncMock(return_value=True)
        ok = await c.async_answer()

    assert ok is True
    bridge.start.assert_awaited_once()
    assert mgr.async_answer.await_args.kwargs["on_downlink"] is bridge.feed_downlink
    # upsert на accept больше НЕ происходит (его делает camera.intercom_call)
    upsert.assert_not_awaited()


async def test_answer_without_go2rtc_uses_counter_sink(controller):
    # go2rtc=None → мост не поднимается, on_downlink = счётчик (degrade).
    controller.handle_signal(_ring())
    with patch(_MGR_PATH) as MgrCls, patch(f"{_CC}.AudioBridge") as BridgeCls:
        mgr = MgrCls.return_value
        mgr.in_call = False
        mgr.async_answer = AsyncMock(return_value=True)
        await controller.async_answer()
    BridgeCls.assert_not_called()
    assert mgr.async_answer.await_args.kwargs["on_downlink"] == controller._count_downlink


async def test_hangup_tears_down_manager(controller):
    controller._manager = MagicMock()
    controller._manager.async_hangup = AsyncMock()
    mgr = controller._manager
    await controller.async_hangup()
    mgr.async_hangup.assert_awaited_once()
    assert controller._manager is None


# ---- register-on-ring (ADR-0012) ----
async def test_ring_holds_via_register_and_hold():
    # ring → _async_hold_current регистрирует и держит INVITE (mint привязан к вызову).
    api = MagicMock()
    api.mint_sip_device = AsyncMock(return_value={"login": "l", "password": "p", "realm": "r"})
    c = DoorbellCallController(_hass(), api, lambda: "TOK")
    c.handle_signal(_ring(place="PLACE", ac="AC"))
    with patch(_MGR_PATH) as MgrCls:
        mgr = MgrCls.return_value
        mgr.register_and_hold = AsyncMock(return_value=True)
        await c._async_hold_current()
    mgr.register_and_hold.assert_awaited_once()
    assert c._manager is mgr  # держим менеджер
    mint_factory = mgr.register_and_hold.await_args.args[0]
    await mint_factory()
    api.mint_sip_device.assert_awaited_once_with("PLACE", "AC")


async def test_answer_accepts_held_invite_without_reregister():
    # Держим INVITE → answer вызывает accept (быстрый путь), не async_answer.
    api = MagicMock()
    api.mint_sip_device = AsyncMock(return_value={"login": "l", "password": "p", "realm": "r"})
    c = DoorbellCallController(_hass(), api, lambda: "TOK")
    c.handle_signal(_ring())
    held = MagicMock()
    held.holding = True
    held.in_call = False
    held.accept = AsyncMock(return_value=True)
    c._manager = held  # имитируем поднятый hold
    ok = await c.async_answer()
    assert ok is True
    held.accept.assert_awaited_once()  # accept держимого INVITE
    held.async_answer.assert_not_called()  # без повторного register-on-answer


async def test_cancel_dismisses_screen():
    # _on_ring_cancelled → EVENT_SIP_CALL active=false (чистит хелпер) + снят менеджер.
    c = DoorbellCallController(_hass(), MagicMock(), lambda: "TOK")
    c._manager = MagicMock()
    c._on_ring_cancelled()
    assert c._manager is None
    c._hass.bus.async_fire.assert_called_with(EVENT_SIP_CALL, {"active": False})


async def test_active_call_media_returns_camera_and_bridge():
    from custom_components.elektronny_gorod.sip.call_controller import (
        DoorbellCallController,
        Go2RtcConfig,
    )

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
