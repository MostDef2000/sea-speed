# Plan: Separate ingestion and root control-plane tokens (#393)

- Specification: specs/393-worker-control-token-separation/spec.md

## Architecture

Two independent bearer credentials with disjoint distribution:

```text
Data plane (unchanged):
  worker.env (operator-owned, 0600)
    SEA_SPEED_API_TOKEN
      -> worker/** event/state posts -> api/app/main.py require_auth (403/500)
Control plane (new separation):
  VPS env for sea-speed-api: SEA_SPEED_WORKER_CONTROL_TOKEN
      -> call_worker_control() Authorization: Bearer <control token>
  worker control.env (operator-owned, 0600, __INSTALL_ROOT__/shared/config/)
    SEA_SPEED_WORKER_CONTROL_TOKEN
      -> sea-speed-worker-control.service (EnvironmentFile=) -> worker-control-agent.py
```

Code changes:

- `api/app/main.py` — one added module constant
  (`WORKER_CONTROL_TOKEN`); inside `call_worker_control()` only: the
  missing-token branch becomes `if not WORKER_CONTROL_TOKEN: raise
  HTTPException(status_code=500, detail="SEA_SPEED_WORKER_CONTROL_TOKEN is
  not set")` (mirroring the `require_auth` 500 pattern) and the outbound
  header becomes `Bearer {WORKER_CONTROL_TOKEN}`. The ingestion surface
  (`API_TOKEN`, `require_auth`, all data-plane endpoints) is byte-unchanged.
- `deploy/worker/ubuntu/worker-control-agent.py` — `token()` reads
  `SEA_SPEED_WORKER_CONTROL_TOKEN`; the startup guard exits with
  `SEA_SPEED_WORKER_CONTROL_TOKEN is required`. `authorized()` keeps
  constant-time comparison; no dual-accept path exists or is added.
- `deploy/worker/ubuntu/sea-speed-worker-control.service.template` — the
  single `EnvironmentFile=` switches from `worker.env` to
  `shared/config/control.env`; the direct `Environment=` injections
  (`SEA_SPEED_WORKER_INSTALL_ROOT`, `SEA_SPEED_SOURCE_COMMIT`) stay. The
  agent reads only the install root, the control token and the optional
  `SEA_SPEED_WORKER_CONTROL_LISTEN` (default `10.123.239.102:19001`), so it
  needs nothing else from `worker.env`.
- `deploy/worker/ubuntu/control.env.example` (new) — the provisioning
  template: `SEA_SPEED_WORKER_CONTROL_TOKEN=` plus a comment-style optional
  `SEA_SPEED_WORKER_CONTROL_LISTEN=10.123.239.102:19001`.
- `deploy/worker/ubuntu/install-systemd.sh` — fail-closed gate before any
  unit rendering/installation, mirroring the existing worker.env gate but
  stricter: file exists, is regular, is not a symlink, mode exactly 600,
  and a silently-parsed non-empty `SEA_SPEED_WORKER_CONTROL_TOKEN` value.
  No chmod repair and no content echo: the file is operator-owned.

## Decisions

- DEC-1: The control unit keeps exactly one `EnvironmentFile=` (now
  `control.env`) and gains no second env file and no dual-accept of
  `SEA_SPEED_API_TOKEN` — a hard cutover. The unit already injects
  `SEA_SPEED_WORKER_INSTALL_ROOT` and `SEA_SPEED_SOURCE_COMMIT` directly,
  and the agent reads only those, the control token, and the optional
  listen variable, so nothing else from `worker.env` is required.
- DEC-2: Names are `SEA_SPEED_WORKER_CONTROL_TOKEN` (env var, both hosts)
  and `control.env` / `control.env.example` (operator-provisioned file,
  0600, `deploy/worker/ubuntu/` example in-repo).
- DEC-3: `configure-analytics-profiles.py` is untouched: it writes
  data-plane env values into worker/road env files and has no relationship
  to the control plane.
- DEC-4: The installer gate requires existence, regular-file type, absence
  of symlink, mode exactly 600 and a non-empty
  `SEA_SPEED_WORKER_CONTROL_TOKEN` value (silent parse, never printed);
  empty, whitespace-only and quote-only values are rejected by the same
  gate; failure exits before rendering/installing any unit. After the
  recursive `chown` of the shared tree the installer re-asserts root
  ownership on `control.env` and its parent config directory (file 0600,
  directory 0750): the data-plane service user must never be able to read
  or replace the control token. Gate error messages never include file
  contents.
