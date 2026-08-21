# Sea Speed Task Runtime

Version: 1.13.0
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
- `BLOCKED`: continuation objectively impossible because of a concrete external blocker; record blocker evidence, unblock condition and next admissible action.
- `HUMAN DECISION REQUIRED`: genuine human decision, source authorization, protected input, standing-delegation/settings administration, configured-environment review or irreversible/high-risk choice is required.

`FAILED` is not a terminal interaction state; it is an internal event. PR creation, CI running, merge/release/deploy preparation, or checkpoint update is not terminal while a safe next action exists.

## Phase semantics

- `DISCUSSION`: read-only discovery, Task Brief, Outcome Contract and visible Scope for a new/materially invalidated task.
- `READY_FOR_IMPLEMENTATION`: complete Scope immediately followed by exact `OUTCOME APPROVED`; source admission OPEN and durable receipt/checkpoint recorded.
- `IMPLEMENTING`: bounded source/SDD work and in-scope CI remediation.
- `SOURCE_INTEGRATED`: exact source accepted on `main`; not runtime evidence.
- `POLICY_PENDING`: runtime applies and autonomous standing-policy evaluation is waiting on exact-main Quality or trusted standing delegation/settings state.
- `ACTIONS_REQUIRED`: a required contour truthfully needs one repository-owned runtime fallback or another protected operator-local action.
- `ACTIONS_RUNNING` / `ACTIONS_COMPLETED`: runtime operation phases.
- `RUNTIME_ACCEPTANCE`: runtime identity, health/freshness/product evidence is being verified.

## Truth classes

- **Repository/product truth**: current `main`, committed contracts/specs/source and accepted runtime evidence.
- **Delivery-control truth**: canonical Issue Outcome, source-authorization receipt, `Sea Speed Delivery Checkpoint v1`, branch/PR/head, completed gates and evidence cursors.
- **Transient interaction state**: live conversation used for new visible-Scope -> immediately-following `OUTCOME APPROVED` admission.

The initial adjacent Scope/approval creates source authority. A durable authorization receipt may continue only the **same exact admitted scope**. It cannot create, widen or replace source authority and never grants production authority.

## Sea Speed Delivery Checkpoint v1

Persist the compact checkpoint in the canonical Issue after valid source admission and update it only at meaningful lifecycle/evidence transitions, not after every tool call.

```text
Sea Speed Delivery Checkpoint v1
- Task: #<canonical-issue>
- Checkpoint generation: <monotonic integer>
- Approved scope identity: <stable scope hash/id>
- Authorization receipt: OUTCOME APPROVED
- Authorization base main: <40-char-sha>
- Current phase: <active phase>
- Branch: <branch/PENDING/NOT APPLICABLE>
- PR: <#N/PENDING/NOT APPLICABLE>
- Exact working head: <40-char-sha/PENDING/NOT APPLICABLE>
- Completed gates: <ordered compact set>
- Evidence cursor / Issue: <issue identity/update identity>
- Evidence cursor / PR: <pr/head/update identity/NONE>
- Evidence cursor / CI: <head/status/run identity/NONE>
- Evidence cursor / Policy: <decision identity/NONE>
- Evidence cursor / Runtime: <deployment/evidence identity/NONE>
- Next admissible action: <single bounded action>
- State invalidation reason: NONE/<explicit reason>
- Terminal interaction state: PENDING/DONE/BLOCKED/HUMAN DECISION REQUIRED
```

Checkpoint generation is monotonic. It does not increment for every read/tool call; it advances when phase, exact source identity, completed gate, evidence cursor, invalidation state, or next admissible action materially changes.

## Resume Probe

For a known task with a valid checkpoint, recovery begins with the bounded Resume Probe:

```text
1. resolve current `main` identity;
2. read the canonical Issue checkpoint and authorization receipt;
3. read only exact referenced PR/head/status or other evidence whose cursor may have changed;
4. validate checkpoint against durable evidence;
5. execute `Next admissible action`.
```

Do not repeat Task Intake, broad Issue/PR searches, full project recovery, or source authorization merely because of context compaction, session restart, response truncation, Connector truncation, or model-memory loss.

Full project recovery is allowed only when no valid checkpoint exists, task identity cannot be resolved, checkpoint validation fails, or durable evidence materially contradicts the checkpoint.

## Monotonic transition rule

Lifecycle state is monotonic under normal continuation. Context loss is not state loss.

Backward transition or fresh source authorization requires a recorded material invalidation reason from this bounded set:

```text
MATERIAL_SCOPE_CHANGE
PROTECTED_BOUNDARY_CHANGE
USER_CHANGED_OUTCOME
MATERIAL_MAIN_DIVERGENCE
EVIDENCE_CONTRADICTION
```

`CONTEXT_LOSS` is intentionally not a valid reason. Context compaction, session restart and Connector truncation do not return an admitted task to `DISCUSSION` and do not require another `OUTCOME APPROVED`.

When invalidation occurs, record the evidence and exact invalidated boundary. Preserve all still-valid earlier evidence rather than restarting unrelated discovery.

## Connector retrieval rule

After task resolution use progressive, cursor-bound retrieval:

```text
known object -> metadata -> targeted detail -> failure fragment
```

Every read must advance the task, validate a mandatory gate, or resolve an explicit evidence gap. An equivalent re-read of the same object for the same question with the same evidence identity is forbidden. Canonical gates that explicitly require a fresh read (for example exact pre-merge base/head verification) are allowed and must record why freshness is required.

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

Missing/stale/ambiguous/non-adjacent Scope leaves a **new or freshly invalidated** task in `DISCUSSION` and prohibits new writes. It does not retroactively invalidate a valid same-scope durable receipt after context loss.

## Required status block

```text
Sea Speed Task Runtime
- Task:
- Issue:
- Responsible role: Sea Speed Delivery Orchestrator
- Current phase:
- Checkpoint generation:
- Approved scope identity:
- Scope presented to operator: YES/NO
- Scope immediately precedes authorization: YES/NO
- Source authorization admission: OPEN/BLOCKED
- Source authorization: OUTCOME APPROVED
- Authorization base main:
- Branch:
- PR:
- Exact working head:
- Completed gates:
- Evidence cursor / Issue:
- Evidence cursor / PR:
- Evidence cursor / CI:
- Next admissible action:
- State invalidation reason: NONE/<reason>
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
OUTCOME APPROVED: one user decision per admitted scope
per-release production approval: zero
standing delegation/settings administration: rare human action, not per release
manual runtime command: zero target; <=1 fallback per required active contour
intermediate deterministic confirmations: zero
```

## Integrity / merge rule

After writes validate complete files, syntax/structure, exact diff/scope, freshness and secret/runtime-artifact absence. Before merge re-read `main`, verify exact head/scope, successful required checks, zero unresolved review threads and expected-head protection when supported. This required fresh read is a canonical gate and does not violate the equivalent-read guard.

## Delivery quality rule

Linked significant work keeps NFR assessment, risk/test design, correct-course check, acceptance traceability and Definition of Done aligned. `FAIL` cannot advance. `WAIVED` does not alter hard gates.

Deployment/release changes use the full eight-stage Deployment Transaction Audit. Production learning additionally audits adjacent stages.

## Evidence hierarchy

```text
operator-visible Scope
-> source admission OPEN
-> durable authorization receipt + Delivery Checkpoint
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
