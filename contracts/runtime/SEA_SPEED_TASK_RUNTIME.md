# Sea Speed Task Runtime

Version: 1.8.0
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

- `DISCUSSION`: read-only Task Intake, repository discovery, Task Brief, Outcome Contract preparation and operator-visible Scope presentation.
- `READY_FOR_IMPLEMENTATION`: the visible Scope block has been presented, scope locked, `OUTCOME APPROVED` valid and capability preflight passed.
- `IMPLEMENTING`: bounded source/SDD work and in-scope CI remediation.
- `SOURCE_INTEGRATED`: exact approved source verified on `main`; not production evidence.
- `ACTIONS_REQUIRED`: one explicit protected fallback action is genuinely required because a declared contour capability is `ONE_COMMAND_FALLBACK`; do not use this state for deterministic internal preparation/activation checkpoints.
- `ACTIONS_RUNNING` / `ACTIONS_COMPLETED`: runtime operation state; not acceptance by itself.
- `RUNTIME_ACCEPTANCE`: provenance, health, freshness/telemetry and product evidence are being verified for applicable contours.
- terminal states: `COMPLETE`, `BLOCKED`, `FAILED` only.

## Canonical owner

The **Sea Speed Delivery Orchestrator** owns the task state from intake through terminal evidence. Domain/release files are on-demand review lenses; invoking them does not transfer lifecycle ownership.

## Outcome Contract and visible Scope gate

The durable Outcome Contract is:

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

Before requesting source authorization, the Orchestrator MUST present this minimum operator-visible block in the conversation:

```text
Scope
- Product outcome:
- Exact repository paths:
- Protected / out of scope:
- Runtime contour:
- Production impact:
- Acceptance evidence:
```

`DISCUSSION` cannot transition to source authorization until that visible scope has been shown. A standalone request to send `OUTCOME APPROVED` without the displayed scope is invalid. The operator is never expected to infer exact paths from internal reasoning. If a material change later makes the authorization stale, the revised Scope block must be shown before requesting a fresh approval.

New repository work requires `OUTCOME APPROVED` after the visible Implementation Scope Check. Historical legacy approvals remain audit history only.

## Required status block

```text
Sea Speed Task Runtime
- Task:
- Issue:
- Responsible role: Sea Speed Delivery Orchestrator
- Current phase:
- Scope presented to operator: YES/NO
- Source authorization: OUTCOME APPROVED
- Branch:
- Approved outcome/scope:
- Changed files:
- Risk profile: REQUIRED/NOT REQUIRED
- Quality verdict: PENDING/PASS/CONCERNS/WAIVED/FAIL
- main updated: YES/NO
- Release manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Production safety envelope: NOT REQUIRED/PENDING/APPROVED/STALE
- Production execution intent: NOT REQUIRED/PENDING/AUTHORIZE_ONLY/EXECUTE
- VPS deployment: NOT REQUIRED/PENDING/RUNNING/SUCCESS/FAILED
- VPS execution capability: NOT APPLICABLE/CONNECTOR/ONE_COMMAND_FALLBACK/MISSING
- VPS deployment manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Ubuntu worker/relay package: NOT REQUIRED/PENDING/PACKAGED/FAILED
- Ubuntu worker/relay installation: NOT REQUIRED/PENDING/INSTALLED/FAILED
- Ubuntu execution capability: NOT APPLICABLE/CONNECTOR/ONE_COMMAND_FALLBACK/MISSING
- Ubuntu deployment manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Windows AI worker package: NOT REQUIRED/PENDING/PACKAGED/FAILED
- Windows AI worker installation: NOT REQUIRED/PENDING/INSTALLED/FAILED
- Windows execution capability: NOT APPLICABLE/CONNECTOR/ONE_COMMAND_FALLBACK/MISSING
- Windows deployment manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Operator actions expected: 0
- Runtime telemetry: NOT REQUIRED/PENDING/VALID/INVALID
- Evidence verdict: NOT REQUIRED/PENDING/accepted/regressed/insufficient_evidence
- User action:
- Final state: PENDING/COMPLETE/BLOCKED/FAILED
```

