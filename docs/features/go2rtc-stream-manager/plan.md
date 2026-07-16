# go2rtc Stream Manager Implementation Plan

> **Status (2026-07-16):** Tasks 1-7 and the original Task 8 automated gates
> are complete, but live validation disproved the PATCH-only keep-warm model:
> five registered lazy streams returned RTSP 404/EOF after idle. The preload
> revision in Tasks 9-14 is approved and pending implementation.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep opt-in Home Assistant camera streams reachable through stable external go2rtc RTSP URLs after long idle periods, without disrupting active viewers or publishing disabled cameras.

**Architecture:** Add one `CameraStreamManager` per config entry as the sole writer of operator camera sources named `eg_<camera_id>`. Camera entities retain the proven A-71 recovery triggers but delegate URL minting, concurrency deduplication, PATCH registration, preload activation, retry, and background lifecycle to the manager. A focused `Go2RtcClient` owns transport, and a diagnostic sensor reports actual sanitized manager state. Recorded in [ADR-0014](../../decisions/0014-go2rtc-stream-manager.md).

**Tech Stack:** Python 3.12+, Home Assistant config entries/entity registry/schedulers, `aiohttp`, `voluptuous`, `pytest`, `pytest-homeassistant-custom-component`.

---

## Preconditions and fixed decisions

- Design source of truth: [`design.md`](design.md).
- Branch: `feat/go2rtc-stream-manager`, created from current `master`; do not
  cherry-pick the implementation from `feat/go2rtc-keep-warm`.
- Keep the existing experimental option keys exactly:
  `go2rtc_keep_warm` and `go2rtc_keep_warm_hidden`, both defaulting to `false`.
- The verified refresh interval remains 28 minutes 30 seconds.
- Operator-camera source writes are PATCH-only. Do not add a streams PUT
  fallback. The preload API intentionally uses `PUT /api/preload?src=<name>`.
- `disabled_by` always excludes a camera. `hidden_by` excludes it unless the
  hidden-camera sub-option is enabled.
- With the main keep-warm option off, the manager may serve HA on-demand and
  A-71 recovery calls but must not schedule background operator traffic or
  delete ordinary on-demand streams.
- The manager owns only `eg_<camera_id>` streams. Existing
  `eg_intercom_call` audio/video composition remains outside this feature.
- Before the write-boundary refactor, the focused A-71 baseline was captured:
  `35 passed in 1.09s` for `test_camera_auto_recovery.py`,
  `test_camera_stream_dedup.py`, and `test_go2rtc_upsert.py` on 2026-07-16.

## Target file map

| File | Responsibility |
|---|---|
| `custom_components/elektronny_gorod/const.py` | option keys/defaults and per-entry manager data key |
| `custom_components/elektronny_gorod/config_flow.py` | initial/options-flow persistence of both opt-in flags |
| `custom_components/elektronny_gorod/go2rtc.py` | sanitized stream/preload transport and stable RTSP URL building |
| `custom_components/elektronny_gorod/stream_manager.py` | eligibility, refresh dedup, preload ownership, scheduling, retry, reconcile, cleanup, observable state |
| `custom_components/elektronny_gorod/__init__.py` | manager construction/start/stop and shared per-entry exposure |
| `custom_components/elektronny_gorod/camera.py` | delegate on-demand and existing A-71 paths to manager |
| `custom_components/elektronny_gorod/sensor.py` | diagnostic sensor backed by manager state |
| `custom_components/elektronny_gorod/strings.json` | source strings for options and sensor |
| `custom_components/elektronny_gorod/translations/{ru,en}.json` | localized options and sensor |
| `tests/test_config_flow_keep_warm.py` | option defaults/persistence |
| `tests/test_go2rtc_client.py` | PATCH-only transport, parsing, deletion, secret-safe errors |
| `tests/test_stream_manager.py` | core refresh/dedup/state/failure behavior |
| `tests/test_stream_manager_reconcile.py` | registry eligibility, reconcile, deferred cleanup, restart recovery |
| `tests/test_stream_manager_scheduler.py` | startup jitter, independent due times, retry, unload cleanup |
| `tests/test_sensor_rtsp_urls.py` | truthful diagnostic state and redaction |
| existing camera/go2rtc/call tests | A-71 and two-way-audio regression coverage |

## Task 1: Add the opt-in configuration contract

**Files:**

- Modify: `custom_components/elektronny_gorod/const.py`
- Modify: `custom_components/elektronny_gorod/config_flow.py`
- Modify: `custom_components/elektronny_gorod/strings.json`
- Modify: `custom_components/elektronny_gorod/translations/ru.json`
- Modify: `custom_components/elektronny_gorod/translations/en.json`
- Create: `tests/test_config_flow_keep_warm.py`

- [x] **Step 1: Write failing config-flow tests**

Cover these cases with real HA flow setup and `validate_go2rtc` mocked at the
existing boundary:

- `test_initial_go2rtc_form_defaults_keep_warm_off`: applying the returned
  schema with only `CONF_GO2RTC_BASE_URL` yields `False` for both flags;
- `test_options_flow_persists_keep_warm_flags`: submit both flags as `True`
  and assert both exact values in the create-entry result;
- `test_options_flow_defaults_from_entry_data`: with no option overrides,
  apply the returned schema and assert the values stored in entry data.

