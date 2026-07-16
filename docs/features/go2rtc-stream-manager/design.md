# Design: go2rtc stream manager for external RTSP

- **Status:** implemented, merged in PR #71 and accepted on the owner's live
  deployment for release 4.0.0
- **Date:** 2026-07-16
- **Delivery:** merged PR #71 (`bf5ba9b`)
- **Origin:** replacement for the superseded/closed PR #61 and
  `feat/go2rtc-keep-warm`
- **Related:** ADR-0009, ADR-0014, audit A-82/A-83/A-84/A-96

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

The replacement branch initially repeated one important false assumption: it
kept the registered source URL fresh with PATCH but intentionally left the
go2rtc producer lazy. Live validation on 2026-07-16 disproved that model. Five
problematic non-doorbell streams were present with one lazy source and zero
consumers, yet RTSP playback returned 404. Arming go2rtc preload against the
already-idle URL failed with TLS EOF. Doorbell streams with an existing
background consumer remained alive. Therefore registration freshness alone is
not keep-warm: the operator URL must be consumed immediately and its producer
must remain active.

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
5. A hidden camera is never background-minted, PATCHed, or preloaded unless
   both publication options are on, including the platform-forwarding window
   before visibility synchronization. An explicit HA open during or after that
   window lazily registers it without a manager preload; when main publication
   remains enabled, its normal reconcile cleanup follows the viewer.
6. Concurrent background, HA-open, and recovery requests for one camera result
   in one operator request, one go2rtc PATCH, and at most one preload PUT when
   preload is missing.
7. Config-entry unload leaves no manager timers or background tasks.
8. An eligible idle camera has an active manager-owned go2rtc preload consumer;
   disabling keep-warm or unloading the entry removes that consumer.
9. A publication-policy save does not reload the config entry or drop existing
   eligible producers. Disabling publication removes idle `eg_*` registrations
   in place, while a stream with an active consumer is preserved.

## Non-goals

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

Home Assistant registry state is the source of truth after visibility
synchronization. During platform forwarding, before the manager starts, an API
`hidden=true` value is a conservative hint for background publication only.
Explicit enabled HA-open remains on-demand so it cannot receive a stable RTSP
URL for a stream that was never PATCHed. A persistent
`user_shown`/integration-owned marker preserves an explicit HA user override.

```text
enabled(camera) =
  correct config entry
  AND registry_entry.disabled_by is None

background_publishable(camera) =
  enabled(camera)
  AND (
    registry_entry.hidden_by is None
    OR (go2rtc_keep_warm AND go2rtc_keep_warm_hidden)
  )

eligible(camera) =
  go2rtc_keep_warm AND background_publishable(camera)
```

`disabled_by` always wins. A disabled camera is never background-published,
even when the hidden-camera option is enabled.

Both options remain opt-in and default off. Enabling ordinary go2rtc support
alone does not add background operator traffic. The manager still serves the
existing on-demand and recovery paths when keep-warm is off. At startup it runs
one consumer-aware cleanup pass: stale idle `eg_*` registrations are removed,
but no timers are installed and no operator URL is minted.

## Architecture and ownership

### Go2RtcClient

`go2rtc.py` provides a single transport boundary for:

- PATCHing a named source;
- listing registered streams and their producer/consumer metadata;
- listing manager-owned go2rtc preloads;
- enabling and disabling preload for a named stream;
- deleting a named stream;
- building authenticated API requests;
- building credential-free diagnostic RTSP addresses.

Sensitive operator URLs and authentication headers never appear in exception
messages returned to callers.

### CameraStreamManager

A new `CameraStreamManager` instance is created per config entry. It owns the
policy and mutable state for `eg_<camera_id>`:

- registry publication policy and background eligibility;
- startup and periodic scheduling;
- one in-flight refresh future per camera;
- last successful refresh time and next due time;
- failure count and retry deadline;
- last observed go2rtc presence/consumer state;
- last observed preload and active-producer state;
- pending cleanup for active consumers.

The manager is the only component allowed to write operator camera sources to
go2rtc. Camera entities, proactive refresh, and recovery all call the same
manager method.

### Camera entity

`ElektronnyGorodCamera` retains its HA-specific responsibilities and the proven
A-71 recovery triggers. It no longer performs go2rtc writes directly.

- `stream_source()` asks the manager for the stable RTSP address. An enabled
  hidden camera may be minted/registered for explicit HA viewing even while
  manager startup is finishing, but receives no preload unless background
  policy also admits it.
