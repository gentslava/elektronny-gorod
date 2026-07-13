# Intercom Busy Production Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a one-shot, fail-safe production diagnostic that identifies which integration action makes a second physical intercom display «Занято» and lose control.

**Architecture:** Extend the SIP REGISTER layer with an opt-in official-app profile and explicit unregister, then add a dormant diagnostic runner armed only by a one-shot marker file. The runner observes the next real FCM call, executes isolated post-call probes, switches the controller to FCM-only mode, unloads the config entry for the official-app-only round, and always restores normal operation through a separate watchdog task.

**Tech Stack:** Python 3.12, Home Assistant config-entry lifecycle, asyncio UDP SIP, aiohttp-backed existing API wrapper, pytest + pytest-homeassistant-custom-component, tcpdump + dpkt for secret-safe production capture analysis.

---

## File map

- Create `custom_components/elektronny_gorod/sip/registration_probe.py` — one REGISTER-only transaction with explicit unregister and no call acceptance.
- Create `custom_components/elektronny_gorod/sip/busy_diagnostic.py` — armed/active/mode state machine, fixed schedule, watchdog and config-entry unload/setup.
- Modify `custom_components/elektronny_gorod/sip/register.py` — opt-in FCM Call-Id Contact parameter and opt-in `Accept: application/sdp`.
- Modify `custom_components/elektronny_gorod/sip/dialog.py` — final `480 Temporarily Unavailable` builder for an unexpected diagnostic INVITE.
- Modify `custom_components/elektronny_gorod/sip/protocol.py` — explicit unregister and diagnostic REGISTER profile; defaults preserve current production packets.
- Modify `custom_components/elektronny_gorod/sip/call_controller.py` — optional diagnostic hook that may suppress only register-on-ring.
- Modify `custom_components/elektronny_gorod/__init__.py` — consume one-shot marker and wire a runner for the selected entry.
- Create `research/intercom-call-probe/analyze_busy_capture.py` — sanitize raw pcap into stage/method/status/profile facts without printing credentials or tokens.
- Create `tests/test_sip_protocol.py`, `tests/test_sip_registration_probe.py`, `tests/test_sip_busy_diagnostic.py`, `tests/test_busy_capture_analyzer.py`.
- Modify `tests/test_sip_register.py`, `tests/test_sip_call_controller.py`, `tests/test_init.py`.
- Update `docs/superpowers/specs/2026-07-13-intercom-busy-production-diagnostic-design.md` only if implementation constraints require wording corrections; do not add conclusions before the live run.

## Task 1: Exact REGISTER profiles and explicit unregister

**Files:**
- Modify: `custom_components/elektronny_gorod/sip/register.py:20-59`
- Modify: `custom_components/elektronny_gorod/sip/dialog.py:23-45`
- Modify: `custom_components/elektronny_gorod/sip/protocol.py:33-160`
- Modify: `tests/test_sip_register.py`
- Create: `tests/test_sip_protocol.py`

- [ ] **Step 1: Write failing tests for current and official REGISTER profiles**

Add to `tests/test_sip_register.py`:

```python
def test_build_contact_official_profile_binds_fcm_call_id() -> None:
    contact = build_contact(
        "000", "1.2.3.4", 5066, "FCMTOKEN123",
        fcm_call_id="FCM-CALL-42", include_transport=False,
    )
    assert contact.startswith("<sip:000@1.2.3.4:5066;app-id=")
    assert ";transport=udp" not in contact
    assert ";Call-Id:%20FCM-CALL-42;pn-tok=FCMTOKEN123>" in contact


def test_build_contact_current_profile_remains_unchanged() -> None:
    contact = build_contact("000", "1.2.3.4", 5066, "FCMTOKEN123")
    assert "Call-Id:%20" not in contact


def test_build_register_accept_sdp_is_opt_in() -> None:
    base = dict(
        login="000", realm="r", host="h", port=5066, call_id="c",
        from_tag="t", cseq=1, contact="<c>", branch="b", user_agent="ua",
    )
    assert "Accept:" not in build_register(**base)
    assert "Accept: application/sdp\r\n" in build_register(**base, accept_sdp=True)
```

- [ ] **Step 2: Run the builder tests and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sip_register.py -q
```

Expected: three new tests fail because `fcm_call_id` and `accept_sdp` are not accepted.

- [ ] **Step 3: Implement opt-in fields without changing default packets**

Change the relevant signatures and body in `sip/register.py`:

```python
def build_contact(
    login: str,
    host: str,
    port: int,
    fcm_token: str,
    *,
    fcm_call_id: str | None = None,
    include_transport: bool = True,
) -> str:
    call_param = f";Call-Id:%20{fcm_call_id}" if fcm_call_id else ""
    transport_param = ";transport=udp" if include_transport else ""
    return (
        f"<sip:{login}@{host}:{port}{transport_param}"
        f";app-id={PUSH_APP_ID};pn-type=google{call_param};pn-tok={fcm_token}>"
    )


def build_register(
    login: str,
    realm: str,
    host: str,
    port: int,
    call_id: str,
    from_tag: str,
    cseq: int,
    contact: str,
    branch: str,
    user_agent: str,
    expires: int = REGISTER_EXPIRES,
    auth: str | None = None,
    *,
    accept_sdp: bool = False,
) -> str:
    lines = [
        f"REGISTER sip:{realm} SIP/2.0",
        f"Via: SIP/2.0/UDP {host}:{port};branch={branch};rport",
        "Max-Forwards: 70",
        f"From: <sip:{login}@{realm}>;tag={from_tag}",
        f"To: <sip:{login}@{realm}>",
        f"Call-ID: {call_id}",
        f"CSeq: {cseq} REGISTER",
        f"Contact: {contact}",
        f"Expires: {expires}",
        "Supported: replaces, outbound, gruu, path",
    ]
    if accept_sdp:
        lines.append("Accept: application/sdp")
    lines.append(f"User-Agent: {user_agent}")
    if auth:
        lines.append(f"Authorization: {auth}")
    lines += ["Content-Length: 0", "", ""]
    return _CRLF.join(lines)