- [x] **Step 2: Run the focused test and confirm RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_config_flow_keep_warm.py -q
```

Expected failure: the two constants/schema fields do not exist.

- [x] **Step 3: Add constants without changing config-entry version**

Add to `const.py`:

```python
CONF_GO2RTC_KEEP_WARM: Final = "go2rtc_keep_warm"
CONF_GO2RTC_KEEP_WARM_HIDDEN: Final = "go2rtc_keep_warm_hidden"
DEFAULT_GO2RTC_KEEP_WARM: Final = False
DEFAULT_GO2RTC_KEEP_WARM_HIDDEN: Final = False
STREAM_MANAGER_DATA: Final = f"{DOMAIN}_stream_managers"
```

Do not increment `ConfigFlow.VERSION`; absent values safely read as `False`.

- [x] **Step 4: Persist both fields in initial and options flows**

Add both booleans to the `go2rtc` form and saved entry data. Add them to the
options form and saved options, reading defaults with the existing
`options -> data -> default` precedence. Persist the hidden sub-option even
when the main option is off, but treat it as ineffective in manager policy.

- [x] **Step 5: Add source and translated strings**

Use these labels:

```json
"go2rtc_keep_warm": "Publish enabled cameras for external RTSP",
"go2rtc_keep_warm_hidden": "Also publish hidden cameras"
```

```json
"go2rtc_keep_warm": "Публиковать включённые камеры для внешнего RTSP",
"go2rtc_keep_warm_hidden": "Также публиковать скрытые камеры"
```

The description must say that disabled entities are never published and the
second option works only with the first one.

- [x] **Step 6: Run config-flow regression tests**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_config_flow_keep_warm.py tests/test_config_flow.py -q
```

- [x] **Step 7: Commit**

```bash
git add custom_components/elektronny_gorod/const.py \
  custom_components/elektronny_gorod/config_flow.py \
  custom_components/elektronny_gorod/strings.json \
  custom_components/elektronny_gorod/translations/ru.json \
  custom_components/elektronny_gorod/translations/en.json \
  tests/test_config_flow_keep_warm.py
git commit -m "feat(go2rtc): add opt-in stream publishing options"
```

## Task 2: Introduce the PATCH-only go2rtc transport

**Files:**

- Modify: `custom_components/elektronny_gorod/go2rtc.py`
- Create: `tests/test_go2rtc_client.py`
- Modify: `tests/test_go2rtc_upsert.py`

- [x] **Step 1: Write failing transport tests**

Test the public contract directly with a fake aiohttp session. Use these exact
test cases: `test_patch_stream_uses_patch_without_put_fallback`,
`test_patch_stream_accepts_missing_stream_creation`,
`test_list_streams_parses_complete_mapping`,
`test_get_stream_parses_single_stream_metadata`,
`test_delete_stream_uses_src_name`,
`test_transport_error_does_not_expose_operator_source_or_auth`, and
`test_rtsp_url_can_omit_credentials_for_diagnostics`.

The failure-path assertion must inspect both `str(exc)` and `repr(exc)` and
verify that the operator token, source URL, password, and Authorization value
are absent.

- [x] **Step 2: Run the focused test and confirm RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_go2rtc_client.py -q
```

- [x] **Step 3: Implement typed transport records and sanitized errors**

Add these public shapes in `go2rtc.py`:

```python
@dataclass(frozen=True)
class Go2RtcStreamInfo:
    producers: tuple[dict[str, Any], ...]
    consumer_count: int


class Go2RtcRequestError(RuntimeError):
    """Sanitized go2rtc transport failure."""

    def __init__(self, operation: str, category: str) -> None:
        super().__init__(f"go2rtc {operation} failed: {category}")
        self.operation = operation
        self.category = category
```

Never attach a URL, response body, headers, or underlying `ClientError` text
to the raised exception. Convert exceptions with `raise ... from None`.

- [x] **Step 4: Implement `Go2RtcClient`**

The class constructor receives normalized base URL, RTSP host, shared
`ClientSession`, and optional HTTP/RTSP credentials. Its operator-stream API is:

```python
class Go2RtcClient:
    async def async_patch_stream(self, name: str, src: str) -> None:
        raise NotImplementedError

    async def async_list_streams(self) -> dict[str, Go2RtcStreamInfo]:
        raise NotImplementedError

    async def async_get_stream(self, name: str) -> Go2RtcStreamInfo | None:
        raise NotImplementedError

    async def async_delete_stream(self, name: str) -> None:
        raise NotImplementedError

    def rtsp_url(self, name: str, *, include_credentials: bool) -> str:
        raise NotImplementedError
```

Implementation rules:

- use `ClientTimeout(total=10)`;
- accept HTTP 200/201/204 for PATCH and DELETE, plus 404 for DELETE;
- PATCH query is `name=<name>&src=<src>` and has no PUT branch;
- full-list GET is `/api/streams` and parses the top-level name mapping;
- single-stream GET is `/api/streams?src=<name>`;
- use `go2rtc_auth_headers()` rather than rebuilding Basic auth;
- URL-encode RTSP credentials with `quote(..., safe="")` only when requested;
- credential-free diagnostics return
  `rtsp://<rtsp_host>:8554/<stream_name>`.

Do not refactor `upsert_audio_stream()` in this task: `eg_intercom_call` is a
separate lifecycle and its tested PATCH/PUT compatibility behavior remains.

- [x] **Step 5: Replace camera-level upsert tests with client assertions**

Keep regression proof that PATCH success never invokes PUT and that a PATCH
failure is sanitized. Delete no test unless its behavior is represented by a
new test.

- [x] **Step 6: Run transport and audio regression tests**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_go2rtc_client.py \
  tests/test_go2rtc_upsert.py tests/test_go2rtc_validate.py \
  tests/test_go2rtc_audio.py -q
