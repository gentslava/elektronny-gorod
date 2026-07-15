# Plan: mobile app parity slices

- **Date:** 2026-07-15
- **Owner:** @gentslava
- **Linked PRD:** [`prd.md`](prd.md)
- **Linked research:** [`research.md`](research.md)

## High-level approach

Add small typed API methods and feature-specific coordinators instead of
expanding the five-minute main coordinator with high-volume history calls.
FCM remains authoritative for realtime doorbell calls. Historical events use a
baseline/watermark, and archive media is resolved only on demand. Guest/key/media
credentials never become entity data. Static-only features are guarded by HAR
fixtures and capability detection.

## Target HA model

| Capability | HA primitive | Persistence policy |
|---|---|---|
| New camera motion event | per-camera `EventEntity` | HA records only newly observed whitelisted events |
| Durable archive | integration `MediaSource` | opaque IDs persisted; signed source URL memory-only |
| Guest link | integration action with response | never stored by integration |
| Access key | disabled-by-default `SensorEntity` using service ID | generic localized name; code/backend name discarded; verified bind status only |
| Key notifications | `SwitchEntity` | authoritative refresh after toggle |
| Sensitivity/volumes | `NumberEntity` | backend values/ranges only |
| Event-record mode | `SwitchEntity` | personal-camera state + confirmed PUT |
| Mirror mode | `SelectEntity` | only after enum capture |
| PTZ | camera action/capability | only after direction/action capture |

## Vertical slices

### Slice 0: sanitized contracts and transport

- **Files:** test fixtures, `http.py`, `api.py`.
- **Change:** add PUT support with JSON content type; add typed methods for the
  selected slice; parse business errors without logging bodies.
- **Acceptance:** request tests assert exact method/path/body and prove redaction.
- **Risk:** medium; shared transport touches all APIs, so PUT must be additive.

### Slice 1: durable event polling

- **Status:** implemented in `feat/durable-event-history`.
- **Files:** `api.py`, a dedicated history manager, `event.py`, tests.
- **Change:** page-0 baseline, bounded ID watermark/dedup, whitelisted event
  mapping. Do not call history from the main coordinator every five minutes if a
  separate interval/task gives clearer lifecycle and backpressure.
- **Acceptance:** old fixture emits zero events; one new ID emits once; restart
  and overlapping pages do not duplicate; unload cancels the interval; a slow
  poll does not queue another cycle. Covered by `test_api_history.py`,
  `test_history.py`, `test_event.py` and translation parity tests.
- **Risk:** medium; wrong baseline can trigger user automations.

### Slice 1b: old-call history browser

- **Status:** implemented in `feat/durable-event-history`.
- **Files:** `history_ws.py`, `__init__.py`, `frontend/src/history/`,
  `frontend/src/eg-event-history-card.ts`, focused backend/frontend tests.
- **Change:** read previous accepted/missed pages only when an authorized
  Lovelace client requests them. Resolve the selected history EventEntity via
  registry/config entry, enforce `POLICY_READ`, bind to its exact
  place/access-control and return only ID/type/timestamp.
- **Acceptance:** page overlap is deduplicated in the view model; page bounds
  and entity mismatch are rejected; previous rows never touch dispatcher,
  EventEntity state or the watermark Store; mobile/desktop loading, empty and
  error states exist in RU/EN.
- **Risk:** medium; a global WS command must not bypass per-entity HA access.

### Slice 2: archive media source

- **Files:** new `media_source.py`, `api.py`, optional authenticated proxy view,
  manifest only if HA requires an explicit dependency, tests.
- **Change:** browse place/camera/date/event, resolve playback/download on
  demand, map retention/availability errors.
- **Acceptance:** browsing uses opaque identifiers; signed URLs are absent from
  states, storage and caplog; Range/cancel behaviour is tested if proxying.
- **Risk:** high; streaming and expiring signed URLs.

### Slice 3: guest invitation action

- **Files:** `api.py`, `__init__.py` or action module, `services.yaml`, strings and
  translations, tests and user documentation.
- **Change:** `create_guest_invite(place_id)` calls NTK `app=2` and returns only
  `{link,message}`. Enforce admin/user policy before the operator request.
