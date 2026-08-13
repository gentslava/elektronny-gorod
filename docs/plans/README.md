Status: Active Owner: Lead Architect Agent Last reviewed: 2026-08-11 (ADR-0015 plan approval and review evidence)

Source files:
- approved specs and executable delivery plans

Related docs:
- `../aidd/quality-gates.md`
- `../aidd/multi-agent-workflow.md`

Used by agents:
- planners, implementers, reviewers

Quality gates:
- PLAN_APPROVED
- CANDIDATE_FROZEN
- REVIEW_OK

---

# Implementation plans

This directory contains executable plans derived from approved specs.

- Use `YYYY-MM-DD-<topic>.md` for standalone plans.
- Reference the source spec and list exact files, tests, commands, and expected results.
- Declare the execution mode. When subagents are available, subagent-driven is the default; an affirmative start signal accepts the recommended mode unless the user explicitly requests inline execution.
- Include a reviewer matrix and an independent review task before push, PR creation, or merge. Self-review alone never satisfies `REVIEW_OK`.
- Record plan revision, approver/date/evidence and concrete implementation and reviewer identities. An affirmative reply counts only against the complete plan it directly answers.
- Freeze a clean committed candidate only after tests/security prechecks/docs and history cleanup. Store base/head/tree SHA in immutable review evidence; post-freeze security review closes `SECURITY_OK`; fixes invalidate approvals.
- After any candidate change, every mandatory reviewer reissues a verdict bound to the new base/head/tree; unchanged scopes may use delta attestation.
- Track implementation with checkboxes and small verifiable steps.
- Keep completed plans as delivery history; current system state remains in the canonical audit and summary documents.

Plans are tool-independent and may be executed by any human or agent workflow.

## Next reading

- For plan template: `../aidd/templates/plan.template.md`
- For workflow: `../../workflow.md`