```

- [x] **Step 7: Commit**

```bash
git add custom_components/elektronny_gorod/go2rtc.py \
  tests/test_go2rtc_client.py tests/test_go2rtc_upsert.py
git commit -m "refactor(go2rtc): add sanitized patch-only client"
```

## Task 3: Build the manager refresh boundary and per-camera dedup

**Files:**

- Create: `custom_components/elektronny_gorod/stream_manager.py`
- Create: `tests/test_stream_manager.py`

- [x] **Step 1: Write failing core manager tests**

Use a fake coordinator and fake `Go2RtcClient`; do not rely only on callbacks.
Implement the exact cases `test_refresh_mints_and_patches_complete_source`,
`test_concurrent_reasons_share_one_operator_request_and_patch`,
`test_sequential_refreshes_mint_separate_operator_urls`,
`test_empty_operator_url_records_failure_without_patch`,
`test_patch_failure_returns_direct_fallback_for_ha_open`,
`test_cancelled_waiter_does_not_cancel_shared_refresh`, and
`test_different_cameras_refresh_independently`.

The first test must assert the full internal chain:

```text
coordinator.get_camera_stream(camera_id)
  -> ffmpeg:<operator-url>#video=copy#audio=aac#audio=opus
  -> client.async_patch_stream("eg_<camera_id>", source)
  -> client.rtsp_url(..., include_credentials=True)
```

- [x] **Step 2: Run the focused test and confirm RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_stream_manager.py -q
```

- [x] **Step 3: Implement immutable refresh results and observable state**

Use monotonic time for scheduling and UTC datetimes only for user-visible
timestamps:

```python
@dataclass(frozen=True)
class StreamRefreshResult:
    url: str | None
    proxied: bool


@dataclass
class ManagedCameraState:
    camera_id: str
    stream_name: str
    display_name: str
    eligible: bool = False
    present: bool = False
    consumer_count: int = 0
    last_success: datetime | None = None
    last_success_monotonic: float | None = None
    next_due_monotonic: float | None = None
    failure_count: int = 0
    status: str = "idle"
    cleanup_pending: bool = False
```

Expose only copied/immutable diagnostic snapshots. Listeners receive no source
URL and can only request a state refresh.

- [x] **Step 4: Implement one in-flight owner per camera**

`CameraStreamManager.async_refresh(camera_id, reason)` must:

1. join an existing future with `asyncio.shield()`;
2. mint one fresh operator URL;
3. PATCH one built source through `Go2RtcClient`;
4. record success and return the authenticated local RTSP URL;
5. on PATCH failure, record only the sanitized category and return the already
   minted direct URL with `proxied=False` so HA-open keeps its current graceful
   fallback;
6. resolve/cancel the shared future in every exception/cancellation path;
7. remove the future from the map only if it is still the current owner.

The raw operator URL must not be retained in `ManagedCameraState`, logs,
diagnostics, or raised errors.

- [x] **Step 5: Run core manager tests**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_stream_manager.py -q
```

- [x] **Step 6: Commit**

```bash
git add custom_components/elektronny_gorod/stream_manager.py \
  tests/test_stream_manager.py
git commit -m "feat(go2rtc): add camera stream manager core"
```

## Task 4: Add eligibility, scheduling, retry, and reconciliation

**Files:**

- Modify: `custom_components/elektronny_gorod/stream_manager.py`
- Create: `tests/test_stream_manager_reconcile.py`
- Create: `tests/test_stream_manager_scheduler.py`

- [x] **Step 1: Write the failing registry eligibility matrix**

Test all meaningful combinations against actual HA entity-registry entries:

| Main | `disabled_by` | `hidden_by` | Hidden option | Eligible |
|---:|---|---|---:|---:|
| off | none | none | off | no |
| on | none | none | off | yes |
| on | integration/user | any | on/off | no |
| on | none | integration/user | off | no |
| on | none | integration/user | on | yes |

Also test that API `camera_info["hidden"]` cannot override registry state.

- [x] **Step 2: Write failing reconcile tests**

Implement the exact cases `test_reconcile_uses_one_complete_stream_list_request`,
`test_missing_eligible_stream_runs_full_refresh_chain`,
`test_go2rtc_restart_is_recovered_on_next_reconcile`,
`test_disabled_stream_with_no_consumers_is_deleted`,
`test_disabled_stream_with_consumers_defers_delete`,
`test_deferred_cleanup_runs_when_consumers_reach_zero`,
`test_hidden_stream_requires_hidden_suboption`,
`test_keep_warm_off_does_not_delete_on_demand_streams`, and
`test_unknown_list_response_preserves_existing_streams`.

The restart test must first complete a successful PATCH, then replace the fake
go2rtc stream map with `{}`, invoke reconcile, and assert a new operator request
and PATCH. Asserting only that a refresh callback was scheduled is insufficient.

- [x] **Step 3: Write failing scheduler and retry tests**

Implement the exact cases
`test_startup_offsets_are_deterministic_bounded_and_distinct`,
`test_each_success_rebases_only_that_cameras_28m30s_due_time`,
`test_slow_camera_does_not_delay_other_camera`,
`test_retry_delays_are_15_30_60_then_capped_at_300_seconds`,
`test_success_resets_retry_and_returns_to_28m30s`,
`test_registry_update_schedules_one_prompt_reconcile`, and
`test_stop_cancels_timer_listener_callbacks_and_inflight_tasks`.

- [x] **Step 4: Run new tests and confirm RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_stream_manager_reconcile.py \
  tests/test_stream_manager_scheduler.py -q
```