- Event-driven and producer-health recovery ask the manager for a refresh.
- The active-consumer proactive timer remains an A-71 trigger only for
  on-demand/non-eligible streams. Background-eligible cameras skip it because
  the manager preload is not an external viewer and owns the staggered 28:30
  cadence.
- Proxied recovery PATCHes the upstream and lets HA Stream retry its unchanged
  stable RTSP URL. It does not call `Stream.update_source()` because HA's
  one-shot fast restart can race idle stop and orphan the worker. Direct-source
  fallback keeps its existing `update_source()` path.

This deliberately avoids a wholesale A-83 refactor. The feature extracts the
write boundary required for single ownership without moving the entire
deterministically tuned recovery state machine.

### Diagnostic sensor

`ElektronnyGorodRtspUrlsSensor` reads manager state rather than inferring
success from coordinator data.

- `native_value`: number of eligible streams that were present, preloaded, and
  observed with an active producer at the latest reconcile;
- `urls`: camera display name to credential-free stable RTSP address;
- per-camera last-success timestamps and sanitized status;
- no operator URL, token, password, or Authorization header.

The sensor reports the latest registration, preload, and producer observation,
not proof that a remote client can decode video. End-to-end playback is covered
by production acceptance.

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
and pending manager tasks are cancelled, then manager-owned preloads are
removed best-effort. A transport/auth reload creates one fresh manager; no task
or state is shared across config-entry lifetimes. Startup reconciliation adopts
eligible preloads left by an unclean HA shutdown. When publication is now off,
the fresh manager also removes idle managed streams after an exact consumer
check; active external viewers are preserved.

Publication-policy changes use the existing started manager when go2rtc API
URL, RTSP host, and credentials are unchanged. The manager updates both flags,
reconciles one current snapshot, preserves eligible preloads, cleans newly
ineligible streams, and schedules only newly eligible/missing cameras. Manual
publication-on uses a short asynchronous ramp (first camera immediately, then
0.5 seconds per camera); it does not reuse cold-start jitter. No
coordinator/entity/platform reload or synchronous operator mint occurs.
Transport/auth changes and disabling go2rtc retain the normal config-entry
reload path.

## Data flows

All write reasons mint and register through one operation. An eligible camera
also acquires a persistent go2rtc preload consumer when it does not already
have one:

```text
background due | HA open | A-71 recovery
  -> CameraStreamManager.async_refresh(camera_id, reason)
  -> join existing per-camera in-flight future, if any
  -> background reason: require background_publishable(camera)
  -> consumer reason after startup: require enabled(camera)
  -> if current reason is not allowed:
       return stable local RTSP address without mint/PATCH/preload
  -> coordinator.get_camera_stream(camera_id)
  -> Go2RtcClient.patch_stream(
       name="eg_<camera_id>",
       src="ffmpeg:<operator-url>#video=copy#audio=aac#audio=opus"
     )
  -> if eligible and preload is absent:
       Go2RtcClient.enable_preload(name="eg_<camera_id>")
  -> update per-camera success state
  -> return stable local RTSP address
```

For allowed cameras the order is mandatory: mint, then PATCH, then optional
preload.
Enabling preload before PATCH can consume an already-expired one-time URL,
which live validation showed as `TLS EOF`. Once preload is active, periodic
refresh performs PATCH only. go2rtc keeps the current producer connected;
PATCH changes the URL used by its next reconnect without interrupting the
current producer or external consumers.

The refresh operation does not require the stream to exist before PATCHing.
PATCH creates a missing in-memory stream or updates the source of an existing
one. A missing-stream check is a trigger, not a precondition.

Concurrent callers share the first caller's in-flight operation and result.
The operation revalidates background policy before and after its network work;
it does not add a separate joined-reason upgrade path for an unobserved race.
A later sequential HA open continues to mint a fresh operator session.

## Scheduling and reconciliation

The verified refresh interval remains 28 minutes 30 seconds. Background
eligible cameras use only the manager's independently phased timers;
entity-level proactive refresh remains for an actively viewed on-demand stream.

### Startup

Eligible cameras receive a deterministic startup offset within 60 seconds.
Each camera's next due time is based on its own successful completion time, so
the phase separation persists across periodic cycles. This replaces the old
design's incorrect assumption that changing `_last_recovery_monotonic` alone
would shift identical per-entity interval timers.

This full jitter applies only to cold config-entry startup. When the user turns
publication on in an already loaded entry, the first missing eligible camera is
scheduled at once and each following camera 0.5 seconds later. The options flow
still returns without awaiting operator mint/PATCH/preload.

### Periodic refresh

After a successful background refresh, that camera is next due in 28:30. The
manager schedules cameras independently, so one slow or failing camera does not
delay the others. The initial successful refresh also enables preload. Later
scheduled refreshes do not re-arm an active preload because replacing its
consumer would unnecessarily reconnect the producer.

### Reconcile

At startup the manager requests the complete go2rtc stream list and preload
list, then compares both with registry-derived desired state. With publication
enabled it repeats this once per minute. With publication disabled it performs
the startup cleanup pass and installs no global reconcile timer.

- Missing eligible stream or preload: schedule the full fresh
  mint/PATCH/preload chain.
- Eligible stream with preload but no active producer: refresh its URL and
  re-arm preload so recovery does not wait for an external viewer.
- Newly eligible stream after a manual policy-on: schedule an initial refresh
  in the short 0.5-second asynchronous ramp.
- Newly ineligible stream: DELETE its manager preload first. If no external
  consumers remain, DELETE the stream; otherwise stop refresh, mark cleanup
  pending, and retry on the next enabled reconcile pass.
- Unknown/error response: preserve current streams and retry later.

Background policy is revalidated after mint/PATCH. Stop first closes
scheduling, then waits for any running reconcile before final owned/pending
preload cleanup. No extra on-demand cleanup poll or theoretical interleaving
lock is installed when publication is off.

The registry update listener marks desired state dirty and schedules a prompt
reconcile. Policy-only option changes reconcile in place; incompatible
transport/auth changes use normal config-entry reload.

## go2rtc write semantics

Operator camera source registration is PATCH-only. Preload lifecycle uses the
dedicated go2rtc preload API.

- PATCH updates an existing source without destroying its active producer and
  consumers.
- PATCH also creates a missing in-memory stream.
- PUT is not used as a fallback: on an existing stream it destroys/recreates
  the producer, and persistent API writes have previously contributed to
  duplicated YAML and plaintext stale operator tokens (A-84).
- Because PATCH state is intentionally in-memory, the one-minute reconcile is
  responsible for recovery after a go2rtc restart.
- `PUT /api/preload?src=<name>` is allowed only after a fresh successful PATCH
  and only when preload is absent or the producer is inactive.
- `DELETE /api/preload?src=<name>` removes manager background traffic before
  stream cleanup.
- go2rtc persists only the stable preload name/query. The operator source URL
  remains in-memory and is never written through the config API.

If a deployment does not support PATCH, keep-warm fails visibly and safely for
that camera; it does not fall back to a disruptive PUT.

## Error handling and retry

Failures are isolated per camera. A failed refresh:

- leaves the previous go2rtc stream untouched when mint or PATCH fails;
- records a sanitized error category, not exception text containing a URL;
- retries after 15 seconds, then 30 seconds, then 60 seconds;
- caps subsequent retry spacing at five minutes;
- resets retry state after success and resumes the 28:30 interval.

A preload failure leaves the freshly PATCHed stream registered but does not
mark the camera ready. It enters the same per-camera retry schedule so the next
attempt mints another one-time URL before trying preload again. Cleanup treats
missing preload as idempotent success.

Setup and coordinator refresh do not fail because go2rtc is temporarily down.
Manager task boundaries catch unexpected exceptions, log a sanitized camera ID
and exception type, and keep the scheduler alive.

## Security

- Never log the operator source URL, access/refresh tokens, go2rtc credentials,
  Authorization headers, SMS codes, or full config-entry data.
- Rebrand transport exceptions with `from None` before they cross the transport
  boundary, because aiohttp errors can embed the requested URL.
- Do not persist operator URLs through go2rtc PUT/config APIs. Persisting a
  stable `eg_<camera_id>` preload name is allowed and contains no credential.
- Diagnostic attributes contain stable local RTSP addresses without embedded
  credentials.
- Retain the warning that the go2rtc RTSP listener may be unauthenticated and
  must be protected by network/firewall policy.

## Testing strategy

### Automated tests

1. Config and defaults for both option keys.
2. Registry publishability/eligibility matrix across main option,
   `disabled_by`, `hidden_by`, and the hidden-camera option.
3. Startup jitter and independent 28:30 rescheduling from per-camera success.
4. Initial mint/PATCH/preload ordering and no preload before a fresh URL.
5. Scheduled refresh PATCHes without replacing an active preload consumer.
6. PATCH of an absent stream without a preceding per-stream GET.
7. One-minute reconcile restores both stream and preload after simulated
   go2rtc state loss.
