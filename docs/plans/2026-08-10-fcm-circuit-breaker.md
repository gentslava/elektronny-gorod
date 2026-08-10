# FCM Circuit Breaker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ограничить повторные падения FCM для одного проблемного аккаунта, не затрагивая остальные функции и аккаунты, и показать пользователю одно понятное предупреждение в Home Assistant Repairs.

**Architecture:** Расширить существующий двухминутный watchdog в `DoorbellFcmListener` независимым per-entry circuit breaker. Первая неактивность только наблюдается, вторая запускает одну попытку переподключения, повторная неудача останавливает FCM и включает автоматические пробы с паузами 15 минут, 1 час, 6 часов и 24 часа. Состояние хранится только в памяти; одна persistent Repairs issue сообщает о временной недоступности realtime-уведомлений и удаляется после подтверждённого восстановления либо удаления config entry.

**Tech Stack:** Python 3.12+, Home Assistant config-entry lifecycle и Repairs issue registry, `async_track_time_interval`, `firebase-messaging`, pytest + pytest-homeassistant-custom-component.

---

## File map

- Modify `custom_components/elektronny_gorod/fcm.py` — per-entry state machine, bounded reconnect/probe schedule, Repairs helpers and recovery logging.
- Modify `custom_components/elektronny_gorod/__init__.py` — remove the persistent FCM issue when the config entry is deleted.
- Modify `custom_components/elektronny_gorod/strings.json` — English source text for the Repairs issue.
- Modify `custom_components/elektronny_gorod/translations/en.json` — English Repairs translation.
- Modify `custom_components/elektronny_gorod/translations/ru.json` — Russian Repairs translation.
- Modify `tests/test_fcm.py` — state-machine, backoff, Repairs, lifecycle, privacy and account-isolation regressions.
- Modify `tests/test_init.py` — config-entry removal cleanup regression.
- Modify `docs/audit/project-audit.md` — update A-80/A-86 with issue #77 and the bounded-recovery mitigation.
- Modify `docs/architecture/overview.md` — document per-entry recovery state and degraded mode.
- Modify `docs/testing/strategy.md` — record the new FCM regression scope.
- Modify `docs/aidd/quality-gates.md` — record the fresh test baseline only after the full suite passes.
- Modify `CHANGELOG.md` — add the user-visible fix under `Unreleased`.

`manifest.json`, requirements, config-entry version, config flow, entity IDs and public README files remain unchanged.

## Task 1: Introduce the per-entry recovery state machine

**Files:**

- Modify: `tests/test_fcm.py`
- Modify: `custom_components/elektronny_gorod/fcm.py`

- [ ] **Step 1: Make the listener fixture identify a real config entry**

In `tests/test_fcm.py`, add explicit entry identity while preserving the existing two-value helper return:

```python
from datetime import UTC, datetime, timedelta

from custom_components.elektronny_gorod.fcm import (
    DoorbellFcmListener,
    _FcmRecoveryPhase,
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
    api = MagicMock()
    api.register_push_device = AsyncMock(return_value=True)
    return DoorbellFcmListener(hass, entry, api), api
```

Keep all existing notification parsing and startup tests. Replace the old immediate-reconnect expectation with the bounded two-observation contract.

- [ ] **Step 2: Write failing tests for SUSPECT and RETRYING**

Add focused tests:

```python
async def test_watchdog_first_inactive_tick_only_observes(
    hass: HomeAssistant,
) -> None:
    listener, _ = _listener(hass)
    listener._client = MagicMock()
    listener._client.is_started.return_value = False

    with (
        patch.object(listener, "_async_disconnect", new=AsyncMock()) as disconnect,
        patch.object(listener, "_async_connect", new=AsyncMock()) as connect,
    ):
        await listener._async_watchdog(NOW)

    assert listener._recovery_phase is _FcmRecoveryPhase.SUSPECT
    disconnect.assert_not_awaited()
    connect.assert_not_awaited()


async def test_watchdog_second_inactive_tick_reconnects_once(
    hass: HomeAssistant,
) -> None:
    listener, _ = _listener(hass)
    listener._client = MagicMock()
    listener._client.is_started.return_value = False

    with (
        patch.object(listener, "_async_disconnect", new=AsyncMock()) as disconnect,
        patch.object(listener, "_async_connect", new=AsyncMock()) as connect,
    ):
        await listener._async_watchdog(NOW)
        await listener._async_watchdog(NOW + timedelta(minutes=2))

    assert listener._recovery_phase is _FcmRecoveryPhase.RETRYING
    disconnect.assert_awaited_once()
    connect.assert_awaited_once()


async def test_healthy_replacement_resets_recovery_state(
    hass: HomeAssistant,
) -> None:
    listener, _ = _listener(hass)
    listener._recovery_phase = _FcmRecoveryPhase.RETRYING
    listener._client = MagicMock()
    listener._client.is_started.return_value = True

    await listener._async_watchdog(NOW)

    assert listener._recovery_phase is _FcmRecoveryPhase.HEALTHY
```