`Scope presented to operator: YES` is a hard prerequisite for `Source authorization: OUTCOME APPROVED` on new work or any fresh re-authorization event.

## Runtime contour rule

Explicit contours are VPS, Ubuntu Worker/relay, Windows AI Worker. `MIXED` never replaces exact per-contour fields. Every non-empty runtime set requires a production safety envelope; CONTROL_PLANE/NONE require all runtime fields and envelope to be `NOT REQUIRED`.

For every required contour the Change Contract declares `CONNECTOR` or `ONE_COMMAND_FALLBACK`; `MISSING` blocks source admission for a normal releasable path. Non-applicable contours declare `NOT APPLICABLE`. `Operator actions expected` equals the number of required one-command fallback contours.

## Continuation rule

After `OUTCOME APPROVED`, continue automatically through deterministic safe repository transitions: implementation, integrity checks, PR, metadata repair, CI, in-scope CI remediation and exact-green-head merge. New source authorization is required only when outcome/scope/protected boundaries materially change. A newly discovered bug inside the approved path set is not a reason to ask for `OUTCOME APPROVED` again.

When new source authorization really is required, return to `DISCUSSION`, present the updated visible Scope block, and only then request the fresh approval.

Production remains separate. The normal production decision may combine durable authorization and explicit execution intent in one exact three-line Issue record:

```text
PRODUCTION APPROVED <sha>
Authorization-Fingerprint: <fingerprint>
Execution-Intent: EXECUTE
```

A two-line approval means `AUTHORIZE_ONLY`. A three-line approval may move directly from release readiness into `ACTIONS_RUNNING` through repository-owned routing; do not insert a second execution-confirmation prompt. When a contour is `ONE_COMMAND_FALLBACK`, expose one largest-safe command/action only after all machine-observable gates have completed.

## Interaction budget

Normal successful task:

```text
visible Scope presentation: mandatory prerequisite, not a separate approval decision
OUTCOME APPROVED: one user decision after scope presentation
exact release production authorization + execution intent: one user decision
manual runtime command: zero target; at most one per required fallback contour
prepare/activate/verify intermediate confirmations: zero
```

Additional interaction is reserved for material reauthorization, new exact SHA, protected credential entry, irreversible/high-risk decisions, configured environment reviewers or evidence not safely automatable.

## Integrity / merge rule

After writes validate complete files, syntax/structure, exact diff, scope, branch freshness and secret/runtime-artifact absence. Before merge re-read `main`, verify exact head/scope, successful required checks and zero unresolved review threads, then merge with expected-head protection when supported.

## Delivery quality rule

For linked significant work, `IMPLEMENTING` includes keeping NFR assessment, risk/test design, correct-course check, acceptance traceability and Definition of Done aligned with the exact implementation. The Change Contract's `Risk profile` declaration must match the derived high-risk triggers.

A quality verdict of `FAIL` cannot advance to source integration. `WAIVED` requires the complete waiver record defined by the delivery policy and does not alter any hard gate. `CONCERNS` remains visible as delivery evidence and may advance only while mandatory authorization, scope, CI and runtime gates are independently satisfied.

When production learning, an architecture pivot or a material scope change changes the accepted design, execute the correct-course check before continuing. If it changes the Outcome Contract, protected boundary or approved repository scope, return to `DISCUSSION`, show the revised Scope block, and then follow the normal reauthorization boundary. Otherwise continue automatically after in-scope remediation and exact-green-head merge; do not create a synthetic approval checkpoint.

## Evidence hierarchy

```text
operator-visible scope presentation
-> approved outcome/scope
-> exact changed files
-> linked SDD quality layer and Change Contract quality verdict
-> PR Validation + aggregate SDD gate
-> exact-green-head merge on main
-> release manifest v2/exact artifacts when applicable
-> durable exact-main production authorization
-> explicit execution intent when runtime mutation is requested
-> deployment manifest for every applicable contour
-> runtime source identity/health
-> freshness/telemetry where applicable
-> product evidence verdict
```

Governance/control-plane-only work may mark runtime acceptance `NOT REQUIRED` after exact merge and post-merge quality verification.
