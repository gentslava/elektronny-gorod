# Camera archive Media Source

- **Status:** approved design
- **Date:** 2026-08-29
- **Scope:** PRD Slice 2 — browse and play forpost motion-event clips through a native HA Media Source
- **Related:** [`features/mobile-app-parity/prd.md`](../features/mobile-app-parity/prd.md) (Slice 2), [`architecture/api-reference.md`](../architecture/api-reference.md) (`/rest/v2/forpost/cameras/{id}/events`, `/rest/v1/forpost/events/{event_id}/downloads`), audit A-50, `history.py`, `history_ws.py`

## Problem

The mobile app plays an archive clip when the user taps a camera motion event in its history feed. The HA integration already polls verified motion events (`HistoryPoller` → `ElektronnyGorodCameraHistoryEvent`) and exposes accepted/missed call rows through a custom card, but the recorded video behind each event is unreachable from Home Assistant: there is no way to browse a camera's archive or play a clip from the Media Browser or a media-player entity.

The backend contract is documented: `IsGotoEnabled=1` events carry a downloadable mp4 behind `GET /rest/v1/forpost/events/{event_id}/downloads?container=mp4`, which returns a one-time signed URL on a separate video-storage host.

## Decisions

Confirmed with the maintainer during brainstorming:

1. **Playback** — playable mp4 clip per event via the downloads endpoint. No archive RTSP seeking (`?TS=` playback), no go2rtc coupling in this slice.
2. **Browse hierarchy** — place → camera → day folder → events, per the PRD wording.
3. **Camera scope** — `source in ("intercom", "public")`, matching the motion-history poller and the already-wrapped `/rest/v2/forpost/cameras/{id}/events` DTO. Personal cameras use a different endpoint/DTO and stay out of scope.
4. **Permissions** — authenticated-user access with hidden-camera gating. Per-user entity-read scoping (the initial choice) proved unimplementable: HA's media source API passes no user context (see Permissions below).

## Goals

1. Camera archive is browseable through HA Media Source by place → camera → day/event.
2. Browsing uses opaque IDs only; signed URLs are resolved on demand, expire naturally, and never appear in entity state, attributes, logs, diagnostics, or persistent storage.
3. `11005` surfaces as "outside retention", not a generic camera failure.
4. `IsGotoEnabled=0` / `isAvailable=false` produces a non-playable item, not a broken link.
5. No new entities, config options, storage, timers, or config-entry migration.

## Non-goals

- Archive timeline streaming/seeking via `/rest/v1/forpost/cameras/{id}/video?TS=`.
- Personal (`source="place"`) cameras and their `mh-camera-personal` events endpoint.
- Downloading/caching clips to `/media`; a `download` service action may be a later slice.
- Per-event thumbnails (no historical preview endpoint is documented; live snapshots would be misleading).
- Any change to the event entities, poller, watermark store, or the history card.

## Design

### Registration

New module `custom_components/elektronny_gorod/media_source.py` exposing `async_get_media_source(hass) -> ElektronnyGorodMediaSource`. HA's core `media_source` component discovers integration-provided sources when the integration's component is loaded (the same mechanism `tts` and `local_ip` use); the plan verifies discovery without a manifest change and falls back to adding `"media_source"` to manifest `dependencies` only if runtime evidence requires it (manifest edits go through the repo ask-first gate either way).

The source declares `domain = DOMAIN` and a static display `name`.

### content_id scheme

Opaque, position-based path segments; no signed URLs, no names, no PII:

```
media-source://elektronny_gorod/                                          → places (one folder per config entry)
…/<entry_id>/<place_id>                                                   → accessible cameras of the place
…/<entry_id>/<place_id>/<camera_id>                                       → day folders (static list)
…/<entry_id>/<place_id>/<camera_id>/<yyyymmdd>                            → events of that day
…/<entry_id>/<place_id>/<camera_id>/<yyyymmdd>/<event_id>                 → playable clip
```

`entry_id`, `place_id`, `camera_id`, `event_id` are the same opaque tokens already used in entity unique IDs and the history watermark store. Malformed or unknown identifiers raise `MediaSourceError`.

### Browse

- **Root** lists one folder per loaded config entry that has at least one accessible place; title = entry title.
- **Place** lists accessible cameras: `source in ("intercom", "public")`, present in `coordinator.data`, not hidden in the entity registry. Titles use existing display helpers (`place_display_name`, camera name).
- **Camera** lists a static set of day folders without extra API calls: the last 14 local days for intercom (`accessControl` class) cameras and 7 for others, matching the documented operator retention defaults. Day boundaries use the HA local timezone (`dt_util`). Over-declaring days is harmless: expansion of a day outside retention yields an empty list or a business error, both handled below.
- **Day** issues one `query_camera_events(camera_id, lower, upper)` call for the day window and lists motion events (subject ID 126, as in the poller) newest-first. Title `HH:MM:SS · <duration>s` in HA local time.
- **Event item**: `can_play = available and goto_enabled`; `can_expand = False`; playable items use `MediaType.VIDEO` / `MediaClass.VIDEO`; folders use `MediaClass.DIRECTORY`. Non-playable events render as greyed-out rows, satisfying the "not a broken link" criterion.

