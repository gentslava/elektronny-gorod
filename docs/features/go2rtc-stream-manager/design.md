# Design: go2rtc stream manager for external RTSP

- **Status:** approved by owner; implementation planned
- **Date:** 2026-07-16
- **Branch:** `feat/go2rtc-stream-manager`
- **Origin:** replacement for the unmerged PR #61 and
  `feat/go2rtc-keep-warm`
- **Related:** ADR-0009, audit A-82/A-83/A-84
- **Planned records:** ADR-0014, audit A-96

## Problem

The integration registers stable local names such as `eg_<camera_id>` in
go2rtc, but each upstream Forpost URL represents an operator session with an
observed lifetime of about 30 minutes. When a camera has no consumer, its
registered source becomes stale. A later external RTSP connection fails with
`500/EOF` until Home Assistant opens the camera and causes `stream_source()` to
mint and register a fresh upstream URL.

The previous keep-warm branch refreshed camera entities in the background, but
production acceptance failed: after a long idle period the external RTSP path
still needed a Home Assistant open. Its unit tests proved callback scheduling,
not the complete path from operator URL minting through go2rtc registration to
external playback.

## Goals and acceptance criteria

When the feature is enabled, every eligible camera must have a stable external
RTSP address that can be opened without first touching the camera in Home
Assistant.

The implementation is accepted only when all of these scenarios pass:

1. After more than one hour without a viewer, an external client opens
   `rtsp://<go2rtc-host>:8554/eg_<camera_id>` successfully without a prior HA
   camera open.
2. An active consumer survives a scheduled source refresh.
3. After a go2rtc restart, eligible streams are recreated within one minute.
4. A disabled camera is no longer refreshed and is removed after its consumers
   leave.
5. A hidden camera is published only when the hidden-camera sub-option is on.
6. Concurrent background, HA-open, and recovery requests for one camera result
   in one operator request and one go2rtc PATCH.
7. Config-entry unload leaves no manager timers or background tasks.

## Non-goals

- Keeping every producer continuously connected or using go2rtc preload.
- Per-camera selection in the first version.
- Changing the operator API contract or introducing endpoints not observed in
  the mobile application.
- Rewriting the proven A-71 recovery state machine as part of this feature.
- Managing `eg_intercom_call`; the manager owns only operator camera streams
  named `eg_<camera_id>`.

## Configuration and eligibility

Retain the option keys already used by the old test branch so an installation
that tested it keeps its settings:

| Key | Default | Meaning |
|---|---:|---|
| `go2rtc_keep_warm` | `false` | Publish eligible cameras for external RTSP without a viewer |
| `go2rtc_keep_warm_hidden` | `false` | Also publish hidden eligible cameras; effective only when the main option is on |

Home Assistant registry state is the source of truth. API visibility flags are
not used for eligibility.

```text
eligible(camera) =
  go2rtc_keep_warm
  AND registry_entry.disabled_by is None
  AND (
    registry_entry.hidden_by is None
    OR go2rtc_keep_warm_hidden
  )
```

`disabled_by` always wins. A disabled camera is never background-published,
even when the hidden-camera option is enabled.

Both options remain opt-in and default off. Enabling ordinary go2rtc support
alone does not add background operator traffic. The manager still serves the
existing on-demand and recovery paths when keep-warm is off.

## Architecture and ownership

### Go2RtcClient

`go2rtc.py` provides a single transport boundary for:

- PATCHing a named source;
- listing registered streams and their producer/consumer metadata;
- deleting a named stream;
- building authenticated API requests;
- building credential-free diagnostic RTSP addresses.

Sensitive operator URLs and authentication headers never appear in exception
messages returned to callers.

### CameraStreamManager

A new `CameraStreamManager` instance is created per config entry. It owns the
policy and mutable state for `eg_<camera_id>`:

- registry eligibility;
- startup and periodic scheduling;
- one in-flight refresh future per camera;
- last successful refresh time and next due time;
- failure count and retry deadline;
- last observed go2rtc presence/consumer state;
- pending cleanup for streams that still have consumers.

The manager is the only component allowed to write operator camera sources to
go2rtc. Camera entities, proactive refresh, and recovery all call the same
manager method.

