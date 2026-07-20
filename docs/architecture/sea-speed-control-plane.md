# Sea Speed Control Plane

Version: 1.1.0
Status: Active

## Overview

Sea Speed uses a controlled delivery graph for a distributed camera-processing system:

```text
Camera/HLS
→ Windows AI worker
→ VPS FastAPI and storage
→ Operator frontend
```

GitHub `main` is the source of truth. VPS and Windows laptop are independent runtime contours.

## Control layers

1. GitHub Issues: canonical persistent backlog and task history.
2. Task Intake: read-only conversion of an unstructured request into a canonical Task Brief.
3. Governance: approval, scope, branch and invariant rules.
4. Task runtime: explicit phases and terminal-state semantics.
5. Project Manager: recovery, capability preflight, routing, lifecycle continuation and final evidence.
6. Domain agents: worker, API, frontend, deploy, diagnostics and governance.
7. Review gate: scope, safety, compatibility and rollback validation.
8. Core Release: PR, CI, merge and applicable runtime release verification.

## Canonical Task Brief

Task Intake records:

- original request and canonical Issue;
- problem and expected behavior;
- scope and out of scope;
- responsible domain and likely files;
- acceptance criteria and required checks;
- security, schema and compatibility impact;
- VPS and Windows release applicability;
- rollout order and rollback requirements;
- risks, dependencies, evidence gaps and blocking questions.

Task Intake is read-only. It does not create branches, edit files, approve work, deploy runtime, or claim implementation completion.

## Normal task flow

```text
User request
→ issue and state recovery
→ read-only Task Intake
→ Task Brief
→ scope lock
→ Implementation Scope Check
→ COMMIT APPROVED
→ capability preflight
→ fresh task branch
→ domain implementation
→ post-write integrity gate
→ pull request validation
→ merge into main
→ VPS deployment and/or Windows worker update when applicable
→ runtime acceptance
→ COMPLETE
```

The existing task-runtime states remain unchanged. Intake occurs within `DISCUSSION`. `READY_FOR_IMPLEMENTATION` means the specification is clear, the Implementation Scope Check is complete, repository-write approval is valid, and the capability preflight permits the full approved implementation path.

## Capability preflight

Before the first repository write, verify that the complete approved file set can be read, changed, validated, committed, published, reviewed, and merged safely. Also verify every applicable release, runtime acceptance, and rollback path.

The preflight must identify:

- current `main` SHA and fresh branch strategy;
- canonical Issue and exact approved file set;
- available file-write, branch, PR, CI and merge capabilities;
- required VPS credentials and health evidence when VPS release applies;
- required Windows updater/runtime evidence when worker release applies;
- rollback target and user-only actions;
- any unavailable capability that would make a complete implementation unsafe.

Do not begin a partial multi-file implementation when the full mandatory set cannot be delivered safely. Return `BLOCKED` before writes when a required capability is unavailable and no safe fallback exists.

## User boundary

The user normally provides the task, grants repository-write approval after the Implementation Scope Check, grants skill-update approval when `skills/**` changes, supplies secrets only through approved secure channels when unavoidable, and performs physical/browser checks that cannot be automated.

The user should not normally transfer handoffs, merge PRs, infer release applicability or manually run delivery steps when the connected tools can continue safely.

## Release contours

### VPS

Applies to API, frontend and affected deployment infrastructure. Completion requires exact deployed commit evidence, process and health evidence, frontend smoke checks when applicable, storage compatibility and rollback readiness.

### Windows worker

Applies to worker source and affected updater infrastructure. Completion requires version/commit evidence, preservation of local runtime assets, successful restart, fresh VPS state and affected overlay/event evidence.

### Mixed API and worker

Mixed work requires an explicit compatibility matrix and rollout order. The normal compatible sequence is VPS/API first, API verification second, worker update third, and worker/runtime verification last. Any different order must be justified by the approved schema or migration design.

### Governance only

Contracts, docs, skills and README changes require validation and merge but no runtime release.

## Compatibility boundary

API, event, worker-state or storage schema changes require explicit approval, version/migration handling, rollout order and compatibility notes for old worker/new API and new worker/old API combinations.

## Evidence principle

A commit is not a PR. A PR is not a merge. A merge is not deployment. Deployment is not runtime acceptance.

COMPLETE requires:

1. the approved source is verified on `main`;
2. PR validation and required review gates passed;
3. each applicable runtime contour received the approved commit/version;
4. required health, freshness, behavior and rollback evidence was observed;
5. the canonical Issue and final status identify the PR, merge and release evidence.
