# Sea Speed Control Plane

Version: 1.0.0
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

1. Governance: approval, scope, branch and invariant rules.
2. Task runtime: explicit phases and terminal-state semantics.
3. Project Manager: recovery, routing, lifecycle continuation and final evidence.
4. Domain agents: worker, API, frontend, deploy, diagnostics and governance.
5. Review gate: scope, safety, compatibility and rollback validation.
6. Core Release: PR, CI, merge and applicable runtime release verification.

## Normal task flow

```text
User task
→ state recovery
→ scope lock
→ COMMIT APPROVED
→ fresh task branch
→ domain implementation
→ post-write integrity gate
→ pull request validation
→ merge into main
→ VPS deployment and/or Windows worker update when applicable
→ runtime acceptance
→ COMPLETE
```

## User boundary

The user normally provides the task, grants repository-write approval, grants skill-update approval when `skills/**` changes, supplies secrets only through approved secure channels when unavoidable, and performs physical/browser checks that cannot be automated.

The user should not normally transfer handoffs, merge PRs, infer release applicability or manually run delivery steps when the connected tools can continue safely.

## Release contours

### VPS

Applies to API, frontend and affected deployment infrastructure. Completion requires exact deployed commit evidence, health checks and rollback readiness.

### Windows worker

Applies to worker source and affected updater infrastructure. Completion requires version/commit evidence, preservation of local runtime assets, successful restart and fresh VPS state.

### Governance only

Contracts, docs, skills and README changes require validation and merge but no runtime release.

## Compatibility boundary

API, event, worker-state or storage schema changes require explicit approval, version/migration handling, rollout order and compatibility notes for mixed old/new components.

## Evidence principle

A commit is not a PR. A PR is not a merge. A merge is not deployment. Deployment is not runtime acceptance. Completion is determined only by verified state transitions.