8. Cleanup removes preload first, then deletes immediately at zero external
   consumers or defers with external consumers.
9. Per-camera concurrency dedup across background, HA open, and recovery.
10. Retry sequence and reset after success, including preload failure.
11. Unload removes manager preloads, timers, listeners, and tasks.
12. No secret material in logs or diagnostic state on every failure path.
13. Diagnostic sensor reflects active producer/preload state rather than desired
    coordinator entries alone.
14. Existing camera auto-recovery, call-camera concurrency, go2rtc audio, config
    flow, and visibility suites remain green.
15. Before visibility sync, background work for API-hidden cameras performs
    zero operator mint, PATCH, and preload calls; a persisted user-shown
    override remains background-publishable. Explicit HA-open/recovery still
    performs lazy mint/PATCH without preload.
16. After visibility sync, registry-hidden cameras perform zero background
    writes unless both options admit them. Explicit HA-open/recovery remains
    available for an enabled hidden camera without manager preload; its idle
    registration is removed after the viewer leaves.
17. Policy-only options changes preserve existing eligible preloads and skip
    config-entry reload; main-off cleanup and newly eligible startup happen in
    the current manager without synchronous mint. Policy-on schedules the first
    missing camera immediately and subsequent cameras at 0.5-second intervals.
18. A background mint already in flight when publication is disabled cannot
    PATCH or preload after the policy transition; an already-started PATCH is
    cleaned after completion and cannot leave a late zero-consumer stream.

Tests must exercise the complete internal chain through a fake go2rtc HTTP
contract. Merely asserting that a callback or recovery method was scheduled is
not sufficient.

### Production baseline and acceptance

Before changing the A-71 write boundary, capture a short baseline of active
consumer refresh/recovery behavior. After implementation, repeat it to show
behavioral equivalence for active HA streams.

The nine acceptance scenarios in this document gated the 4.0.0 release. In
particular, the idle-over-one-hour external RTSP test and go2rtc restart test
had to run on the user's real go2rtc deployment; mocked tests could not prove
them.

Targeted startup-grid acceptance passed on 2026-07-16 after deploying
`3a3ad02`: explicit lift-camera opens while integration setup was finishing
created their go2rtc streams, playback worked, and closing the HA UI no longer
left an extra non-preload consumer. This closed the observed 404/orphan
regression. The subsequent owner acceptance covered long-running stream
behavior and a manual go2rtc restart. A read-only post-restart snapshot showed
three managed streams, each with one active producer and one preload consumer;
aggregate `bytes_recv` increased by about 4.8 MB over five seconds. Combined
with the earlier publication-toggle, hidden/on-demand, startup-grid, timing and
orphan-consumer observations, this closed the 4.0.0 production gate on
2026-07-16.

## Rollout and compatibility

- Use the implementation merged by PR #71; do not revive or cherry-pick the old
  keep-warm implementation.
- Manually reuse its runtime evidence, option keys, translations, diagnostic
  sensor concept, security requirements, and useful test cases.
- Default-off options make the change inert for existing users.
- No config-entry version migration is required because both values are
  optional options/data keys with false defaults.
- Retaining the old option names preserves settings from installations that
  tested the unmerged branch.

## Documentation status

- ADR-0014 records the final unified lifecycle: PATCH plus dedicated preload,
  consumer-aware cleanup, the separation of enabled on-demand playback from
  background eligibility, and in-place publication-policy updates.
- The pre-visibility gate prevents transient background hidden-camera writes;
  the on-demand path remains valid before and after manager startup so explicit
  HA playback never receives an unregistered RTSP name.
- Audit A-96 records both automated implementation and the completed owner live
  acceptance, and cross-references A-82/A-84.
- Project map, architecture, testing, roadmap and changelog are synchronized
  with the implemented preload revision; ADR-0009 remains active for proven
  A-71 behavior.
- PR #61 is closed as superseded with a thank-you and link to merged PR #71;
  its opt-in/diagnostic concepts are credited and retained.

Automated evidence on 2026-07-16: 131 focused preload/manager tests, 151
related camera/go2rtc/config/visibility regressions and the complete 549-test
backend suite passed. Targeted startup-grid and final post-restart live
acceptance passed; release 4.0.0 is no longer gated by A-96.

## Deferred work

- Per-camera include/exclude controls.
- A complete extraction of the A-71 state machine (A-83).
- go2rtc-side dynamic `echo:`/`exec:` sources, which remain blocked in the
  tested add-on and would require operator authorization outside HA.
