# Sea Speed Testing Policy

Status: Active
Version: 1.1.0

## Required layers

Sea Speed changes are evaluated through unit, contract, property/invariant, adversarial, deterministic fuzz/recovery, exact-artifact, release-evidence and deployment-verification layers.

The single merge-facing context is:

```text
Quality integration gate / quality-integration
```

The aggregate context succeeds only when all four independent domains succeed:

1. `static-contract-security`;
2. `property-fuzz-reliability`;
3. `exact-artifact-e2e`;
4. `release-deployment-evidence`.

The aggregate workflow has no path filters and its final job runs with `if: always()`.

## Mock boundary

Only external boundaries may be mocked: physical camera/RTSP transport, NVIDIA hardware, network failure and production infrastructure. Production identity, storage, packaging, contract and evidence code must execute in its real form.

## Exact artifact

Source-module tests do not replace exact-artifact tests. CI builds deterministic VPS and edge archives and validates the exact archived bytes, inventory, digest, safe extraction and executable syntax.

The GitHub-hosted gate does not prove NVIDIA/CUDA operation on the physical edge server. That limitation is an accepted temporary risk and must be closed with a self-hosted staging/runtime gate.

## Media boundary

The active MVP mode is `mvp_v1`, which temporarily permits VPS JPEG persistence. The target mode is `edge_v2`, where durable images and video exist only on the edge node. VPS may store metadata and proxy media bytes but may not durably store media.

Switching the active mode to `edge_v2` requires a separately approved migration and merge-blocking boundary tests.

## Release and deployment

Merge, release, deployment and runtime acceptance are separate operations.

- A green PR does not prove deployment.
- A merge does not create deployment evidence.
- A release artifact is not installation evidence.
- Deployment is not product acceptance.

Production deployment is manual, requires an exact full commit SHA, a successful aggregate quality check for that commit, production-environment approval, validated evidence and an available rollback target.

## Delivery quality artifacts

Risk-based test design lives in the active feature `plan.md`, not a parallel QA document. Each test-design record states the covered acceptance criteria/risks, evidence level and priority:

- levels: `unit`, `integration`, `end-to-end`, `runtime-manual`;
- priorities: `P0`, `P1`, `P2`, `P3`.

Every `AC-*` in a linked significant specification is mapped in `tasks.md` to an implementation task plus test/evidence. A physical-runtime criterion may use `RUNTIME-MANUAL` only with an explicit reason and observable evidence path.

The NFR assessment in `spec.md` uses `PASS`, `CONCERNS`, `FAIL`, `NOT APPLICABLE`; `PASS` requires a measurable target and evidence method. Unknown targets cannot be promoted to `PASS`.

A full risk profile is mandatory for high-risk triggers defined by the delivery policy. Risk categories are `TECH`, `SEC`, `PERF`, `DATA`, `BUS`, `OPS`, with 1-5 probability and impact scoring. The test plan should prioritize the highest residual-risk paths without replacing the repository's always-running aggregate quality domains.

## Risk acceptance

Ideal governance requires independent review. When the repository operates under a single-maintainer model, owner approval is not described as independent review. The exception and compensating automated gates must be represented in the accepted-risk register.

A PR-level `WAIVED` quality verdict is narrower than the accepted-risk register: it records one bounded delivery concern with an owner, review/expiry date, compensating controls and remediation target. It cannot waive hard authorization, scope, CI, production or rollback requirements. Long-lived architectural risk should still be represented in `data/quality/accepted-risks-v1.json` when applicable.