- [x] **Step 5: Implement registry-derived desired state**

Resolve each camera entity by stable unique ID
`elektronny_gorod_camera_<camera_id>`. Eligibility is exactly:

```python
return (
    self.keep_warm
    and registry_entry is not None
    and registry_entry.disabled_by is None
    and (
        registry_entry.hidden_by is None
        or self.keep_warm_hidden
    )
)
```

When the main option is off, do not create background timers, retries, or
cleanup ownership. When it is on, hidden/disabled streams are outside desired
state and are cleaned according to consumer count.

- [x] **Step 6: Implement independent scheduling**

Keep timing constants local to `stream_manager.py`:

```python
BACKGROUND_REFRESH_INTERVAL = timedelta(minutes=28, seconds=30)
RECONCILE_INTERVAL = timedelta(minutes=1)
STARTUP_JITTER_MAX_SECONDS = 60.0
RETRY_DELAYS_SECONDS = (15.0, 30.0, 60.0)
RETRY_MAX_SECONDS = 300.0
```

Derive initial offset from SHA-256 of `entry_id:camera_id`, modulo 60 seconds.
Use a separate `async_call_later` cancellation handle for each camera. A
successful refresh sets that camera's next due to completion monotonic time +
1710 seconds. Failures schedule 15, 30, 60, 120, 240, then 300 seconds.

- [x] **Step 7: Implement one-minute full reconciliation**

Every tick calls `client.async_list_streams()` once. For each current
coordinator camera:

- missing and eligible: start/join `async_refresh(..., "missing")`;
- present and eligible: update presence/consumer observations;
- ineligible while main keep-warm is on and zero consumers: DELETE;
- ineligible with consumers: mark `cleanup_pending` and retry next minute;
- list failure: update sanitized manager status, do not delete anything.

The entity-registry listener only marks state dirty and coalesces a prompt
reconcile. Config option changes continue to reload the entry.

- [x] **Step 8: Implement idempotent stop**

Cancel the registry listener, one-minute interval, prompt reconcile callback,
all per-camera due handles, and owned background tasks. Cancel shared futures
so no waiter can hang. `async_stop()` must be safe when called twice.

- [x] **Step 9: Run manager suites**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_stream_manager.py \
  tests/test_stream_manager_reconcile.py \
  tests/test_stream_manager_scheduler.py -q
```

- [x] **Step 10: Commit**

```bash
git add custom_components/elektronny_gorod/stream_manager.py \
  tests/test_stream_manager_reconcile.py \
  tests/test_stream_manager_scheduler.py
git commit -m "feat(go2rtc): reconcile eligible external rtsp streams"
```

## Task 5: Wire lifecycle and delegate camera writes

**Files:**

- Modify: `custom_components/elektronny_gorod/__init__.py`
- Modify: `custom_components/elektronny_gorod/camera.py`
- Modify: `tests/test_camera_stream_dedup.py`
- Modify: `tests/test_camera_auto_recovery.py`
- Modify: `tests/test_camera_call_video_rtsp.py`
- Modify: `tests/test_stream_manager_scheduler.py`

- [x] **Step 1: Add failing setup/unload integration tests**

Prove this exact setup order with mocks/events:

```text
coordinator first refresh
  -> manager stored in hass.data[STREAM_MANAGER_DATA][entry_id]
  -> camera/sensor platform setup sees the same manager
  -> visibility sync completes
  -> manager.async_start()
```

On unload, assert the manager is stopped and removed from shared data, with no
scheduled callbacks or owned tasks remaining.

- [x] **Step 2: Change camera tests to assert manager delegation**

Keep the behavioral assertions from the 35-test baseline:

- concurrent `stream_source()` calls share one operator request and PATCH;
- later sequential calls mint a new URL;
- unavailable HA Stream triggers refresh and `Stream.update_source()`;
- producer-health stall triggers refresh;
- active-consumer proactive refresh delegates with no forced HA restart;
- call-camera live-producer reuse avoids a second operator URL;
- direct FLV behavior is unchanged when go2rtc is disabled.

- [x] **Step 3: Run focused tests and confirm RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_camera_stream_dedup.py \
  tests/test_camera_auto_recovery.py tests/test_camera_call_video_rtsp.py \
  tests/test_stream_manager_scheduler.py -q
```

- [x] **Step 4: Create and expose the manager before platform forwarding**

In `async_setup_entry`, after the coordinator first refresh and before
`async_forward_entry_setups`:

1. if go2rtc is configured and enabled, build `Go2RtcClient` with
   `async_get_clientsession(hass)`;
2. create `CameraStreamManager`;
3. store it at `hass.data[STREAM_MANAGER_DATA][entry.entry_id]`;
4. register idempotent manager stop with config-entry lifecycle.

After platforms and `_sync_visibility`, call `await manager.async_start()`.
Temporary go2rtc failure must not fail integration setup.

- [x] **Step 5: Make camera entities depend on the manager**

Pass the shared manager to each ordinary `ElektronnyGorodCamera`. Preserve
existing go2rtc config extraction for `ElektronnyGorodCallCamera` only.

Replace the camera-owned `_go2rtc_upsert_stream`, `_last_src`, auth-header
builder, and in-flight future with manager calls. Keep the A-71 cooldown,
health-poll, proactive trigger, and HA `Stream.update_source()` coordination in
`camera.py`.

The on-demand path becomes:

```python
result = await self._stream_manager.async_refresh(self._id, "ha_open")
return result.url
```

The recovery path becomes:

