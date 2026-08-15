# Sea Speed Task Runtime

Version: 1.4.0
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

- `DISCUSSION` includes read-only Task Intake, repository discovery, Task Brief and Outcome Contract preparation.
- `READY_FOR_IMPLEMENTATION` requires a canonical Task Brief, Outcome Contract / Implementation Scope Check and valid source authorization.
- `SOURCE_INTEGRATED` means source is verified on `main`; it does not mean production deployment or worker update.
- `ACTIONS_REQUIRED` is manual fallback only.
- `ACTIONS_COMPLETED` may mean a package or deployment action completed; it is not runtime acceptance by itself.
- `RUNTIME_ACCEPTANCE` verifies provenance, health, freshness, telemetry and product evidence for applicable runtime contours.
- Terminal states are only `COMPLETE`, `BLOCKED`, and `FAILED`.

## Canonical Task Brief and Outcome Contract

Implementation tasks should be represented in the linked GitHub Issue with the existing Task Brief plus:

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

The Project Manager validates both against current repository state before requesting source authorization.

## Source authorization

Preferred authorization is `OUTCOME APPROVED` after the Outcome Contract / Implementation Scope Check. It covers the bounded reversible repository lifecycle through exact-green-head merge when the outcome, exact approved scope, runtime contour and protected boundaries remain unchanged.

Legacy `COMMIT APPROVED` remains accepted during transition but does not remove the legacy separate merge-approval requirement.

## Required status block

```text
Sea Speed Task Runtime
- Task:
- Issue:
- Responsible agent:
- Current phase:
- Source authorization: OUTCOME APPROVED/LEGACY COMMIT APPROVED/OTHER
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

## Production contour rule

The explicit production runtime contours are VPS, Ubuntu Worker/relay, and Windows AI Worker. A task may affect exactly one contour or a mixed set. The summary class `MIXED` never replaces the exact per-contour deployment fields. Ubuntu-only production-impact source is not CONTROL_PLANE simply because it resides under `deploy/**`; shared Worker source may legitimately require both Ubuntu and Windows contours.

Every non-empty runtime contour set requires `Production safety envelope: REQUIRED`. CONTROL_PLANE and NONE require all three deployment fields and the production safety envelope to be `NOT REQUIRED`.

## Continuation rule

After `OUTCOME APPROVED`, continue automatically through every deterministic safe repository transition: implementation, integrity checks, PR, metadata repair, CI, in-scope CI remediation and exact-green-head merge. Do not wait for another user message between these transitions.

New source authorization is required only when the product outcome materially changes or a protected boundary is crossed: scope expansion, destructive action, secrets/security-boundary change, protected behavior change, schema incompatibility, data migration, behavior redesign, or equivalent material change.

Ordinary in-scope bug fixes, test changes and CI remediation do not require fresh authorization.

Production mutation is never implied by source authorization. When production applies, continue only after the separate production safety envelope is available and release readiness binds it to the final exact green SHA.

## Production authorization identity

Production authorization is durable Issue evidence bound to the canonical Issue, applicable merged PR, exact source SHA, Outcome Contract, exact runtime contour set, security impact, deployment target and rollback target. The authorized actor set is source controlled. Material change to a bound field makes prior authorization stale; GitHub API failure, ambiguity or missing linkage fails closed.

## Capability rule

Before first write, verify that the full approved file set and required lifecycle are executable. Do not create a partial implementation when mandatory files, PR operations, CI evidence, merge, release, deployment, verification or rollback paths are unavailable.

## Remote worker execution boundary

The canonical worker SSH transport and local sudo boundary remain unchanged. SSH reachability is transport only and does not authorize source publication or production mutation.

## Integrity rule

After writes, fetch complete files, validate syntax/structure, compare the branch with `main`, verify exact changed-file scope and check for secrets/runtime artifacts. In-scope repairs remain covered by active Outcome Authorization.

## Merge rule

Before merge verify fresh base/head, exact scope, successful required CI and zero unresolved review threads. If source authorization is `OUTCOME APPROVED` and remains valid, merge may proceed automatically with expected-head protection when supported. Legacy `COMMIT APPROVED` tasks still require post-CI `MERGE APPROVED`.

## Evidence hierarchy

Completion evidence remains:

```text
approved outcome/scope
→ exact changed files
→ PR validation and aggregate SDD gate
→ authorized merge commit on main
→ release manifest v2 and exact artifact identity when runtime delivery applies
→ durable production authorization bound to exact main SHA
→ deployment manifest for each applicable contour
→ runtime source identity and health
→ freshness/telemetry where applicable
→ post-release evidence verdict
```

A running process, open PR, green CI, merge, uploaded package or deployment start is not sufficient by itself.

## Runtime acceptance

Worker/API runtime acceptance requirements remain unchanged for their applicable contours. Governance/control-plane-only work may classify runtime acceptance as `NOT REQUIRED` after successful aggregate CI and authorized merge.

## Feedback decision

Use `docs/evidence/POST_RELEASE_REVIEW.md`. A regression creates a linked Issue and requires a rollback decision unless an active production safety envelope already covers the exact declared safe rollback condition.

## Terminal response gate

After source authorization, a final response is permitted only in `COMPLETE`, `BLOCKED`, or `FAILED`. Waiting for CI is not itself a blocker. Waiting for a legacy merge approval or a required production/user privilege boundary is a valid `BLOCKED` state when no further authorized transition is possible.