- **Acceptance:** response-only action, no entity, no log/diagnostic persistence;
  unauthorized/invalid place/operator errors are sanitized.
- **Risk:** high security, low code volume.

### Slice 4: access-key read model

- **Files:** `api.py`, coordinator/manager, chosen entity platform, translations,
  diagnostics redaction and tests.
- **Change:** capability/tariff-safe list fetch; discard `accessKeyCode`; stable
  IDs from key service ID; disabled by default.
- **Acceptance:** a fixture containing a sentinel key code never exposes that
  sentinel outside the parser test; endpoint failure affects only keys.
- **Risk:** medium-high; enabled-account semantics not yet captured.

### Slice 5: key notification toggle

- **Prerequisite:** HAR proves body-less PUT semantics and response shape.
- **Change:** non-optimistic notification switch, then coordinator refresh.
- **Acceptance:** mutation failure leaves prior state and raises a safe error.
- **Risk:** high until contract capture.

### Slice 6: private-camera settings

- **Files:** `api.py`, feature manager, `number.py`, optional `select.py`/
  `switch.py`, translations and tests.
- **Change:** feature info → settings read → capability-gated entities; exact PUT
  paths for values; no provisioning/firmware operations.
- **Acceptance:** ranges come from fixtures; unsupported feature creates no
  entity; writes are confirmed by refresh; partial endpoint failure is isolated.
- **Risk:** high until hardware capture.

### Slice 7: release/documentation hardening

- **Files:** README/info/release notes only after features ship; API/audit/
  roadmap/testing docs in the same PR.
- **Acceptance:** link checker, secret scan, full test suite, release notes state
  which features require operator tariff/hardware.

## Dependencies

```text
HAR fixtures ─► Slice 0 ─┬─► Slice 1 ─► Slice 1b ─► Slice 2
                         ├─► Slice 3
                         ├─► Slice 4 ─► Slice 5
                         └─► Slice 6
Slices 1..6 ───────────────────────────► Slice 7
```

History/archive and guest can ship independently. Keys and private-camera
settings must not delay them.

## Error model

- Invalid user input or unknown place: `ServiceValidationError`.
- Operator/network/auth/capability failure: `HomeAssistantError` or coordinator
  update error appropriate to the surface.
- Never interpolate operator response body, link, key code or signed URL into
  an exception.
- `11005` becomes a typed retention error with a sanitized boundary timestamp.

## Security model

| Data | Allowed | Forbidden |
|---|---|---|
| Guest link/message | immediate action response | entity, recorder, log, diagnostics, store |
| Resident names/account IDs | in-memory API response only if needed | HA state/attributes by default |
| Access key code | transient request/parser only | unique ID, name, state, attrs, log, diagnostics |
| Archive signed URL | on-demand resolver/proxy memory | state, attrs, store, diagnostics, logs |
| Event message | only after PII review | blind copying from backend into attributes |

Prefer an authenticated HA proxy for media. If a direct upstream URL must be
returned by Media Source, keep it short-lived and never persist/log it. Any HA
proxy URL should use authenticated access or `async_sign_path` with a short TTL.

## Tests

- Exact URL/method/query/body for every API method.
- Baseline, dedup, pagination overlap, restart and unload for history.
- Retention 11005, HTTP-200 business error, unavailable clip and ID mismatch.
- Action response support, admin/invalid place/error paths and caplog sentinel.
- Key-code sentinel propagation test across state/diagnostics.
- Feature-info matrix, dynamic ranges, non-optimistic write and partial failure.
- Translation and service schema tests; full existing suite before merge.

## Migration and rollback

No config-entry version bump for additive discovered entities/actions. Slice 1
uses independent HA `Store` schema v1 under
`elektronny_gorod.history.{entry_id}` and retains at most 200 opaque IDs per
stream—no timestamps, messages or signed URLs. Its interval unregisters through
entry unload. Each later feature remains a separate slice/PR.

## Open questions

See [`prd.md`](prd.md#open-questions). A static-only slice is blocked until its
matching task in [`tasklist.md`](tasklist.md) supplies a sanitized fixture.

## Quality gate

`PLAN_APPROVED` — granted for Slice 1; later slices require their own gate.
