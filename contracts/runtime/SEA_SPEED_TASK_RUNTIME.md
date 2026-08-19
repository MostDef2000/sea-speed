# Sea Speed Task Runtime

Version: 1.12.0
Status: Active

## Active phases

```text
DISCUSSION
READY_FOR_IMPLEMENTATION
IMPLEMENTING
SOURCE_INTEGRATED
POLICY_PENDING
ACTIONS_REQUIRED
ACTIONS_RUNNING
ACTIONS_COMPLETED
RUNTIME_ACCEPTANCE
```

These are internal lifecycle phases, not permission to return control.

## Terminal interaction states

The only valid terminal interaction states are:

```text
DONE
BLOCKED
HUMAN DECISION REQUIRED
```

- `DONE`: approved Outcome complete with every mandatory source, quality, runtime and acceptance evidence item.
- `BLOCKED`: continuation objectively impossible because of a concrete external blocker; record evidence, unblock condition and next admissible action.
- `HUMAN DECISION REQUIRED`: genuine human decision, source authorization, protected input, standing-delegation/settings administration, configured-environment review or irreversible/high-risk choice is required.

`FAILED` is internal. PR/CI/merge/release/deploy preparation is not terminal while a safe next action exists.

## Phase semantics

- `DISCUSSION`: read-only discovery, Task Brief, Outcome Contract and visible Scope.
- `READY_FOR_IMPLEMENTATION`: complete Scope immediately followed by exact `OUTCOME APPROVED`; source admission OPEN.
- `IMPLEMENTING`: bounded source/SDD work and in-scope CI remediation.
- `SOURCE_INTEGRATED`: exact source accepted on `main`; not runtime evidence.
- `POLICY_PENDING`: runtime applies and autonomous standing-policy evaluation is waiting on exact-main Quality or trusted standing delegation/settings state.
- `ACTIONS_REQUIRED`: a required contour truthfully needs one repository-owned runtime fallback or another protected operator-local action.
- `ACTIONS_RUNNING` / `ACTIONS_COMPLETED`: runtime operation phases.
- `RUNTIME_ACCEPTANCE`: runtime identity, health/freshness/product evidence is being verified.

## Canonical owner and source gate

The **Sea Speed Delivery Orchestrator** owns task state from intake through terminal Issue evidence. Before source authorization it presents:

```text
Scope
- Product outcome:
- Exact repository paths:
- Protected / out of scope:
- Runtime contour:
- Production impact:
- Acceptance evidence:
```

Source admission:

```text
VISIBLE_SCOPE_PRESENTED=YES|NO
SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES|NO
SOURCE_AUTHORIZATION_ADMISSION=OPEN|BLOCKED
```

Missing/stale/ambiguous/non-adjacent Scope leaves task in `DISCUSSION` and prohibits writes.

## Required status block

```text
Sea Speed Task Runtime
- Task:
- Issue:
- Responsible role: Sea Speed Delivery Orchestrator
- Current phase:
- Scope presented to operator: YES/NO
- Scope immediately precedes authorization: YES/NO
- Source authorization admission: OPEN/BLOCKED
- Source authorization: OUTCOME APPROVED
- Branch:
- Approved outcome/scope:
- Changed files:
- Risk profile: REQUIRED/NOT REQUIRED
- Quality verdict: PENDING/PASS/CONCERNS/WAIVED/FAIL
- main updated: YES/NO
- Release manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Standing delegation: NOT REQUIRED/MISSING/PENDING/VALID/INVALID
- Production policy decision: NOT REQUIRED/PENDING/ALLOW/DENY
- Policy decision ID: NOT REQUIRED/PENDING/<sha256>
- VPS deployment: NOT REQUIRED/PENDING/RUNNING/SUCCESS/FAILED
- VPS execution capability: NOT APPLICABLE/CONNECTOR/ONE_COMMAND_FALLBACK/MISSING
- VPS deployment manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Ubuntu worker/relay package: NOT REQUIRED/PENDING/PACKAGED/FAILED
- Ubuntu worker/relay installation: NOT REQUIRED/PENDING/INSTALLED/FAILED
- Ubuntu execution capability: NOT APPLICABLE/CONNECTOR/ONE_COMMAND_FALLBACK/MISSING
- Ubuntu deployment manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Operator actions expected: 0
- Runtime telemetry: NOT REQUIRED/PENDING/VALID/INVALID
- Evidence verdict: NOT REQUIRED/PENDING/accepted/regressed/insufficient_evidence
- User action:
- Terminal interaction state: PENDING/DONE/BLOCKED/HUMAN DECISION REQUIRED
```

