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
Applicable active contour(s): VPS / Ubuntu Worker/relay / MIXED
VPS deployment manifest: NOT REQUIRED / path-id
Ubuntu deployment manifest: NOT REQUIRED / path-id
API source_commit: NOT REQUIRED / value
Ubuntu source/runtime identity: NOT REQUIRED / value
Evidence window UTC:
```

Windows Worker is retired from active post-release review. Historical Windows evidence may be read for audit/rollback context but is never a required new acceptance contour.

## Runtime gates

For every applicable active contour prove exact installed identity, valid deployment evidence, health/process state, known rollback target and task-specific behavior. Worker tasks additionally require advancing freshness/frame/state and AI/relay telemetry when those behaviors are in scope. GitHub-hosted CI cannot by itself prove GPU/camera runtime.

## Quality observations

Record only aggregate/sanitized evidence: state/event validation counts, freshness progression, applicable operator acceptance, observed runtime errors and protected-boundary smokes. Do not claim accuracy improvement without comparable evidence.

When the linked significant feature contains an NFR assessment, record whether runtime evidence confirms, contradicts or leaves each applicable NFR unresolved. A production-only discovery must not be converted into synthetic CI `PASS`.

## Correct-course feedback

If production acceptance reveals a material architecture difference, new protected-boundary concern, unplanned operational risk, changed NFR target, or mismatch between expected and actual runtime behavior, feed the finding into the active feature `spec.md`, `plan.md` and `tasks.md` through the next approved repository scope.

Use the plan trigger vocabulary: `PRODUCTION_LEARNING`, `ARCHITECTURE_PIVOT`, or `MATERIAL_SCOPE_CHANGE`. Record Issue/spec/plan/tasks/authorization impact and follow-up. A material Outcome Contract, repository-scope or protected-boundary change requires fresh source authorization before source writes.

A runtime finding may produce `CONCERNS`, `regressed`, or `insufficient_evidence`; it is not automatically waivable. A waiver never bypasses runtime acceptance or rollback requirements.

## Verdicts

### `accepted`

All required active contour and product criteria passed with sufficient evidence.

### `regressed`

A required health/freshness/schema/security/product criterion failed. Link a regression Issue and decide rollback unless the exact safe rollback is already covered by the active production envelope.

### `insufficient_evidence`

Runtime may be installed/healthy but evidence is insufficient for the approved product decision. Do not represent it as acceptance.

`DONE` requires an allowed final evidence verdict for every applicable active contour/outcome. Historical Windows evidence is not an active completion prerequisite.