```python
result = await self._stream_manager.async_refresh(self._id, "recovery")
if result.proxied and force_restart and self.stream is not None:
    self.stream.update_source(result.url)
```

The proactive path uses reason `active_consumer` and does not call
`Stream.update_source()`. Stream-info reads delegate to the manager/client and
remain read-only.

- [x] **Step 6: Stop and remove the manager during unload**

Stop before removing shared state. Keep cleanup idempotent because HA may also
invoke the registered unload callback. Do not delete go2rtc streams merely
because an entry reloads; eligibility cleanup is reconcile policy.

- [x] **Step 7: Run the A-71 comparison suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_camera_auto_recovery.py \
  tests/test_camera_stream_dedup.py tests/test_go2rtc_upsert.py -q
```

Expected: at least the same 35 behavioral cases pass, with direct transport
assertions moved to the client tests where appropriate.

- [x] **Step 8: Run call-camera and visibility regressions**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_camera_call_video_rtsp.py \
  tests/test_call_camera.py tests/test_visibility.py \
  tests/test_visibility_real.py tests/test_visibility_user_override.py -q
```

- [x] **Step 9: Commit**

```bash
git add custom_components/elektronny_gorod/__init__.py \
  custom_components/elektronny_gorod/camera.py \
  tests/test_camera_stream_dedup.py \
  tests/test_camera_auto_recovery.py \
  tests/test_camera_call_video_rtsp.py \
  tests/test_stream_manager_scheduler.py
git commit -m "refactor(camera): delegate go2rtc writes to stream manager"
```

## Task 6: Add truthful credential-free diagnostics

**Files:**

- Modify: `custom_components/elektronny_gorod/sensor.py`
- Modify: `custom_components/elektronny_gorod/strings.json`
- Modify: `custom_components/elektronny_gorod/translations/ru.json`
- Modify: `custom_components/elektronny_gorod/translations/en.json`
- Create: `tests/test_sensor_rtsp_urls.py`

- [x] **Step 1: Write failing sensor tests**

Implement the exact cases
`test_sensor_counts_only_present_fresh_eligible_streams`,
`test_sensor_does_not_claim_desired_but_failed_stream`,
`test_sensor_updates_when_manager_state_changes`,
`test_sensor_urls_are_credential_free`,
`test_sensor_attributes_never_contain_operator_url_or_token`, and
`test_sensor_is_absent_when_go2rtc_is_disabled`.

- [x] **Step 2: Run the focused test and confirm RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sensor_rtsp_urls.py -q
```

- [x] **Step 3: Implement `ElektronnyGorodRtspUrlsSensor`**

Add one diagnostic-category sensor only when a manager exists. It is not a
`CoordinatorEntity`; it subscribes to sanitized manager-state changes.

- `native_value`: count of eligible streams that are present and whose last
  successful refresh is no older than 28 minutes 30 seconds;
- `urls`: display-name to credential-free stable RTSP URL for those streams;
- `streams`: per-camera objects containing only `camera_id`, `status`,
  `present`, `consumer_count`, and ISO `last_success`;
- unique ID: `elektronny_gorod_<entry_id>_go2rtc_rtsp_urls`;
- translation key: `go2rtc_rtsp_urls`;
- icon: `mdi:cctv`;
- entity category: diagnostic.

Do not expose the authenticated HA RTSP URL. A username/password in config
must never appear in state attributes.

- [x] **Step 4: Run sensor and platform regression tests**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sensor_rtsp_urls.py \
  tests/test_sensor_call_state.py -q
```

- [x] **Step 5: Commit**

```bash
git add custom_components/elektronny_gorod/sensor.py \
  custom_components/elektronny_gorod/strings.json \
  custom_components/elektronny_gorod/translations/ru.json \
  custom_components/elektronny_gorod/translations/en.json \
  tests/test_sensor_rtsp_urls.py
git commit -m "feat(sensor): report actual external rtsp readiness"
```

## Task 7: Record the architecture and audit trail

**Files:**

- Create: `docs/decisions/0014-go2rtc-stream-manager.md`
- Modify: `docs/decisions/README.md`
- Modify: `docs/audit/project-audit.md`
- Modify: `docs/project/project-map.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/testing/strategy.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/features/go2rtc-stream-manager/design.md`
- Modify: `docs/features/go2rtc-stream-manager/plan.md`
- Modify: `CHANGELOG.md`

- [x] **Step 1: Add ADR-0014**

Record status `accepted`, context (idle 500/EOF), decision (single writer,
PATCH-only, registry eligibility, one-minute in-memory recovery), alternatives
(old entity timers, PUT fallback, discard feature), consequences, and links to
ADR-0009/A-82/A-84/A-96.

- [x] **Step 2: Add audit A-96**

Mark automated implementation status separately from production acceptance.
Do not claim the idle-over-one-hour path fixed until the live checklist passes.

- [x] **Step 3: Synchronize maps and testing docs**

Update stale architecture text that currently describes camera-owned PUT and
`Camera._last_src`. Document manager state ownership, option defaults,
transport boundary, test files, and the mandatory live acceptance gate.

- [x] **Step 4: Run documentation consistency checks**

```bash
rg -n "camera-owned PUT|_last_src|pending written-spec review|A-96|ADR-0014" docs
rg -n "TODO|TBD|PLACEHOLDER|</content>" docs/features/go2rtc-stream-manager
```

Review every hit; the finished feature package must contain no placeholder or
false completion claim.

- [x] **Step 5: Commit**