```

- [ ] **Step 4: Run builder tests and verify GREEN**

Run the Step 2 command.

Expected: all `tests/test_sip_register.py` tests pass and the old current-profile assertions remain unchanged.

- [ ] **Step 5: Write failing protocol tests for authenticated unregister and safe INVITE rejection**

Create `tests/test_sip_protocol.py` with a recording transport and focused assertions:

```python
from __future__ import annotations

import asyncio

from custom_components.elektronny_gorod.sip.message import parse_sip
from custom_components.elektronny_gorod.sip.protocol import SipProtocol


class RecordingTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple | None]] = []
        self.closed = False

    def get_extra_info(self, name: str):
        return ("10.0.0.2", 5066) if name == "sockname" else None

    def sendto(self, data: bytes, addr: tuple | None = None) -> None:
        self.sent.append((data, addr))

    def close(self) -> None:
        self.closed = True


def _protocol(**kwargs) -> tuple[SipProtocol, RecordingTransport]:
    protocol = SipProtocol(
        {"login": "000", "password": "secret", "realm": "r.example"},
        "10.0.0.2", "FCM", "Myhome/Myhome-android", **kwargs,
    )
    transport = RecordingTransport()
    protocol.connection_made(transport)  # type: ignore[arg-type]
    return protocol, transport


async def test_unregister_uses_expires_zero_and_waits_for_200() -> None:
    protocol, transport = _protocol()
    protocol.datagram_received(
        b'SIP/2.0 200 OK\r\nCSeq: 1 REGISTER\r\nContent-Length: 0\r\n\r\n',
        ("1.2.3.4", 5060),
    )
    task = asyncio.create_task(protocol.async_unregister(timeout=1))
    await asyncio.sleep(0)
    assert b"Expires: 0" in transport.sent[-1][0]
    protocol.datagram_received(
        b'SIP/2.0 401 Unauthorized\r\nCSeq: 2 REGISTER\r\n'
        b'WWW-Authenticate: Digest realm="r.example",nonce="N"\r\n'
        b'Content-Length: 0\r\n\r\n',
        ("1.2.3.4", 5060),
    )
    assert b"Expires: 0" in transport.sent[-1][0]
    assert b"Authorization: Digest" in transport.sent[-1][0]
    protocol.datagram_received(
        b'SIP/2.0 200 OK\r\nCSeq: 3 REGISTER\r\nContent-Length: 0\r\n\r\n',
        ("1.2.3.4", 5060),
    )
    assert await task is True


def test_official_profile_changes_only_opt_in_register_fields() -> None:
    _, transport = _protocol(
        fcm_call_id="FCM-CALL-42",
        accept_sdp=True,
        include_contact_transport=False,
    )
    register = transport.sent[0][0].decode()
    assert "Call-Id:%20FCM-CALL-42" in register
    assert "Accept: application/sdp" in register
    assert ";transport=udp" not in register


def test_reject_pending_invite_sends_480_not_100_or_200() -> None:
    protocol, transport = _protocol()
    invite = parse_sip(
        "INVITE sip:000@host SIP/2.0\r\n"
        "Via: SIP/2.0/UDP host;branch=z\r\n"
        "From: <sip:door@r>;tag=a\r\nTo: <sip:000@r>\r\n"
        "Call-ID: call\r\nCSeq: 1 INVITE\r\nContent-Length: 0\r\n\r\n"
    )
    protocol._on_invite(invite, ("1.2.3.4", 5060))
    protocol.reject_pending_invite()
    payload = transport.sent[-1][0]
    assert payload.startswith(b"SIP/2.0 480 Temporarily Unavailable")
```

- [ ] **Step 6: Run protocol tests and verify RED**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sip_protocol.py -q
```

Expected: failures for unsupported constructor arguments and missing unregister/reject methods.

- [ ] **Step 7: Implement protocol profile, unregister state and 480 response**

In `sip/dialog.py`, expose a final response using the existing response helper:

```python
def build_480(invite, local_tag: str) -> str:
    """Final response used only by the non-answering diagnostic probe."""
    return _build_invite_response(
        invite, "SIP/2.0 480 Temporarily Unavailable", local_tag
    )
```

In `SipProtocol`, extend the constructor without changing any existing call site:

```python
def __init__(
    self,
    creds: dict,
    local_ip: str,
    fcm_token: str,
    user_agent: str,
    on_bye: Callable[[], None] | None = None,
    on_cancel: Callable[[], None] | None = None,
    *,
    fcm_call_id: str | None = None,
    accept_sdp: bool = False,
    include_contact_transport: bool = True,
) -> None:
    self.login = creds["login"]
    self.password = creds["password"]
    self.realm = creds["realm"]
    self.local_ip = local_ip
    self.fcm_token = fcm_token
    self.ua = user_agent
    self.on_bye = on_bye
    self.on_cancel = on_cancel
    self.transport: asyncio.DatagramTransport | None = None
    self._lport = 0
    self.call_id = f"{uuid.uuid4()}@{local_ip}"
    self.from_tag = uuid.uuid4().hex[:8]
    self.local_tag = uuid.uuid4().hex[:8]
    self.cseq = 0
    self.registered: asyncio.Future[bool] | None = None
    self.unregistered: asyncio.Future[bool] | None = None
    self.invite: asyncio.Future[tuple] | None = None
    self.dialog: DialogState | None = None
    self._invite_msg = None
    self._invite_addr: tuple | None = None
    self._fcm_call_id = fcm_call_id
    self._accept_sdp = accept_sdp
    self._include_contact_transport = include_contact_transport
    self._register_expires = REGISTER_EXPIRES
```

