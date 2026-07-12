# Sea Speed Task Runtime

Version: 1.0.0
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

- `SOURCE_INTEGRATED` means source is verified on `main`; it does not mean VPS deployment or Windows worker update.
- `ACTIONS_REQUIRED` is manual fallback only.
- `RUNTIME_ACCEPTANCE` verifies the applicable VPS and/or worker contour.
- Terminal states are only `COMPLETE`, `BLOCKED`, and `FAILED`.

## Required status block

```text
Sea Speed Task Runtime
- Task:
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

## Integrity rule

After each write, fetch the complete file, verify its start and ending, validate syntax where applicable, compare the branch with `main`, and confirm the changed-file list remains in scope.

## Terminal response gate

After repository-write approval, a final response is permitted only in `COMPLETE`, `BLOCKED`, or `FAILED`. Waiting for CI, mergeability, deployment or publication is not itself a blocker.