```bash
git add docs/decisions/0014-go2rtc-stream-manager.md \
  docs/decisions/README.md docs/audit/project-audit.md \
  docs/project/project-map.md docs/architecture/overview.md \
  docs/testing/strategy.md docs/roadmap.md CHANGELOG.md \
  docs/features/go2rtc-stream-manager
git commit -m "docs(go2rtc): record stream manager architecture"
```

## Task 8: Run automated gates and prepare live acceptance

**Files:**

- Create after live run: `docs/features/go2rtc-stream-manager/qa-report.md`

- [x] **Step 1: Run focused feature suites**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_config_flow_keep_warm.py \
  tests/test_go2rtc_client.py tests/test_stream_manager.py \
  tests/test_stream_manager_reconcile.py \
  tests/test_stream_manager_scheduler.py tests/test_sensor_rtsp_urls.py -q
```

- [x] **Step 2: Run all go2rtc/camera/config/visibility regressions**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_go2rtc_*.py tests/test_camera_*.py \
  tests/test_call_camera.py tests/test_config_flow.py \
  tests/test_visibility*.py -q
```

- [x] **Step 3: Run the full suite**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

- [x] **Step 4: Inspect the final diff and secret surface**

```bash
git diff --check
git status --short
rg -n "LOGGER\.(debug|info|warning|error|exception).*\{.*\}" \
  custom_components/elektronny_gorod
rg -n "operator_url|access_token|refresh_token|Authorization|go2rtc_password" \
  custom_components/elektronny_gorod/stream_manager.py \
  tests/test_stream_manager*.py tests/test_sensor_rtsp_urls.py
```

Review the hits manually. Test fixtures may contain obvious fake tokens; code
must not log or expose them.

- [ ] **Step 5: Execute the production acceptance checklist**

On the owner's real HA/go2rtc deployment:

1. enable `go2rtc_keep_warm`, leave one visible enabled camera idle for over
   one hour, then open its external RTSP URL without opening HA first;
2. hold an active consumer across a scheduled PATCH and confirm no disconnect;
3. restart go2rtc and confirm the stream returns within 60 seconds;
4. disable a camera, close its consumers, and confirm its `eg_<id>` disappears;
5. hide a camera and confirm publication follows the hidden sub-option;
6. trigger background/HA/recovery concurrently and confirm one operator mint
   and one PATCH in sanitized diagnostics/test instrumentation;
7. reload/unload the entry and confirm no manager callbacks continue.

- [ ] **Step 6: Write the QA report truthfully**

Create `qa-report.md` with timestamps, environment versions, each scenario's
observable evidence, automated test count, and any failure. Change the design
status to implemented/verified only after all seven live scenarios pass.

- [ ] **Step 7: Close or supersede PR #61 only after live acceptance**

Reference the replacement branch/PR, credit the original opt-in and diagnostic
concept, and explain that the old implementation did not prove the full idle
external-RTSP chain. Do not close it before the replacement evidence exists.

## Preload revision after live failure

Live checks on 2026-07-16 found five `eg_<camera_id>` entries with one lazy
producer and no consumers. The HTML page returned normally, but direct RTSP
DESCRIBE returned 404/EOF. Only doorbell streams already kept active by
background loading survived. Tasks 9-14 replace the disproved assumption that
PATCH registration alone keeps a disposable operator URL usable.

## Task 9: Add the sanitized preload transport contract

**Files:**

- Modify: `custom_components/elektronny_gorod/go2rtc.py`
- Modify: `tests/test_go2rtc_client.py`
- Modify: `tests/test_camera_auto_recovery.py`

- [ ] **Step 1: Write RED tests for sanitized producer health**

Add a lazy producer fixture containing an obvious secret URL and an active
producer fixture containing `bytes_recv`. Assert that the parsed result exposes
only safe health metadata and a boolean:

```python
assert streams["eg_lazy"].producer_active is False
assert streams["eg_active"].producer_active is True
assert "OPERATOR_SECRET" not in repr(streams)
```

Keep `bytes_recv` available for the existing A-71 health poll, but strip the
raw producer `url` before constructing `Go2RtcStreamInfo`.

- [ ] **Step 2: Write RED tests for preload list/enable/disable**

Cover these exact cases:

- `GET /api/preload` returns only string keys from a mapping;
- a non-mapping response raises `Go2RtcRequestError("preload_list", ...)`;
- `PUT /api/preload?src=eg_42` accepts 200/201/204;
- `DELETE /api/preload?src=eg_42` accepts 200/201/204/404;
- timeout, aiohttp error, and HTTP 500 expose only a sanitized operation and
  category, never response text, credentials, or a source URL.

- [ ] **Step 3: Run the focused tests and confirm RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_go2rtc_client.py \
  tests/test_camera_auto_recovery.py -q
```

Expected failures: preload methods and `producer_active` do not exist.

- [ ] **Step 4: Implement the typed client surface**

Extend the existing record and client without adding a streams PUT fallback:

```python
@dataclass(frozen=True)
class Go2RtcStreamInfo:
    producers: tuple[dict[str, Any], ...]
    consumer_count: int
    producer_active: bool

async def async_list_preloads(self) -> set[str]: ...
async def async_enable_preload(self, name: str) -> None: ...
async def async_disable_preload(self, name: str) -> None: ...
```

`_parse_stream_info` computes activity from the raw producer object but stores
only the integer `bytes_recv` field needed by `camera.py`. Preload mutation
uses the shared auth headers and ten-second timeout. Every exception crosses
the boundary as `Go2RtcRequestError(... ) from None`.

- [ ] **Step 5: Run GREEN and commit**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_go2rtc_client.py \
  tests/test_camera_auto_recovery.py -q
git add custom_components/elektronny_gorod/go2rtc.py \
  tests/test_go2rtc_client.py tests/test_camera_auto_recovery.py
git commit -m "feat(go2rtc): add sanitized preload transport"
```