- [ ] **Step 3: Run the focused tests and verify RED**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest \
  tests/test_fcm.py::test_watchdog_first_inactive_tick_only_observes \
  tests/test_fcm.py::test_watchdog_second_inactive_tick_reconnects_once \
  tests/test_fcm.py::test_healthy_replacement_resets_recovery_state -q
```

Expected: collection or assertion failures because `_FcmRecoveryPhase` and the new state transitions do not exist yet.

- [ ] **Step 4: Add explicit phases and state fields**

In `fcm.py`, change the datetime import and add the enum:

```python
from datetime import datetime, timedelta
from enum import StrEnum


class _FcmRecoveryPhase(StrEnum):
    HEALTHY = "healthy"
    SUSPECT = "suspect"
    RETRYING = "retrying"
    OPEN = "open"
    PROBING = "probing"
```

Add these fields to `DoorbellFcmListener.__init__`:

```python
self._recovery_phase = _FcmRecoveryPhase.HEALTHY
self._next_probe_at: datetime | None = None
self._backoff_index = 0
```

The explicit `SUSPECT` phase is the first inactive observation; a separate counter is unnecessary.

- [ ] **Step 5: Replace immediate reconnect with state transitions**

Add these helpers before `_async_watchdog`:

```python
@callback
def _async_mark_healthy(self) -> None:
    """Reset transient recovery state after a confirmed healthy tick."""
    recovered = self._recovery_phase in {
        _FcmRecoveryPhase.RETRYING,
        _FcmRecoveryPhase.OPEN,
        _FcmRecoveryPhase.PROBING,
    }
    self._recovery_phase = _FcmRecoveryPhase.HEALTHY
    self._next_probe_at = None
    self._backoff_index = 0
    if recovered:
        LOGGER.info("FCM: push-receiver восстановлен")

async def _async_reconnect(self, phase: _FcmRecoveryPhase) -> None:
    """Perform one guarded disconnect/connect cycle."""
    self._reconnecting = True
    try:
        await self._async_disconnect()
        await self._async_connect()
        self._recovery_phase = phase
    finally:
        self._reconnecting = False
```

Replace `_async_watchdog` with the initial bounded state behavior:

```python
async def _async_watchdog(self, _now: datetime | None = None) -> None:
    """Observe receiver health and perform at most one immediate recovery."""
    if self._reconnecting:
        return

    client = self._client
    if client is not None and client.is_started():
        self._async_mark_healthy()
        return

    if self._recovery_phase is _FcmRecoveryPhase.HEALTHY:
        self._recovery_phase = _FcmRecoveryPhase.SUSPECT
        return

    if self._recovery_phase is _FcmRecoveryPhase.SUSPECT:
        LOGGER.warning(
            "FCM: push-receiver неактивен — выполняю одну попытку восстановления"
        )
        await self._async_reconnect(_FcmRecoveryPhase.RETRYING)
```

Task 2 completes the `RETRYING`, `OPEN` and `PROBING` branches. Do not inspect dependency-private exceptions or log text.

- [ ] **Step 6: Run all FCM tests and verify GREEN**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest tests/test_fcm.py -q
```

Expected: all existing parsing/start tests plus the three new state tests pass. The replaced legacy watchdog test must now use two inactive ticks.

- [ ] **Step 7: Commit the state-machine foundation**

