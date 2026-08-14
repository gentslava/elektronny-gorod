Status: Approved Owner: Root orchestrator Last reviewed: 2026-08-14 (revision 4 adds neutral canonical agent contracts after owner feedback)

Source files:
- `docs/decisions/0015-independent-review-candidate.md`
- `docs/decisions/0016-canonical-agent-contracts.md`
- `workflow.md`
- `docs/aidd/quality-gates.md`
- canonical `.agents/**` contracts and tool-specific adapters

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

- **Revision:** 4.
- **Approver:** @gentslava.
- **Date:** 2026-08-14.
- **Evidence:** direct owner instruction that Claude/Codex/other agent rules must reference one source of truth instead of duplicating instructions, with path-fence drift shown in PR #79.
- **Execution mode:** inline implementation in the root session under the active collaboration policy; independent candidate reviews remain mandatory after freeze.

## Goal

Make it impossible for a nontrivial change to reach ordinary push/merge using self-review, stale approvals, unrelated CI, or contradictory Claude/Codex adapters, without coupling this process remediation to the FCM product fix.

## Scope

- One accepted ADR for plan approval, candidate freeze, independent review, publication evidence, CI and live test-baseline ownership.
- Synchronized root contracts, workflow, quality gates, agent profiles, commands, migrated skills, templates and runbooks.
- One canonical secret-log scanner and one canonical audit-reconciliation hook; tool-specific wrappers contain no duplicate logic.
- One neutral `.agents/**` source for roles, rules, commands and hook implementations; tool directories retain discovery metadata only.
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

All final reviewers receive one exact base/head/tree, work read-only, declare non-participation in implementation, and reissue a verdict after any change.

## Tasks

- [x] Separate product commits from AIDD/process changes.
- [x] Consolidate the iterative review decisions into final ADR-0015 semantics.
- [x] Move portable specs/plans into repository-owned `docs/` directories.
- [x] Deduplicate Claude/Codex hooks around canonical implementations.
- [x] Add deterministic secret-log and reconciliation regressions.
- [x] Synchronize active Claude/Codex profiles and operational adapters.
- [x] Bind release checks to PR head SHA and support stacked `<target-ref>`.
- [x] Reconcile hook/tool/roadmap docs and remove tool-specific plan mandates.
- [x] Consolidate role, rule, command and hook bodies under `.agents/**`; replace Claude/Codex/Cursor/Copilot copies with thin adapters.
- [x] Add ADR-0016, source-of-truth mapping and adapter drift regressions.
- [ ] Recheck PR `headRefOid` after `gh pr checks --watch` to close the stale-head race.
- [ ] Remove stale `READY_FOR_RELEASE`/Silver claims from roadmap summaries.
- [ ] Extend portability regression coverage to feature-local plans and finish metadata/`Next reading` for the new plan.
- [ ] Rewrite the two commit messages with real paragraph breaks while preserving the exact final tree.
- [ ] Freeze the remediated clean candidate and obtain new process/docs/QA/ security verdicts on the same tuple.
- [ ] Publish the stacked branch, add durable review evidence and wait for CI.

## Acceptance

- Focused hook/contract tests and full backend suite pass.
- Secret and reconciliation hooks pass; pending findings are reported as open.
- No active adapter checks CI from `master` or diffs a stacked PR from hardcoded `master`.
- Canonical final reviewer roles contain tuple, independence, Critical/Important and re-attestation invariants; Claude/Codex profiles only delegate to them.
- Adapter sets match canonical roles/commands, remain thin and contain no parent-relative Markdown path fences.
- Plans are tool-independent; hook docs name only canonical live files.
- History is self-contained, with no commit requiring an executable introduced only by a later commit.
- Independent reviewers report no Critical/Important finding on the final tuple.
