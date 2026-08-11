# FCM circuit breaker and bounded recovery

- **Status:** approved design
- **Date:** 2026-08-10
- **Scope:** per-config-entry resilience for `DoorbellFcmListener`
- **Related:** issue #77, ADR-0011, audit A-80/A-86, upstream
  `firebase-messaging` issues #40/#42 and PR #37

## Problem

`firebase-messaging` can terminate `FcmPushClient` when a single incoming
message contains Base64URL encryption fields it cannot decode. The message is
not acknowledged because acknowledgement happens after decryption. The
integration watchdog then recreates the client every two minutes, and the same
condition can repeat for every configured account. This can fill the Home
Assistant log while realtime doorbell notifications remain unavailable.

The upstream parsing bug is outside the integration, but bounding retries,
isolating accounts, and explaining the degraded state to the user are the
integration's responsibility.

Issue #77 supplies direct timestamped crash-boundary evidence: the integration
reports an inactive receiver, the dependency fails in `urlsafe_b64decode` with
`Incorrect padding` two seconds later and shuts that client down. Source
inspection establishes the local causal chain: dependency shutdown → watchdog
observes inactive receiver → unbounded client recreation → repeated dependency
traceback. This design contains that amplification; it does not claim to fix
the upstream parser.

## Goals

1. Stop unbounded FCM restart and traceback loops per config entry.
2. Preserve automatic recovery after temporary network or Google service
   failures.
3. Notify the user once, in Home Assistant Repairs, when realtime doorbell
   notifications are temporarily unavailable.
4. Keep cameras, locks, sensors, history, and coordinator polling operational.
5. Avoid new long-running tasks, timers, persistent retry storage, or config
   entry migrations.

## Non-goals

- Patch, fork, or vendor `firebase-messaging` in this change.
- Guarantee that an unsupported FCM payload can be decrypted.
- Add an automated Repair flow that rotates FCM credentials.
- Change config entry version, entity IDs, or public services. The dependency
  floor is raised to the verified `firebase-messaging>=0.4.5` API contract.
  Later releases may be selected on a fresh install or dependency re-resolution;
  the range does not proactively upgrade an already-satisfied environment.

## Decision

Extend the existing two-minute per-entry watchdog with an in-memory circuit
breaker and exponential recovery schedule. The watchdog remains the only HA
timer owned by `DoorbellFcmListener`.

Each listener instance owns its own state, so one failing account cannot stop or
delay FCM for another account.

### State model

```text
HEALTHY -> SUSPECT -> VERIFYING -> HEALTHY
                        |
                        v
                      OPEN -- deadline/reconnect --> VERIFYING
                        ^                            |
                        +--------- inactive --------+
```

- **HEALTHY:** `client.is_started()` is true. Failure counters and backoff are
  reset. An existing Repair issue is removed after this healthy watchdog tick.
- **SUSPECT:** the first inactive watchdog observation records the condition but
  does not recreate the client. This gives the dependency time to recover from
  a transient connection reset.
- **VERIFYING:** after either the immediate reconnect or a scheduled probe, the
  integration waits for the next watchdog tick to confirm the replacement.
- **OPEN:** if the replacement is still inactive on the following tick, the
  circuit opens. The integration stops frequent reconnects, creates one Repair
  issue, and records the next probe time. When the backoff expires, one
  reconnect moves the listener back to VERIFYING; success closes the circuit
  and failure reopens it with the next delay.

At most the original dependency failure and one immediate recovery failure are
expected before the circuit opens. Calls to the upstream logger are not
intercepted or filtered; their frequency is bounded by the circuit.

### Recovery schedule

The backoff sequence is:

1. 15 minutes
2. 1 hour
3. 6 hours
4. 24 hours

After reaching 24 hours, subsequent failures remain at 24-hour intervals. The
existing two-minute watchdog checks whether the deadline has passed, so probes
may occur up to two minutes after the nominal deadline.

A successful healthy watchdog tick resets the schedule to its initial state.
A config entry reload also resets transient in-memory state and starts an
immediate normal connection attempt.

No retry state is written to `entry.data` or `Store`. After a Home Assistant
restart, each account gets a fresh connection attempt. This deliberately trades
one bounded post-restart attempt for lower complexity, no migrations, and no
periodic disk writes.

## Home Assistant Repairs issue

When the circuit first enters OPEN, create one persistent Repairs issue:

- domain: `elektronny_gorod`
- issue ID: `fcm_receiver_unavailable_<entry_id>`
- severity: error (realtime doorbell notifications are already unavailable)
- fixable: false for this change
- translation placeholder: the config entry title only; its default value is
  the resident name plus operator account ID

Privacy trade-off (accepted 2026-08-11): a persistent issue duplicates that
title in `repairs.issue_registry`. This adds no authorization audience because
authenticated HA users can already read the same title through
`config_entries/get`; the duplication is accepted so a multi-account user can
identify the affected entry. The acceptance is conditional on diagnostics
redacting every `title` key before a user shares the export outside HA. The
generated title is sourced only from resident name and operator account ID;
custom titles are copied verbatim, so users must not place credentials in them.
FCM tokens, credentials and complete `entry.data` remain forbidden in the issue.

The user-facing message states that:

- realtime doorbell notifications are temporarily unavailable for the named
  account;
- cameras, locks, balance, history, and other integration functions continue to
  work;
- the integration will retry automatically;
- reload can request an immediate attempt;
- reconnecting the same account can issue a new FCM registration if the problem
  repeats.

Create or update the issue only on a state transition, never on every watchdog
tick. Do not include FCM tokens, credentials, operator tokens, headers, payloads,
phone numbers, or complete `entry.data` in the issue or logs.

The issue is deleted after a confirmed HEALTHY watchdog tick. It is also deleted
when the config entry is removed, preventing an orphaned persistent issue. It is
not deleted merely because a probe was scheduled or `client.start()` returned;
those events do not prove that the MTalk listener remained healthy.

## Lifecycle and overhead

The healthy path retains the current resource model per account:

- one HA interval timer;
- two tasks owned by `FcmPushClient` (listener and monitor);
- one `DoorbellFcmListener` instance.

The change adds only scalar in-memory state: phase, consecutive inactive
observations, backoff index, and next probe time. It adds no timer and no
background task. In OPEN, the failed FCM client is stopped, so the number of
active tasks decreases.

The integration performs an idempotent delete on a healthy tick so the HA issue
registry remains the only source of truth. Deleting an absent issue produces no
registry event or disk write.

## Error handling

- Exceptions from disconnect/connect remain contained by the existing graceful
  degradation boundary and log only their class, never dependency-provided text.
- If the dependency raises while stopping a client, the listener retains that
  client reference, opens the circuit and does not create a replacement. Later
  scheduled probes may retry the same stop, so a failed stop cannot multiply
  receiver tasks or restore the log loop.
- A failed probe must leave the listener in OPEN and advance backoff; it must not
  escape the watchdog callback.
- Startup, watchdog transitions and unload are serialized by a per-entry lock;
  overlapping watchdog ticks are skipped and cannot advance backoff twice.
- If unload begins during FCM check-in or the awaited operator bind, startup
  observes the stop request before client start. The unstarted dependency client
  remains local, is discarded without calling its incompatible pre-start
  `stop()`, and no watchdog is scheduled.
- `async_stop()` marks the listener as stopping, cancels the existing interval,
  waits for any active transition and performs a final disconnect. If dependency
  stop fails, config-entry unload fails and HA cannot create an overlapping
  listener on reload; a later unload may retry the same retained client.
- The unstarted listener claims per-entry ownership only after the last fallible
  setup await. If a prior owner cannot stop, setup still completes with only
  realtime FCM disabled for that entry, a Repairs issue is shown, and the old
  owner is not replaced. This path must not raise `ConfigEntryNotReady`, because
  HA setup retries would recreate the log loop outside the circuit breaker.
- Setup-unwind releases ownership only after a confirmed stop. Normal unload
  likewise fails rather than replacing a dependency client that may still run.
- Removing one config entry deletes only that entry's Repairs issue.
- If ordinary unload cannot confirm dependency shutdown, HA blocks replacement
  and reports that removal requires restart. `async_remove_entry` performs one
  final stop attempt but retains ownership if that also fails, rather than
  orphaning a live receiver. The stopping listener ignores late callbacks and
  cannot schedule recovery or a replacement before restart.
- The existing FCM token is not logged or exposed by the circuit breaker.

The circuit breaker intentionally treats repeated inactivity generically. It
does not depend on private `firebase-messaging` exception types or parse its log
messages. This keeps it useful for future fatal failures as well as the current
Base64URL bug. Automatic probes prevent a long network outage from becoming a
permanent disablement.

## Planned code boundaries