```bash
rtk git add tests/test_fcm.py custom_components/elektronny_gorod/fcm.py
rtk git commit -m "fix: bound immediate FCM reconnect attempts"
```

## Task 2: Open the circuit, back off probes and expose one Repair issue

**Files:**

- Modify: `tests/test_fcm.py`
- Modify: `custom_components/elektronny_gorod/fcm.py`
- Modify: `custom_components/elektronny_gorod/strings.json`
- Modify: `custom_components/elektronny_gorod/translations/en.json`
- Modify: `custom_components/elektronny_gorod/translations/ru.json`

- [ ] **Step 1: Write failing tests for OPEN and the first 15-minute deadline**

Add imports and assertions using the real HA issue registry:

```python
from homeassistant.helpers import issue_registry as ir

from custom_components.elektronny_gorod.const import DOMAIN, LOGGER, SIGNAL_DOORBELL
from custom_components.elektronny_gorod.fcm import (
    FCM_RETRY_BACKOFFS,
    DoorbellFcmListener,
    _FcmRecoveryPhase,
    fcm_repair_issue_id,
)


async def test_inactive_replacement_opens_circuit_and_creates_issue(
    hass: HomeAssistant,
) -> None:
    listener, _ = _listener(hass)
    client = MagicMock()
    client.is_started.return_value = False
    client.stop = AsyncMock()
    listener._client = client
    listener._recovery_phase = _FcmRecoveryPhase.RETRYING

    await listener._async_watchdog(NOW)

    assert listener._recovery_phase is _FcmRecoveryPhase.OPEN
    assert listener._client is None
    assert listener._next_probe_at == NOW + timedelta(minutes=15)
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-1")
    )
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.is_fixable is False
    assert issue.is_persistent is True
    assert issue.translation_placeholders == {"entry_title": "Аккаунт 1"}
```

- [ ] **Step 2: Write failing tests for quiet OPEN ticks and capped backoff**

Cover both no-op polling and the full sequence:

```python
async def test_open_circuit_is_quiet_before_deadline(
    hass: HomeAssistant,
) -> None:
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
    listener, _ = _listener(hass)

    observed: list[timedelta] = []
    for _ in range(5):
        await listener._async_open_circuit(NOW)
        observed.append(listener._next_probe_at - NOW)
        listener._recovery_phase = _FcmRecoveryPhase.PROBING

    assert FCM_RETRY_BACKOFFS == (
        timedelta(minutes=15),
        timedelta(hours=1),
        timedelta(hours=6),
        timedelta(hours=24),
    )
    assert observed == [
        timedelta(minutes=15),
        timedelta(hours=1),
        timedelta(hours=6),
        timedelta(hours=24),
        timedelta(hours=24),
    ]
```

- [ ] **Step 3: Write a failing test for probe confirmation and issue removal**

```python
async def test_successful_probe_removes_issue_only_on_next_healthy_tick(
    hass: HomeAssistant,
) -> None:
    listener, _ = _listener(hass)
    listener._async_create_repair_issue()
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
    assert listener._recovery_phase is _FcmRecoveryPhase.PROBING
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    await listener._async_watchdog(NOW + timedelta(minutes=2))

    assert listener._recovery_phase is _FcmRecoveryPhase.HEALTHY
    assert registry.async_get_issue(DOMAIN, issue_id) is None
```

- [ ] **Step 4: Run the new tests and verify RED**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest tests/test_fcm.py -q
```

Expected: failures for missing backoff constants, Repairs helpers and OPEN/PROBING behavior.

- [ ] **Step 5: Add backoff constants and Repairs helpers**

In `fcm.py`, import the registry and HA UTC helper, and add `DOMAIN` to the existing const import:

```python
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .const import DOMAIN

FCM_RETRY_BACKOFFS = (
    timedelta(minutes=15),
    timedelta(hours=1),
    timedelta(hours=6),
    timedelta(hours=24),
)
_FCM_REPAIR_ISSUE_PREFIX = "fcm_receiver_unavailable"


def fcm_repair_issue_id(entry_id: str) -> str:
    """Return the stable per-config-entry Repairs issue ID."""
    return f"{_FCM_REPAIR_ISSUE_PREFIX}_{entry_id}"


