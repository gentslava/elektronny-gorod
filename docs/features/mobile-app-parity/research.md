# Research: mobile apps 9.9.0 parity

- **Date:** 2026-07-15
- **Owner:** @gentslava / Research Agent
- **Linked PRD:** [`prd.md`](prd.md)

## Research question

What useful capabilities exist in the updated apps but not in our integration,
and what evidence/API information is sufficient to implement each safely?

## Evidence matrix

| Area | AVD UI | Decrypted HAR | Signed APK | Confidence |
|---|---:|---:|---:|---|
| Event list/filtering | yes | yes | yes | high |
| Archive playback/download | yes | yes | yes | high |
| People list | yes | existing place query | yes | high |
| Guest invite generation | yes | yes (NTK `app=2`) | yes | high |
| Access keys | account-gated | no | yes | medium-low |
| Private-camera settings | no hardware | no | yes | medium-low |
| Arming/alarm | no | no | event strings only | insufficient |

Exact request/response contracts are maintained once in
[`api-reference.md`](../../architecture/api-reference.md); this document does
not duplicate live schemas.

## Runtime findings

### Event/archive

- The Events tab filters by date, device and people and shows accepted/missed
  intercom calls.
- Selecting an event opens archive at its timestamp.
- Archive supports timeline seek, event-duration rows and MP4 download.
- General history and per-camera event endpoints use different IDs; the
  `CameraID` inside a forpost event is not guaranteed to equal the public camera
  ID used in the request.
- A clean runtime sequence captured history pages `0 → 1 → 2 → 0`. Adjacent
  pages did not overlap; the repeated page 0 shared all 20 IDs with the first
  poll. `totalElements` changed `21 → 41 → 61 → 21`, confirming that it is not
  a stable total and must not drive polling termination.
- Runtime general-history types were `accessControlCallAccepted` and
  `accessControlCallMissed`. Forpost camera-event fixtures cover motion clips;
  older archive captures cover the HTTP-500/`11005` unavailable range.
- Retention is rolling: observed defaults are 14 days for intercom sources and
  7 days for other cameras. Backend error `11005` carries the actual boundary.

### People/guests

- The People screen can show owners and guests from place-scoped
  `subscriber-places` data.
- Add guest produces both QR and share text/link.
- NTK runtime traffic confirms `POST .../guests/link?placeId&app=2`, no body,
  HTTP 200 and `{data:{link,message}}`. The same request without Authorization
  returns HTTP 401 with a short non-JSON text body.
- The live credential was not copied into commit-safe artifacts; fixtures use
  `example.invalid` and placeholder text.

### Keys and private cameras

- Both 9.9.0 flavours contain the same endpoint set and DTOs.
- The current accounts did not expose the required key tariff/private camera;
  exact server behaviour is still unknown.
- Static API confirms list/register/delete/lookup/rename/reactivate and a new
  notification-status toggle for keys.
- Static camera API confirms sensitivity, event recording, record mode,
  microphone/speaker volume, mirror and PTZ. Provisioning/firmware endpoints
  exist but are intentionally excluded.

## Current integration comparison

Already implemented: password/SMS auth, places, live/snapshot cameras, door
open, balance/blocking/payment attributes, DND, FCM doorbell events and SIP
two-way call media.

Missing API wrappers: event search, camera event list, archive playback and
download, guest link generation, key APIs, feature info and private-camera
settings. `HTTP` currently supports GET/POST/DELETE but not PUT.

## HA design sources

| Official source | Applied decision |
|---|---|
| [Service actions and response data](https://developers.home-assistant.io/docs/dev_101_services/) | guest invite uses JSON-serializable response data and `SupportsResponse.ONLY` |
| [Service exceptions](https://developers.home-assistant.io/docs/core/platform/raising_exceptions/) | validation vs operator/communication errors are distinct and sanitized |
| [Event entity](https://developers.home-assistant.io/docs/core/entity/event/) | publish new device events through `EventEntity`, with declared event types |
| [Integration events](https://developers.home-assistant.io/docs/integration_events/) | prefer EventEntity over a new raw event-bus API |
| [Media source](https://developers.home-assistant.io/docs/core/platform/media_source/) | archive browsing/resolution belongs in `media_source.py` |
| [Browse media source root](https://developers.home-assistant.io/blog/2026/05/20/browse-media-source-root-class/) | use current `BrowseMediaSource` root model, not the legacy root item |
| [Auth and signed paths](https://developers.home-assistant.io/docs/auth_api/) | if proxy URLs are exposed, use short-lived HA-signed paths |
| [Permissions](https://developers.home-assistant.io/docs/auth_permissions/) | credential-generating/admin HTTP or websocket surfaces must enforce permissions |

## Risks and unknowns

- Guest link, access key code and signed media URLs are credentials.
- Service response data is not automatically secret once an automation stores or
  forwards it; user docs must call this out.
- Polling without a baseline would replay old history as new events.
- Full six-month pagination is expensive and backend totals are not reliable.
- Static-only endpoints may be tariff-gated, renamed or behave as toggles.
- Media proxying must support Range/stream cancellation and must not buffer a
  complete video in the HA event loop.

## Recommendation

Implement in evidence order: history/archive first, then the now-unblocked NTK
guest invitation slice. Keys and private-camera controls still wait for enabled
account/hardware captures. Keep each capability independently degradable.

## Quality gate

`RESEARCH_DONE` — completed. Static-only slices retain explicit capture gates.