## Task 10: Activate preload in the deduplicated refresh chain

**Files:**

- Modify: `custom_components/elektronny_gorod/stream_manager.py`
- Modify: `tests/test_stream_manager.py`
- Modify: `tests/test_stream_manager_scheduler.py`

- [ ] **Step 1: Write RED initial-activation tests**

For an eligible keep-warm camera, assert exact ordering through mock call
history:

```text
coordinator.get_camera_stream -> client.async_patch_stream
  -> client.async_enable_preload
```

After success, assert `present`, `preloaded`, and `producer_active` are true.
For keep-warm off or an ineligible camera, assert the existing on-demand PATCH
still works and preload is not called.

- [ ] **Step 2: Write RED failure and dedup tests**

Make preload PUT fail with `Go2RtcRequestError("preload_enable", "http_500")`.
Assert the PATCHed stream remains present, the camera is not ready, the caller
gets the existing direct-source fallback, and the retry schedule starts at 15
seconds. A later retry must mint a different URL before PATCH and preload.

Run three concurrent background/HA/recovery callers and assert one mint, one
PATCH, and one preload PUT.

- [ ] **Step 3: Write the RED active-preload refresh test**

Seed `state.preloaded = True` and `state.producer_active = True`, then refresh.
Assert a fresh mint and PATCH occur but preload PUT does not. This preserves
the current producer and external consumers across the verified 28:30 refresh.

- [ ] **Step 4: Run the focused tests and confirm RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_stream_manager.py \
  tests/test_stream_manager_scheduler.py -q
```

- [ ] **Step 5: Implement refresh state and activation**

Add credential-free state only:

```python
preloaded: bool = False
producer_active: bool = False
```

After successful PATCH, enable preload only when all are true: keep-warm is
enabled, registry policy says the camera is eligible, and the state does not
already record an active preload. Do not mark refresh success until required
preload activation succeeds. A preload failure calls the same sanitized
failure/retry path as PATCH failure.

- [ ] **Step 6: Run GREEN and commit**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_stream_manager.py \
  tests/test_stream_manager_scheduler.py -q
git add custom_components/elektronny_gorod/stream_manager.py \
  tests/test_stream_manager.py tests/test_stream_manager_scheduler.py
git commit -m "feat(go2rtc): preload eligible camera streams"
```

## Task 11: Reconcile stream, preload, and producer health

**Files:**

- Modify: `custom_components/elektronny_gorod/stream_manager.py`
- Modify: `tests/test_stream_manager_reconcile.py`

- [ ] **Step 1: Write RED snapshot and recovery tests**

Extend the fake client with `async_list_preloads`. One reconcile must request
exactly one complete stream map and one complete preload map. Cover:

1. missing stream and preload -> fresh mint/PATCH/preload;
2. present stream but missing preload -> fresh mint/PATCH/preload;
3. present preload with active producer -> no immediate recovery;
4. present preload with lazy/inactive producer -> fresh mint/PATCH and preload
   re-arm;
5. simulated go2rtc restart (both maps empty) -> restore the complete chain on
   the next reconcile;
6. a preload-list error preserves all streams and schedules no destructive
   work.

- [ ] **Step 2: Write RED cleanup-order tests**

For a newly disabled/hidden camera, assert preload DELETE happens before the
exact per-stream GET. If zero consumers remain, delete the stream. If external
consumers remain, keep the stream, cancel refresh scheduling, and mark cleanup
pending. A later zero-consumer reconcile deletes it. Missing preload and 404
are idempotent success.

- [ ] **Step 3: Run the reconcile tests and confirm RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_stream_manager_reconcile.py -q
```

- [ ] **Step 4: Implement one locked two-map reconcile**

Within `_reconcile_lock`, list streams and preloads before mutating state.
Populate `present`, `consumer_count`, `preloaded`, and `producer_active` from
those snapshots. For an inactive preloaded producer, clear the observed
preload state before joining `async_refresh`; the successful refresh then
re-arms the existing preload only after a new PATCH.

Cleanup must call a dedicated coroutine with this order:

```text
disable preload -> get exact stream state ->
  consumers > 0: defer
  consumers == 0: delete stream
```

- [ ] **Step 5: Run GREEN and commit**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_stream_manager_reconcile.py \
  tests/test_stream_manager.py -q
git add custom_components/elektronny_gorod/stream_manager.py \
  tests/test_stream_manager_reconcile.py
git commit -m "fix(go2rtc): reconcile preload producer health"
```

## Task 12: Remove manager background consumers on off/unload

**Files:**

- Modify: `custom_components/elektronny_gorod/stream_manager.py`
- Modify: `tests/test_stream_manager_scheduler.py`
- Modify: `tests/test_stream_manager_lifecycle.py`

- [ ] **Step 1: Write RED option-off startup cleanup test**

With keep-warm off and stale `eg_100`/`eg_200` preloads present, `async_start`
must remove those preloads once, mint no operator URLs, install no timers or
registry listener, and leave ordinary on-demand streams untouched.

- [ ] **Step 2: Write RED unload/idempotence tests**

After adopting or creating an eligible preload, `async_stop` must first cancel
callbacks/tasks and then best-effort DELETE every manager camera preload.
Calling stop twice must not repeat network cleanup or fail. A sanitized delete
failure must not prevent config-entry unload.

