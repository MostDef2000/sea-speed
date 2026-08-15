# Sea Speed Task Runtime

Version: 1.5.0
Status: Active

## Active states

```text
DISCUSSION
READY_FOR_IMPLEMENTATION
IMPLEMENTING
SOURCE_INTEGRATED
ACTIONS_REQUIRED
ACTIONS_RUNNING
ACTIONS_COMPLETED
RUNTIME_ACCEPTANCE
COMPLETE
BLOCKED
FAILED
```

Historical evidence may contain `HANDOFF_VALIDATED` or `CORE_RELEASE_INTEGRATING`; new tasks do not emit those states because Delivery Orchestrator retains one task context instead of handing lifecycle ownership to another orchestrator.

## Semantics

- `DISCUSSION`: read-only Task Intake, repository discovery, Task Brief and Outcome Contract preparation.
- `READY_FOR_IMPLEMENTATION`: scope locked, `OUTCOME APPROVED` valid and capability preflight passed.
- `IMPLEMENTING`: bounded source/SDD work and in-scope CI remediation.
- `SOURCE_INTEGRATED`: exact approved source verified on `main`; not production evidence.
- `ACTIONS_REQUIRED`: explicit manual/fallback protected action is required.
- `ACTIONS_RUNNING` / `ACTIONS_COMPLETED`: runtime operation state; not acceptance by itself.
- `RUNTIME_ACCEPTANCE`: provenance, health, freshness/telemetry and product evidence are being verified for applicable contours.
- terminal states: `COMPLETE`, `BLOCKED`, `FAILED` only.

## Canonical owner

The **Sea Speed Delivery Orchestrator** owns the task state from intake through terminal evidence. Domain/release files are on-demand review lenses; invoking them does not transfer lifecycle ownership.

## Outcome Contract

```text
Outcome Contract
- Product outcome:
- Protected things that must not change:
- Main constraints:
- Approved repository scope:
- Runtime contour:
- Production involved: YES/NO
- Acceptance evidence:
```

New repository work requires `OUTCOME APPROVED` after the Implementation Scope Check. Historical legacy approvals remain audit history only.

## Required status block

```text
Sea Speed Task Runtime
- Task:
- Issue:
- Responsible role: Sea Speed Delivery Orchestrator
- Current phase:
- Source authorization: OUTCOME APPROVED
- Branch:
- Approved outcome/scope:
- Changed files:
- main updated: YES/NO
- Release manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Production safety envelope: NOT REQUIRED/PENDING/APPROVED/STALE
- VPS deployment: NOT REQUIRED/PENDING/RUNNING/SUCCESS/FAILED
- VPS deployment manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Ubuntu worker/relay package: NOT REQUIRED/PENDING/PACKAGED/FAILED
- Ubuntu worker/relay installation: NOT REQUIRED/PENDING/INSTALLED/FAILED
- Ubuntu deployment manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Windows AI worker package: NOT REQUIRED/PENDING/PACKAGED/FAILED
- Windows AI worker installation: NOT REQUIRED/PENDING/INSTALLED/FAILED
- Windows deployment manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Runtime telemetry: NOT REQUIRED/PENDING/VALID/INVALID
- Evidence verdict: NOT REQUIRED/PENDING/accepted/regressed/insufficient_evidence
- User action:
- Final state: PENDING/COMPLETE/BLOCKED/FAILED
```

## Runtime contour rule

Explicit contours are VPS, Ubuntu Worker/relay, Windows AI Worker. `MIXED` never replaces exact per-contour fields. Every non-empty runtime set requires a production safety envelope; CONTROL_PLANE/NONE require all runtime fields and envelope to be `NOT REQUIRED`.

## Continuation rule

After `OUTCOME APPROVED`, continue automatically through deterministic safe repository transitions: implementation, integrity checks, PR, metadata repair, CI, in-scope CI remediation and exact-green-head merge. New source authorization is required only when outcome/scope/protected boundaries materially change.

Production remains separate. Continue runtime mutation only after the exact production envelope and release-readiness evidence are current.

## Integrity / merge rule

After writes validate complete files, syntax/structure, exact diff, scope, branch freshness and secret/runtime-artifact absence. Before merge re-read `main`, verify exact head/scope, successful required checks and zero unresolved review threads, then merge with expected-head protection when supported.

## Evidence hierarchy

```text
approved outcome/scope
-> exact changed files
-> PR Validation + aggregate SDD gate
-> exact-green-head merge on main
-> release manifest v2/exact artifacts when applicable
-> durable exact-main production authorization
-> deployment manifest for every applicable contour
-> runtime source identity/health
-> freshness/telemetry where applicable
-> product evidence verdict
```

Governance/control-plane-only work may mark runtime acceptance `NOT REQUIRED` after exact merge and post-merge quality verification.