@callback
def async_delete_fcm_repair_issue(
    hass: HomeAssistant, entry_id: str
) -> None:
    """Delete the persistent degraded-FCM issue for one entry."""
    ir.async_delete_issue(hass, DOMAIN, fcm_repair_issue_id(entry_id))
```

Initialize the cached issue flag without writing the registry:

```python
self._repair_issue_active = (
    ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id(entry.entry_id)
    )
    is not None
)
```

Add the creation and open helpers:

```python
@callback
def _async_create_repair_issue(self) -> None:
    if self._repair_issue_active:
        return
    ir.async_create_issue(
        self._hass,
        DOMAIN,
        fcm_repair_issue_id(self._entry.entry_id),
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="fcm_receiver_unavailable",
        translation_placeholders={"entry_title": self._entry.title},
    )
    self._repair_issue_active = True

async def _async_open_circuit(self, now: datetime) -> None:
    """Stop the failed client and schedule one later probe."""
    await self._async_disconnect()
    delay = FCM_RETRY_BACKOFFS[self._backoff_index]
    self._backoff_index = min(
        self._backoff_index + 1, len(FCM_RETRY_BACKOFFS) - 1
    )
    self._next_probe_at = now + delay
    self._recovery_phase = _FcmRecoveryPhase.OPEN
    self._async_create_repair_issue()
    LOGGER.warning(
        "FCM: частые попытки восстановления приостановлены; "
        "следующая проверка через %s",
        delay,
    )
```

Extend `_async_mark_healthy` so it deletes an active issue only on the confirmed healthy tick:

```python
if self._repair_issue_active:
    async_delete_fcm_repair_issue(self._hass, self._entry.entry_id)
    self._repair_issue_active = False
```

- [ ] **Step 6: Complete the OPEN and PROBING watchdog branches**

Use the callback timestamp when supplied and HA UTC otherwise:

```python
now = _now or dt_util.utcnow()

if self._recovery_phase is _FcmRecoveryPhase.OPEN:
    if self._next_probe_at is not None and now < self._next_probe_at:
        return
    LOGGER.info("FCM: выполняю пробную попытку восстановления")
    await self._async_reconnect(_FcmRecoveryPhase.PROBING)
    return

if self._recovery_phase in {
    _FcmRecoveryPhase.RETRYING,
    _FcmRecoveryPhase.PROBING,
}:
    await self._async_open_circuit(now)
    return
```

Place these branches after the healthy-client check and before the HEALTHY/SUSPECT branches. `_async_connect()` already contains setup exceptions, so a failed probe remains inside the watchdog boundary.

- [ ] **Step 7: Add the user-facing Repairs translations**

Add this top-level object to both `strings.json` and `translations/en.json`:

```json
"issues": {
  "fcm_receiver_unavailable": {
    "title": "Doorbell notifications are temporarily unavailable",
    "description": "Realtime doorbell notifications for {entry_title} are temporarily unavailable. The integration stopped frequent reconnection attempts to prevent repeated log errors. Cameras, locks, balance, history, and other features continue to work. The connection will be retried automatically. Reload the integration to try immediately. If the problem returns, reconnect the same account."
  }
}
```

Add the matching object to `translations/ru.json`:

```json
"issues": {
  "fcm_receiver_unavailable": {
    "title": "Уведомления о звонках временно недоступны",
    "description": "Уведомления о звонках для аккаунта «{entry_title}» временно недоступны. Интеграция несколько раз не смогла запустить канал уведомлений и приостановила частые попытки, чтобы не заполнять журнал ошибками. Камеры, замки, баланс, история и остальные функции продолжают работать. Подключение будет проверяться автоматически. Чтобы попробовать сразу, перезагрузите интеграцию. Если ошибка повторяется, подключите этот аккаунт заново."
  }
}
```

Preserve valid JSON commas and the existing top-level ordering.

- [ ] **Step 8: Run the FCM tests and JSON validation**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest tests/test_fcm.py -q
rtk python -m json.tool custom_components/elektronny_gorod/strings.json
rtk python -m json.tool custom_components/elektronny_gorod/translations/en.json
rtk python -m json.tool custom_components/elektronny_gorod/translations/ru.json
```

Expected: all FCM tests pass and all three JSON commands exit successfully.

- [ ] **Step 9: Commit backoff, Repairs and translations**

