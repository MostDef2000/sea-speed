# Plan: Ruff and progressive mypy quality gates

- Specification: specs/399-ruff-progressive-type-gates/spec.md

## Architecture

No new workflow and no aggregate mutation. Two steps are inserted inside the
existing `static-contract-security` job of
`.github/workflows/quality-integration.yml`, after the "Validate JSON and
Python syntax" step and before the "Run repository behavioral tests" step —
the same placement pattern documented in
`docs/quality/quality-gate-architecture.md:86` ("These checks execute inside
the existing `static-contract-security` domain, so the merge-facing aggregate
remains unchanged"). The aggregate job list, triggers, permissions,
concurrency, `if: always()` logic and the other three domains are untouched;
no new required context is introduced.

- `Ruff lint (non-mutating)` — `pip install ruff==0.16.10` then
  `ruff check .`. The committed `ruff.toml` selects `["E9", "F"]` with
  `fix = false` and `target-version = "py314"`, so the step is analysis-only:
  it fails on findings and never rewrites source.
- `Progressive mypy (strict baseline)` — `pip install mypy==1.18.2` then
  `mypy --config-file mypy.ini` over exactly the five strict modules
  (`scripts/quality/common.py`, `worker/analytics_profiles.py`,
  `worker/detection_performance.py`, `scripts/release/production_policy.py`,
  `scripts/ci/validate_delivery_checkpoint.py`). The committed `mypy.ini`
  keeps the global section permissive and enables full strict mode
  per-module — the adoption mechanism.

Both installs are plain pip installs with exact pins (no `uses:` entries, no
heredocs, no download-to-shell pipes), so the workflow-policy validator's
closed action allowlist is unaffected.

## Decisions

- DEC-1: mypy over pyright — the pyright pip CLI downloads Node.js at
  runtime from an external registry, a supply-chain surface this repository
  does not accept immediately after #401's hardening; mypy is a pure pip
  install with no runtime fetches.
- DEC-2: mypy pinned to **1.18.2** — the last release line whose
  dependencies are pure-Python (1.19+ requires the librt C extension; 2.x
  additionally requires the Rust-based `ast_serialize` parser), keeping the
  CI install toolchain-free. Version bumps are deliberate decisions with a
  re-run of the local battery, not silent floating pins.
- DEC-3: Ruff rule set `select = ["E9", "F"]` with the default E4/E7 families
  and E501 deliberately deferred — measured on base 27c90b7 with
  ruff 0.16.10: 290 findings under the full default E4/E7/E9/F set vs 14
  under E9+F; E701/E702 dense-style legacy dominates and ~300 legacy lines
  exceed 120 characters. A mass style rewrite is out of scope for this task;
  widening the rule set is a deliberate follow-up decision.
- DEC-4: The 14 baseline findings are resolved mechanically rather than
  suppressed (10 F401 + 3 F841 + 1 F541; full list in spec.md R-3), each
  verified side-effect-free: unused stdlib/named imports, dead locals with
  pure right-hand sides, one f-string prefix, and one unused `result` binding
  where the `subprocess.run(check=True)` call itself is retained. No
  `# noqa` and no `# type: ignore` comments are introduced.
- DEC-5: The initial strict set is the five fully-annotated, small, pure
  modules named above; four of them were already strict-clean on base, and
  `worker/detection_performance.py` needed only the five
  `collections.deque[float]` annotations (its `no-any-return` finding
  disappears once the deques are parameterized).
- DEC-6: No validator or test changes — blast radius verified: no test reads
  the aggregate's job list, and the workflow-policy validator's required
  markers (job names, `if: always()`, `validate_sdd.py --event`, trigger
  blocks, permissions) are untouched by the two inserted steps.

## Affected contours

- CI/CONTROL_PLANE: `.github/workflows/quality-integration.yml` (two
  inserted steps in the existing `static-contract-security` domain).
- UBUNTU_WORKER (classifier-derived): the calibrated `worker/**` and
  `deploy/worker/ubuntu/**` files map the diff to the Ubuntu worker/relay
  contour under `data/contracts/change-control-policy-v1.json`; the edits
  themselves are behavior-preserving dead-code removals that reach the
  running worker through the normal release channel.
- New committed configuration: `ruff.toml`, `mypy.ini` (repository root).
- Calibrated source files (dead code and unused imports only):
  `worker/detection_performance.py`,
  `worker/hls_motion_yolo_worker_events.py`,
  `deploy/worker/ubuntu/storage_lifecycle_common.py`,
  `deploy/worker/ubuntu/storage_lifecycle_inventory.py`,
  `scripts/ci/sync_tasks_md.py`,
  `scripts/quality/verify_quality_status.py`,
  `scripts/worker/benchmark_detector_frequency.py`,
  `tests/test_camera_preview_gallery.py`,
  `tests/test_roi_normalization.py`,
  `tests/test_worker_operator_control.py`,
  `tests/test_mediamtx_compatibility_remediation.py`.
- Documentation: `docs/quality/testing-policy.md` (new "Static analysis"
  section) and the `specs/399-ruff-progressive-type-gates/` SDD trio.
- No schemas, no contracts, no deploy scripts, no
  `data/quality/quality-gates-v1.json`, no other workflow file.

## Validation

- `ruff check .` (after `pip install ruff==0.16.10`) — zero findings on the
  calibrated tree.
- `mypy --config-file mypy.ini scripts/quality/common.py worker/analytics_profiles.py worker/detection_performance.py scripts/release/production_policy.py scripts/ci/validate_delivery_checkpoint.py` (after `pip install mypy==1.18.2`) — zero errors over the strict set.
- `python scripts/quality/validate_workflow_policy.py` — workflow policy
  validator with the two inserted steps present (markers byte-identical).
- `python scripts/ci/validate_repo.py` — repository structure/secret rules.
- `python scripts/ci/validate_contracts.py` — canonical contract set.
- `python scripts/quality/validate_quality_contracts.py` — quality
  contracts, fixtures, rollout and accepted-risk state.
- `python -m py_compile scripts/quality/*.py scripts/release/*.py` — syntax
  gate over the compiled script contours.
- `python -m unittest discover -s tests -p 'test_*.py' -v` on CPython 3.14 —
  expected baseline: Ran 649 tests, OK, skipped=3 (calibrated fixes are
  behavior-preserving).
- `git diff --stat` — exactly the 18 allowed files.
- At PR time: "Quality integration gate" green at exact-green-head with both
  new steps green inside `static-contract-security`.

## Runtime feedback

- RF-001: Operator actions expected: 0; both steps run autonomously inside
  the existing aggregate on pull_request, push to main and
  workflow_dispatch.
- RF-002: Evidence to record in the PR: CI run links ("Quality integration
  gate" PR run and push-to-main run with both steps green), local ruff/mypy
  outputs, validator outputs, unittest baseline output and the
  `git diff --stat` scope review.

## Risk profile

- Risk profile: NOT REQUIRED

Rationale: Security impact NONE — the change inserts two analysis-only steps
into an existing job, adds two committed config files, removes dead code and
documents policy. Nothing existing is weakened, bypassed or removed; the
workflow-policy validator's markers stay byte-identical; no new permissions,
actions, heredocs or download pipes appear. The one supply-chain
consideration is bounded by design: both pip installs use exact pins
(`ruff==0.16.10`, `mypy==1.18.2`), no runtime toolchain downloads occur, and
neither tool executes repository code in a privileged context — mypy
type-checks, ruff lints, both fail closed on findings. Runtime acceptance
beyond the behavioral suite is not applicable to this change itself: the
workflow insertion is CI-only, and the calibrated worker-source edits are
behavior-preserving dead-code removals. The diff nonetheless classifies
UBUNTU_WORKER under `data/contracts/change-control-policy-v1.json`
(`worker/**` and `deploy/worker/ubuntu/**` patterns), so the Change Contract
declares the Ubuntu worker/relay update contour REQUIRED and the fixes reach
the running worker through the normal release channel. Not destructive: the
calibrated source edits are verified-side-effect-free dead-code removals
covered by the behavioral suite baseline.

## Test design

- TEST-001 | Covers: R-1,R-6 | Level: integration | Priority: P0 | Evidence: the `Ruff lint (non-mutating)` step present in static-contract-security between the JSON/py_compile and unittest steps; local `ruff check .` exits 0 with `fix = false` config (AC-001)
- TEST-002 | Covers: R-2,R-6 | Level: integration | Priority: P0 | Evidence: the `Progressive mypy (strict baseline)` step present in the same position; local mypy 1.18.2 over the five strict modules exits 0 (AC-002)
- TEST-003 | Covers: R-3 | Level: unit | Priority: P0 | Evidence: ruff 0.16.10 reports zero findings on the calibrated tree (14 baseline findings resolved per spec R-3 list); `python -m unittest discover -s tests -p 'test_*.py' -v` shows Ran 649 tests, OK, skipped=3 (AC-003)
- TEST-004 | Covers: R-4 | Level: integration | Priority: P0 | Evidence: `python scripts/quality/validate_workflow_policy.py`, `validate_repo.py`, `validate_contracts.py`, `validate_quality_contracts.py` and `python -m py_compile scripts/quality/*.py scripts/release/*.py` all pass with the insertion present (AC-003)
- TEST-005 | Covers: R-5 | Level: integration | Priority: P1 | Evidence: `docs/quality/testing-policy.md` "Static analysis (Ruff and mypy)" section carries the exact CI-identical local commands, pin rationale, progressive-strict policy and suppression rules; `Status: Active` marker untouched (AC-004)
- TEST-006 | Covers: R-1,R-2,R-6 | Level: end-to-end | Priority: P0 | Evidence: post-merge "Quality integration gate" push-to-main run shows both new steps green inside static-contract-security with the aggregate green (AC-001, AC-002)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE
