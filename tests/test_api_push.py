"""Тесты привязки FCM push-токена (api.py register/unregister_push_device).

Проверяем: register шлёт тело-зеркало на оба endpoint с pushToken; на ошибке
возвращает False; unregister шлёт DELETE.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.elektronny_gorod.api import (
    _DEVICE_INSTALLATIONS,
    _SUBSCRIBER_NOTIFICATIONS,
    ElektronnyGorodAPI,
)
from custom_components.elektronny_gorod.user_agent import UserAgent


class _FakeResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.ok = 200 <= status < 300
        self.reason = "OK" if self.ok else "Error"
        self.headers: dict = {}
        self.method = "POST"
        self.url = "https://example/"


@pytest.fixture
def fake_session() -> MagicMock:
    session = MagicMock()
    session.post = AsyncMock(return_value=_FakeResponse(200))
    session.delete = AsyncMock(return_value=_FakeResponse(200))
    return session


@pytest.fixture
def api(hass, fake_session, monkeypatch) -> ElektronnyGorodAPI:
    monkeypatch.setattr(
        "custom_components.elektronny_gorod.http.async_get_clientsession",
        lambda _hass: fake_session,
    )
    ua = UserAgent()
    ua.operator_id = "1"
    return ElektronnyGorodAPI(hass, ua, access_token="T1", refresh_token=None, operator="1")


async def test_register_posts_both_endpoints_with_push_token(api, fake_session):
    ok = await api.register_push_device("FCMTOKEN123")
    assert ok is True
    assert fake_session.post.await_count == 2
    urls = [call.args[0] for call in fake_session.post.await_args_list]
    assert any(_DEVICE_INSTALLATIONS in u for u in urls)
    assert any(_SUBSCRIBER_NOTIFICATIONS in u for u in urls)

    body = json.loads(fake_session.post.await_args_list[0].kwargs["data"])
    assert body["pushToken"] == "FCMTOKEN123"
    assert body["deviceType"] == "MOBILE_APPLICATION"
    assert body["platform"] == "google"
    assert body["appId"] == 2
    assert "installationId" in body and "deviceId" in body


async def test_register_returns_false_on_http_error(api, fake_session):
    fake_session.post = AsyncMock(return_value=_FakeResponse(500))
    assert await api.register_push_device("X") is False


async def test_unregister_sends_delete(api, fake_session):
    ok = await api.unregister_push_device()
    assert ok is True
    fake_session.delete.assert_awaited_once()
    assert _SUBSCRIBER_NOTIFICATIONS in fake_session.delete.await_args.args[0]