Create `unregistered` in `connection_made`, pass the opt-in fields from `send_register`,
and preserve the requested expires value across a 401/407 challenge:

```python
def send_register(self, auth: str | None = None, *, expires: int = REGISTER_EXPIRES) -> None:
    if self.transport is None:
        return
    self._register_expires = expires
    self.cseq += 1
    branch = f"z9hG4bK{random.randint(0, 1 << 31)}"
    contact = build_contact(
        self.login, self.local_ip, self._lport, self.fcm_token,
        fcm_call_id=self._fcm_call_id,
        include_transport=self._include_contact_transport,
    )
    reg = build_register(
        self.login, self.realm, self.local_ip, self._lport, self.call_id,
        self.from_tag, self.cseq, contact, branch, self.ua,
        expires=expires, auth=auth, accept_sdp=self._accept_sdp,
    )
    self.transport.sendto(reg.encode())
```

Create `self.unregistered = loop.create_future()` in `connection_made`. In
`_on_response`, keep the existing challenge parsing and replace its final branch with:

```python
auth = build_register_authorization(
    self.login,
    self.password,
    realm,
    nonce.group(1),
    f"sip:{self.realm}",
    qop=qop,
)
self.send_register(auth, expires=self._register_expires)

# in the 200 branch
if code == "200" and self._register_expires == 0:
    if self.unregistered is not None and not self.unregistered.done():
        self.unregistered.set_result(True)
elif code == "200" and self.registered is not None and not self.registered.done():
    self.registered.set_result(True)
```

Then add:

```python
async def async_unregister(self, *, timeout: float = 5.0) -> bool:
    if self.transport is None or self.unregistered is None:
        return False
    self.send_register(expires=0)
    try:
        return await asyncio.wait_for(self.unregistered, timeout=timeout)
    except asyncio.TimeoutError:
        return False


def reject_pending_invite(self) -> None:
    if self.transport is None or self._invite_msg is None or self._invite_addr is None:
        return
    self.transport.sendto(
        build_480(self._invite_msg, self.local_tag).encode(), self._invite_addr
    )
```

- [ ] **Step 8: Run REGISTER/protocol regression tests**

Run:

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sip_register.py tests/test_sip_protocol.py tests/test_sip_manager.py -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Commit Task 1**

```bash
git add custom_components/elektronny_gorod/sip/register.py \
  custom_components/elektronny_gorod/sip/dialog.py \
  custom_components/elektronny_gorod/sip/protocol.py \
  tests/test_sip_register.py tests/test_sip_protocol.py
git commit -m "test: add safe SIP registration profiles"
```

## Task 2: REGISTER-only diagnostic probe

**Files:**
- Create: `custom_components/elektronny_gorod/sip/registration_probe.py`
- Create: `tests/test_sip_registration_probe.py`

- [ ] **Step 1: Write failing probe tests with injected networking**

Create tests around a factory so unit tests never open a socket:

```python
from unittest.mock import AsyncMock, MagicMock

from custom_components.elektronny_gorod.sip.registration_probe import (
    RegistrationProfile,
    async_run_registration_probe,
)


def _resolved_future(value):
    future = asyncio.get_running_loop().create_future()
    future.set_result(value)
    return future


def _pending_future():
    return asyncio.get_running_loop().create_future()


async def test_current_probe_registers_then_unregisters_without_answering() -> None:
    protocol = MagicMock()
    protocol.registered = _resolved_future(True)
    protocol.invite = _pending_future()
    protocol.async_unregister = AsyncMock(return_value=True)
    transport = MagicMock()
    opener = AsyncMock(return_value=(transport, protocol))

    result = await async_run_registration_probe(
        creds={"login": "000", "password": "secret", "realm": "r"},
        fcm_token="FCM",
        fcm_call_id="CALL",
        profile=RegistrationProfile.CURRENT,
        observe_seconds=0,
        open_endpoint=opener,
    )

    assert result.registered is True
    assert result.invite_received is False
    assert result.unregistered is True
    protocol.async_unregister.assert_awaited_once()
    protocol.send_trying.assert_not_called()
    protocol.answer.assert_not_called()
    transport.close.assert_called_once()


async def test_unexpected_invite_is_rejected_and_marks_result_ambiguous() -> None:
    protocol = MagicMock()
    protocol.registered = _resolved_future(True)
    protocol.invite = _resolved_future((MagicMock(), ("1.2.3.4", 5060)))
    protocol.async_unregister = AsyncMock(return_value=True)
    result = await async_run_registration_probe(
        creds={"login": "000", "password": "secret", "realm": "r"},
        fcm_token="FCM", fcm_call_id="CALL",
        profile=RegistrationProfile.OFFICIAL,
        observe_seconds=0,
        open_endpoint=AsyncMock(return_value=(MagicMock(), protocol)),
    )
    assert result.invite_received is True
    assert result.ambiguous is True
    protocol.reject_pending_invite.assert_called_once()
```

