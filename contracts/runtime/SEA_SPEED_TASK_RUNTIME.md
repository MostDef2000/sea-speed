# Sea Speed Task Runtime

Version: 1.11.0
Status: Active

## Active phases

```text
DISCUSSION
READY_FOR_IMPLEMENTATION
IMPLEMENTING
SOURCE_INTEGRATED
ACTIONS_REQUIRED
ACTIONS_RUNNING
ACTIONS_COMPLETED
RUNTIME_ACCEPTANCE
```

These are internal lifecycle phases, not permission to return control. Historical evidence may contain older lifecycle names; new tasks retain one Delivery Orchestrator context.

## Terminal interaction states

The only valid terminal interaction states are:

```text
DONE
BLOCKED
HUMAN DECISION REQUIRED
```

- `DONE`: the approved Outcome is complete and every mandatory source, quality, runtime and acceptance evidence item applicable to it is satisfied.
- `BLOCKED`: continuation is objectively impossible because of a concrete external blocker outside authorized deterministic control. The response records blocker evidence, the unblock condition and the next admissible action. A remediable source/test/CI/PR-metadata defect or queued/running CI is not `BLOCKED`.
- `HUMAN DECISION REQUIRED`: continuation requires a genuine human decision, authorization or protected input, configured environment review, or irreversible/high-risk choice. The response records the exact decision, bounded options/consequences where relevant, and exact reply/action format. After the decision, execution resumes automatically.

`FAILED` is an internal event, not a terminal interaction state. Remediate it automatically where possible; otherwise classify the actual external/human boundary. Progress such as PR created, CI is running, merge ready or deployment prepared is never terminal while a safe authorized next action exists.

## Phase semantics

- `DISCUSSION`: read-only discovery, Task Brief, Outcome Contract and visible Scope presentation.
- `READY_FOR_IMPLEMENTATION`: complete Scope immediately preceded exact `OUTCOME APPROVED`, admission is OPEN and capability preflight passed.
- `IMPLEMENTING`: bounded source/SDD work and in-scope CI remediation.
- `SOURCE_INTEGRATED`: exact approved source verified on `main`; not runtime evidence.
- `ACTIONS_REQUIRED`: one protected fallback action is genuinely required because an active contour capability is `ONE_COMMAND_FALLBACK`.
- `ACTIONS_RUNNING` / `ACTIONS_COMPLETED`: runtime operation phases, not product acceptance.
- `RUNTIME_ACCEPTANCE`: provenance, health, freshness/telemetry and product evidence are being verified for applicable active contours.

## Canonical owner and authorization gate

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

The Scope must be the last substantive assistant block and `OUTCOME APPROVED` must be the immediately following user decision. Source admission is fail closed:

```text
VISIBLE_SCOPE_PRESENTED=YES|NO
SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES|NO
SOURCE_AUTHORIZATION_ADMISSION=OPEN|BLOCKED
```

Any missing/stale/ambiguous/non-adjacent scope leaves the task in `DISCUSSION` and prohibits branch/source writes until a fresh correct sequence occurs.

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
- Production safety envelope: NOT REQUIRED/PENDING/APPROVED/STALE
- Production execution intent: NOT REQUIRED/PENDING/AUTHORIZE_ONLY/EXECUTE
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

`FAILED` values in sub-operation fields are observations and not terminal interaction states.

## Runtime contour rule

The active production contours are **VPS** and **Ubuntu Worker/relay**. `MIXED` means both. Every non-empty active runtime set requires a production safety envelope; CONTROL_PLANE/NONE require both active deployment fields and the envelope to be `NOT REQUIRED`.

Shared executable `worker/**` maps to Ubuntu Worker/relay unless a more-specific archival rule applies. Windows `.cmd`/`.ps1`/`worker/windows/**` tooling is retired non-production archive/control-plane material. New status blocks, Change Contracts, production fingerprints and execution routing contain no Windows runtime field.

Historical Windows manifests/fingerprints remain readable audit evidence and do not create an active contour.

For every required active contour the Change Contract declares `CONNECTOR` or `ONE_COMMAND_FALLBACK`; `MISSING` blocks normal releasable admission. Non-applicable active contours declare `NOT APPLICABLE`. `Operator actions expected` equals the number of required one-command fallback contours.

## Continuation rule

After valid `OUTCOME APPROVED`, continue automatically through implementation, integrity checks, PR, metadata repair, CI, in-scope remediation and exact-green-head merge. A material outcome/scope/protected-boundary change requires fresh source authorization; ordinary in-scope defects do not.

Production remains separate. The preferred exact runtime decision is:

```text
PRODUCTION APPROVED <sha>
Authorization-Fingerprint: <fingerprint>
Execution-Intent: EXECUTE
```

A two-line approval means AUTHORIZE_ONLY. The runtime router may then execute VPS and/or Ubuntu only. A required `ONE_COMMAND_FALLBACK` exposes one largest-safe action after machine-observable gates.

## Interaction budget

```text
visible Scope presentation: mandatory immediately preceding assistant turn
OUTCOME APPROVED: one user decision
exact release production authorization + execution intent: one user decision when runtime applies
manual runtime command: zero target; at most one per required active fallback contour
intermediate deterministic confirmations: zero
```

Additional interaction is reserved for material reauthorization, new exact SHA, protected credential entry, irreversible/high-risk decision, configured environment reviewer or evidence not safely automatable.

## Integrity / merge rule

After writes validate complete files, syntax/structure, exact diff/scope, freshness and secret/runtime-artifact absence. Before merge re-read `main`, verify exact head/scope, successful required checks and zero unresolved review threads, then use expected-head protection when supported.

## Delivery quality rule

Linked significant work keeps NFR assessment, risk/test design, correct-course check, acceptance traceability and Definition of Done aligned with the implementation. Quality `FAIL` cannot advance. `WAIVED` requires a complete durable record and does not alter hard gates.

When production learning, architecture pivot or material scope change changes accepted design, execute the correct-course check. Deployment/release changes use the full eight-stage Deployment Transaction Audit.

## Evidence hierarchy

```text
operator-visible scope
-> source authorization admission OPEN
-> approved outcome/scope
-> exact changed files
-> linked SDD and Change Contract
-> PR Validation + aggregate Quality
-> exact-green-head merge
-> release evidence when applicable
-> exact production authorization when applicable
-> deployment manifest for each active applicable contour
-> runtime identity/health/freshness
-> product evidence verdict
-> terminal interaction state
```

Governance/control-plane-only work resolves release/runtime acceptance as `NOT REQUIRED` after exact merge and post-merge quality, then may return `DONE` with durable Issue evidence.
