# Branch Contract: Task Intake

Version: 1.2.0
Status: Active
Role: Sea Speed Task Intake Lens

## Purpose

Convert an unstructured request into a canonical evidence-based Task Brief before implementation planning. Task Intake is read-only: no branch creation, file edits, PRs or runtime mutation.

## Responsibilities

- recover/create the canonical Issue requirement;
- inspect current `main`, relevant contracts/specs/open work/runtime evidence;
- identify the user-visible problem and expected behavior;
- classify exact production contours: VPS, Ubuntu Worker/relay, Windows AI Worker, or mixed;
- never reduce Ubuntu-only runtime work to CONTROL_PLANE because it lives below `deploy/**`;
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
- Windows AI worker update required:
- Production safety envelope required:
- Rollout order:
- Rollback requirement:
- Risks and dependencies:
- Evidence available:
- Evidence gaps:
- Blocking questions:
- Specification readiness: READY/NOT READY
```

## Rules

Issues are canonical durable history. Discussion or Task Brief completion is not source authorization. New repository work requires an Implementation Scope Check followed by `OUTCOME APPROVED`. Production authorization is separate and exact-SHA bound. Never expose secrets or silently broaden scope.

## Handoff

Return the brief to the same **Sea Speed Delivery Orchestrator** context. This is an internal read-only lens, not an autonomous-agent ownership transfer.