### Camera entity

`ElektronnyGorodCamera` retains its HA-specific responsibilities and the proven
A-71 recovery triggers. It no longer performs go2rtc writes directly.

- `stream_source()` asks the manager to mint/register the source, then returns
  the stable RTSP address.
- Event-driven and producer-health recovery ask the manager for a refresh.
- The existing active-consumer proactive timer remains an A-71 trigger in
  `camera.py` for this slice and delegates its write to the manager.
- Existing active-consumer timing and HA `Stream.update_source()` coordination
  remain behaviorally unchanged.

This deliberately avoids a wholesale A-83 refactor. The feature extracts the
write boundary required for single ownership without moving the entire
deterministically tuned recovery state machine.

### Diagnostic sensor

`ElektronnyGorodRtspUrlsSensor` reads manager state rather than inferring
success from coordinator data.

- `native_value`: number of eligible streams that were present at the latest
  reconcile and successfully refreshed within the operator TTL;
- `urls`: camera display name to credential-free stable RTSP address;
- per-camera last-success timestamps and sanitized status;
- no operator URL, token, password, or Authorization header.

The sensor reports registration freshness, not proof that a remote client can
decode video. End-to-end playback is covered by production acceptance.

## Lifecycle

Setup order:

```text
coordinator first refresh
  -> create Go2RtcClient and CameraStreamManager
  -> expose manager for camera-platform setup
  -> forward entity platforms
  -> synchronize entity visibility
  -> start manager scheduling and registry listener
```

Creating the manager before camera setup gives entities one stable dependency.
Starting it after entity setup and visibility synchronization ensures registry
entries exist and eligibility is correct on the first run.

On unload, the registry listener, reconcile timer, scheduled camera callbacks,
and pending manager tasks are cancelled. A reload creates one fresh manager;
no task or state is shared across config-entry lifetimes.

## Data flows

All write reasons use one operation:

```text
background due | HA open | A-71 recovery
  -> CameraStreamManager.async_refresh(camera_id, reason)
  -> join existing per-camera in-flight future, if any
  -> coordinator.get_camera_stream(camera_id)
  -> Go2RtcClient.patch_stream(
       name="eg_<camera_id>",
       src="ffmpeg:<operator-url>#video=copy#audio=aac#audio=opus"
     )
  -> update per-camera success state
  -> return stable local RTSP address
```

The refresh operation does not require the stream to exist before PATCHing.
PATCH creates a missing in-memory stream or updates the source of an existing
one. A missing-stream check is a trigger, not a precondition.

Concurrent callers share only the in-flight result. A later sequential HA open
continues to mint a fresh operator session, preserving current behavior.

## Scheduling and reconciliation

The proactive interval verified in the owner's runtime testing remains
`GO2RTC_PROACTIVE_REFRESH_INTERVAL = 28 minutes 30 seconds`.

### Startup

Eligible cameras receive a deterministic startup offset within 60 seconds.
Each camera's next due time is based on its own successful completion time, so
the phase separation persists across periodic cycles. This replaces the old
design's incorrect assumption that changing `_last_recovery_monotonic` alone
would shift identical per-entity interval timers.

### Periodic refresh

After a successful background refresh, that camera is next due in 28:30. The
manager schedules cameras independently, so one slow or failing camera does not
delay the others.

### One-minute reconcile

Once per minute the manager makes one local request for the complete go2rtc
stream list and compares it with registry-derived desired state.

- Missing eligible stream: schedule a fresh operator URL and PATCH.
- Newly eligible stream: schedule an initial refresh with bounded jitter.
- Newly ineligible stream with no consumers: DELETE.
- Newly ineligible stream with consumers: stop refresh, mark cleanup pending,
  and DELETE after a later reconcile observes zero consumers.
- Unknown/error response: preserve current streams and retry later.

The registry update listener marks desired state dirty and schedules a prompt
reconcile. Config option changes continue to use normal config-entry reload.

## go2rtc write semantics

Operator camera registration is PATCH-only.

- PATCH updates an existing source without destroying its active producer and
  consumers.
