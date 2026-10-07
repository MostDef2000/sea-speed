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

## Static analysis (Ruff and mypy)

The static analysis gate runs inside the `static-contract-security` domain of the merge-facing aggregate `Quality integration gate`; it adds no new workflow, no new required context and no aggregate mutation.

### Ruff

Ruff is pinned at `ruff==0.16.10` and configured by the committed `scripts/quality/ruff.toml`. The rule set is deliberately low-noise and non-mutating:

- `select = ["E9", "F"]` — syntax/runtime-level errors (E9) plus pyflakes (F: unused imports/variables, f-strings without placeholders). The default E4/E7 rule families are deferred: the legacy codebase uses a dense multi-statement style (267 findings on main for E701/E702/E401 alone), and enabling them now would require a mass rewrite that no task has requested. Line length (E501) is likewise deferred: ~300 legacy lines exceed 120 characters.
- `fix = false` — the gate is non-mutating. CI never rewrites source, locally or remotely.
- No blanket ignores: suppressions are only ever narrow — a per-file-ignore entry for a named rule or an inline `# noqa: CODE` with the specific code, each with written justification in review.

### mypy

mypy is pinned at `mypy==1.18.2` — the last release line whose dependencies are pure-Python (1.19+ requires the librt C extension; 2.x additionally requires the Rust-based `ast_serialize` parser), so the install is a pure `pip install` with no native toolchain. Version bumps are deliberate decisions with a re-run of the local battery, not silent floating pins.

The committed `scripts/quality/mypy.ini` is the progressive baseline. The global section stays permissive; per-module sections with `strict = True` are the adoption mechanism. Current strict set:

1. `scripts/quality/common.py`
2. `worker/analytics_profiles.py`
3. `worker/detection_performance.py`
4. `scripts/release/production_policy.py`
5. `scripts/ci/validate_delivery_checkpoint.py`

New small, pure, well-tested modules should be added to the strict set during code review (one `[mypy-<module>]` section each). Suppressions must be narrow — `# type: ignore[code]` with the specific error code — never blanket ignores.

### Deterministic local invocation

After `pip install ruff==0.16.10 mypy==1.18.2`, from the repository root:

```text
ruff check --config scripts/quality/ruff.toml .
mypy --config-file scripts/quality/mypy.ini scripts/quality/common.py worker/analytics_profiles.py worker/detection_performance.py scripts/release/production_policy.py scripts/ci/validate_delivery_checkpoint.py
```

Both commands must exit zero on every merge candidate; CI runs exactly these commands.
