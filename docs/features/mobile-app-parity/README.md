# Mobile app parity: history, archive, guests, keys and camera settings

- **Status:** Slice 1 implemented in `feat/durable-event-history`; review pending
- **Date:** 2026-07-15
- **Owner:** @gentslava
- **Apps:** Мой Дом 9.9.0 and Умный Дом.ру 9.9.0

This folder is the implementation hand-off for features found while exercising
the 9.9.0 Android applications. It deliberately separates observed behaviour
from static-only APK contracts.

## Feature matrix

| Feature | Best evidence | Proposed HA surface | Audit | Gate before code |
|---|---|---|---|---|
| Durable event history | decrypted HAR + AVD UI | polling baseline + device `event` entities | A-58 / A-50 | implemented in feature branch |
| Camera archive and clips | decrypted HAR + AVD UI | `media_source.py`, no URL attributes | A-50 / A-59 | playback/download fixtures |
| Guest invitation | decrypted POST + AVD UI + APK DTO | response-only admin action | A-93 | captured; admin/security review |
| Access keys | APK Retrofit/DTO | read-only inventory, then notification switch | A-94 | enabled-account HAR |
| Private camera settings | APK Retrofit/DTO | capability-gated `number`/`switch`/`select` | A-95 | private-camera HAR + hardware |

## Documents

| File | Purpose |
|---|---|
| [`idea.md`](idea.md) | why the parity work is useful and where scope stops |
| [`prd.md`](prd.md) | user-visible requirements and acceptance criteria |
| [`research.md`](research.md) | runtime/static evidence and unresolved contracts |
| [`plan.md`](plan.md) | architecture, vertical slices, security and tests |
| [`tasklist.md`](tasklist.md) | executable tasks and capture prerequisites |

## Sources of truth

- Exact endpoint/DTO contracts and evidence labels:
  [`api-reference.md`](../../architecture/api-reference.md).
- APK/HAR/PCAP and AVD conclusions:
  [`9.9.0-analysis.md`](../../../research/apk/9.9.0-analysis.md).
- Commit-safe response fixtures:
  [`tests/fixtures/mobile_app_9_9_0`](../../../tests/fixtures/mobile_app_9_9_0/README.md).
- Priority/status:
  [`project-audit.md`](../../audit/project-audit.md) and
  [`roadmap.md`](../../roadmap.md).

Do not copy live guest links, access-key codes or signed archive URLs into this
folder. They are access credentials even when short-lived.

## Quality gates

- [x] `IDEA_CAPTURED`
- [x] `RESEARCH_DONE`
- [x] `SPEC_READY` — Slice 1
- [x] `PLAN_APPROVED` — Slice 1
- [x] `TESTS_PASS` — 411 passed
- [x] `SECURITY_OK` — history DTO/state/store sentinel boundary reviewed
- [x] `DOCS_UPDATED`
