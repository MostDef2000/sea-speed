# Tasks — Issue #697 typed reason for every unknown speed status

- Issue: #697
- Specification: specs/697-typed-unknown-reason/spec.md

## Delivery tasks

- T-001 (code unit): add stdlib-only `api/app/unknown_reason.py` — closed
  string set with emitted `too_few_observations` / `gate_unavailable` /
  `legacy_unspecified`, reserved-not-emitted `black_frame` / `slate_frame` /
  `frozen_frame`, `UNKNOWN_REASONS` tuple, frozensets and
  `is_unknown_reason()`.
- T-002 (code unit): `worker/water_passage.py` — release-relative,
  cwd-independent import of the shared module; `_unknown_meta` helper; reasons
  attached inside `measurement_meta` on the selected result only, per the
  spec's per-path table; measured/measuring carry none.
- T-003 (code unit): `worker/worker_transport.py` — append
  ` unknown_reason=<value>` to the existing `POST passage ok` log only when a
  reason is present.
- T-004 (code unit): `api/app/water_passages.py` — extend the dual import seam;
  boundary rejects non-string/non-enum supplied reasons; read-side
  `_normalize_unknown_reason` supplies `legacy_unspecified` for unknown rows
  without a valid reason and drops reasons from known-status rows; rank-merge
  untouched.
- T-005 (packaging): add `api/app/unknown_reason.py` to the vps, ubuntu-worker
  and edge required inventories in `build_exact_artifacts.py` and
  `validate_exact_artifacts.py`; mirror every module touchpoint in
  `deploy/vps/deploy.sh` (target, release_complete, download loop,
  install-to-release, bootstrap capture, `.next` staging, activation and
  rollback removal).
- T-006 (SDD): this spec/plan/tasks trio with the closed enum, per-path table,
  additive JSON contract, legacy policy, Gherkin scenarios, #700 reservation
  statement, risk profile, test design, correct-course check, 8-stage
  deployment transaction audit and AC traceability.
- T-007 (verification, this worker): py_compile, ruff, bash -n, exact-artifact
  build/validate, deploy convergence and archive inventory. Observed outputs
  in "Verification evidence" below.
- T-008 (test worker, out of this worker's scope): behavioral tests for worker
  per-path reasons, API accept/reject, legacy read, rank-merge non-demotion,
  log line, and the exact-artifact/deploy fixture updates.

## Requirements traceability

- AC-001 | Task: T-001 | Evidence: tests/test_697_typed_unknown_reason.py — closed-set membership and stdlib-only/import-isolation assertions (green) | Coverage: COVERED
- AC-002 | Task: T-002 | Evidence: tests/test_697_typed_unknown_reason.py — per-path reason assertions incl. disabled/finalize branches (green) | Coverage: COVERED
- AC-003 | Task: T-002 | Evidence: tests/test_697_typed_unknown_reason.py — measured/measuring no-reason and selection-contract assertions (green) | Coverage: COVERED
- AC-004 | Task: T-003 | Evidence: tests/test_697_typed_unknown_reason.py — byte-exact success log assertion (green) | Coverage: COVERED
- AC-005 | Task: T-004 | Evidence: tests/test_697_typed_unknown_reason.py — boundary 400 for invalid supplied reason, accept when absent (green) | Coverage: COVERED
- AC-006 | Task: T-004 | Evidence: tests/test_697_typed_unknown_reason.py — legacy unknown read supplies legacy_unspecified, row unchanged (green) | Coverage: COVERED
- AC-007 | Task: T-004 | Evidence: tests/test_697_typed_unknown_reason.py — rank-merge non-demotion assertions (green) | Coverage: COVERED
- AC-008 | Task: T-005, T-007 | Evidence: build+validate exact artifacts green; convergence 11/11; all three archives contain the module | Coverage: COVERED

## Completion gate

- All in-scope Python files `py_compile` clean.
- ruff (base tier) clean on changed files.
- `bash -n deploy/vps/deploy.sh` clean.
- Exact-artifact build + validate green in a temp output dir.
- Deploy convergence check green (11/11) and the edge archive contains
  `api/app/unknown_reason.py`.
- Behavioral tests: `tests/test_697_typed_unknown_reason.py` green — 35
  passed, 58 subtests passed, 0 failed.

## Verification evidence

Observed in this change's verification run (commands run from the repository
root at base `83e8851a896b795786fc4db7c3f6fe7088436302`):

- `python3 -m py_compile` on `api/app/unknown_reason.py`,
  `api/app/water_passages.py`, `worker/water_passage.py`,
  `worker/worker_transport.py`, `scripts/quality/build_exact_artifacts.py`,
  `scripts/quality/validate_exact_artifacts.py` → `PYCOMPILE_OK`.
- `python3 -m ruff check --config scripts/quality/ruff.toml` on the same
  files → `All checks passed!` (`RUFF_EXIT=0`).
- `bash -n deploy/vps/deploy.sh` → clean (`BASH_OK`).
- `python3 scripts/quality/build_exact_artifacts.py --source-commit
  83e8851a896b795786fc4db7c3f6fe7088436302 --output-dir
  /tmp/opencode/697-artifacts` → `BUILD_EXIT=0`.
- `python3 scripts/quality/validate_exact_artifacts.py --manifest
  /tmp/opencode/697-artifacts/exact-artifacts.json` → `Exact artifacts valid:
  VPS/edge quality evidence plus Ubuntu Worker release inventory, digests,
  extraction and syntax` (`VALIDATE_EXIT=0`).
- Convergence: `vps api/app required: 11`, `deploy.sh mirrored: 11`,
  `unmirrored: []`, `unshipped: []`, `CONVERGENCE_OK`.
- Archive inventory: `vps unknown_reason: True`, `edge unknown_reason: True`,
  `ubuntu-worker unknown_reason: True`.
- `python3 -m pytest tests/test_697_typed_unknown_reason.py -q` →
  `35 passed, 58 subtests passed` (0 failed).
- Full suite `python3 -m pytest tests/ -q` → `1702 passed, 2 failed, 2 skipped,
  941 subtests passed`; the two failures are the pre-existing working-tree
  scope guards (#685, #687) rejecting the one uncommitted in-scope
  `worker/water_passage.py` edit before the orchestrator commit — not
  behavioral regressions and not caused by this change's logic.

## Definition of Done

- Issue/spec/plan/tasks current — this trio added for #697.
- Exact changed-file scope verified — only the admitted production, packaging
  and SDD paths are touched.
- Required tests and evidence complete — compile/lint/convergence evidence
  recorded; `tests/test_697_typed_unknown_reason.py` green (35 passed, 58
  subtests, 0 failed).
- Required CI green — not yet observed in this worker scope (no commit/PR).
- Exact-green-head merge complete — not yet; owned by the delivery
  orchestrator after `commit approved`.
- Deployment state resolved — not yet; additive change rides the normal VPS
  and Ubuntu release contours.
- Runtime acceptance resolved — not yet; governed by the lane-A VPS probe and
  the Ubuntu worker progression gate after merge.
- Deferred work recorded — #700 frame-quality reasons are reserved and
  deliberately not emitted; behavioral tests owned by the test worker.
- Risks resolved or explicitly accepted — RISK-001..RISK-004 in plan.md are
  MITIGATED.
- Waivers resolved or current — none requested.