- [ ] **Step 2: Run probe tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sip_registration_probe.py -q
```

Expected: collection fails because `registration_probe.py` does not exist.

- [ ] **Step 3: Implement the focused probe**

Create `registration_probe.py` with these public types and flow:

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from typing import Awaitable, Callable

from .manager import SIP_PORT, SIP_USER_AGENT, _outbound_ip
from .protocol import SipProtocol


class RegistrationProfile(StrEnum):
    CURRENT = "current"
    OFFICIAL = "official"


@dataclass(frozen=True, slots=True)
class RegistrationProbeResult:
    profile: RegistrationProfile
    registered: bool
    invite_received: bool
    unregistered: bool
    ambiguous: bool


async def async_run_registration_probe(
    *,
    creds: dict,
    fcm_token: str,
    fcm_call_id: str,
    profile: RegistrationProfile,
    observe_seconds: float = 10.0,
    open_endpoint: Callable[..., Awaitable[tuple]] | None = None,
) -> RegistrationProbeResult:
    factory = open_endpoint or _open_endpoint
    transport, protocol = await factory(
        creds=creds,
        fcm_token=fcm_token,
        fcm_call_id=fcm_call_id if profile is RegistrationProfile.OFFICIAL else None,
        accept_sdp=profile is RegistrationProfile.OFFICIAL,
        include_contact_transport=profile is RegistrationProfile.CURRENT,
    )
    invite_received = False
    registered = unregistered = False
    try:
        registered = await asyncio.wait_for(protocol.registered, timeout=5.0)
        try:
            await asyncio.wait_for(asyncio.shield(protocol.invite), timeout=observe_seconds)
            invite_received = True
            protocol.reject_pending_invite()
        except asyncio.TimeoutError:
            pass
        unregistered = await protocol.async_unregister(timeout=5.0)
    finally:
        transport.close()
    return RegistrationProbeResult(
        profile, registered, invite_received, unregistered, invite_received
    )
```

Implement `_open_endpoint` as the only function that resolves `creds["realm"]`, derives
the outbound local IP, and calls `loop.create_datagram_endpoint` with an ephemeral local
UDP port (`local_addr=("0.0.0.0", 0)`), `remote_addr=(registrar_ip, SIP_PORT)`, and the
opt-in `SipProtocol` arguments. The OFFICIAL profile passes
`include_contact_transport=False`; CURRENT preserves `transport=udp`. This boundary lets
tests inject `open_endpoint` without DNS or socket I/O. Do not log `creds`, Contact,
headers or tokens.

- [ ] **Step 4: Run probe tests and selected SIP tests**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sip_registration_probe.py \
  tests/test_sip_protocol.py tests/test_sip_register.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add custom_components/elektronny_gorod/sip/registration_probe.py \
  tests/test_sip_registration_probe.py
git commit -m "feat: add non-answering SIP registration probe"
```

## Task 3: One-shot diagnostic state machine and watchdog

**Files:**
- Create: `custom_components/elektronny_gorod/sip/busy_diagnostic.py`
- Create: `tests/test_sip_busy_diagnostic.py`

- [ ] **Step 1: Write failing state-machine tests**

Cover the complete schedule with an injected `wait_until` that records offsets instead
of sleeping:

```python
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call


def _ring(call_id: str, place: str, ac: str) -> dict:
    return {
        "event_type": "ring",
        "place_id": place,
        "access_control_id": ac,
        "attributes": {"call_id": call_id},
    }


def _ended(call_id: str, place: str, ac: str) -> dict:
    return {
        "event_type": "ended",
        "place_id": place,
        "access_control_id": ac,
        "attributes": {"call_id": call_id},
    }


def _probe_result():
    return SimpleNamespace(
        registered=True, invite_received=False, unregistered=True, ambiguous=False
    )


async def _wait_forever(_offset: float) -> None:
    await asyncio.Event().wait()


def _hass(config_entries=None):
    hass = MagicMock()
    if config_entries is None:
        config_entries = MagicMock()
        config_entries.async_unload = AsyncMock(return_value=True)
        config_entries.async_setup = AsyncMock(return_value=True)
    hass.config_entries = config_entries
    hass.async_create_task.side_effect = (
        lambda coro, name=None: asyncio.create_task(coro, name=name)
    )
    return hass


def _runner(*, run_register=None, fcm_token_getter=lambda: "FCM"):
    api = MagicMock()
    api.mint_sip_device = AsyncMock(
        return_value={"login": "000", "password": "secret", "realm": "r"}
    )
    return BusyDiagnosticRunner(
        hass=_hass(), entry_id="entry", api=api,
        fcm_token_getter=fcm_token_getter,
        wait_until=AsyncMock(), watchdog_wait_until=_wait_forever,
        run_register=run_register or AsyncMock(return_value=_probe_result()),
    )


async def test_schedule_runs_three_probes_and_switches_modes() -> None:
    api = MagicMock()
    api.mint_sip_device = AsyncMock(return_value={"login": "000", "password": "s", "realm": "r"})
    wait_until = AsyncMock()
    run_register = AsyncMock(return_value=_probe_result())
    config_entries = MagicMock()
    config_entries.async_unload = AsyncMock(return_value=True)
    config_entries.async_setup = AsyncMock(return_value=True)
    runner = BusyDiagnosticRunner(
        hass=_hass(config_entries), entry_id="entry",
        api=api, fcm_token_getter=lambda: "FCM",
        wait_until=wait_until, watchdog_wait_until=_wait_forever,
        run_register=run_register,
    )

    runner.handle_signal(_ring("CALL", "PLACE", "AC"))
    runner.handle_signal(_ended("CALL", "PLACE", "AC"))
    await runner.task

    assert runner.stage_history == [
        "real_call", "mint_only", "register_current", "register_official",
        "fcm_only", "official_only", "restored",
    ]
    assert run_register.await_args_list[0].kwargs["profile"] is RegistrationProfile.CURRENT
    assert run_register.await_args_list[1].kwargs["profile"] is RegistrationProfile.OFFICIAL
    config_entries.async_unload.assert_awaited_once_with("entry")
    config_entries.async_setup.assert_awaited_once_with("entry")
    runner.watchdog_task.cancel()


async def test_fcm_only_mode_suppresses_hold_but_keeps_signal_tracking() -> None:
    runner = _runner()
    runner.mode = DiagnosticMode.FCM_ONLY
    assert runner.allow_sip_hold is False
    runner.handle_signal(_ring("SECOND", "PLACE", "AC"))
    assert runner.second_call_seen is True


