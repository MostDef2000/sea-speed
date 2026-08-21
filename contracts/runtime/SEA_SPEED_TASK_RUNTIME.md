# Sea Speed Task Runtime

Version: 1.14.0
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

## Session dispositions and terminal interaction states

Every synchronous invocation has one session disposition:

```text
ACTIVE
WAITING_EXTERNAL
TERMINAL
```

- `ACTIVE`: at least one safe authorized action is executable now, so execution continues in the current invocation.
- `WAITING_EXTERNAL`: no safe authorized action is executable now and continuation depends only on a named machine-observable external transition. This returns control without ending the task or promising background work.
- `TERMINAL`: exactly one terminal interaction state below is justified.

The only valid terminal interaction states are:

```text
DONE
BLOCKED
HUMAN DECISION REQUIRED
```

- `DONE`: approved Outcome complete with every mandatory source, quality, runtime and acceptance evidence item.
- `BLOCKED`: continuation objectively impossible because of a concrete external blocker; record blocker evidence, unblock condition and next admissible action.
- `HUMAN DECISION REQUIRED`: genuine human decision, source authorization, protected input, standing-delegation/settings administration, configured-environment review or irreversible/high-risk choice is required.

`WAITING_EXTERNAL` is not a lifecycle phase, terminal interaction state, blocker, or human decision. `FAILED` is not a terminal interaction state; it is an internal event. Progress is not terminal while a safe next action is executable now.

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
- **Delivery-control truth**: canonical Issue Outcome, source-authorization receipt, `Sea Speed Delivery Checkpoint v2`, branch/PR/head, completed gates and evidence cursors.
- **Transient interaction state**: live conversation used for new visible-Scope -> immediately-following `OUTCOME APPROVED` admission.

The initial adjacent Scope/approval creates source authority. A durable authorization receipt may continue only the **same exact admitted scope**. It cannot create, widen or replace source authority and never grants production authority.

## Sea Speed Delivery Checkpoint v2

Persist the compact machine-readable checkpoint in the canonical Issue after valid source admission and update it only at meaningful lifecycle/evidence transitions, not after every tool call. The JSON object conforms to `schemas/delivery-checkpoint-v2.schema.json`; cross-field invariants and v1 upgrade are implemented by `scripts/ci/validate_delivery_checkpoint.py`.

```json
{
  "schema": "sea_speed_delivery_checkpoint_v2",
  "task": "#<canonical-issue>",
  "generation": 1,
  "approved_scope_identity": "<stable-scope-hash-or-id>",
  "authorization_receipt": "OUTCOME APPROVED",
  "authorization_base_main": "<40-char-lowercase-sha>",
  "current_phase": "<active-phase>",
  "branch": null,
  "pr": null,
  "exact_working_head": null,
  "completed_gates": [],
  "evidence_cursors": {"issue": null, "pr": null, "ci": null, "policy": null, "runtime": null},
  "next_admissible_action": {"kind": "<kind>", "description": "<action>", "executable_now": true},
  "session_disposition": "ACTIVE",
  "external_wait": null,
  "state_invalidation_reason": null,
  "terminal_interaction_state": null
}
```

Checkpoint generation is monotonic. It does not increment for every read/tool call; it advances when phase, exact source identity, completed gate, evidence cursor, invalidation state, next action, session disposition, or wait predicate materially changes.

Persisted `Sea Speed Delivery Checkpoint v1` records remain readable continuation evidence for the same exact admitted scope. The repository validator parses and upgrades active v1 evidence to v2 at its next meaningful transition. Conversion does not recreate source authority and does not require another `OUTCOME APPROVED`.

## WAITING_EXTERNAL contract

`WAITING_EXTERNAL` is valid only when:

```text
safe authorized action executable now = NO
machine-observable external condition named = YES
exact evidence cursor recorded = YES
resume trigger recorded = YES
terminal interaction state = NONE
```

The `external_wait` object records `condition`, `resume_trigger`, and an `evidence_cursor` that identifies exactly one checkpoint evidence cursor. `next_admissible_action.executable_now` is `false` until that cursor changes. Waiting for authorization, protected input or settings administration is `HUMAN DECISION REQUIRED`; an objective external blocker is `BLOCKED`.

Sea Speed sessions are synchronous. After persisting `WAITING_EXTERNAL`, return control and perform no background polling. On a later invocation, observe the exact wait cursor once:

```text
cursor unchanged -> preserve WAITING_EXTERNAL and generation; do not replan or reread
cursor changed   -> increment generation; update cursor; produce valid ACTIVE state; execute next action
```

If another safe authorized action is executable now, `ACTIVE` takes precedence. A terminal condition cannot coexist with executable work.

## Resume Probe

For a known task with a valid checkpoint, recovery begins with the bounded Resume Probe:

```text
1. resolve current `main` identity;
2. read the canonical Issue checkpoint and authorization receipt;
3. read only exact referenced PR/head/status or other evidence whose cursor may have changed;
4. validate checkpoint against durable evidence;
5. execute `Next admissible action`.
```

For `WAITING_EXTERNAL`, step 3 is one exact cursor observation. An unchanged cursor ends the invocation in the same nonterminal disposition without full recovery or repeated planning.

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
- Session disposition: ACTIVE/WAITING_EXTERNAL/TERMINAL
- External wait condition: NONE/<machine-observable predicate>
- External wait resume trigger: NONE/<bounded trigger>
- External wait evidence cursor: NONE/<identity>
- Next admissible action:
- Next action executable now: YES/NO
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
- Terminal interaction state: NONE/DONE/BLOCKED/HUMAN DECISION REQUIRED
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

Automatic continuation means execute every safe action available now. It does not mean busy-wait, repeatedly poll unchanged evidence, or claim background execution. When the only prerequisite is a machine-observable external transition, persist `WAITING_EXTERNAL`; a later synchronous invocation resumes through the bounded wait replay rule.

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

<!-- Canonical: contracts/DELIVERY_CANONICAL.md -->