- PATCH also creates a missing in-memory stream.
- PUT is not used as a fallback: on an existing stream it destroys/recreates
  the producer, and persistent API writes have previously contributed to
  duplicated YAML and plaintext stale operator tokens (A-84).
- Because PATCH state is intentionally in-memory, the one-minute reconcile is
  responsible for recovery after a go2rtc restart.

If a deployment does not support PATCH, keep-warm fails visibly and safely for
that camera; it does not fall back to a disruptive PUT.

## Error handling and retry

Failures are isolated per camera. A failed refresh:

- leaves the previous go2rtc stream untouched;
- records a sanitized error category, not exception text containing a URL;
- retries after 15 seconds, then 30 seconds, then 60 seconds;
- caps subsequent retry spacing at five minutes;
- resets retry state after success and resumes the 28:30 interval.

Setup and coordinator refresh do not fail because go2rtc is temporarily down.
Manager task boundaries catch unexpected exceptions, log a sanitized camera ID
and exception type, and keep the scheduler alive.

## Security

- Never log the operator source URL, access/refresh tokens, go2rtc credentials,
  Authorization headers, SMS codes, or full config-entry data.
- Rebrand transport exceptions with `from None` before they cross the transport
  boundary, because aiohttp errors can embed the requested URL.
- Do not persist operator URLs through go2rtc PUT/config APIs.
- Diagnostic attributes contain stable local RTSP addresses without embedded
  credentials.
- Retain the warning that the go2rtc RTSP listener may be unauthenticated and
  must be protected by network/firewall policy.

## Testing strategy

### Automated tests

1. Config and defaults for both option keys.
2. Registry eligibility matrix across main option, `disabled_by`, `hidden_by`,
   and the hidden-camera option.
3. Startup jitter and independent 28:30 rescheduling from per-camera success.
4. PATCH of an absent stream without a preceding per-stream GET.
5. One-minute reconcile after simulated go2rtc state loss.
6. Cleanup immediately at zero consumers and deferred cleanup with consumers.
7. Per-camera concurrency dedup across background, HA open, and recovery.
8. Retry sequence and reset after success.
9. Unload cleanup of timers, listeners, and tasks.
10. No secret material in logs or diagnostic state on every failure path.
11. Diagnostic sensor reflects manager success/presence rather than desired
    coordinator entries alone.
12. Existing camera auto-recovery, call-camera concurrency, go2rtc audio, config
    flow, and visibility suites remain green.

Tests must exercise the complete internal chain through a fake go2rtc HTTP
contract. Merely asserting that a callback or recovery method was scheduled is
not sufficient.

### Production baseline and acceptance

Before changing the A-71 write boundary, capture a short baseline of active
consumer refresh/recovery behavior. After implementation, repeat it to show
behavioral equivalence for active HA streams.

The seven acceptance scenarios in this document are merge-blocking. In
particular, the idle-over-one-hour external RTSP test and go2rtc restart test
must run on the user's real go2rtc deployment; mocked tests cannot prove them.

## Rollout and compatibility

- Implement on a new branch from current `master`; do not cherry-pick the old
  keep-warm implementation.
- Manually reuse its runtime evidence, option keys, translations, diagnostic
  sensor concept, security requirements, and useful test cases.
- Default-off options make the change inert for existing users.
- No config-entry version migration is required because both values are
  optional options/data keys with false defaults.
- Retaining the old option names preserves settings from installations that
  tested the unmerged branch.

## Documentation updates

The implementation series will:

- add ADR-0014 for manager ownership and PATCH-only lifecycle;
- add audit A-96 for the external-idle RTSP gap and cross-reference A-82/A-84;
- update the project map, architecture overview, testing strategy, changelog,
  and decision index;
- keep ADR-0009 active and describe the manager as an extension of its proven
  A-71 behavior;
- close PR #61 only after the replacement passes production acceptance, with
  credit for the original idea and reused diagnostic/config concepts.

## Deferred work

- Per-camera include/exclude controls.
- Continuous producer preload.
- A complete extraction of the A-71 state machine (A-83).
- go2rtc-side dynamic `echo:`/`exec:` sources, which remain blocked in the
  tested add-on and would require operator authorization outside HA.