async def test_exception_restores_entry_and_normal_mode() -> None:
    runner = _runner(run_register=AsyncMock(side_effect=RuntimeError("boom")))
    runner.handle_signal(_ring("CALL", "PLACE", "AC"))
    runner.handle_signal(_ended("CALL", "PLACE", "AC"))
    await runner.task
    assert runner.mode is DiagnosticMode.CURRENT
    assert runner.failed is True
    runner.hass.config_entries.async_setup.assert_awaited()
    runner.watchdog_task.cancel()


async def test_arm_timeout_makes_no_network_or_config_entry_calls() -> None:
    runner = _runner()
    await runner.async_expire_armed()
    assert runner.armed is False
    runner.api.mint_sip_device.assert_not_awaited()
    runner.hass.config_entries.async_unload.assert_not_awaited()
```

- [ ] **Step 2: Run runner tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sip_busy_diagnostic.py -q
```

Expected: collection fails because `busy_diagnostic.py` does not exist.

- [ ] **Step 3: Implement modes, signal correlation and fixed offsets**

Create `busy_diagnostic.py` with explicit constants and no configurable arbitrary SIP
payloads:

```python
ARM_TIMEOUT_SEC = 20 * 60.0
MINT_OFFSET_SEC = 50.0
CURRENT_REGISTER_OFFSET_SEC = 80.0
OFFICIAL_REGISTER_OFFSET_SEC = 115.0
FCM_ONLY_OFFSET_SEC = 140.0
ENTRY_UNLOAD_OFFSET_SEC = 270.0
ENTRY_SETUP_OFFSET_SEC = 450.0
WATCHDOG_OFFSET_SEC = 540.0


class DiagnosticMode(StrEnum):
    CURRENT = "current"
    FCM_ONLY = "fcm_only"
    OFFICIAL_ONLY = "official_only"


@dataclass(frozen=True, slots=True)
class TargetCall:
    call_id: str
    place_id: str
    access_control_id: str
```

The constructor accepts two wait dependencies with production defaults pointing to the
same monotonic `_wait_until`; tests pass `_wait_forever` for the watchdog so it cannot
race the main schedule:

```python
WaitUntil = Callable[[float], Awaitable[None]]


def __init__(
    self,
    *,
    hass: HomeAssistant,
    entry_id: str,
    api: Any,
    fcm_token_getter: Callable[[], str | None],
    wait_until: WaitUntil | None = None,
    watchdog_wait_until: WaitUntil | None = None,
    run_register=async_run_registration_probe,
) -> None:
    self.hass = hass
    self.entry_id = entry_id
    self.api = api
    self._fcm_token_getter = fcm_token_getter
    self._wait = wait_until or self._wait_until
    self._watchdog_wait = watchdog_wait_until or self._wait_until
    self._run_register = run_register
```

`handle_signal` must accept the same payload shape as `DoorbellCallController`, bind
the first ring, accept `ended` only when call/access-control match, and never store the
entire FCM payload. Its ring path starts two HA tasks:

```python
self.task = self.hass.async_create_task(
    self._async_run(), name="elektronny_gorod_busy_diagnostic"
)
self.watchdog_task = self.hass.async_create_task(
    self._async_watchdog(), name="elektronny_gorod_busy_diagnostic_watchdog"
)
```

The main sequence uses the injected `_wait(offset)` for every absolute offset, requires the
first `ended` event before `MINT_OFFSET_SEC`, obtains a fresh mint for each REGISTER
profile, and stores only stage names/results:

```python
await asyncio.wait_for(
    self.first_call_ended.wait(), timeout=MINT_OFFSET_SEC - 5.0
)
await self._wait(MINT_OFFSET_SEC)
await self.api.mint_sip_device(target.place_id, target.access_control_id)
self._mark("mint_only")

await self._wait(CURRENT_REGISTER_OFFSET_SEC)
await self._run_profile(RegistrationProfile.CURRENT)
self._mark("register_current")

await self._wait(OFFICIAL_REGISTER_OFFSET_SEC)
await self._run_profile(RegistrationProfile.OFFICIAL)
self._mark("register_official")

await self._wait(FCM_ONLY_OFFSET_SEC)
self.mode = DiagnosticMode.FCM_ONLY
self._mark("fcm_only")

await self._wait(ENTRY_UNLOAD_OFFSET_SEC)
self.mode = DiagnosticMode.OFFICIAL_ONLY
if not await self.hass.config_entries.async_unload(self.entry_id):
    raise RuntimeError("diagnostic config-entry unload failed")
self._mark("official_only")

await self._wait(ENTRY_SETUP_OFFSET_SEC)
if not await self.hass.config_entries.async_setup(self.entry_id):
    raise RuntimeError("diagnostic config-entry setup failed")
self.mode = DiagnosticMode.CURRENT
self._mark("restored")
```

Implement `_run_profile` completely so credentials never leave the method and any
ambiguous or non-unregistered result aborts later stages:

```python
async def _run_profile(self, profile: RegistrationProfile) -> None:
    target = self.target
    if target is None:
        raise RuntimeError("diagnostic target missing")
    fcm_token = self._fcm_token_getter()
    if not fcm_token:
        raise RuntimeError("diagnostic FCM token unavailable")
    creds = await self.api.mint_sip_device(
        target.place_id, target.access_control_id
    )
    result = await self._run_register(
        creds=creds,
        fcm_token=fcm_token,
        fcm_call_id=target.call_id,
        profile=profile,
    )
    if result.ambiguous or not result.unregistered:
        raise RuntimeError(f"diagnostic {profile.value} probe unsafe result")
```

`_async_watchdog` must wait independently until `WATCHDOG_OFFSET_SEC`, set mode to
CURRENT, and call `async_setup(entry_id)` whenever the entry is not loaded. Both main
and watchdog paths catch exceptions, log only stage/type, and call the same idempotent
`_async_restore()`.

- [ ] **Step 4: Run runner tests and verify GREEN**

Run the Step 2 command.

Expected: all state-machine tests pass without real sleeps, network or config-entry I/O.

- [ ] **Step 5: Add tests for mismatched ended/ring and missing FCM token**

Add three assertions:

```python
runner.handle_signal(_ring("CALL", "PLACE", "AC"))
runner.handle_signal(_ended("OTHER", "PLACE", "AC"))
assert runner.first_call_ended.is_set() is False

runner.mode = DiagnosticMode.FCM_ONLY
runner.handle_signal(_ring("SECOND", "PLACE", "OTHER_AC"))
assert runner.failed is True

runner = _runner(fcm_token_getter=lambda: None)
runner.handle_signal(_ring("CALL", "PLACE", "AC"))
runner.handle_signal(_ended("CALL", "PLACE", "AC"))
await runner.task
assert runner.failed is True
```

- [ ] **Step 6: Run runner tests again**

Expected: all tests pass and no secret values appear in `caplog.text`.

- [ ] **Step 7: Commit Task 3**

```bash
git add custom_components/elektronny_gorod/sip/busy_diagnostic.py \
  tests/test_sip_busy_diagnostic.py
git commit -m "feat: add one-shot intercom busy diagnostic"
```

## Task 4: Dormant HA wiring and one-shot marker

**Files:**
- Modify: `custom_components/elektronny_gorod/sip/call_controller.py:100-201`
- Modify: `custom_components/elektronny_gorod/__init__.py:56-123`
- Modify: `tests/test_sip_call_controller.py`
- Modify: `tests/test_init.py`

- [ ] **Step 1: Write failing controller test for opt-in hold suppression**

Add to `tests/test_sip_call_controller.py`:

```python
async def test_diagnostic_fcm_only_tracks_ring_without_starting_sip() -> None:
    diagnostic = MagicMock()
    diagnostic.allow_sip_hold = False
    controller = DoorbellCallController(
        _hass(), MagicMock(), lambda: "TOK", diagnostic=diagnostic
    )
    with patch.object(controller, "_async_hold_current") as hold:
        controller.handle_signal(_ring_payload(call_id="CALL", ac="AC"))
    diagnostic.handle_signal.assert_called_once()
    hold.assert_not_called()
    assert controller.current_call() is not None
```

- [ ] **Step 2: Write failing setup tests for absent and consumed marker**

In `tests/test_init.py`, patch `async_consume_busy_diagnostic_marker`:

```python
async def test_setup_without_marker_does_not_create_diagnostic(hass, config_entry) -> None:
    with patch(
        "custom_components.elektronny_gorod.async_consume_busy_diagnostic_marker",
        AsyncMock(return_value=False),
    ), patch("custom_components.elektronny_gorod.BusyDiagnosticRunner") as runner_cls:
        assert await async_setup_entry(hass, config_entry) is True
    runner_cls.assert_not_called()


async def test_setup_with_marker_wires_armed_runner(hass, config_entry) -> None:
    runner = MagicMock()
    runner.async_arm = AsyncMock()
    with patch(
        "custom_components.elektronny_gorod.async_consume_busy_diagnostic_marker",
        AsyncMock(return_value=True),
    ), patch(
        "custom_components.elektronny_gorod.BusyDiagnosticRunner", return_value=runner
    ):
        assert await async_setup_entry(hass, config_entry) is True
    runner.async_arm.assert_awaited_once()
```

- [ ] **Step 3: Run focused tests and verify RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sip_call_controller.py tests/test_init.py -q
```

Expected: new constructor argument and marker symbols are missing.

- [ ] **Step 4: Wire diagnostic hook without changing default ring behavior**

Add an optional protocol-like dependency to `DoorbellCallController`:

```python
class BusyDiagnosticHook(Protocol):
    @property
    def allow_sip_hold(self) -> bool: ...
    def handle_signal(self, payload: dict[str, Any]) -> None: ...


def __init__(
    self,
    hass: HomeAssistant,
    api: Any,
    fcm_token_getter: Callable[[], str | None],
    on_downlink: Callable[[bytes], None] | None = None,
    go2rtc: Go2RtcConfig | None = None,
    camera_resolver: Callable[[str], str | None] | None = None,
    diagnostic: BusyDiagnosticHook | None = None,
) -> None:
    self._hass = hass
    self._api = api
    self._fcm_token_getter = fcm_token_getter
    self._on_downlink = on_downlink or self._count_downlink
    self._go2rtc = go2rtc
    self._camera_resolver = camera_resolver
    self._diagnostic = diagnostic
```

At the beginning of `handle_signal`, notify the diagnostic. On the `ring` branch keep
all existing active-call and HA-state logic, but guard only the hold task:

```python
if self._diagnostic is not None:
    self._diagnostic.handle_signal(payload)

# existing ring validation and state emission remain unchanged
if self._diagnostic is None or self._diagnostic.allow_sip_hold:
    task = self._async_hold_current()
    self._hass.async_create_task(task, name="elektronny_gorod_sip_hold")
else:
    LOGGER.info("Busy diagnostic: FCM-only, SIP hold suppressed")
```

- [ ] **Step 5: Implement the one-shot marker consumer and setup wiring**

In `busy_diagnostic.py`:

```python
BUSY_DIAGNOSTIC_MARKER = ".elektronny_gorod_busy_diagnostic_arm"


async def async_consume_busy_diagnostic_marker(hass: HomeAssistant) -> bool:
    path = Path(hass.config.path(BUSY_DIAGNOSTIC_MARKER))

    def _consume() -> bool:
        if not path.is_file():
            return False
        path.unlink()
        return True

    return await hass.async_add_executor_job(_consume)
```

In `async_setup_entry`, after `fcm_listener` creation and before controller creation:

```python
diagnostic = None
if await async_consume_busy_diagnostic_marker(hass):
    diagnostic = BusyDiagnosticRunner(
        hass=hass,
        entry_id=entry.entry_id,
        api=coordinator.api,
        fcm_token_getter=lambda: fcm_listener.fcm_token,
    )
    await diagnostic.async_arm()
```

Pass `diagnostic=diagnostic` to `DoorbellCallController`. The runner task must be
created with `hass.async_create_task`, not `entry.async_create_background_task`, so the
watchdog survives the deliberate config-entry unload. No runner is created without the
marker.

- [ ] **Step 6: Run focused setup/controller tests**

Run the Step 3 command.

Expected: all selected tests pass, including all pre-existing register-on-ring tests.

- [ ] **Step 7: Run the full suite before production packaging**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: the complete suite passes.

- [ ] **Step 8: Commit Task 4**

```bash
git add custom_components/elektronny_gorod/__init__.py \
  custom_components/elektronny_gorod/sip/call_controller.py \
  custom_components/elektronny_gorod/sip/busy_diagnostic.py \
  tests/test_init.py tests/test_sip_call_controller.py
git commit -m "feat: wire dormant busy diagnostic runner"
```

## Task 5: Secret-safe pcap analyzer

**Files:**
- Create: `research/intercom-call-probe/analyze_busy_capture.py`
- Create: `tests/test_busy_capture_analyzer.py`

- [ ] **Step 1: Write failing sanitizer tests**

```python
import importlib.util
from pathlib import Path