```bash
rtk git add \
  custom_components/elektronny_gorod/fcm.py \
  custom_components/elektronny_gorod/strings.json \
  custom_components/elektronny_gorod/translations/en.json \
  custom_components/elektronny_gorod/translations/ru.json \
  tests/test_fcm.py
rtk git commit -m "fix: pause repeated FCM failures per account"
```

## Task 3: Prove account isolation, lifecycle cleanup and secret safety

**Files:**

- Modify: `tests/test_fcm.py`
- Modify: `tests/test_init.py`
- Modify: `custom_components/elektronny_gorod/__init__.py`

- [ ] **Step 1: Add a failing multi-account isolation test**

Create two listeners with distinct entry IDs. Open only the failing listener and keep the second healthy:

```python
async def test_recovery_state_and_issue_are_isolated_per_entry(
    hass: HomeAssistant,
) -> None:
    failing, _ = _listener(hass, entry_id="entry-a", title="Аккаунт A")
    healthy, _ = _listener(hass, entry_id="entry-b", title="Аккаунт B")
    failing._recovery_phase = _FcmRecoveryPhase.RETRYING
    failing._client = MagicMock()
    failing._client.is_started.return_value = False
    failing._client.stop = AsyncMock()
    healthy._client = MagicMock()
    healthy._client.is_started.return_value = True

    await failing._async_watchdog(NOW)
    await healthy._async_watchdog(NOW)

    registry = ir.async_get(hass)
    assert registry.async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-a")
    ) is not None
    assert registry.async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-b")
    ) is None
    assert failing._recovery_phase is _FcmRecoveryPhase.OPEN
    assert healthy._recovery_phase is _FcmRecoveryPhase.HEALTHY
```

- [ ] **Step 2: Add lifecycle tests for startup failure and idempotent stop**

Keep `test_async_start_graceful_on_error` and extend lifecycle coverage:

```python
async def test_failed_start_enters_bounded_recovery(hass: HomeAssistant) -> None:
    listener, _ = _listener(hass)
    listener._client = None

    with patch.object(listener, "_async_connect", new=AsyncMock()) as connect:
        await listener._async_watchdog(NOW)
        await listener._async_watchdog(NOW + timedelta(minutes=2))
        await listener._async_watchdog(NOW + timedelta(minutes=4))

    connect.assert_awaited_once()
    assert listener._recovery_phase is _FcmRecoveryPhase.OPEN


async def test_async_stop_is_idempotent_while_circuit_open(
    hass: HomeAssistant,
) -> None:
    listener, _ = _listener(hass)
    unsubscribe = MagicMock()
    listener._watchdog_unsub = unsubscribe
    listener._recovery_phase = _FcmRecoveryPhase.OPEN

    await listener.async_stop()
    await listener.async_stop()

    unsubscribe.assert_called_once()
    assert listener._watchdog_unsub is None
    assert listener._client is None
```

The OPEN issue must survive ordinary unload/reload until a healthy tick; `async_stop()` therefore does not delete it.

- [ ] **Step 3: Add a secret-safety regression**

Use deliberately recognizable secret values and assert they appear neither in logs nor issue placeholders:

```python
async def test_recovery_logs_and_issue_do_not_expose_credentials(
    hass: HomeAssistant, caplog
) -> None:
    listener, _ = _listener(hass)
    listener._entry.data = {
        "fcm_credentials": {"token": "FCM-CREDENTIAL-SECRET"}
    }
    listener.fcm_token = "FCM-PUSH-TOKEN-SECRET"
    listener._recovery_phase = _FcmRecoveryPhase.RETRYING

    await listener._async_watchdog(NOW)

    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, fcm_repair_issue_id("entry-1")
    )
    assert "FCM-CREDENTIAL-SECRET" not in caplog.text
    assert "FCM-PUSH-TOKEN-SECRET" not in caplog.text
    assert issue is not None
    assert issue.translation_placeholders == {"entry_title": "Аккаунт 1"}
```

This exercises only integration-owned output. The dependency's original traceback is outside the integration logger and is bounded by the circuit breaker.

- [ ] **Step 4: Add a failing config-entry removal test**