- `custom_components/elektronny_gorod/fcm.py`
  - state and backoff constants;
  - watchdog state transitions;
  - Repairs issue creation/deletion helpers;
  - cleanup of the active client.
- `custom_components/elektronny_gorod/__init__.py`
  - keep the per-entry FCM listener registry key local to this lifecycle module;
  - own the listener through config-entry unload/reload;
  - fail unload if a started dependency client cannot stop;
  - delete the per-entry persistent issue on config entry removal.
- `custom_components/elektronny_gorod/strings.json`
- `custom_components/elektronny_gorod/translations/ru.json`
- `custom_components/elektronny_gorod/translations/en.json`
  - Repairs title and description.
- `tests/test_fcm.py`
  - state-machine, backoff, Repairs, lifecycle, and multi-entry tests.
- AIDD documentation required by the project maintenance rules.

`manifest.json`, dependency versions, config flow, entity platforms, and public
documentation are outside this change.

## Test design

Unit tests use the existing mocked `FcmPushClient` and pass explicit timestamps
to `_async_watchdog`; no real Google or operator connection is used.

Required cases:

1. A healthy client causes no reconnect and clears transient failure state.
2. The first inactive observation enters SUSPECT without reconnecting.
3. A second consecutive observation performs exactly one reconnect.
4. A healthy replacement closes the circuit and resets backoff.
5. An inactive replacement opens the circuit and creates exactly one Repair
   issue.
6. Watchdog ticks before the deadline perform no network work, logging, registry
   updates, or new task creation.
7. Probe failures advance through 15 minutes, 1 hour, 6 hours, and 24 hours;
   further failures stay at 24 hours.
8. A successful probe is confirmed on the following healthy tick before the
   issue is deleted.
9. Two listener instances maintain independent counters, deadlines, clients,
   and issue IDs.
10. Startup/check-in failures remain contained and enter bounded recovery.
11. `async_stop()` is idempotent in HEALTHY, OPEN, and VERIFYING.
12. A failed dependency stop blocks config-entry unload/reload and retains the
    same client for a later stop attempt.
13. A surviving prior owner is not replaced; setup completes with only FCM
    degraded, shows Repairs, and does not enter HA's setup-retry loop.
14. FCM ownership/start occurs after the last fallible setup await; setup errors
    before that point cannot strand a newly registered receiver.
15. Removal after a failed unload retries stop; another failure retains the
    owner and HA reports that restart is required.
16. A late dependency notification after terminal stop is ignored.
17. Logs and issue placeholders contain no FCM credentials or tokens; the only
    placeholder is the config-entry title exposed to the same authenticated HA
    audience as `config_entries/get`, and diagnostics redacts `title` before an
    export can be shared outside HA (accepted privacy trade-off S-23).
18. Existing notification parsing and healthy-start tests remain green.

## Documentation updates with implementation

- Record the incident and mitigation in `docs/audit/project-audit.md`, updating
  A-80/A-86 rather than creating duplicate sources of truth.
- Update `docs/architecture/overview.md` with bounded FCM recovery.
- Update `docs/testing/strategy.md` with the new regression coverage and test
  result.
- Add the user-visible fix to `CHANGELOG.md`.

## Alternatives considered

### Wait only for upstream

Rejected as the sole response. The parsing bug belongs upstream, but an
unbounded restart loop and poor degraded-state UX remain integration concerns.

### Local compatibility adapter

Deferred. Normalizing the encrypted headers and containing one bad payload could
restore realtime notifications, but it couples the integration to private
methods of `firebase-messaging`. It can be reconsidered independently after
field feedback or if the upstream fix remains unreleased.

### Fork or vendor `firebase-messaging`

Deferred as a last resort. The package is small and MIT-licensed, but owning the
FCM protocol, crypto path, protobuf definitions, and private Google APIs creates
substantial long-term maintenance and security responsibility.

### Automatic token rotation

Deferred until issue #77 confirms whether reconnecting the account clears the
condition. Rotation can discard a token-bound poison message, but it cannot fix
a message format that the operator sends repeatedly and can leave stale remote
registrations if cleanup fails.

## Acceptance criteria

1. No config entry can reconnect FCM every two minutes indefinitely.
2. A repeated failure produces at most one immediate reconnect before backoff.
3. Automatic recovery remains possible without user action.
4. One account's failure cannot affect another account.
5. The user receives one actionable, translated Repairs issue naming the
   affected config entry.
6. Non-FCM integration functionality remains loaded and operational.
7. The complete test suite passes with no secret-bearing logs or diagnostics.