MODULE_PATH = Path("research/intercom-call-probe/analyze_busy_capture.py")
SPEC = importlib.util.spec_from_file_location("analyze_busy_capture", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
summarize_sip_message = MODULE.summarize_sip_message


def test_register_summary_never_contains_tokens_or_authorization() -> None:
    message = (
        "REGISTER sip:r SIP/2.0\r\n"
        "Contact: <sip:000@h;Call-Id:%20CALL;pn-tok=SECRET_FCM>\r\n"
        "Authorization: Digest username=000,response=SECRET_DIGEST\r\n"
        "Expires: 30\r\n\r\n"
    )
    summary = summarize_sip_message(message)
    rendered = repr(summary)
    assert "SECRET_FCM" not in rendered
    assert "SECRET_DIGEST" not in rendered
    assert summary["method"] == "REGISTER"
    assert summary["has_fcm_call_id"] is True
    assert summary["has_pn_token"] is True
    assert summary["expires"] == 30
```

- [ ] **Step 2: Run sanitizer test and verify RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_busy_capture_analyzer.py -q
```

Expected: the analyzer module does not exist.

- [ ] **Step 3: Implement structural summaries with lazy dpkt import**

The analyzer must expose a pure helper for tests and import `dpkt` only inside
`iter_pcap_summaries`:

```python
def summarize_sip_message(message: str) -> dict[str, object]:
    lines = message.split("\r\n")
    first = lines[0]
    headers = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers.setdefault(name.lower(), value.strip())
    contact = headers.get("contact", "")
    cseq = headers.get("cseq", "")
    return {
        "method": first.split(" ", 1)[0] if not first.startswith("SIP/") else None,
        "status": first.split(" ", 2)[1] if first.startswith("SIP/") else None,
        "cseq_method": cseq.rsplit(" ", 1)[-1] if cseq else None,
        "expires": int(headers["expires"]) if headers.get("expires", "").isdigit() else None,
        "has_fcm_call_id": "Call-Id:%20" in contact,
        "has_pn_token": "pn-tok=" in contact,
        "has_accept_sdp": headers.get("accept") == "application/sdp",
    }
```

`main()` prints JSON lines containing relative time, redacted endpoint role
(`HA`/`SIP_SERVER`), UDP ports, and the helper output. It must never print raw Contact,
Authorization, login, realm, FCM Call-ID, token, packet bytes or SDP.

`iter_pcap_summaries` must inspect `reader.datalink()` and decode all formats used by
the project captures: DLT_RAW as IPv4 directly, DLT_EN10MB through
`dpkt.ethernet.Ethernet`, DLT_LINUX_SLL through `dpkt.sll.SLL`, and
DLT_LINUX_SLL2 by stripping its 20-byte cooked header before `dpkt.ip.IP`. Unknown
link types raise a descriptive error before any packet content is printed.

- [ ] **Step 4: Run analyzer tests and security scan**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_busy_capture_analyzer.py -q
rtk rg -n "print\(.*(contact|authorization|pn-tok|payload|message)" \
  research/intercom-call-probe/analyze_busy_capture.py
```

Expected: pytest passes; the ripgrep command finds no unsafe print.

- [ ] **Step 5: Commit Task 5**

```bash
git add research/intercom-call-probe/analyze_busy_capture.py \
  tests/test_busy_capture_analyzer.py
git commit -m "test: add secret-safe busy capture analyzer"
```

## Task 6: Verification, production deployment and one-trip run

**Files:**
- Verify: all files from Tasks 1–5
- Production backup: `/opt/homeassistant/custom_components/elektronny_gorod`
- Production marker: `/opt/homeassistant/.elektronny_gorod_busy_diagnostic_arm`
- Temporary capture: `/tmp/eg_busy_diagnostic.pcap`

- [ ] **Step 1: Run proportional local verification**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sip_register.py \
  tests/test_sip_protocol.py tests/test_sip_registration_probe.py \
  tests/test_sip_busy_diagnostic.py tests/test_sip_call_controller.py \
  tests/test_init.py tests/test_busy_capture_analyzer.py -q
PYTHONPATH=. .venv/bin/pytest tests/ -q
git diff --check
git status --short
```

Expected: targeted and full suites pass, diff check is clean, only intentional files are
modified or committed.

- [ ] **Step 2: Inspect the production version and create a timestamped backup**

Run read-only checksum comparison first, then create a backup only after confirming the
deployed component matches the expected pre-diagnostic revision:

```bash
ssh home.server sudo sha256sum \
  /opt/homeassistant/custom_components/elektronny_gorod/__init__.py \
  /opt/homeassistant/custom_components/elektronny_gorod/sip/protocol.py
ssh home.server sudo cp -a \
  /opt/homeassistant/custom_components/elektronny_gorod \
  /opt/homeassistant/custom_components/elektronny_gorod.pre-busy-diagnostic-20260713
```

Expected: backup exists and no Home Assistant process has been restarted yet.

- [ ] **Step 3: Deploy only the tested integration files without arming**

Use `rsync --checksum` over SSH from the repository component directory to the
production component directory. Do not copy `.git`, tests, docs, captures or secrets.

```bash
rsync -a --checksum \
  custom_components/elektronny_gorod/ \
  home.server:/tmp/elektronny_gorod-diagnostic/
ssh home.server sudo rsync -a --checksum \
  /tmp/elektronny_gorod-diagnostic/ \
  /opt/homeassistant/custom_components/elektronny_gorod/
```

Expected: files are present but running HA behavior is unchanged until restart; marker
does not exist.

- [ ] **Step 4: Prepare capture and production rollback checks**

Pre-create a root-only pcap and start a bounded capture shortly before arming:

```bash
ssh home.server sudo install -m 600 /dev/null /tmp/eg_busy_diagnostic.pcap
ssh home.server sudo timeout 660 /usr/bin/tcpdump -i any -s 0 -U \
  -w /tmp/eg_busy_diagnostic.pcap 'udp port 5060 or udp port 5066'
```

Run tcpdump in a managed background session so its PID/output remain available to the
agent. Separately tail timestamped Home Assistant logs from the restart point.

- [ ] **Step 5: Arm only after the user writes `пошёл`**

Create the one-shot marker and restart the HA container once:

```bash
ssh home.server sudo install -m 600 /dev/null \
  /opt/homeassistant/.elektronny_gorod_busy_diagnostic_arm
ssh home.server sudo docker restart home-assistant-core-skdjyi-homeassistant-1
```

Poll health and logs. Invite the user to leave only after the log contains the sanitized
`Busy diagnostic armed for 1200s` marker and the normal coordinator refresh succeeds.

- [ ] **Step 6: Observe the autonomous schedule without additional user messages**

Correlate stage markers with SIP packet metadata. Do not intervene unless one of these
abort conditions occurs:

- marker consumed but runner not armed;
- first call has not ended by `T0 + 45s`;
- unexpected INVITE during a post-call REGISTER probe;
- unregister returns false;
- config-entry unload/setup returns false;
- Home Assistant health check fails.

On an abort, stop active probes, ensure the config entry is set up, restore CURRENT mode,
and tell the user after they return; do not start later stages.

- [ ] **Step 7: Verify automatic functional restoration at `T0 + 9m`**

Check:

```bash
ssh home.server sudo docker ps --filter \
  name=home-assistant-core-skdjyi-homeassistant-1
ssh home.server sudo docker logs --since 12m --timestamps \
  home-assistant-core-skdjyi-homeassistant-1
```

Filter the returned output in-memory before displaying it. Required facts: stage
`restored`, config entry loaded, FCM listener started, coordinator refresh successful,
no active/held SIP manager.

- [ ] **Step 8: Produce a sanitized result matrix and delete raw capture**

Copy the pcap to local `/tmp`, run the safe analyzer, record only structural results in
the task response, then remove both raw copies:

```bash
scp home.server:/tmp/eg_busy_diagnostic.pcap /tmp/eg_busy_diagnostic.pcap
.venv/bin/python research/intercom-call-probe/analyze_busy_capture.py \
  /tmp/eg_busy_diagnostic.pcap
ssh home.server sudo rm /tmp/eg_busy_diagnostic.pcap
rm /tmp/eg_busy_diagnostic.pcap
```

Expected: no raw pcap remains and no secret appears in terminal/chat output.

- [ ] **Step 9: Restore the pre-diagnostic source after evidence is secured**

Atomically move the diagnostic tree aside, restore the timestamped backup and restart
HA. This avoids deleting files and preserves the diagnostic tree for inspection:

```bash
ssh home.server sudo mv \
  /opt/homeassistant/custom_components/elektronny_gorod \
  /opt/homeassistant/custom_components/elektronny_gorod.busy-diagnostic-run-20260713
ssh home.server sudo mv \
  /opt/homeassistant/custom_components/elektronny_gorod.pre-busy-diagnostic-20260713 \
  /opt/homeassistant/custom_components/elektronny_gorod
ssh home.server sudo docker restart home-assistant-core-skdjyi-homeassistant-1
```

Delete the preserved diagnostic tree only after checks pass and after explicit
confirmation; otherwise keep it for rollback evidence.

- [ ] **Step 10: Commit any implementation-driven spec correction**

If no correction was needed, make no docs-only commit. If exact timings or an HA lifecycle
constraint changed, update the design with observed implementation facts and commit only
that change:

```bash
git add docs/superpowers/specs/2026-07-13-intercom-busy-production-diagnostic-design.md
git commit -m "docs: align busy diagnostic with implementation"
```

## Completion criteria

- The default integration emits the same SIP packets and follows the same control flow
  when the marker is absent.
- The marker is one-shot and consumed through executor-backed file I/O.
- No path sends `200 OK` to INVITE, RTP, DTMF or door-open commands.
- Every diagnostic REGISTER is followed by `Expires: 0`, including exception paths.
- The watchdog restores CURRENT mode and a loaded config entry.
- The three physical rounds are distinguishable by stage markers and production time.
- Raw SIP secrets never appear in tests, logs, analyzer output, chat or committed files.
- Production source and runtime state are restored after evidence collection.
