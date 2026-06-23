"""Тесты mint SIP-устройства (api.mint_sip_device).

Зеркало приложения: POST sipdevices с installationId аккаунта (UA.uuid) →
{login, password, realm}. См. docs/.../call-answer-model.md §4, design.md §2.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientError, ClientResponse

from custom_components.elektronny_gorod.api import ElektronnyGorodAPI
from custom_components.elektronny_gorod.user_agent import UserAgent

_CREDS = {"login": "sip-login", "password": "sip-pass", "realm": "ac.intercom.op.ru"}


def _FakeResponse(status: int = 200, payload: dict | None = None) -> MagicMock:
    # spec=ClientResponse — проходит isinstance(response, ClientResponse) в api.
    resp = MagicMock(spec=ClientResponse)
    resp.status = status
    resp.ok = 200 <= status < 300
    resp.reason = "OK" if resp.ok else "Error"
    resp.headers = {}
    resp.method = "POST"
    resp.url = "https://example/"
    resp.json = AsyncMock(return_value=payload or {})
    return resp


@pytest.fixture
def fake_session() -> MagicMock:
    session = MagicMock()
    session.post = AsyncMock(return_value=_FakeResponse(200, {"data": _CREDS}))
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


async def test_mint_sip_device_posts_installation_id_and_returns_creds(api, fake_session):
    creds = await api.mint_sip_device("PLACE", "AC")

    assert creds == _CREDS
    # endpoint + тело — зеркало приложения (installationId = UA.uuid).
    url = fake_session.post.await_args.args[0]
    assert "/rest/v1/places/PLACE/accesscontrols/AC/sipdevices" in url
    body = json.loads(fake_session.post.await_args.kwargs["data"])
    assert body == {"installationId": api.http.user_agent.uuid}


async def test_mint_sip_device_raises_on_http_error(api, fake_session):
    fake_session.post = AsyncMock(return_value=_FakeResponse(403))
    with pytest.raises(ClientError):
        await api.mint_sip_device("PLACE", "AC")


async def test_mint_sip_device_null_data_returns_empty_dict(api, fake_session):
    # backend может отдать {"data": null} — не должно просочиться None в SipManager.
    fake_session.post = AsyncMock(return_value=_FakeResponse(200, {"data": None}))
    assert await api.mint_sip_device("PLACE", "AC") == {}