In `tests/test_init.py`, import `async_remove_entry`, `issue_registry`, `UserAgent` and the issue helper, then add:

```python
from homeassistant.helpers import issue_registry as ir

from custom_components.elektronny_gorod import (
    async_migrate_entry,
    async_remove_entry,
)
from custom_components.elektronny_gorod.fcm import fcm_repair_issue_id
from custom_components.elektronny_gorod.user_agent import UserAgent


async def test_remove_entry_deletes_fcm_repair_issue(
    hass: HomeAssistant, mock_remove_entry_api
) -> None:
    user_agent = UserAgent()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Аккаунт 1",
        data={
            CONF_ACCESS_TOKEN: "AT",
            CONF_REFRESH_TOKEN: "RT",
            CONF_OPERATOR_ID: "1",
            CONF_USER_AGENT: json.dumps(user_agent.json()),
        },
    )
    entry.add_to_hass(hass)
    issue_id = fcm_repair_issue_id(entry.entry_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="fcm_receiver_unavailable",
        translation_placeholders={"entry_title": entry.title},
    )

    await async_remove_entry(hass, entry)

    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    mock_remove_entry_api.return_value.unregister_push_device.assert_awaited_once()
```

- [ ] **Step 5: Run the lifecycle tests and verify RED**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/pytest tests/test_fcm.py tests/test_init.py -q
```

Expected: only the removal-cleanup test fails because `async_remove_entry` does not yet delete the issue. Any other failure indicates a circuit-breaker lifecycle bug and must be fixed before proceeding.

- [ ] **Step 6: Delete the per-entry issue before best-effort remote cleanup**

Change the import in `__init__.py`:

```python
from .fcm import DoorbellFcmListener, async_delete_fcm_repair_issue
```

At the beginning of `async_remove_entry`, before the existing `try` block, add:

```python
async_delete_fcm_repair_issue(hass, entry.entry_id)
```

This local cleanup is deterministic and must not be skipped if the operator unregister request or stored user-agent parsing fails.

- [ ] **Step 7: Run both test modules and verify GREEN**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest tests/test_fcm.py tests/test_init.py -q
```

Expected: all tests pass with no pending-task or cleanup warnings.

- [ ] **Step 8: Commit lifecycle and isolation coverage**

```bash
rtk git add \
  custom_components/elektronny_gorod/__init__.py \
  tests/test_fcm.py \
  tests/test_init.py
rtk git commit -m "test: cover isolated FCM recovery lifecycle"
```

## Task 4: Synchronize architecture, audit and release documentation

**Files:**

- Modify: `docs/audit/project-audit.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/testing/strategy.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update A-80 and A-86 without creating a duplicate finding**

In `docs/audit/project-audit.md`:

- add issue #77 as field evidence under A-80: `firebase-messaging 0.4.5` can terminate the client on malformed Base64URL encryption headers;
- explain that the external parsing defect remains upstream, while retry amplification is mitigated locally;
- amend A-86 so the old immediate watchdog recovery is described as bounded by a per-entry circuit breaker;
- record the 15m → 1h → 6h → 24h probe schedule, persistent warning Repair, confirmed-healthy cleanup and independent multi-account behavior;
- replace the old fixed `9 tests` evidence with the actual test count obtained after Task 3.

Do not mark the upstream dependency bug resolved.

- [ ] **Step 2: Update the architecture overview**

In `docs/architecture/overview.md`:

- expand the FCM listener row to mention bounded per-entry recovery and Repairs visibility;
- add `DoorbellFcmListener` phase, backoff index and next-probe deadline to the state-management table with TTL `listener session; reset on reload/restart`;
- update weak point 6 to state that private Google API compatibility is still not guaranteed, but failures no longer cause an unbounded two-minute restart loop.

- [ ] **Step 3: Update the testing strategy**

In `docs/testing/strategy.md`, replace `FCM parse/reconnect/watchdog` with an explicit list covering:

- notification parsing and dispatcher lifecycle;
- SUSPECT → RETRYING → OPEN → PROBING → HEALTHY transitions;
- 15m/1h/6h/24h capped backoff and quiet pre-deadline ticks;
- persistent Repairs create/retain/delete behavior;
- multi-entry isolation, removal cleanup and no-secret output.

- [ ] **Step 4: Add the Unreleased changelog entry**

Under `## [Unreleased]`, add:

