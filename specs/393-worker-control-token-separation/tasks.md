# Tasks: Separate ingestion and root control-plane tokens (#393)

- Specification: specs/393-worker-control-token-separation/spec.md

## Delivery tasks

- T-393-001: Add `SEA_SPEED_WORKER_CONTROL_TOKEN` to `api/app/main.py`;
  switch `call_worker_control()` to the control-token fail-closed 500 and
  `Bearer {WORKER_CONTROL_TOKEN}` header while keeping the ingestion
  surface (`API_TOKEN`/`require_auth`) byte-unchanged (implements R-4)
- T-393-002: Switch `worker-control-agent.py` to
  `SEA_SPEED_WORKER_CONTROL_TOKEN` with a control-token-specific startup
  fail-closed message and no dual-accept of the ingestion token (implements
  R-1)
- T-393-003: Point the control unit's single `EnvironmentFile=` at
  `__INSTALL_ROOT__/control.env`, keeping the direct
  `SEA_SPEED_WORKER_INSTALL_ROOT` / `SEA_SPEED_SOURCE_COMMIT` environment
  injections, and add `deploy/worker/ubuntu/control.env.example` (token
  line plus comment-style optional listen) (implements R-2, R-3)
- T-393-004: Add the fail-closed installer gate for
  `$install_root/control.env` in `install-systemd.sh` (exists, regular
  file, not a symlink, mode exactly 600, non-empty token parsed silently;
  messages never leak contents) before rendering/installing any unit
  (implements R-5)
- T-393-005: Verify `update-exact.sh` protection by reading (unit-only
  backup/restore, `restore_previous_control`, abort path) without changes,
  and confirm `worker/**` plus `configure-analytics-profiles.py` are
  untouched (implements R-6)
- T-393-006: Update pinned tests (agent bearer matrix, API contract
  markers, control unit env references, ops-doc pins, worker Authentik
  stage absence) and add the separation matrix with installer-gate and
  example-hygiene tests (implements R-7)
- T-393-007: Update `docs/operations/SEA_SPEED_AUTH_V1.md` (two-token
  model, pre-merge provisioning, hard cutover, deploy gap, rollback
  semantics) and `deploy/vps/README.md` (VPS env var; deploys never
  overwrite operator-managed env) (implements R-8)
- T-393-008: Write this SDD trio with NFR assessment, Risk profile
  REQUIRED, test design, deployment transaction audit, correct-course
  check, requirements traceability and Definition of Done
- T-393-009: Run the full local battery (validators, ruff, mypy, full
  behavioral suite on CPython 3.14, `bash -n`, py_compile) and record
  evidence; verify exact changed-file scope
- T-393-010: Open the PR with the Change Contract (Production impact MIXED,
  Risk profile REQUIRED, Production safety envelope REQUIRED, VPS +
  Ubuntu worker/relay REQUIRED), record CI evidence, reach exact-green-head
  and merge after the operator provisioning step is confirmed

## Completion gate

- [ ] T-393-001
- [ ] T-393-002
- [ ] T-393-003
- [ ] T-393-004
- [ ] T-393-005
- [ ] T-393-006
- [ ] T-393-007
- [ ] T-393-008
- [ ] T-393-009
- [ ] T-393-010

## Deferred work

- None. The control-token provisioning itself is an operator runtime step
  documented in the ops runbook, not deferred repository work.

## Requirements traceability

- AC-001 | Task: T-393-002 | Evidence: tests/test_worker_operator_control.py — control-token bearer acceptance, ingestion-token bearer rejection, startup fail-closed naming SEA_SPEED_WORKER_CONTROL_TOKEN, no dual-accept markers in agent source | Coverage: COVERED
- AC-002 | Task: T-393-003,T-393-004 | Evidence: tests/test_ubuntu_worker_systemd.py — control unit references control.env and not worker.env; installer gate markers for exists/regular/no-symlink/0600/non-empty-token before rendering | Coverage: COVERED
- AC-003 | Task: T-393-001 | Evidence: tests/test_393_control_token_separation.py — pinned ingestion require_auth block, exactly one Bearer {API_TOKEN} occurrence, call_worker_control 500 naming the unset control token and control-token bearer header | Coverage: COVERED
- AC-004 | Task: T-393-005 | Evidence: git diff review — worker/**, configure-analytics-profiles.py and update-exact.sh untouched; ingestion token name/value unchanged; update-exact.sh keeps unit-only control backup/restore (DEC-7) | Coverage: COVERED
- AC-005 | Task: T-393-009 | Evidence: full local suite (baseline 649 passed / 2 skipped plus new #393 tests) and validators green; numbers recorded in the PR | Coverage: COVERED
- AC-006 | Task: T-393-007 | Evidence: docs/operations/SEA_SPEED_AUTH_V1.md two-token section and deploy/vps/README.md env var note present; tests/test_sea_speed_auth_v1.py pins updated accordingly | Coverage: COVERED
- R-1 | Task: T-393-002,T-393-006 | Evidence: TEST-001 outputs | Coverage: COVERED
- R-2 | Task: T-393-003 | Evidence: control unit EnvironmentFile switch pinned in tests/test_ubuntu_worker_systemd.py | Coverage: COVERED
- R-3 | Task: T-393-003 | Evidence: control.env.example content pinned by example-hygiene test | Coverage: COVERED
- R-4 | Task: T-393-001 | Evidence: TEST-003 outputs | Coverage: COVERED
- R-5 | Task: T-393-004 | Evidence: TEST-004 outputs | Coverage: COVERED
- R-6 | Task: T-393-005 | Evidence: update-exact.sh source review; diff shows worker/** and configurator untouched | Coverage: COVERED
- R-7 | Task: T-393-006 | Evidence: TEST-006 full-suite run | Coverage: COVERED
- R-8 | Task: T-393-007 | Evidence: TEST-007 docs pins plus docs diff in PR | Coverage: COVERED

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [ ] Deferred work recorded
- [ ] Risks resolved or explicitly accepted
- [ ] Waivers resolved or current
