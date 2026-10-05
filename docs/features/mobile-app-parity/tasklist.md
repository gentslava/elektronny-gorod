# Tasklist: mobile app parity slices

- **Date:** 2026-07-16
- **Owner:** @gentslava
- **Linked plan:** [`plan.md`](plan.md)

No task below authorizes code changes by itself; implementation starts after the corresponding spec/capture gate is approved. «Capture» here means HAR or a live probe with the research account (ADR-0006); where neither is possible, a static-only contract may ship labelled as such.

## Capture prerequisites

- [x] **T-001** Capture and sanitize guest-link POST success + authorization failure without retaining the live link. _Acceptance:_ method/query/status and placeholder fixture reproduce parser. Captured NTK `app=2`: success is HTTP 200 JSON; missing auth is HTTP 401 non-JSON text. _Audit:_ A-93.
- [ ] **T-002** Capture access-key list and notification toggle on an enabled account. _Acceptance:_ list wrapper, status enums and toggle request body are exact. _Audit:_ A-94.
- [ ] **T-003** Capture `features/info`, motion, volumes, record/mirror/PTZ on a private camera. _Acceptance:_ capability strings, enums and ranges are exact; no destructive provisioning action. _Audit:_ A-95.
- [x] **T-004** Extend event fixtures with missed/accepted calls, motion, unavailable clip and multi-page overlap. _Acceptance:_ sanitized fixtures now cover accepted/missed calls, forpost motion, HTTP-500/11005 and page `0 → 1 → 2 → 0` with a 20-ID repeated-page overlap. _Audit:_ A-50/A-58.

## Slice 0 — API/transport

- [ ] **T-010** Add additive HTTP PUT support and unit tests. _Acceptance:_ JSON content type, timeout, auth and redacted logging match POST. _Plan:_ Slice 0.
- [x] **T-011** Add typed, sanitized history API methods. _Acceptance:_ exact general/forpost URL, query/body and ID mapping pass; backend message is absent from DTO. Archive/11005 methods remain T-031. _Audit:_ A-50/A-58.
- [ ] **T-012** Add guest/key/settings methods only when T-001/T-002/T-003 exists. _Acceptance:_ no guessed request field. _Audit:_ A-93..A-95.

## Slice 1 — history events

- [x] **T-020** Implement first-page baseline/watermark. _Acceptance:_ old fixture emits zero events; a newly discovered place/access-control gets its own silent baseline without replay. _Audit:_ A-58.
- [x] **T-021** Implement bounded dedup and whitelist mapping. _Acceptance:_ one new event triggers once across overlapping polls/restart. _Audit:_ A-50/A-58.
- [x] **T-022** Add/unload dedicated polling lifecycle. _Acceptance:_ no leaked tasks/listeners after config-entry unload. _Audit:_ A-58.
- [x] **T-023** Add per-camera motion EventEntity only for verified event types. _Acceptance:_ declared types/device mapping and translations pass; entity is disabled by default and camera API polling starts only when enabled. _Audit:_ A-50.
- [x] **T-024** Add entity-scoped previous-page WebSocket browse. _Acceptance:_ `POLICY_READ`, source routing, page `0..100`, safe API failure and exact sanitized response are covered. _Audit:_ A-58/S-21.
- [x] **T-025** Add `custom:eg-event-history-card` to the existing bundle. _Acceptance:_ RU/EN date groups, accepted/missed rows, refresh, load-more, loading/empty/error states and responsive HA-theme styling. _Audit:_ A-58.
- [x] **T-026** Harden the frontend history boundary. _Acceptance:_ malformed events and cross-entity responses are rejected; page overlap deduplicates by opaque event ID; partial refresh preserves rows of failed feeds. _Audit:_ S-21.

## Slice 2 — archive

Закрыт PR #81 (merged 2026-09-02): `media_source.py` + `clip_proxy.py`.


- [x] **T-030** Implement Media Source browse tree with opaque identifiers. _Acceptance:_ no signed URL in browse response. _Audit:_ A-50.
- [x] **T-031** Add typed archive playback/download methods and on-demand resolver, including retention errors. _Acceptance:_ exact fixtures cover 11005, HTTP-200 business error and unavailable event with user-readable mapping. _Audit:_ A-59.
- [x] **T-032** Decide/prove direct resolve vs HA proxy, including Range and cancellation. _Acceptance:_ security review + streaming test. _Audit:_ A-50.
- [x] **T-033** Run caplog/storage/state sentinel scan for signed URL. _Acceptance:_ sentinel appears only in mocked upstream/resolver result.