- DEC-5: The API mirrors `require_auth`'s fail-closed posture for the
  control path: HTTP 500 naming the unset variable instead of the previous
  API-token-derived 503, and the Authorization header is built from
  `WORKER_CONTROL_TOKEN`. `require_auth` itself is untouched.
- DEC-6: Hard cutover with pre-merge operator provisioning and no
  dual-accept: both sides must be provisioned before the deploys run; the
  bounded two-job deploy gap (VPS API job and Ubuntu worker job) is
  accepted because both sides are provisioned in advance and ingestion
  keeps working on the unchanged `SEA_SPEED_API_TOKEN` throughout.
- DEC-7: `update-exact.sh` gets no backup/restore entry for `control.env`:
  it is operator-owned and never deploy-mutated. Protection remains the
  existing install-systemd failure path (`abort_activation` +
  `restore_previous_control`), verified by reading the script; nothing
  there references env files, so no change is required.
- DEC-8: Docs and tests move in lockstep with the code: ops doc pins in
  `tests/test_sea_speed_auth_v1.py` are updated to the revised
  `SEA_SPEED_AUTH_V1.md`, an absence assertion keeps the worker Authentik
  stage free of the control token, and example-hygiene tests pin the
  example-file split.

## Affected contours

- VPS: `api/app/main.py` (worker-control call path only),
  `deploy/vps/README.md` (env documentation).
- Ubuntu worker/relay: `deploy/worker/ubuntu/worker-control-agent.py`,
  `sea-speed-worker-control.service.template`, `control.env.example` (new),
  `install-systemd.sh`.
- Documentation: `docs/operations/SEA_SPEED_AUTH_V1.md`.
- Tests: `tests/test_worker_operator_control.py`,
  `tests/test_ubuntu_worker_systemd.py`, `tests/test_sea_speed_auth_v1.py`,
  `tests/test_393_control_token_separation.py` (new).
- SDD: `specs/393-worker-control-token-separation/` (trio).
- Explicitly unchanged: `worker/**`, `scripts/**`, `.github/**`,
  `schemas/**`, `data/**`, `configure-analytics-profiles.py`,
  `update-exact.sh`, the ingestion token name/value and every data-plane
  behavior.

## Deployment transaction audit

