Status: Pending approval
Owner: Root orchestrator
Last reviewed: 2026-08-11 (revision 3 after second independent critic pass)

Source files:
- `docs/decisions/0015-independent-review-candidate.md`
- `workflow.md`
- `docs/aidd/quality-gates.md`
- active Claude/Codex agents, commands, skills and hooks

Related docs:
- `../audit/project-audit.md` (A-97)
- `../aidd/multi-agent-workflow.md`
- `../testing/strategy.md`

Quality gates:
- PLAN_APPROVED
- CANDIDATE_FROZEN
- REVIEW_OK
- REVIEW_EVIDENCE_PUBLISHED
- CI_GREEN

---

# AIDD candidate review gates — implementation plan

## Approval record

- **Revision:** 3.
- **Approver:** @gentslava.
- **Date:** 2026-08-12.
- **Evidence:** direct session instruction to publish this branch as its own pull
  request ("chore/aidd-review-gates нужно запушить и создать PR"), which accepts
  revision 3 and releases the remaining remediation tasks.
- **Execution mode:** subagent-driven implementation/review where isolated
  ownership is useful; root orchestrator owns integration and publication.

## Goal

Make it impossible for a nontrivial change to reach ordinary push/merge using
self-review, stale approvals, unrelated CI, or contradictory Claude/Codex
adapters, without coupling this process remediation to the FCM product fix.

## Scope

- One accepted ADR for plan approval, candidate freeze, independent review,
  publication evidence, CI and live test-baseline ownership.
- Synchronized root contracts, workflow, quality gates, agent profiles,
  commands, migrated skills, templates and runbooks.
- One canonical secret-log scanner and one canonical audit-reconciliation hook;
  tool-specific wrappers contain no duplicate logic.
- Regression tests for scanner, reconciliation and cross-tool invariants.
- A product-only PR #78 plus a separate stacked process/tooling PR.

## Non-goals

- No runtime integration behavior in the stacked AIDD diff.
- No public README/release changes.
- No merge or release without current candidate evidence and remote CI.

## Ownership and reviewer matrix

| Area | Implementer | Mandatory independent reviewer |
|---|---|---|
| Process/ADR/gates | root orchestrator | lead-architect critic |
| Docs/adapters/portable plans | root orchestrator | docs-keeper |
| Hooks and regression tests | root orchestrator | QA + security reviewer |
| History and publication | root orchestrator | read-only history audit + final reviewers |

All final reviewers receive one exact base/head/tree, work read-only, declare
non-participation in implementation, and reissue a verdict after any change.

## Tasks

- [x] Separate product commits from AIDD/process changes.
- [x] Consolidate the iterative review decisions into final ADR-0015 semantics.
- [x] Move portable specs/plans into repository-owned `docs/` directories.
- [x] Deduplicate Claude/Codex hooks around canonical implementations.
- [x] Add deterministic secret-log and reconciliation regressions.
- [x] Synchronize active Claude/Codex profiles and operational adapters.
- [x] Bind release checks to PR head SHA and support stacked `<target-ref>`.
- [x] Reconcile hook/tool/roadmap docs and remove tool-specific plan mandates.
- [ ] Recheck PR `headRefOid` after `gh pr checks --watch` to close the
  stale-head race.
- [ ] Remove stale `READY_FOR_RELEASE`/Silver claims from roadmap summaries.
- [ ] Extend portability regression coverage to feature-local plans and finish
  metadata/`Next reading` for the new plan.
- [ ] Rewrite the two commit messages with real paragraph breaks while
  preserving the exact final tree.
- [ ] Freeze the remediated clean candidate and obtain new process/docs/QA/
  security verdicts on the same tuple.
- [ ] Publish the stacked branch, add durable review evidence and wait for CI.

## Acceptance

- Focused hook/contract tests and full backend suite pass.
- Secret and reconciliation hooks pass; pending findings are reported as open.
- No active adapter checks CI from `master` or diffs a stacked PR from hardcoded
  `master`.
- Claude/Codex final reviewer profiles share tuple, independence,
  Critical/Important and re-attestation invariants.
- Plans are tool-independent; hook docs name only canonical live files.
- History is self-contained, with no commit requiring an executable introduced
  only by a later commit.
- Independent reviewers report no Critical/Important finding on the final tuple.
