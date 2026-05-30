"""Unit tests для validate_go2rtc / cleanup_go2rtc_stream.

Закрывают G-9: до сих пор `validate_go2rtc` тестировалась только через
mock-call в options-flow тесте (test_options_flow_clear_creds.py), сама
функция и её helper'ы прямого покрытия не имели. Это создавало риск
silent regression в HTTP-контракте с go2rtc API при рефакторинге.

Также покрывают G-7: TCP-probe RTSP-порта `(rtsp_host, 8554)` после
успешной HTTP-валидации. См. docs/audit/project-audit.md A-79.

NB: используем прямой mock session.* вместо `aioresponses` — последний
leak'ает aiohttp `_run_safe_shutdown_loop` thread на старых комбах
HA/Python, что валит `verify_cleanup` фикстуру pytest-homeassistant
(см. commit 091aa9d).
"""
from __future__ import annotations

import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientConnectionError

from custom_components.elektronny_gorod.go2rtc import (
    Go2RtcValidationResult,
    cleanup_go2rtc_stream,
    derive_rtsp_host,
    normalize_base_url,
    validate_go2rtc,
)


# ─── Helpers ────────────────────────────────────────────────────────────


class _AsyncCtxMgr:
    """Reusable async context manager returning a pre-built response mock."""

    def __init__(self, resp: Any) -> None:
        self._resp = resp

    async def __aenter__(self) -> Any:
        return self._resp

    async def __aexit__(self, *args: Any) -> bool:
        return False


def _make_resp(status: int, text: str = "") -> AsyncMock:
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    return resp


def _make_session(
    *,
    get_resp: AsyncMock | Exception | None = None,
    put_resp: AsyncMock | Exception | None = None,
    delete_resp: AsyncMock | Exception | None = None,
) -> MagicMock:
    """Build a mock session whose verb methods return pre-canned responses.

    Pass an `Exception` instance to make the verb raise on call (simulating
    `ClientError`); pass `None` to leave unmocked.
    """
    session = MagicMock()
    for verb, resp in (
        ("get", get_resp),
        ("put", put_resp),
        ("delete", delete_resp),
    ):
        if resp is None:
            continue
        if isinstance(resp, Exception):
            setattr(session, verb, MagicMock(side_effect=resp))
        else:
            setattr(session, verb, MagicMock(return_value=_AsyncCtxMgr(resp)))
    return session


# ─── normalize_base_url / derive_rtsp_host ──────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, ""),
        ("", ""),
        ("  ", ""),
        ("http://127.0.0.1:1984", "http://127.0.0.1:1984"),
        ("http://127.0.0.1:1984/", "http://127.0.0.1:1984"),
        ("  http://host:1984/  ", "http://host:1984"),
        ("http://host:1984///", "http://host:1984"),
    ],
)
def test_normalize_base_url(raw: str | None, expected: str) -> None:
    assert normalize_base_url(raw) == expected


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("http://127.0.0.1:1984", "127.0.0.1"),
        ("https://go2rtc.example.com:1984", "go2rtc.example.com"),
        ("http://host:1984/path", "host"),
        ("not a url", None),
        ("", None),
    ],
)
def test_derive_rtsp_host(base_url: str, expected: str | None) -> None:
    assert derive_rtsp_host(base_url) == expected


# ─── validate_go2rtc: early-exit paths ──────────────────────────────────


async def test_validate_returns_required_fields_when_url_empty() -> None:
    session = MagicMock()
    result = await validate_go2rtc("", session)
    assert result == Go2RtcValidationResult(False, "go2rtc_required_fields", None)


async def test_validate_returns_invalid_url_when_host_missing() -> None:
    session = MagicMock()
    result = await validate_go2rtc("not a url", session)
    assert result.ok is False
    assert result.error == "go2rtc_invalid_url"
    assert result.rtsp_host is None


# ─── validate_go2rtc: GET /api ──────────────────────────────────────────


async def test_validate_get_api_401_returns_auth_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """401 на GET /api → дискриминация от unreachable (G-6)."""
    session = _make_session(get_resp=_make_resp(401))
    monkeypatch.setattr(
        "custom_components.elektronny_gorod.go2rtc._probe_rtsp_port",
        AsyncMock(return_value=True),
    )
    result = await validate_go2rtc(
        "http://127.0.0.1:1984", session, username="u", password="p"
    )
    assert result.ok is False
    assert result.error == "go2rtc_auth_failed"
    assert result.rtsp_host == "127.0.0.1"


async def test_validate_get_api_500_returns_unreachable() -> None:
    session = _make_session(get_resp=_make_resp(500))
    result = await validate_go2rtc("http://127.0.0.1:1984", session)
    assert result.ok is False
    assert result.error == "go2rtc_unreachable"


async def test_validate_get_api_client_error_returns_unreachable() -> None:
    session = _make_session(get_resp=ClientConnectionError("connection refused"))
    result = await validate_go2rtc("http://127.0.0.1:1984", session)
    assert result.ok is False
    assert result.error == "go2rtc_unreachable"


async def test_validate_basic_auth_header_sent_when_creds_set() -> None:
    """Sanity: при заданных creds в GET /api идёт Basic <b64>."""
    get_resp = _make_resp(200)
    put_resp = _make_resp(200)
    delete_resp = _make_resp(204)
    session = _make_session(
        get_resp=get_resp, put_resp=put_resp, delete_resp=delete_resp
    )

    with patch(
        "custom_components.elektronny_gorod.go2rtc._probe_rtsp_port",
        new=AsyncMock(return_value=True),
    ):
        await validate_go2rtc(
            "http://127.0.0.1:1984", session, username="alice", password="s3cr3t"
        )

    expected_b64 = base64.b64encode(b"alice:s3cr3t").decode()
    expected_header = f"Basic {expected_b64}"
    # Все три verb-метода должны были получить наш Authorization header
    for verb in ("get", "put", "delete"):
        call = getattr(session, verb).call_args
        assert call is not None
        assert call.kwargs["headers"]["Authorization"] == expected_header


# ─── validate_go2rtc: PUT /api/streams ──────────────────────────────────


async def test_validate_put_streams_401_returns_auth_failed() -> None:
    """401 на PUT тоже трактуется как auth_failed (а не streams_api_failed)."""
    session = _make_session(
        get_resp=_make_resp(200),
        put_resp=_make_resp(401),
        delete_resp=_make_resp(404),
    )
    result = await validate_go2rtc("http://127.0.0.1:1984", session)
    assert result.ok is False
    assert result.error == "go2rtc_auth_failed"


async def test_validate_put_streams_500_returns_streams_api_failed() -> None:
    session = _make_session(
        get_resp=_make_resp(200),
        put_resp=_make_resp(500, text="boom"),
        delete_resp=_make_resp(404),
    )
    result = await validate_go2rtc("http://127.0.0.1:1984", session)
    assert result.ok is False
    assert result.error == "go2rtc_streams_api_failed"


async def test_validate_put_streams_client_error_returns_streams_api_failed() -> None:
    session = _make_session(
        get_resp=_make_resp(200),
        put_resp=ClientConnectionError("rst"),
        delete_resp=_make_resp(404),
    )
    result = await validate_go2rtc("http://127.0.0.1:1984", session)
    assert result.ok is False
    assert result.error == "go2rtc_streams_api_failed"


async def test_validate_cleanup_runs_even_if_put_fails() -> None:
    """`finally` блок: DELETE вызывается даже когда PUT упал."""
    delete_called = MagicMock()
    delete_resp = _make_resp(204)
    session = MagicMock()
    session.get = MagicMock(return_value=_AsyncCtxMgr(_make_resp(200)))
    session.put = MagicMock(return_value=_AsyncCtxMgr(_make_resp(500, text="x")))

    def _delete_tracker(*args: Any, **kwargs: Any) -> _AsyncCtxMgr:
        delete_called(*args, **kwargs)
        return _AsyncCtxMgr(delete_resp)

    session.delete = MagicMock(side_effect=_delete_tracker)

    await validate_go2rtc("http://127.0.0.1:1984", session)
    assert delete_called.called


# ─── validate_go2rtc: happy path + RTSP probe (G-7) ─────────────────────


async def test_validate_happy_path_returns_ok() -> None:
    session = _make_session(
        get_resp=_make_resp(200),
        put_resp=_make_resp(200),
        delete_resp=_make_resp(204),
    )
    with patch(
        "custom_components.elektronny_gorod.go2rtc._probe_rtsp_port",
        new=AsyncMock(return_value=True),
    ):
        result = await validate_go2rtc("http://127.0.0.1:1984", session)
    assert result == Go2RtcValidationResult(True, "", "127.0.0.1")


async def test_validate_returns_rtsp_port_closed_when_probe_fails() -> None:
    """G-7: TCP-probe RTSP-порта неудачен → отдельный error key.

    Не fatal по архитектуре (см. ADR / audit A-79), но в options-flow
    показывается отдельным сообщением — юзеру понятнее чем «всё ок».
    """
    session = _make_session(
        get_resp=_make_resp(200),
        put_resp=_make_resp(200),
        delete_resp=_make_resp(204),
    )
    with patch(
        "custom_components.elektronny_gorod.go2rtc._probe_rtsp_port",
        new=AsyncMock(return_value=False),
    ):
        result = await validate_go2rtc("http://127.0.0.1:1984", session)
    assert result.ok is False
    assert result.error == "go2rtc_rtsp_port_closed"
    assert result.rtsp_host == "127.0.0.1"


# ─── cleanup_go2rtc_stream ──────────────────────────────────────────────


async def test_cleanup_noop_when_base_url_empty() -> None:
    session = MagicMock()
    await cleanup_go2rtc_stream("", "name", session)
    assert not session.delete.called


async def test_cleanup_noop_when_stream_name_empty() -> None:
    session = MagicMock()
    await cleanup_go2rtc_stream("http://127.0.0.1:1984", "", session)
    assert not session.delete.called


async def test_cleanup_passes_src_query_param() -> None:
    """go2rtc DELETE handler берёт `?src=<name>` (см. internal/streams/api.go)."""
    session = _make_session(delete_resp=_make_resp(204))
    await cleanup_go2rtc_stream("http://127.0.0.1:1984", "my_stream", session)
    call = session.delete.call_args
    assert call is not None
    (url,) = call.args
    assert "src=my_stream" in url


async def test_cleanup_swallows_404() -> None:
    session = _make_session(delete_resp=_make_resp(404))
    # должен завершиться без exceptions
    await cleanup_go2rtc_stream("http://127.0.0.1:1984", "gone", session)


async def test_cleanup_swallows_client_error() -> None:
    session = _make_session(delete_resp=ClientConnectionError("nope"))
    await cleanup_go2rtc_stream("http://127.0.0.1:1984", "stream", session)