## Slice 3 — guests

- [x] **T-040** Implement owner-side `create_home_invite` response action. _Acceptance:_ `app=2`, `SupportsResponse.ONLY`, `{link,message}` and nothing else from the operator payload. _Audit:_ A-93.
- [x] **T-041** Enforce place/admin policy and safe exception mapping. _Acceptance:_ unauthorized caller never reaches API; the place is addressed by its device, so an id from another account cannot route the request; transport failures — refusal, timeout and a malformed body alike — and a 200 without a link all surface as translated refusals. _Audit:_ A-93.
- [x] **T-042** Add service schema, ru/en strings, docs and secret sentinel test. _Acceptance:_ no response persisted/logged by integration, pinned at the transport layer as well as through the action. _Audit:_ A-93.
- [x] **T-043** Temporary access from the static `mh-temp-pass` contract (APK 9.10.0/9.11.0, ADR-0006 static-only). Live probes (2026-10-05) settled what they could: `time-to-life` = [3600, 14400, 43200, 86400] s, `access-controls` fields `{id, name, roleName, externalId}`, delete route reachable; create stays static-only (404 until the operator provisions `TEMP_PASS` on the address). Implemented in `feat/temporary-access`: `create_temporary_access` / `list_temporary_access` / `revoke_temporary_access`, admin-only, link redacted. _Acceptance:_ first live create confirmation — пользователь с подключённой услугой. _Audit:_ A-118.

## Slices 4-5 — keys

- [ ] **T-050** Parse read-only key list and discard code at boundary. _Acceptance:_ sentinel cannot reach coordinator/entity/diagnostics. _Audit:_ A-94.
- [ ] **T-051** Add disabled-by-default non-sensitive key entity/model. _Acceptance:_ unique ID uses service ID and partial failure is isolated.
- [ ] **T-052** After toggle contract capture, add non-optimistic notification switch. _Acceptance:_ failed mutation preserves state, successful mutation refreshes. _Audit:_ A-94.
- [ ] **T-053** Keep register/delete/rename/reactivate out of MVP; create a new approved plan/security review before adding them.

## Slice 6 — private camera

- [ ] **T-060** Implement feature-info discovery. _Acceptance:_ no setting endpoint is called without capability. _Audit:_ A-95.
- [ ] **T-061** Add motion sensitivity NumberEntity using backend min/max. _Acceptance:_ range and authoritative refresh from fixture. _Audit:_ A-95.
- [ ] **T-062** Add microphone/speaker NumberEntity using returned range arrays. _Acceptance:_ sparse ranges are handled or rejected explicitly. _Audit:_ A-95.
- [ ] **T-063** Add record/mirror/PTZ only after enum captures. _Acceptance:_ no guessed string constants. _Audit:_ A-95.
- [ ] **T-064** Prove one unsupported endpoint does not mark live camera/config entry unavailable. _Acceptance:_ partial-failure test.

## Finalization

- [x] **T-070** Update API reference, audit, roadmap, feature docs and release notes in each implementation PR.
- [x] **T-071** Run focused/full pytest, markdown link checker, `git diff --check` and secret sentinel scan. _Evidence:_ 47 focused + 432 full backend and 62 frontend tests passed; TypeScript check and production build clean; changed-doc links and diff check clean; global link scan still reports 11 pre-existing template/private-memory references outside this slice.
- [x] **T-072** Update public README/info only for features actually shipped.

## Dependencies

```text
T-004 ─► T-011 ─► T-020..T-033
T-001 ─► T-012 ─► T-040..T-042
T-002 ─► T-012 ─► T-050..T-052
T-003 ─► T-012 ─► T-060..T-064
all implemented slices ─► T-070..T-072
```

## Progress

| Status | Count |
|---|---:|
| done | 13 |
| in progress | 0 |
| pending | 20 |

## Quality gates

- `PLAN_APPROVED` granted for Slice 1; required separately for later slices.
- `IMPLEMENTATION_STEP_OK` per slice.
- `TESTS_PASS`, `SECURITY_OK`, `DOCS_UPDATED` before merge.
