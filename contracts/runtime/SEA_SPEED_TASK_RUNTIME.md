# Sea Speed Task Runtime

Version: 1.1.0
Status: Active

## States

```text
DISCUSSION
READY_FOR_IMPLEMENTATION
IMPLEMENTING
MODULE_COMMITTED
HANDOFF_VALIDATED
CORE_RELEASE_INTEGRATING
SOURCE_INTEGRATED
ACTIONS_REQUIRED
ACTIONS_RUNNING
ACTIONS_COMPLETED
RUNTIME_ACCEPTANCE
COMPLETE
BLOCKED
FAILED
```

## Semantics

- `DISCUSSION` includes read-only Task Intake, repository discovery and Task Brief preparation.
- `READY_FOR_IMPLEMENTATION` requires a canonical Task Brief, an Implementation Scope Check and valid repository-write approval.
- `SOURCE_INTEGRATED` means source is verified on `main`; it does not mean VPS deployment or Windows worker update.
- `ACTIONS_REQUIRED` is manual fallback only.
- `RUNTIME_ACCEPTANCE` verifies the applicable VPS and/or worker contour.
- Terminal states are only `COMPLETE`, `BLOCKED`, and `FAILED`.

## Canonical Task Brief

Implementation tasks should be represented in the linked GitHub Issue with:

```text
Task Brief
- Original request:
- Problem:
- Expected behavior:
- Scope:
- Out of scope:
- Responsible area:
- Likely files:
- Acceptance criteria:
- Security impact:
- API compatibility impact:
- Runtime contour:
- VPS deployment required:
- Windows worker update required:
- Rollout order:
- Risks:
```

Task Intake prepares this brief without repository writes. The Project Manager validates it against current repository state before requesting approval.

## Required status block

```text
Sea Speed Task Runtime
- Task:
- Issue:
- Responsible agent:
- Current phase:
- Branch:
- Approved commit/range:
- Changed files:
- main updated: YES/NO
- VPS deployment: NOT REQUIRED/PENDING/RUNNING/SUCCESS/FAILED
- Windows worker update: NOT REQUIRED/PENDING/RUNNING/SUCCESS/FAILED
- User action:
- Final state: PENDING/COMPLETE/BLOCKED/FAILED
```

## Continuation rule

After approval, continue automatically through every deterministic safe transition. Do not wait for another user message between implementation, integrity checks, PR, CI, merge, release execution and verification.

New approval is required only for scope expansion, destructive action, secrets, protected files, schema changes, or behavior redesign.

## Capability rule

Before the first write, verify that the full approved file set and required delivery lifecycle are executable. Do not create a partial implementation when mandatory files, PR operations, CI evidence, merge, release or rollback paths are unavailable.

## Integrity rule

After each write, fetch the complete file, verify its start and ending, validate syntax where applicable, compare the branch with `main`, and confirm the changed-file list remains in scope.

## Evidence hierarchy

Completion evidence is evaluated in this order:

```text
approved scope
→ exact changed files
→ PR validation
→ merge commit on main
→ applicable delivery evidence
→ runtime acceptance evidence
```

A process running, an open PR, green CI, a merge, or a deployment start is not sufficient by itself.

## Terminal response gate

After repository-write approval, a final response is permitted only in `COMPLETE`, `BLOCKED`, or `FAILED`. Waiting for CI, mergeability, deployment or publication is not itself a blocker.