- [ ] **Step 3: Run the lifecycle tests and confirm RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_stream_manager_scheduler.py \
  tests/test_stream_manager_lifecycle.py -q
```

- [ ] **Step 4: Implement stale-preload adoption and cleanup ownership**

Track stable names only, never source URLs. Startup always performs the minimal
preload inventory needed to remove stale names when the option is off. Normal
unload removes manager preloads but does not delete stream registrations or
disconnect external consumers.

- [ ] **Step 5: Run GREEN and commit**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_stream_manager_scheduler.py \
  tests/test_stream_manager_lifecycle.py -q
git add custom_components/elektronny_gorod/stream_manager.py \
  tests/test_stream_manager_scheduler.py tests/test_stream_manager_lifecycle.py
git commit -m "fix(go2rtc): clean preloads on option off and unload"
```

## Task 13: Make diagnostics require an active preload producer

**Files:**

- Modify: `custom_components/elektronny_gorod/sensor.py`
- Modify: `tests/test_sensor_rtsp_urls.py`

- [ ] **Step 1: Write RED truthful-readiness tests**

Keep freshness and eligibility checks, then add cases where registration is
fresh but preload is missing or producer is inactive. Both must report zero
ready URLs. Extend every per-camera sanitized object with `preloaded` and
`producer_active`, and assert secret URLs/passwords remain absent.

- [ ] **Step 2: Run the sensor tests and confirm RED**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sensor_rtsp_urls.py -q
```

- [ ] **Step 3: Implement the diagnostic predicate and attributes**

`_is_fresh` must require all of:

```python
state.eligible
and state.present
and state.preloaded
and state.producer_active
and state.last_success_monotonic is not None
and 0 <= age <= BACKGROUND_REFRESH_INTERVAL.total_seconds()
```

- [ ] **Step 4: Run GREEN and commit**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_sensor_rtsp_urls.py \
  tests/test_sensor_call_state.py -q
git add custom_components/elektronny_gorod/sensor.py \
  tests/test_sensor_rtsp_urls.py
git commit -m "fix(sensor): require active go2rtc preload"
```

## Task 14: Synchronize docs, verify, publish, and repeat live acceptance

**Files:**

- Modify: `docs/decisions/0014-go2rtc-stream-manager.md`
- Modify: `docs/audit/project-audit.md`
- Modify: `docs/project/project-map.md`
- Modify: `docs/architecture/overview.md`
- Modify: `docs/testing/strategy.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/features/go2rtc-stream-manager/{design,plan}.md`
- Modify: `CHANGELOG.md`
- Create after live completion: `docs/features/go2rtc-stream-manager/qa-report.md`

- [ ] **Step 1: Run focused and related suites**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_go2rtc_client.py \
  tests/test_stream_manager.py tests/test_stream_manager_reconcile.py \
  tests/test_stream_manager_scheduler.py tests/test_stream_manager_lifecycle.py \
  tests/test_sensor_rtsp_urls.py tests/test_camera_auto_recovery.py -q
PYTHONPATH=. .venv/bin/pytest tests/test_go2rtc_*.py tests/test_camera_*.py \
  tests/test_call_camera.py tests/test_config_flow.py tests/test_visibility*.py -q
```

- [ ] **Step 2: Synchronize architecture and audit truth**

Use the project documentation update workflow. Revise ADR-0014 and A-96 from
PATCH-only registration to PATCH plus dedicated preload lifecycle. Record the
five-camera failure as evidence against the old model. Do not claim the
idle-over-one-hour scenario fixed before the repeat live run passes.

- [ ] **Step 3: Run full current and minimum-HA gates**

```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```

Push only after the local suite is green, then verify both PR #71 CI variants
(`min` and current), hassfest/HACS, and the updated pre-release artifact.

- [ ] **Step 4: Inspect diff and secret surface**

```bash
git diff --check
git status --short
rg -n "TODO|TBD|PLACEHOLDER|</content>" \
  docs/features/go2rtc-stream-manager
rg -n "operator_url|access_token|refresh_token|Authorization|go2rtc_password" \
  custom_components/elektronny_gorod/stream_manager.py \
  custom_components/elektronny_gorod/go2rtc.py \
  tests/test_stream_manager*.py tests/test_sensor_rtsp_urls.py
```

- [ ] **Step 5: Repeat production acceptance on the five failed cameras**

Use `eg_5595470`, `eg_5595471`, `eg_5595472`, `eg_5593584`, and
`eg_5593570`. Confirm each has a preload and active producer, survives idle,
and opens externally without first opening HA. Then repeat active-viewer PATCH,
go2rtc restart, disabled/hidden cleanup, concurrent trigger, and unload checks.
Record observations in `qa-report.md`; only then mark A-96 and this plan
verified and supersede PR #61.

- [ ] **Step 6: Commit documentation and live evidence separately**

```bash
git add docs CHANGELOG.md
git commit -m "docs(go2rtc): record preload stream lifecycle"
```

Commit `qa-report.md` and final status changes only after the real deployment
evidence exists.

## Rollback

The runtime rollback is to turn off `go2rtc_keep_warm`; startup/unload removes
manager preload consumers and stops background operator traffic while
preserving ordinary go2rtc on-demand behavior. Code
rollback should revert the feature commits in reverse order. Do not remove
the option keys or translations in a patch rollback because installations that
tested the feature may retain those option values.

## Completion gate

The original PATCH-only implementation is not complete despite its green test
suite. Automated implementation is complete when Tasks 9-14 through the full
test/CI gates pass. The feature is merge-ready only after all eight revised
production acceptance scenarios are recorded in `qa-report.md`.