```markdown
### Fixed

- Повторное падение FCM-канала одного аккаунта больше не запускает бесконечное
  переподключение каждые две минуты и не раздувает журнал Home Assistant.
  После одной контрольной попытки интеграция временно приостанавливает FCM только
  для проблемного аккаунта, показывает понятное предупреждение в Repairs и
  автоматически проверяет восстановление с увеличивающимися интервалами.
  Камеры, замки, баланс, история и остальные аккаунты продолжают работать.
```

- [ ] **Step 5: Review the documentation diff and commit it**

Run:

```bash
rtk git diff --check
rtk git diff -- docs/audit/project-audit.md docs/architecture/overview.md \
  docs/testing/strategy.md CHANGELOG.md
```

Verify the docs distinguish the upstream parsing bug from the integration-owned retry amplification.

Commit:

```bash
rtk git add \
  docs/audit/project-audit.md \
  docs/architecture/overview.md \
  docs/testing/strategy.md \
  CHANGELOG.md
rtk git commit -m "docs: document bounded FCM recovery"
```

## Task 5: Run the full quality gate and record evidence

**Files:**

- Modify: `docs/aidd/quality-gates.md`
- Modify: `docs/testing/strategy.md` only if its suite count is stored there

- [ ] **Step 1: Run focused FCM and lifecycle tests**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest tests/test_fcm.py tests/test_init.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run the full backend suite**

```bash
rtk env PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Expected: the entire suite passes with no failures, errors, leaked tasks or cleanup warnings. Record the exact passed-test count from this run; do not reuse the old baseline.

- [ ] **Step 3: Run formatting, translation and secret-output checks**

```bash
rtk git diff --check
rtk python -m json.tool custom_components/elektronny_gorod/strings.json
rtk python -m json.tool custom_components/elektronny_gorod/translations/en.json
rtk python -m json.tool custom_components/elektronny_gorod/translations/ru.json
rtk rg -n 'LOGGER\..*(fcm_token|CONF_FCM_CREDENTIALS|entry\.data|headers)' \
  custom_components/elektronny_gorod/fcm.py \
  custom_components/elektronny_gorod/__init__.py
```

Expected: diff and JSON checks succeed; the `rg` command prints no matches.

- [ ] **Step 4: Update the quality-gate evidence**

In `docs/aidd/quality-gates.md`, update `Last reviewed` with date `2026-08-10`, the exact backend suite count, and a short note that bounded FCM recovery regressions were added. If `docs/testing/strategy.md` states a suite count, update it to the same number.

- [ ] **Step 5: Perform final self-review against the approved design**

Check every invariant:

- exactly one HA interval timer per listener;
- no new task, Store, config-entry field, migration or dependency;
- only one immediate reconnect after two inactive observations;
- no connection work or repeated warning before an OPEN deadline;
- delays progress 15m → 1h → 6h → 24h and remain at 24h;
- issue ID and runtime state are independent per `entry_id`;
- ordinary unload preserves the persistent issue, confirmed health removes it, entry removal cleans it unconditionally;
- `client.start()` alone does not remove the issue;
- no credential, token, header, payload, phone number or full `entry.data` is logged or placed in Repairs.

- [ ] **Step 6: Commit final verification evidence**

```bash
rtk git add docs/aidd/quality-gates.md docs/testing/strategy.md
rtk git commit -m "docs: record FCM recovery quality gate"
rtk git status --short
```

Expected: the commit succeeds and the final status is clean.

## Acceptance checklist

- [ ] A poison or otherwise fatal FCM message can produce only a bounded initial failure sequence for its config entry.
- [ ] A transient network failure still receives one automatic recovery attempt and later automatic probes.
- [ ] OPEN performs no FCM reconnect before its deadline and owns no additional timer/task.
- [ ] Other config entries and non-FCM integration features remain operational.
- [ ] Home Assistant Repairs shows one localized warning for the affected entry.
- [ ] The warning survives unload/reload, disappears after a confirmed healthy tick, and is removed with the entry.
- [ ] Focused and full pytest suites pass.
- [ ] Audit, architecture, testing, quality-gate and changelog sources are synchronized.