All deploy/** transaction stages for this change (pre-flight gates, backup,
apply, activation, verify, rollback) are audited below. Backup is part of
PRE-MUTATION; apply and activation are part of MUTATION — the transaction
writes units only after every gate passes and never starts services.

- TX-ADMISSION | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no merge and no deploy; the control-token provisioning checklist remains an open operator prerequisite and the Change Contract is not admissible | Retry: after the operator provisions both token sides and the PR body matches the exact diff, re-run admission | Rollback: not applicable — no runtime state exists at this stage | Evidence: PR Change Contract (Production impact MIXED, Risk profile REQUIRED, Production safety envelope REQUIRED) plus the ops runbook pre-merge provisioning section
- TX-PRE-MUTATION | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: the installer gate (exit 6/7/8) fails inside the OUTER updater transaction after unit backups were taken, so update-exact.sh aborts and executes its restore path — previous worker/road/control units are reinstalled and restarted from backups per desired state; the failure is not a disturbance-free no-op (services may be restarted), but no target-release unit is ever installed and control.env itself is never mutated by deploy tooling (operator-owned) | Retry: after fixing the failing precondition (missing/non-regular/symlinked/non-0600/empty-or-quote-only-token control.env) re-run the transaction | Rollback: the outer updater's restore path IS the rollback for this stage — previous units are reinstalled from the taken backups; no target-release state was committed | Evidence: installer gate error messages naming path/mode/variable requirements only (never file contents), plus RESTORE/RESTORED lines from update-exact.sh in deploy logs
- TX-MUTATION | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: if unit rendering/installation or activation fails after backup — including a late installer-gate rejection — the OUTER updater transaction aborts and executes its restore path (previous worker/road/control units reinstalled and restarted from backups); it is not a disturbance-free no-op; a later-stage failure falls back to CRITICAL logging with ACTIVE_MARKER_UNCHANGED | Retry: re-run the exact deploy after remediation; unit installation is idempotent per exact source commit | Rollback: restore_previous_control() reinstalls the previous control unit, restores its enabled/active state and verifies the restored ExecStart matches the previous commit; control.env itself is never backed up, written, chowned or removed by deploy tooling (operator-owned; the installer only re-asserts its pre-existing root:root 0600 state) | Evidence: INSTALLED/ENABLED/NOT_STARTED installer output, ACTIVATION_ABORTED / RESTORED lines from update-exact.sh
- TX-VERIFICATION | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: deployment reported failed with active worker services unchanged (activation enables but never starts units); post-deploy acceptance probes report the failing contour | Retry: re-run verification after remediation; systemd-analyze verify is deterministic | Rollback: explicit rollback-exact.sh to the previous verified release if later runtime acceptance fails | Evidence: systemd-analyze verify output for the three units plus deploy workflow check results; the VPS API and Ubuntu worker deploy jobs are independent and unordered (either skew direction is possible), so verification evidence is per-job and no cross-host ordering is assumed
- TX-STATE-COMMIT | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: active-marker/state-commit writes are the final mutation; failure triggers abort_activation, which restores the previous marker and units together | Retry: re-run the deploy; the marker write is idempotent for the exact release identity | Rollback: rollback-exact.sh restores the previous active marker, units and runtime binding | Evidence: active-marker output lines and deploy workflow logs
- TX-HOUSEKEEPING | Stage: HOUSEKEEPING | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: stale staging/temp/backup files may remain under the updater root; committed unit/marker state on hosts is unaffected | Retry: next deploy run reuses the updater root and re-cleans; no operator action required | Rollback: not applicable — housekeeping never touches operator env files (control.env included) or installed units | Evidence: cleanup() coverage pinned in tests/test_ubuntu_worker_exact_updater.py (unit/road/control backups and marker temp files)
- TX-EVIDENCE | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: missing or inconsistent evidence blocks PR admission and merge | Retry: rebuild artifacts/evidence at the exact head and re-run CI | Rollback: not applicable — evidence collection mutates nothing | Evidence: quality-integration run links, exact artifacts manifest and quality evidence bundle at the exact-green head
- TX-ROLLBACK | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: restore_previous()/restore_previous_control() restore the previous units, enabled/active state and marker; on total failure the previous release keeps running and the transaction reports CRITICAL with the active marker unchanged | Retry: operator re-runs rollback after fixing the host-level failure | Rollback: SEA_SPEED_API_TOKEN is never removed; the control token is removed only after a full rollback succeeds, and operator-owned control.env is never removed by deploy tooling | Evidence: RESTORED / ACTIVE_MARKER_UNCHANGED outputs plus the rollback section of docs/operations/SEA_SPEED_AUTH_V1.md

- Adjacent-stage review: COMPLETE — every stage above was checked against
  the current `update-exact.sh` transaction (pre-flight gates, backup,
  apply, activation, verify, rollback) and `install-systemd.sh` gates; no
  stage is newly unguarded by this change.

## Validation

- `python3 scripts/ci/validate_sdd.py` — SDD structure for all feature dirs
  including specs/393-worker-control-token-separation/.
- `python3 scripts/ci/validate_repo.py`,
  `python3 scripts/ci/validate_contracts.py`,
  `python3 scripts/quality/validate_quality_contracts.py`,
  `python3 scripts/quality/validate_workflow_policy.py` — repository and
  contract validators.
- `ruff check --config scripts/quality/ruff.toml .` (ruff 0.16.10) and
  `mypy --config-file scripts/quality/mypy.ini <pinned targets>`
  (mypy 1.18.2) — progressive strict gates unchanged.
- `python3 -m py_compile` on changed Python files.
- Full behavioral suite on CPython 3.14: 662 tests, OK (3 skipped),
  including the 12 tests of tests/test_393_control_token_separation.py
  (documented pre-#393 baseline: 649 passed / 2 skipped).
- `bash -n deploy/worker/ubuntu/install-systemd.sh`.
- `git diff --stat` review against the allowed-path list.
- At PR time: Change Contract declares Production impact MIXED, Risk
  profile REQUIRED, Production safety envelope REQUIRED, VPS deployment
  REQUIRED, Ubuntu worker/relay update REQUIRED.

## Runtime feedback

- RF-001: Operator actions expected before merge: provision
  `control.env` on the worker and `SEA_SPEED_WORKER_CONTROL_TOKEN` in the
  VPS API environment (two protected-channel steps, zero actions during
  CI).
- RF-002: Post-deploy acceptance: worker-control status/start/stop through
  the VPS API succeeds with the new token; ingestion event/state posts keep
  using the unchanged `SEA_SPEED_API_TOKEN`; a wrong-token (ingestion
  token) control call is rejected.
- RF-003: Evidence to record in the PR: full local battery outputs, CI run
  links at exact-green-head, and the operator provisioning confirmation
  (paths only, never values).

## Risk profile

- Risk profile: REQUIRED

- RISK-SEC-1 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: hard cutover with no dual-accept; agent and API each fail closed when the control token is absent; installer gate rejects malformed `control.env` before any unit write; separation-matrix tests pin rejection of the ingestion token on the control path | Validation: tests/test_worker_operator_control.py + tests/test_393_control_token_separation.py | Residual risk: a misprovisioned operator environment (token set on only one side) surfaces as control-plane 500/403 until the operator completes provisioning — detectable, non-silent, ingestion unaffected | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-OPS-1 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: docs give exact pre-merge provisioning steps; the bounded two-job deploy gap is accepted explicitly because both sides are provisioned in advance and ingestion is unaffected; rollback keeps `SEA_SPEED_API_TOKEN` and never deletes `control.env` | Validation: ops doc + deploy/vps/README.md diff review | Residual risk: operator delay between the two deploy jobs extends the window where one side already expects the token; mitigated by provisioning-first runbook | Owner: Operator (provisioning), Delivery Orchestrator (verification) | Status: ACCEPTED
- RISK-REG-1 | Category: TECH | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: ingestion path pinned byte-for-byte in tests; `worker/**` and configurator untouched; full suite + validators run locally | Validation: tests/test_393_control_token_separation.py byte-pin test; full unittest run | Residual risk: minimal — data plane has no new code path | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: R-1 | Level: unit | Priority: P0 | Evidence: tests/test_worker_operator_control.py — bearer acceptance under `SEA_SPEED_WORKER_CONTROL_TOKEN`, explicit rejection of the `SEA_SPEED_API_TOKEN` bearer, startup fail-closed naming the control token, no dual-accept markers in agent source
- TEST-002 | Covers: R-2,R-3 | Level: unit | Priority: P0 | Evidence: tests/test_ubuntu_worker_systemd.py — control unit references control.env and not worker.env; installer gate markers (exists/regular/no-symlink/0600/non-empty, silent parse); control.env.example hygiene in tests/test_worker_operator_control.py
- TEST-003 | Covers: R-4 | Level: unit | Priority: P0 | Evidence: tests/test_393_control_token_separation.py — AST-extracted `call_worker_control` returns 500 naming the unset control token and sends the control-token bearer; ingestion `require_auth` block byte-pinned; exactly one `Bearer {API_TOKEN}` occurrence in api/app/main.py
- TEST-004 | Covers: R-5 | Level: integration | Priority: P0 | Evidence: tests/test_ubuntu_worker_systemd.py gate markers + `bash -n` installer syntax check
- TEST-005 | Covers: R-6 | Level: integration | Priority: P1 | Evidence: update-exact.sh source review (no control.env backup/restore entry; restore_previous_control intact) pinned by tests/test_ubuntu_worker_exact_updater.py baseline; `git diff --stat` shows worker/** and configure-analytics-profiles.py untouched
- TEST-006 | Covers: R-7 | Level: integration | Priority: P0 | Evidence: full `python -m unittest discover -s tests -v` run on CPython 3.14 — baseline 649 passed / 2 skipped plus new tests, zero regressions
- TEST-007 | Covers: R-8 | Level: unit | Priority: P1 | Evidence: tests/test_sea_speed_auth_v1.py ops-doc pins (two-token model, provisioning, no dual-accept) and worker Authentik stage absence assertion
- TEST-008 | Covers: R-4,R-8 | Level: runtime-manual | Priority: P1 | Evidence: post-deploy operator acceptance per docs/operations/SEA_SPEED_AUTH_V1.md (control call with new token succeeds; ingestion unchanged) | Reason: requires the real VPS/worker runtime after merge

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE
