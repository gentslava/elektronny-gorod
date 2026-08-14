"""Тесты FCM-listener (fcm.py).

Без реального Google: парсинг пуша → SIGNAL_DOORBELL; старт регистрирует токен;
сбой checkin не валит (graceful degradation). firebase-messaging замокан.
"""
from __future__ import annotations

import asyncio
from base64 import urlsafe_b64encode
import binascii
from datetime import UTC, datetime, timedelta
import json
import logging
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import issue_registry as ir

from custom_components.elektronny_gorod.const import DOMAIN, LOGGER, SIGNAL_DOORBELL
from custom_components.elektronny_gorod.fcm import (
    FCM_ABORT_AFTER_ERRORS,
    FCM_RETRY_BACKOFFS,
    DoorbellFcmListener,
    _FcmRecoveryPhase,
    _b64_pad,
    _normalize_push_header,
    _patch_push_headers,
    async_delete_fcm_repair_issue,
    fcm_repair_issue_id,
)

NOW = datetime(2026, 8, 10, 9, 0, tzinfo=UTC)


def _listener(
    hass: HomeAssistant,
    *,
    entry_id: str = "entry-1",
    title: str = "Аккаунт 1",
):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.title = title
    entry.data = {}
    entry.disabled_by = None
    api = MagicMock()
    api.register_push_device = AsyncMock(return_value=True)
    return DoorbellFcmListener(hass, entry, api), api


def _create_repair_issue(
    hass: HomeAssistant, entry_id: str = "entry-1"
) -> None:
    """Create the persistent FCM issue used as test precondition."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        fcm_repair_issue_id(entry_id),
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="fcm_receiver_unavailable",
    )


def _capture(hass: HomeAssistant) -> list:
    got: list = []
    async_dispatcher_connect(hass, SIGNAL_DOORBELL, lambda p: got.append(p))
    return got


async def test_call_incoming_dispatches_ring(hass: HomeAssistant):
    listener, _ = _listener(hass)
    got = _capture(hass)
    listener._on_notification({"data": {
        "PushType": "CALL_INCOMING", "PlaceId": "P1", "AccessControlId": "AC1",
        "GateName": "Подъезд 1", "Apartment": "57", "Call-ID": "C1", "AllowOpen": "true",
    }}, "pid")
    await hass.async_block_till_done()
    assert len(got) == 1
    payload = got[0]
    assert payload["event_type"] == "ring"
    assert payload["place_id"] == "P1"
    assert payload["access_control_id"] == "AC1"
    assert payload["attributes"]["call_id"] == "C1"
    assert payload["attributes"]["gate_name"] == "Подъезд 1"


async def test_call_end_dispatches_ended(hass: HomeAssistant):
    listener, _ = _listener(hass)
    got = _capture(hass)
    listener._on_notification({"data": {
        "PushType": "CALL_END_ANSWERED_MOBILE", "PlaceId": "P1",
        "AccessControlId": "AC1", "Call-ID": "C1",
    }}, "pid")
    await hass.async_block_till_done()
    assert got[0]["event_type"] == "ended"
    assert got[0]["attributes"]["reason"] == "answered_elsewhere"


async def test_unknown_push_type_ignored(hass: HomeAssistant):
    listener, _ = _listener(hass)
    got = _capture(hass)
    listener._on_notification({"data": {"PushType": "SOMETHING_ELSE"}}, "pid")
    await hass.async_block_till_done()
    assert got == []


async def test_notification_after_stop_is_ignored(hass: HomeAssistant):
    """A terminally removed listener cannot publish late dependency callbacks."""
    listener, _ = _listener(hass)
    got = _capture(hass)
    listener._stopping = True

    listener._on_notification(
        {"data": {"PushType": "CALL_INCOMING", "PlaceId": "P1"}}, "pid"
    )
    await hass.async_block_till_done()

    assert got == []


async def test_async_start_registers_token(hass: HomeAssistant):
    listener, api = _listener(hass)
    fake_client = MagicMock()
    fake_client.checkin_or_register = AsyncMock(return_value="FCMTOKEN")
    fake_client.start = AsyncMock()
    fake_client.stop = AsyncMock()
    with patch("firebase_messaging.FcmPushClient", return_value=fake_client), \
         patch("firebase_messaging.FcmRegisterConfig"):
        await listener.async_start()
    api.register_push_device.assert_awaited_once_with("FCMTOKEN")
    fake_client.start.assert_awaited_once()
    await listener.async_stop()


async def test_async_start_graceful_on_error(hass: HomeAssistant):
    """Сбой до start не вызывает несовместимый dependency stop()."""
    listener, _ = _listener(hass)
    fake_client = MagicMock()
    fake_client.checkin_or_register = AsyncMock(side_effect=RuntimeError("google down"))
    fake_client.stop = AsyncMock(
        side_effect=TypeError("stopping_lock is not initialized before start")
    )
    with patch("firebase_messaging.FcmPushClient", return_value=fake_client), \
         patch("firebase_messaging.FcmRegisterConfig"):
        await listener.async_start()
    assert listener._client is None
    fake_client.stop.assert_not_awaited()
    await listener.async_stop()


async def test_async_start_uses_ha_shared_http_session(
    hass: HomeAssistant,
) -> None:
    """FCM registration reuses HA's session, including failure paths."""
    listener, _ = _listener(hass)
    shared_session = object()
    fake_client = MagicMock()
    fake_client.checkin_or_register = AsyncMock(
        side_effect=RuntimeError("checkin failed")
    )
    fake_client.stop = AsyncMock()

    with (
        patch(
            "firebase_messaging.FcmPushClient", return_value=fake_client
        ) as client_cls,
        patch("firebase_messaging.FcmRegisterConfig"),
        patch(
            "custom_components.elektronny_gorod.fcm.async_get_clientsession",
            return_value=shared_session,
            create=True,
        ),
    ):
        await listener.async_start()

    assert client_cls.call_args.kwargs["http_client_session"] is shared_session
    assert listener._client is None
    await listener.async_stop()


async def test_retry_and_probe_failures_do_not_log_exception_message(
    hass: HomeAssistant,
    caplog,
) -> None:
    """Initial, immediate retry and scheduled probe all redact exception text.

    Покрывает и первичный connect: `_async_connect` логирует ошибку ровно в
    одном месте, а этот тест проходит через него трижды.
    """
    listener, _ = _listener(hass)
    secret = "REPEATED-FCM-EXCEPTION-SECRET"
    fake_client = MagicMock()
    fake_client.checkin_or_register = AsyncMock(
        side_effect=RuntimeError(secret)
    )
    fake_client.stop = AsyncMock()

    with (
        patch("firebase_messaging.FcmPushClient", return_value=fake_client),
        patch("firebase_messaging.FcmRegisterConfig"),
    ):
        await listener.async_start()
        await listener._async_watchdog(NOW)
        await listener._async_watchdog(NOW + timedelta(minutes=2))
        await listener._async_watchdog(NOW + timedelta(minutes=4))
        assert listener._next_probe_at is not None
        probe_at = listener._next_probe_at
        await listener._async_watchdog(probe_at)
        await listener._async_watchdog(probe_at + timedelta(minutes=2))

    assert fake_client.checkin_or_register.await_count == 3
    assert secret not in caplog.text
    assert "RuntimeError" in caplog.text
    await listener.async_stop()


async def test_import_failure_does_not_log_exception_message(
    hass: HomeAssistant,
    caplog,
) -> None:
    """Import errors also expose only their type, not arbitrary exception text."""
    listener, _ = _listener(hass)
    secret = "IMPORT-EXCEPTION-SECRET"
    original_import = __import__

    def guarded_import(name, *args, **kwargs):
        if name == "firebase_messaging":
            raise ImportError(secret)
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=guarded_import):
        await listener._async_connect()

    assert secret not in caplog.text
    assert "ImportError" in caplog.text


async def test_async_start_keeps_finite_abort_count(hass: HomeAssistant):
    """Предохранитель библиотеки конечен: иначе _listen зацикливается (#77).

    При `None` проверка в `_try_increment_error_count` всегда ложна, `_terminate()`
    недостижим, и библиотека бесконечно перечитывает мёртвый StreamReader, печатая
    растущий traceback в общем event loop.
    """
    listener, _ = _listener(hass)
    fake_client = MagicMock()
    fake_client.checkin_or_register = AsyncMock(return_value="T")
    fake_client.start = AsyncMock()
    fake_client.stop = AsyncMock()
    with patch("firebase_messaging.FcmPushClient", return_value=fake_client), \
         patch("firebase_messaging.FcmRegisterConfig"), \
         patch("firebase_messaging.FcmPushClientConfig") as cfg_cls:
        await listener.async_start()
        cfg_cls.assert_called_once_with(
            abort_on_sequential_error_count=FCM_ABORT_AFTER_ERRORS
        )
        await listener.async_stop()

    assert FCM_ABORT_AFTER_ERRORS is not None
    assert FCM_ABORT_AFTER_ERRORS > 0


async def test_library_terminated_receiver_enters_bounded_recovery(
    hass: HomeAssistant,
) -> None:
    """Регрессия #77: клиент, погашенный предохранителем, доходит до OPEN.

    Так выглядит receiver после `_terminate()`: объект жив, но `is_started()`
    False. Именно этот путь раньше был недостижим при `abort=None`.
    """
    listener, _ = _listener(hass)
    terminated = MagicMock()
    terminated.is_started.return_value = False
    terminated.stop = AsyncMock()
    listener._client = terminated

    replacement = MagicMock()
    replacement.is_started.return_value = False
    replacement.checkin_or_register = AsyncMock(return_value="T")
    replacement.start = AsyncMock()
    replacement.stop = AsyncMock()

    with (
        patch("firebase_messaging.FcmPushClient", return_value=replacement),
        patch("firebase_messaging.FcmRegisterConfig"),
        patch("firebase_messaging.FcmPushClientConfig"),
    ):
        # Первый тик только наблюдает: ни disconnect, ни connect.
        await listener._async_watchdog(NOW)
        assert listener._recovery_phase is _FcmRecoveryPhase.SUSPECT
        terminated.stop.assert_not_awaited()
        replacement.checkin_or_register.assert_not_awaited()

        # Второй — ровно один reconnect.
        await listener._async_watchdog(NOW + timedelta(minutes=2))
        assert listener._recovery_phase is _FcmRecoveryPhase.VERIFYING
        terminated.stop.assert_awaited_once()
        replacement.checkin_or_register.assert_awaited_once()

        await listener._async_watchdog(NOW + timedelta(minutes=4))

    assert listener._recovery_phase is _FcmRecoveryPhase.OPEN
    assert (
        listener._next_probe_at
        == NOW + timedelta(minutes=4) + FCM_RETRY_BACKOFFS[0][0]
    )
    assert ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-1")
    ) is not None


async def test_healthy_replacement_resets_recovery_state(
    hass: HomeAssistant,
) -> None:
    """Живой replacement подтверждается watchdog и сбрасывает recovery-state."""
    listener, _ = _listener(hass)
    listener._recovery_phase = _FcmRecoveryPhase.VERIFYING
    listener._client = MagicMock()
    listener._client.is_started.return_value = True

    await listener._async_watchdog(NOW)

    assert listener._recovery_phase is _FcmRecoveryPhase.HEALTHY


async def test_inactive_replacement_opens_circuit_and_creates_issue(
    hass: HomeAssistant,
) -> None:
    """Неудачный replacement останавливается и создаёт одну Repairs issue."""
    listener, _ = _listener(hass)
    client = MagicMock()
    client.is_started.return_value = False
    client.stop = AsyncMock()
    listener._client = client
    listener._recovery_phase = _FcmRecoveryPhase.VERIFYING

    await listener._async_watchdog(NOW)

    assert listener._recovery_phase is _FcmRecoveryPhase.OPEN
    assert listener._client is None
    assert listener._next_probe_at == NOW + timedelta(minutes=15)
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-1")
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR
    assert issue.is_fixable is False
    assert issue.is_persistent is True
    assert issue.translation_placeholders == {"entry_title": "Аккаунт 1"}


async def test_open_circuit_is_quiet_before_deadline(
    hass: HomeAssistant,
) -> None:
    """OPEN-тик до deadline не делает I/O и не пишет повторный warning."""
    listener, _ = _listener(hass)
    listener._recovery_phase = _FcmRecoveryPhase.OPEN
    listener._next_probe_at = NOW + timedelta(minutes=15)

    with (
        patch.object(listener, "_async_disconnect", new=AsyncMock()) as disconnect,
        patch.object(listener, "_async_connect", new=AsyncMock()) as connect,
        patch(
            "custom_components.elektronny_gorod.fcm.ir.async_create_issue"
        ) as create_issue,
        patch.object(LOGGER, "warning") as warning,
        patch.object(LOGGER, "info") as info,
    ):
        await listener._async_watchdog(NOW + timedelta(minutes=14))

    disconnect.assert_not_awaited()
    connect.assert_not_awaited()
    create_issue.assert_not_called()
    warning.assert_not_called()
    info.assert_not_called()


async def test_failed_probes_advance_and_cap_backoff(
    hass: HomeAssistant,
) -> None:
    """Повторные probe-failure используют 15m/1h/6h/24h и затем 24h."""
    listener, _ = _listener(hass)

    observed: list[timedelta] = []
    create_issue = ir.async_create_issue
    with patch(
        "custom_components.elektronny_gorod.fcm.ir.async_create_issue",
        wraps=create_issue,
    ) as create:
        for _ in range(5):
            listener._async_open_circuit(NOW)
            assert listener._next_probe_at is not None
            observed.append(listener._next_probe_at - NOW)

    assert observed == [
        timedelta(minutes=15),
        timedelta(hours=1),
        timedelta(hours=6),
        timedelta(hours=24),
        timedelta(hours=24),
    ]
    assert create.call_count == 5
    assert ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-1")
    ) is not None


async def test_overlapping_watchdog_ticks_advance_backoff_once(
    hass: HomeAssistant,
) -> None:
    """An in-flight OPEN transition owns the tick; an overlap is skipped."""
    listener, _ = _listener(hass)
    stop_entered = asyncio.Event()
    allow_stop = asyncio.Event()

    async def gated_stop() -> None:
        stop_entered.set()
        await allow_stop.wait()

    client = MagicMock()
    client.is_started.return_value = False
    client.stop = gated_stop
    listener._client = client
    listener._recovery_phase = _FcmRecoveryPhase.VERIFYING

    first_tick = asyncio.create_task(listener._async_watchdog(NOW))
    await stop_entered.wait()
    second_tick = asyncio.create_task(listener._async_watchdog(NOW))
    await asyncio.sleep(0)
    allow_stop.set()
    await asyncio.gather(first_tick, second_tick)

    assert listener._backoff_index == 1
    assert listener._next_probe_at == NOW + timedelta(minutes=15)


async def test_stop_waits_for_in_flight_open_before_remove_cleanup(
    hass: HomeAssistant,
) -> None:
    """Removal cleanup runs after an active tick can no longer recreate issue."""
    listener, _ = _listener(hass)
    stop_entered = asyncio.Event()
    allow_stop = asyncio.Event()

    async def gated_stop() -> None:
        stop_entered.set()
        await allow_stop.wait()

    client = MagicMock()
    client.is_started.return_value = False
    client.stop = gated_stop
    listener._client = client
    listener._recovery_phase = _FcmRecoveryPhase.VERIFYING

    watchdog_task = asyncio.create_task(listener._async_watchdog(NOW))
    await stop_entered.wait()

    async def unload_then_remove() -> None:
        await listener.async_stop()
        async_delete_fcm_repair_issue(hass, "entry-1")

    remove_task = asyncio.create_task(unload_then_remove())
    await asyncio.sleep(0)
    allow_stop.set()
    await asyncio.gather(watchdog_task, remove_task)

    assert listener._client is None
    assert ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-1")
    ) is None


async def test_stop_disconnects_client_created_by_in_flight_reconnect(
    hass: HomeAssistant,
) -> None:
    """Unload waits for a reconnect and then closes its replacement client."""
    listener, _ = _listener(hass)
    listener._client = MagicMock()
    listener._client.is_started.return_value = False
    listener._client.stop = AsyncMock()
    listener._recovery_phase = _FcmRecoveryPhase.SUSPECT
    connect_entered = asyncio.Event()
    allow_connect = asyncio.Event()
    replacement = MagicMock()
    replacement.stop = AsyncMock()

    async def gated_connect() -> None:
        connect_entered.set()
        await allow_connect.wait()
        listener._client = replacement

    with patch.object(listener, "_async_connect", side_effect=gated_connect):
        watchdog_task = asyncio.create_task(listener._async_watchdog(NOW))
        await connect_entered.wait()
        stop_task = asyncio.create_task(listener.async_stop())
        await asyncio.sleep(0)
        allow_connect.set()
        await asyncio.gather(watchdog_task, stop_task)

    assert listener._client is None
    replacement.stop.assert_awaited_once()


async def test_successful_probe_removes_issue_only_on_next_healthy_tick(
    hass: HomeAssistant,
) -> None:
    """start() probe не закрывает issue до следующего healthy watchdog-тика."""
    listener, _ = _listener(hass)
    _create_repair_issue(hass)
    listener._recovery_phase = _FcmRecoveryPhase.OPEN
    listener._next_probe_at = NOW
    healthy = MagicMock()
    healthy.is_started.return_value = True

    async def connect() -> None:
        listener._client = healthy

    with (
        patch.object(listener, "_async_disconnect", new=AsyncMock()),
        patch.object(listener, "_async_connect", side_effect=connect),
    ):
        await listener._async_watchdog(NOW)

    registry = ir.async_get(hass)
    issue_id = fcm_repair_issue_id("entry-1")
    assert listener._recovery_phase is _FcmRecoveryPhase.VERIFYING
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    await listener._async_watchdog(NOW + timedelta(minutes=2))

    assert listener._recovery_phase is _FcmRecoveryPhase.HEALTHY
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_recovery_state_and_issue_are_isolated_per_entry(
    hass: HomeAssistant,
) -> None:
    """Падение FCM одного entry не меняет состояние соседнего аккаунта."""
    failing, _ = _listener(hass, entry_id="entry-a", title="Аккаунт A")
    healthy, _ = _listener(hass, entry_id="entry-b", title="Аккаунт B")
    failing._recovery_phase = _FcmRecoveryPhase.VERIFYING
    failing_client = MagicMock()
    failing_client.is_started.return_value = False
    failing_client.stop = AsyncMock()
    failing._client = failing_client
    healthy_client = MagicMock()
    healthy_client.is_started.return_value = True
    healthy._client = healthy_client

    await failing._async_watchdog(NOW)
    await healthy._async_watchdog(NOW)

    registry = ir.async_get(hass)
    failing_issue = registry.async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-a")
    )
    assert failing_issue is not None
    assert failing_issue.translation_placeholders == {"entry_title": "Аккаунт A"}
    assert registry.async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-b")
    ) is None
    assert failing._recovery_phase is _FcmRecoveryPhase.OPEN
    assert healthy._recovery_phase is _FcmRecoveryPhase.HEALTHY
    assert failing._client is None
    assert healthy._client is healthy_client
    assert failing._next_probe_at == NOW + timedelta(minutes=15)
    assert healthy._next_probe_at is None
    assert failing._backoff_index == 1
    assert healthy._backoff_index == 0


async def test_failed_start_enters_bounded_recovery(
    hass: HomeAssistant,
) -> None:
    """Провал initial connect получает одну попытку, затем circuit OPEN."""
    listener, _ = _listener(hass)
    listener._client = None

    with patch.object(listener, "_async_connect", new=AsyncMock()) as connect:
        await listener._async_watchdog(NOW)
        await listener._async_watchdog(NOW + timedelta(minutes=2))
        await listener._async_watchdog(NOW + timedelta(minutes=4))

    connect.assert_awaited_once()
    assert listener._recovery_phase is _FcmRecoveryPhase.OPEN


async def test_async_stop_is_idempotent_and_preserves_open_issue(
    hass: HomeAssistant,
) -> None:
    """Unload останавливает timer/client, но persistent issue остаётся."""
    listener, _ = _listener(hass)
    unsubscribe = MagicMock()
    listener._watchdog_unsub = unsubscribe
    listener._recovery_phase = _FcmRecoveryPhase.OPEN
    _create_repair_issue(hass)

    await listener.async_stop()
    await listener.async_stop()

    unsubscribe.assert_called_once()
    assert listener._watchdog_unsub is None
    assert listener._client is None
    assert ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-1")
    ) is not None


async def test_async_stop_removes_issue_when_entry_is_disabled(
    hass: HomeAssistant,
) -> None:
    """A deliberately disabled entry must not retain an active Repairs issue."""
    listener, _ = _listener(hass)
    listener._entry.disabled_by = "user"
    _create_repair_issue(hass)

    await listener.async_stop()

    assert ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-1")
    ) is None


async def test_reloaded_listener_clears_existing_issue_after_healthy_tick(
    hass: HomeAssistant,
) -> None:
    """Reload сохраняет issue до фактически healthy receiver."""
    first, _ = _listener(hass)
    _create_repair_issue(hass)
    reloaded, _ = _listener(hass)
    reloaded._client = MagicMock()
    reloaded._client.is_started.return_value = True

    await reloaded._async_watchdog(NOW)

    assert ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-1")
    ) is None


async def test_recovery_logs_and_issue_do_not_expose_credentials(
    hass: HomeAssistant,
    caplog,
) -> None:
    """Integration-owned recovery output не содержит FCM secrets."""
    listener, _ = _listener(hass)
    listener._entry.data = {
        "fcm_credentials": {"token": "FCM-CREDENTIAL-SECRET"}
    }
    listener.fcm_token = "FCM-PUSH-TOKEN-SECRET"
    listener._recovery_phase = _FcmRecoveryPhase.VERIFYING

    await listener._async_watchdog(NOW)

    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-1")
    )
    assert "FCM-CREDENTIAL-SECRET" not in caplog.text
    assert "FCM-PUSH-TOKEN-SECRET" not in caplog.text
    assert issue is not None
    assert issue.translation_placeholders == {"entry_title": "Аккаунт 1"}


async def test_watchdog_skips_healthy_client(hass: HomeAssistant):
    """Watchdog при живом receiver (is_started=True) — ничего не делает."""
    listener, _ = _listener(hass)
    client = MagicMock()
    client.checkin_or_register = AsyncMock(return_value="T")
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.is_started = MagicMock(return_value=True)
    with patch("firebase_messaging.FcmPushClient", return_value=client), \
         patch("firebase_messaging.FcmRegisterConfig"):
        await listener.async_start()
        await listener._async_watchdog()
        client.stop.assert_not_awaited()
        assert listener._client is client
        await listener.async_stop()


async def test_async_start_idempotent_single_watchdog(hass: HomeAssistant):
    """Повторный async_start не плодит второй watchdog-таймер."""
    listener, _ = _listener(hass)
    client = MagicMock()
    client.checkin_or_register = AsyncMock(return_value="T")
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.is_started = MagicMock(return_value=True)
    with patch("firebase_messaging.FcmPushClient", return_value=client), \
         patch("firebase_messaging.FcmRegisterConfig"), \
         patch(
             "custom_components.elektronny_gorod.fcm.async_track_time_interval",
             return_value=MagicMock(),
         ) as track:
        await listener.async_start()
        await listener.async_start()
        track.assert_called_once()
        await listener.async_stop()


@pytest.mark.parametrize("gate", ["checkin", "operator_bind"])
async def test_stop_during_start_leaves_listener_fully_stopped(
    hass: HomeAssistant, gate: str
) -> None:
    """Выгрузка, догнавшая старт на любом из двух await'ов, не оставляет хвостов.

    Guard стоит после каждого: после checkin — чтобы не пойти к оператору,
    после привязки токена — чтобы не поднять MTalk-клиент.
    """
    listener, api = _listener(hass)
    entered = asyncio.Event()
    allow = asyncio.Event()
    client = MagicMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()

    async def gated_checkin() -> str:
        entered.set()
        await allow.wait()
        return "T"

    async def gated_bind(_token: str) -> bool:
        entered.set()
        await allow.wait()
        return True

    if gate == "checkin":
        client.checkin_or_register = gated_checkin
    else:
        client.checkin_or_register = AsyncMock(return_value="T")
        api.register_push_device = gated_bind

    with (
        patch("firebase_messaging.FcmPushClient", return_value=client),
        patch("firebase_messaging.FcmRegisterConfig"),
        patch(
            "custom_components.elektronny_gorod.fcm.async_track_time_interval",
            return_value=MagicMock(),
        ) as track,
    ):
        start_task = asyncio.create_task(listener.async_start())
        await entered.wait()
        stop_task = asyncio.create_task(listener.async_stop())
        await asyncio.sleep(0)
        allow.set()
        await asyncio.gather(start_task, stop_task)

    client.stop.assert_not_awaited()
    client.start.assert_not_awaited()
    track.assert_not_called()
    assert listener._client is None
    assert listener._watchdog_unsub is None
    assert listener._stopping is True
    if gate == "checkin":
        # Без этой проверки удаление guard'а не роняет ни один тест.
        api.register_push_device.assert_not_awaited()


async def test_stop_failure_keeps_client_and_opens_circuit(
    hass: HomeAssistant,
    caplog,
) -> None:
    """A failed dependency stop must not lose the client or create another."""
    listener, _ = _listener(hass)
    secret = "STOP-EXCEPTION-SECRET"
    client = MagicMock()
    client.is_started.return_value = False
    client.stop = AsyncMock(side_effect=RuntimeError(secret))
    listener._client = client
    listener._recovery_phase = _FcmRecoveryPhase.SUSPECT

    with patch.object(listener, "_async_connect", new=AsyncMock()) as connect:
        await listener._async_watchdog(NOW)
        await listener._async_watchdog(NOW + timedelta(minutes=2))
        await listener._async_watchdog(NOW + timedelta(minutes=15))

    connect.assert_not_awaited()
    assert client.stop.await_count == 2
    assert listener._client is client
    assert listener._recovery_phase is _FcmRecoveryPhase.OPEN
    assert listener._next_probe_at == NOW + timedelta(hours=1, minutes=15)
    assert secret not in caplog.text
    assert "RuntimeError" in caplog.text
    assert ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-1")
    ) is not None


async def test_async_stop_reports_dependency_stop_failure(
    hass: HomeAssistant,
) -> None:
    """Config-entry unload must be able to block replacement after failed stop."""
    listener, _ = _listener(hass)
    client = MagicMock()
    client.stop = AsyncMock(side_effect=RuntimeError("cannot stop"))
    listener._client = client

    assert await listener.async_stop() is False
    assert listener._client is client


def test_every_backoff_has_a_readable_label() -> None:
    """У каждой паузы есть подпись, и она не сырой timedelta."""
    for delay, text in FCM_RETRY_BACKOFFS:
        assert ":" not in text
        assert text[0].isdigit()
        # Подпись обязана описывать именно это значение, иначе лог соврёт.
        assert str(int(delay.total_seconds()) // 3600 or
                   int(delay.total_seconds()) // 60) == text.split()[0]


async def test_open_circuit_logs_human_readable_delay(
    hass: HomeAssistant, caplog
) -> None:
    """В warning'е о паузе — «15 минут», а не «0:15:00»."""
    listener, _ = _listener(hass)

    with caplog.at_level(logging.WARNING, logger=LOGGER.name):
        listener._async_open_circuit(NOW)

    assert "через 15 минут" in caplog.text
    assert "0:15:00" not in caplog.text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("a" * 87, "a" * 87 + "="),      # dh: 65 байт → 87 символов
        ("a" * 22, "a" * 22 + "=="),     # salt: 16 байт → 22 символа
        ("a" * 88, "a" * 88),            # уже кратно 4 — не трогаем
        ("", ""),
    ],
)
def test_b64_pad(value: str, expected: str) -> None:
    """Padding добивается только до кратности 4 и не портит корректный вход."""
    assert _b64_pad(value) == expected


@pytest.fixture
def real_decrypt_raw_data():
    """Отдать НАСТОЯЩИЙ `_decrypt_raw_data` в обход мока из conftest.

    `conftest.py` кладёт MagicMock в `sys.modules["firebase_messaging"]` до
    любых импортов, иначе тесты ходили бы в Google. Здесь нужен реальный код
    зависимости, поэтому мок временно снимаем и возвращаем обратно. Если
    библиотека не установлена (CI не ставит manifest-deps) — тест скипается.
    """
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "firebase_messaging" or name.startswith("firebase_messaging.")
    }
    for name in saved:
        del sys.modules[name]
    try:
        from firebase_messaging import FcmPushClient as real_cls
    except ImportError:
        pytest.skip("firebase-messaging не установлена (CI не ставит manifest-deps)")
        return
    finally:
        sys.modules.update(saved)

    if isinstance(real_cls, MagicMock):  # pragma: no cover - защита от подмены
        pytest.skip("firebase-messaging подменена моком")
    yield real_cls.__dict__["_decrypt_raw_data"].__func__


@pytest.mark.parametrize(
    ("header", "label", "expected"),
    [
        # Лишний сегмент отброшен, dh дополнен до кратности 4.
        ("dh=" + "a" * 87 + "; p256ecdsa=" + "b" * 87, "dh", "dh=" + "a" * 87 + "="),
        # Выбор по метке, а не по позиции: порядок сегментов спецификацией
        # не закреплён, и VAPID-сегмент достаётся так же, как dh.
        ("dh=AAA; p256ecdsa=BBB", "p256ecdsa", "p256ecdsa=BBB="),
        ("p256ecdsa=BBB;dh=AAA", "dh", "dh=AAA="),
        # Единственный сегмент — форма, которая приходила до июня 2026.
        ("dh=AAA", "dh", "dh=AAA="),
        # Метки нет, но и голым значением строка быть не может — не трогаем.
        ("p256ecdsa=BBB", "dh", "p256ecdsa=BBB"),
        # Уже корректный salt проходит без изменений.
        ("salt=" + "c" * 22 + "==", "salt", "salt=" + "c" * 22 + "=="),
        # Значение без метки: метку восстанавливаем, иначе слепой срез
        # библиотеки съест реальные байты ключа.
        ("a" * 87, "dh", "dh=" + "a" * 87 + "="),
        ("c" * 22 + "==", "salt", "salt=" + "c" * 22 + "=="),
        # Незнакомую форму отдаём библиотеке нетронутой.
        ("foo=bar; baz=qux", "dh", "foo=bar; baz=qux"),
        ("", "dh", ""),
    ],
)
def test_normalize_push_header(header: str, label: str, expected: str) -> None:
    """Нормализация оставляет один сегмент с корректным padding."""
    assert _normalize_push_header(header, label) == expected


def _library_slices(crypto_key_header: str, encryption_header: str) -> tuple[str, str]:
    """Повторить слепой срез префикса из `fcmpushclient.py:425-426`.

    Библиотека читает заголовки как одиночные значения: `[3:]` вместо разбора
    `dh=`, `[5:]` вместо `salt=`. Тест обязан пройти ровно этот путь, иначе он
    проверяет не то, что ломается на проде.
    """
    return crypto_key_header[3:], encryption_header[5:]


def test_prod_header_shape_decrypts_only_after_normalization(
    real_decrypt_raw_data,
) -> None:
    """Регрессия #77 на настоящей криптографии, а не на моке.

    Воспроизводим форму заголовков, снятую DIAG-пробой с прода 2026-08-13:
    `crypto-key: dh=<87>; p256ecdsa=<87>` (dh без padding) и
    `encryption: salt=<24>` (salt уже с padding). Проверяем обе исторические
    ошибки и то, что нормализация их снимает.
    """
    # http_ece приходит транзитивно с firebase-messaging, а CI её не ставит —
    # поэтому импорт локальный, под тем же skip'ом, что и сама зависимость.
    from http_ece import encrypt as http_encrypt

    priv = ec.generate_private_key(ec.SECP256R1())
    der = priv.private_bytes(
        Encoding.DER, PrivateFormat.PKCS8, NoEncryption()
    )
    auth_secret = os.urandom(16)
    credentials = {
        "keys": {
            "private": urlsafe_b64encode(der).decode().rstrip("="),
            "secret": urlsafe_b64encode(auth_secret).decode().rstrip("="),
        }
    }
    salt = os.urandom(16)
    server_key = ec.generate_private_key(ec.SECP256R1())
    dh_public = server_key.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )
    payload = json.dumps({"PushType": "CALL_INCOMING"}).encode()
    raw_data = http_encrypt(
        payload,
        salt=salt,
        private_key=server_key,
        dh=priv.public_key().public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint
        ),
        auth_secret=auth_secret,
        version="aesgcm",
    )
    dh_b64 = urlsafe_b64encode(dh_public).decode().rstrip("=")
    vapid_b64 = urlsafe_b64encode(os.urandom(65)).decode().rstrip("=")
    crypto_key_header = f"dh={dh_b64}; p256ecdsa={vapid_b64}"
    encryption_header = f"salt={urlsafe_b64encode(salt).decode()}"

    # Ровно то, что показала проба: dh без padding, salt с ним.
    assert len(dh_b64) % 4 == 3
    assert len(encryption_header[5:]) % 4 == 0

    raw_key, raw_salt = _library_slices(crypto_key_header, encryption_header)

    # Симптом до 0bd2f29: срез оставил хвост `; p256ecdsa=…`, длина не кратна 4.
    with pytest.raises(binascii.Error):
        real_decrypt_raw_data(credentials, raw_key, raw_salt, raw_data)

    # Симптом после 0bd2f29: padding позволил декодировать мусор — 137 байт
    # вместо 65, точка не на кривой.
    with pytest.raises(ValueError, match="Invalid EC key"):
        real_decrypt_raw_data(credentials, _b64_pad(raw_key), raw_salt, raw_data)

    # С нормализацией слепой срез попадает ровно в dh и salt.
    norm_key, norm_salt = _library_slices(
        _normalize_push_header(crypto_key_header, "dh"),
        _normalize_push_header(encryption_header, "salt"),
    )
    decrypted = real_decrypt_raw_data(credentials, norm_key, norm_salt, raw_data)
    assert json.loads(decrypted) == {"PushType": "CALL_INCOMING"}


class _FakeAppDataItem:
    """Минимальный двойник protobuf-записи `app_data` (есть .key и .value)."""

    def __init__(self, key: str, value: str) -> None:
        self.key = key
        self.value = value


def _fake_message(**app_data: str) -> MagicMock:
    msg = MagicMock()
    msg.app_data = [_FakeAppDataItem(k, v) for k, v in app_data.items()]
    return msg


class _FakeClient:
    """Двойник `FcmPushClient`: только то, что видит патч."""

    def __init__(self) -> None:
        self.seen: list[list[tuple[str, str]]] = []

    def _handle_data_message(self, msg):  # noqa: ANN001, ANN202
        self.seen.append([(i.key, i.value) for i in msg.app_data])


def _patched_client() -> _FakeClient:
    client = _FakeClient()
    _patch_push_headers(client)
    return client


def test_patch_normalizes_app_data_before_library_reads_it() -> None:
    """Библиотека получает уже приведённые заголовки, прочее не тронуто."""
    client = _patched_client()
    msg = _fake_message(
        **{
            "crypto-key": "dh=" + "a" * 87 + "; p256ecdsa=" + "b" * 87,
            "encryption": "salt=" + "c" * 22 + "==",
            "subtype": "не трогаем",
        }
    )

    client._handle_data_message(msg)

    assert client.seen == [
        [
            ("crypto-key", "dh=" + "a" * 87 + "="),
            ("encryption", "salt=" + "c" * 22 + "=="),
            ("subtype", "не трогаем"),
        ]
    ]


def test_patch_is_scoped_to_one_client() -> None:
    """Патч живёт на экземпляре: чужие клиенты того же класса не затронуты.

    `firebase-messaging` тянет не только эта интеграция — её же использует
    `ring_doorbell[listen]`. Классовый патч чинил бы и чужие клиенты.
    """
    patched = _patched_client()
    untouched = _FakeClient()
    header = "dh=" + "a" * 87 + "; p256ecdsa=" + "b" * 87

    patched._handle_data_message(_fake_message(**{"crypto-key": header}))
    untouched._handle_data_message(_fake_message(**{"crypto-key": header}))

    assert patched.seen == [[("crypto-key", "dh=" + "a" * 87 + "=")]]
    assert untouched.seen == [[("crypto-key", header)]]


@pytest.fixture
def real_data_message_stanza():
    """Отдать настоящий protobuf-класс в обход мока из conftest.

    Тот же приём, что и в `real_decrypt_raw_data`: мок снимаем на время
    импорта и возвращаем обратно. Без библиотеки (CI) — skip.
    """
    saved = {
        name: module
        for name, module in sys.modules.items()
        if name == "firebase_messaging" or name.startswith("firebase_messaging.")
    }
    for name in saved:
        del sys.modules[name]
    try:
        from firebase_messaging.proto.mcs_pb2 import DataMessageStanza
    except ImportError:
        pytest.skip("firebase-messaging не установлена (CI не ставит manifest-deps)")
        return
    finally:
        sys.modules.update(saved)

    if isinstance(DataMessageStanza, MagicMock):  # pragma: no cover
        pytest.skip("firebase-messaging подменена моком")
    yield DataMessageStanza


def test_patch_mutates_real_protobuf_app_data(real_data_message_stanza) -> None:
    """Правка `app_data` держится на настоящем protobuf, а не только на моке."""
    client = _patched_client()
    msg = real_data_message_stanza()
    for key, value in (
        ("crypto-key", "dh=" + "a" * 87 + "; p256ecdsa=" + "b" * 87),
        ("encryption", "salt=" + "c" * 22 + "=="),
    ):
        item = msg.app_data.add()
        item.key = key
        item.value = value

    client._handle_data_message(msg)

    assert msg.app_data[0].value == "dh=" + "a" * 87 + "="
    assert msg.app_data[1].value == "salt=" + "c" * 22 + "=="
