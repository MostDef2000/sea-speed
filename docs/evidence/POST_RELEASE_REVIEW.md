# Sea Speed post-release evidence review

Status: Active
Issue: #28

## Purpose

Determine whether a deployed change is accepted, regressed or lacks sufficient evidence. Use sanitized deployment manifests/runtime telemetry; never store secrets/private media/model/env contents.

## Required identity

```text
Issue:
Pull request:
Merge/source commit:
Release manifest v2:
Applicable contour(s): VPS / Ubuntu Worker/relay / Windows AI Worker
VPS deployment manifest: NOT REQUIRED / path-id
Ubuntu deployment manifest: NOT REQUIRED / path-id
Windows deployment manifest: NOT REQUIRED / path-id
API source_commit: NOT REQUIRED / value
Ubuntu source/runtime identity: NOT REQUIRED / value
Windows source identity: NOT REQUIRED / value
Evidence window UTC:
```

## Runtime gates

For every applicable contour prove exact installed identity, valid deployment evidence, health/process state, known rollback target and task-specific behavior. Worker tasks additionally require advancing freshness/frame/state and AI/relay telemetry when those behaviors are in scope. GitHub-hosted CI cannot by itself prove GPU/camera runtime.

## Quality observations

Record only aggregate/sanitized evidence: state/event validation counts, freshness progression, applicable operator acceptance, observed runtime errors and protected-boundary smokes. Do not claim accuracy improvement without comparable before/after evidence.

## Verdicts

### `accepted`
All required contour and product criteria passed with sufficient evidence.

### `regressed`
A required health/freshness/schema/security/product criterion failed. Link a regression Issue and decide rollback unless the exact safe rollback is already covered by the active production envelope.

### `insufficient_evidence`
Runtime may be installed/healthy but evidence is insufficient for the approved product decision. Do not represent it as acceptance.

`COMPLETE` requires an allowed final verdict for every applicable contour/outcome.
