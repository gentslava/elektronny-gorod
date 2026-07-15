# PRD: mobile app parity slices

- **Date:** 2026-07-15
- **Owner:** @gentslava
- **Status:** Slice 1 approved and implemented in feature branch
- **Linked idea:** [`idea.md`](idea.md)

## Problem

The 9.9.0 stock apps expose durable event history, archive clips, guest
invitations, access keys and private-camera settings that are absent from the HA
integration. Exact support varies by account, tariff and hardware.

## Users and use cases

1. A resident opens HA after a missed intercom call and browses the matching
   archive clip.
2. An owner generates a guest link and deliberately shares it.
3. A resident sees registered keys and controls key notifications without
   exposing the physical key code.
4. A private-camera owner changes sensitivity or audio volume from HA and sees
   the authoritative backend value after refresh.

## Goals

1. Cover the useful 9.9.0 gaps with native HA primitives.
2. Preserve evidence tiers: no static-only write endpoint ships without HAR.
3. Keep credentials/PII out of states, recorder, logs and diagnostics.
4. Degrade per feature: an unavailable tariff must not make the whole config
   entry unavailable.

## Non-goals

- Recreate the mobile timeline pixel-for-pixel.
- Emit months of old events into HA as if they happened now.
- Store or display people names, account IDs, invite QR payloads or key codes.
- Automate invite acceptance, key tariff activation, camera provisioning,
  firmware update or payment CAPTCHA pages.

## Solution and acceptance criteria

### 1. Durable history and archive

- [x] `events/search` establishes a page-0 watermark on first start without
  triggering automations for old events.
- [x] Later polls deduplicate by server event ID and emit only explicitly mapped
  event types; unknown types are ignored without copying message/PII.
- [x] Existing FCM remains the realtime source for doorbell `ring`/`ended`.
- [ ] Camera archive is browseable through HA Media Source by place → camera →
  date/event; browsing uses opaque IDs, not signed URLs.
- [ ] Playback/download URLs are resolved on demand, expire naturally and never
  appear in entity state, attributes, logs, diagnostics or persistent storage.
- [ ] `11005` is surfaced as “outside retention”, not a generic camera failure.
- [ ] `IsGotoEnabled=0`/`isAvailable=false` produces a non-playable item, not a
  broken link.

### 2. Guest invitation

- [ ] An admin invokes `elektronny_gorod.create_guest_invite` for one place and
  receives JSON-serializable `{link, message}` response data.
- [ ] The action is `SupportsResponse.ONLY`; it creates no entity or
  notification and does not persist its response.
- [ ] The NTK integration sends `app=2`; ERTH `app=4` remains documented for a
  future backend/client variant.
- [ ] Missing place, non-owner/not-authorized backend response and transport
  failure raise user-safe HA exceptions with no response body or link in logs.
- [ ] Documentation warns that service response variables can still be exposed
  by a user's automation/blueprint.

### 3. Access keys

- [ ] Only accounts whose list endpoint succeeds get key entities.
- [ ] Stable identity uses `key_service_id`; `accessKeyCode` is discarded after
  parsing and cannot reach state, attributes, unique ID or diagnostics.
- [ ] MVP is read-only inventory with non-sensitive state/bind status; entities
  are disabled by default until real-account semantics are verified.
- [ ] Default entity name is localized/generic and derived only from service ID;
  backend key name is treated as possible PII and is not copied automatically.
- [ ] Key notification switch is a separate slice after HAR confirms the
  body-less toggle contract and authoritative refresh.
- [ ] Register/delete/rename/reactivate remain later admin actions with explicit
  confirmation and separate security review.

### 4. Private-camera settings

- [ ] `cameras/features/info` gates every settings entity.
- [ ] Sensitivity and volume entities derive allowed values from the response;
  no hardcoded range.
- [ ] Writes are non-optimistic: refresh must confirm the new state.
- [ ] Unsupported or tariff-gated endpoints make only their entity unavailable.
- [ ] Mirror/PTZ/record-mode are not added until enum/action values are captured
  from runtime traffic.

## Affected modules

- Slice 1: `api.py`, new `history.py`, `event.py`, `__init__.py`
- Slice 2: new `media_source.py`; archive additions in `api.py`
- potential `number.py`, `select.py`, `switch.py`, `services.yaml`
- `__init__.py`, `strings.json`, `translations/{ru,en}.json`
- focused tests and sanitized fixtures under `tests/`

## Existing config entries

No config-entry migration is needed for the additive history entities.
`HistoryManager` owns an independently versioned HA `Store` schema v1 containing
only bounded opaque event IDs. If user options are later added, they must default
safely for existing entries; increment `ConfigFlow.VERSION` only with an explicit
migration.

## HA Quality Scale impact

This work improves feature completeness but also expands action, exception,
translation and test obligations. Every new action must be documented; every
new config step/entity translation must exist in both languages.

## Open questions

- [ ] Full observed `eventTypeName` taxonomy and missed-vs-accepted semantics.
- [ ] Signed URL lifetime, redirect behaviour and Range support through HA.
- [ ] Guest link expiry/revocation and backend authorization rules.
- [ ] Key notification toggle body/response and bind status enum.
- [ ] Camera capability strings, record/mirror/PTZ enum values and range shape.

## Quality gate

`SPEC_READY` and `PLAN_APPROVED` are granted for Slice 1. Later slices retain
their individual capture/security gates.