### Resolve

`async_resolve_media` accepts only event nodes. After the permission check it calls a new API wrapper:

```
query_event_download(event_id: str) -> str
```

`GET /rest/v1/forpost/events/{event_id}/downloads?container=mp4` → `{"data": "<signed mp4 url>"}` (note: `data` is a string, not an object). The wrapper raises typed errors for the forpost `{errorCode, errorMessage}` shape and non-200 responses. Resolve returns `PlayMedia(url, "video/mp4")`. The signed URL is used transiently for the single response and discarded; every play re-resolves a fresh link, so expiry is naturally tolerated.

### Error mapping

HA's `media_source` websocket handlers relay the exception message as plain text (`resolve_media_failed` / `browse_media_failed`), and `HomeAssistantError.__str__` degrades `translation_key`-based errors to a domain.key string on this path. Errors are therefore raised as `Unresolvable` (resolve) / `BrowseError` (browse) with plain English messages — no new translation keys:

| Condition | Message |
|---|---|
| `errorCode 11005` (archive out of range) | `Archive is outside the retention window` |
| Event not downloadable (`IsGotoEnabled=0` / `isAvailable=false` / missing `data`) | `Recording is not available` |
| Transient API/transport failure | `Archive is temporarily unavailable` |
| Malformed or deep-linked unknown ID | `Unknown media item` |

### Permissions

**Deviation from the original decision (entity-read scoped), forced by the HA platform.** Verified against both CI-pinned HA versions (2024.10.4 and 2026.5.4): `MediaSource.async_browse_media`/`async_resolve_media` receive a `MediaSourceItem` with no user context — core's `media_source/browse_media` and `resolve_media` websocket commands never pass the connected user. Per-user entity-read checks are therefore not implementable inside a media source (this is also why core sources like `tts` and `local_ip` do no per-user scoping).

Effective model, identical to every other HA media source:

- Any authenticated HA user can browse and resolve the source.
- Cameras hidden in the HA entity registry (`hidden_by is not None`, checked via `unique_id = f"{DOMAIN}_camera_{camera_id}"`) are excluded for everyone — in browse and in resolve. Cameras whose entity is disabled (but not hidden) still appear in the archive: the visibility gate is `hidden_by` only (the «Показывать на панели» toggle).
- Places without any eligible camera are omitted from entries; entries without places are omitted from the root. Resolve validates the full path (entry/place/camera must exist) before hitting the API.

### Security & privacy

- Signed URLs exist only inside the `PlayMedia` response to the requesting client. No `LOGGER` call includes them; the module holds no storage; `diagnostics.py` and `TO_REDACT` are untouched.
- Logs carry only opaque IDs (`entry_id`, `place_id`, `camera_id`, `event_id`) — tokens already considered non-sensitive throughout the codebase.
- No new credentials, headers, or auth paths; the downloads call rides the existing authenticated `HTTP` layer with its redaction guarantees (ADR-0004).

## Affected modules

- new: `custom_components/elektronny_gorod/media_source.py`
- `api.py`: add `query_event_download` and `ForpostDownloadError`
- tests: new `tests/test_media_source.py`, additions to the API contract tests
- docs: this spec, `features/mobile-app-parity/media-source.md` (new), `api-reference.md` cross-link, `history-card.md` limitation note, PRD checklist, `AGENTS.md` structure tree, `docs/testing/strategy.md` baseline entry

## Testing

`tests/test_media_source.py` (pytest-homeassistant-custom-component):

1. Browse tree happy path: root → place → camera → day → events, correct media classes and titles.
2. Day folder count matches retention class (14 intercom / 7 other).
3. Non-playable event (`IsGotoEnabled=0` or `isAvailable=false`) → `can_play=False`.
4. Hidden-camera gating: a camera with `hidden_by` set in the registry appears neither in browse nor resolves; camera registry entry missing → treated as visible (entities are created for every eligible camera at setup).
5. Resolve success: exact API URL asserted via mocked `http.get`, `PlayMedia` mime `video/mp4`, signed URL absent from any log record.
6. `11005` → "outside retention"; missing recording → "not available"; transport error → "temporarily unavailable".
7. Multi-entry aggregation and per-entry isolation.

API contract tests: `query_event_download` URL shape, string-`data` parsing, forpost error-body mapping.

## Quality gate / execution mode

Subagent-driven execution (repo default). Implementer subagents write code and tests; independent read-only reviewers close the gates: `ha-expert` (media source lifecycle, registry use, HA version compatibility) and `security-auditor` (signed URL handling, logging, the authentication-user trust boundary) before merge; `qa-engineer` for the test plan. Final candidate follows the clean-worktree + SHA fixation procedure.

## Open runtime-verification items

1. Media-source discovery without a manifest change (expected: automatic via `media_source` component's load listener).
2. Browser-side playback of the signed URL (`Content-Disposition`, Range, redirect behavior) on a real account — the PRD already tracks signed-URL lifetime/redirect/Range as an open question; failures degrade to a playback error without affecting browse.
3. Whether the downloads endpoint enforces one-time use (each play re-resolves, so this should be invisible either way).