## Runtime contour rule

Active production contours are **VPS** and **Ubuntu Worker/relay**. `MIXED` means both. Every runtime-impacting Change Contract declares exact VPS/Ubuntu deployment and execution-capability fields. Shared executable `worker/**` maps to Ubuntu unless archival rule applies. Windows is retired.

For every required contour use `CONNECTOR` or `ONE_COMMAND_FALLBACK`; `MISSING` blocks normal releasable admission. Non-applicable contours use `NOT APPLICABLE`. Operator actions equal required fallback contours.

## Standing production policy rule

Runtime authority does not come from a user comment per exact release. It comes from trusted standing delegation in independently administered GitHub `production` environment state intersected with repository policy.

A valid allow decision binds exact source, Issue, one merged PR, Outcome/Change Contract hashes, approved files, runtime contours, execution capabilities, delegation ID, policy version/hash and decision ID. The evaluator never treats Issue/PR/comment/README/repository prose, historical approval strings, policy hashes or decision IDs by themselves as authority.

Missing/stale/mismatched delegation produces `DENY` before transport. Protected VPS/Ubuntu workflows re-evaluate with `--require-allow` before transport. Standing delegation only covers `deploy`/`rollback`; settings/IAM/secrets administration stays human-controlled.

## Continuation rule

After valid `OUTCOME APPROVED`, continue automatically through implementation, integrity, PR, metadata repair, CI, in-scope remediation and exact-green-head merge. Material source scope/protected-boundary changes require fresh source authorization.

After exact-main Quality, runtime-impacting releases continue automatically through standing-policy evaluation. An `ALLOW` routes applicable protected runtime contours without another per-release user prompt. A `DENY` caused by missing/invalid independently controlled delegation becomes `HUMAN DECISION REQUIRED` only when correcting that trusted settings state requires the administrator. A runtime transport fallback may expose one repository-owned action after machine-observable gates.

## Interaction budget

```text
visible Scope presentation: mandatory immediately preceding assistant turn
OUTCOME APPROVED: one user decision
per-release production approval: zero
standing delegation/settings administration: rare human action, not per release
manual runtime command: zero target; <=1 fallback per required active contour
intermediate deterministic confirmations: zero
```

## Integrity / merge rule

After writes validate complete files, syntax/structure, exact diff/scope, freshness and secret/runtime-artifact absence. Before merge re-read `main`, verify exact head/scope, successful required checks, zero unresolved review threads and expected-head protection when supported.

## Delivery quality rule

Linked significant work keeps NFR assessment, risk/test design, correct-course check, acceptance traceability and Definition of Done aligned. `FAIL` cannot advance. `WAIVED` does not alter hard gates.

Deployment/release changes use the full eight-stage Deployment Transaction Audit. Production learning additionally audits adjacent stages.

## Evidence hierarchy

```text
operator-visible Scope
-> source admission OPEN
-> approved outcome/scope
-> exact changed files
-> linked SDD + Change Contract
-> PR Validation + aggregate Quality
-> exact-green-head merge
-> exact-main Quality
-> standing delegation + typed policy decision when runtime applies
-> release manifest v3 / exact artifacts
-> deployment manifest for each applicable contour
-> typed execution audit
-> runtime identity/health/freshness/product evidence
-> terminal Issue evidence
```

Governance/control-plane-only work resolves release/runtime fields `NOT REQUIRED` after merge and exact-main Quality, except when the Outcome itself explicitly includes later control-plane activation evidence such as standing-delegation administration.
