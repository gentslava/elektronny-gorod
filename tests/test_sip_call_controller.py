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
    DoorbellCallController,
)

_MGR_PATH = "custom_components.elektronny_gorod.sip.call_controller.SipManager"


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
    return DoorbellCallController(MagicMock(), api, lambda: "FCMTOK")


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
    c = DoorbellCallController(MagicMock(), api, lambda: None)
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


async def test_hangup_tears_down_manager(controller):
    controller._manager = MagicMock()
    controller._manager.async_hangup = AsyncMock()
    mgr = controller._manager
    await controller.async_hangup()
    mgr.async_hangup.assert_awaited_once()
    assert controller._manager is None
