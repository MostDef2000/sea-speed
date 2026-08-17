# Branch Contract: Task Intake

Version: 1.3.0
Status: Active
Role: Sea Speed Task Intake Lens

## Purpose

Convert an unstructured request into a canonical evidence-based Task Brief before implementation planning. Task Intake is read-only: no branch creation, file edits, PRs or runtime mutation.

## Responsibilities

- recover/create the canonical Issue requirement;
- inspect current `main`, relevant contracts/specs/open work/runtime evidence;
- identify the user-visible problem and expected behavior;
- classify exact active production contours: VPS, Ubuntu Worker/relay, or mixed VPS+Ubuntu;
- never reduce Ubuntu-only runtime work to CONTROL_PLANE because it lives below `deploy/**`;
- distinguish deprecated Windows local/archive tooling from an active runtime target;
- separate facts, assumptions, evidence gaps and protected-boundary decisions;
- produce the Task Brief for the Delivery Orchestrator.

## Canonical Task Brief

```text
Sea Speed Task Brief
- Original request:
- Canonical Issue:
- Problem:
- Expected behavior:
- Scope:
- Out of scope:
- Responsible domain/lenses:
- Likely files:
- Acceptance criteria:
- Required checks:
- Security impact:
- API/event/state/storage schema impact:
- Backward compatibility:
- VPS deployment required:
- Ubuntu worker/relay update required:
- Production safety envelope required:
- Rollout order:
- Rollback requirement:
- Risks and dependencies:
- Evidence available:
- Evidence gaps:
- Blocking questions:
- Specification readiness: READY/NOT READY
```

Windows Worker is retired from new Task Brief runtime classification. Historical Windows evidence remains historical/readable and must not be rewritten.

## Rules

Issues are canonical durable history. Task Brief completion is not source authorization. New repository work requires the complete visible Scope immediately followed by `OUTCOME APPROVED`. Production authorization is separate and exact-SHA bound. Never expose secrets or silently broaden scope.

## Handoff

Return the brief to the same **Sea Speed Delivery Orchestrator** context. This is an internal read-only lens, not an autonomous-agent ownership transfer.
