# Spec: Separate ingestion and root control-plane tokens

- Issue: #393
- Specification: specs/393-worker-control-token-separation/spec.md

## Product outcome

Ingestion and root control-plane trust surfaces use disjoint bearer
credentials: data-plane workers keep `SEA_SPEED_API_TOKEN` (name and value
unchanged) while only the VPS API and the root control agent hold the new
operator-provisioned `SEA_SPEED_WORKER_CONTROL_TOKEN` from a 0600
`control.env`. A leaked data-plane credential can no longer stop or start
AI worker services, and both sides fail closed when the control token is
absent.

### Problem

Today one secret — `SEA_SPEED_API_TOKEN` — guards two different trust
surfaces: the data-plane ingestion endpoints (`require_auth` on
`/api/cam1/*` writes) and the root control-plane path (the VPS API's
`call_worker_control()` and the Ubuntu worker's root
`worker-control-agent.py`). Every data-plane worker holds the ingestion
token in its protected `worker.env`, so the token that can stop/start the
AI worker services via the root control agent is distributed to the widest
credential population. Issue #393 separates these contours: ingestion
keeps `SEA_SPEED_API_TOKEN` (name and value unchanged); a new dedicated
`SEA_SPEED_WORKER_CONTROL_TOKEN`, operator-provisioned in
`__INSTALL_ROOT__/control.env` (mode 0600, root:root, under the root-owned
install root and outside the `shared/` tree), is known only to
the VPS API and the root control agent.

### Contours

- VPS: `api/app/main.py` gains `WORKER_CONTROL_TOKEN` and the worker-control
  call path switches to it (fail-closed 500 mirroring `require_auth`);
  ingestion path stays byte-identical.
- Ubuntu worker: `worker-control-agent.py`, control unit template,
  `control.env.example` (new) and the `install-systemd.sh` fail-closed gate.
- Docs and tests: `docs/operations/SEA_SPEED_AUTH_V1.md`,
  `deploy/vps/README.md`, the pinned test files and one new separation
  test file.
- Untouched by design: `worker/**` data-plane code,
  `configure-analytics-profiles.py`, `update-exact.sh` (operator-owned
  `control.env` is never deploy-mutated or backed up by deploy tooling),
  `schemas/**`, `scripts/**`, `.github/**`.

### Solution summary

1. The control agent reads only `SEA_SPEED_WORKER_CONTROL_TOKEN` and exits
   at startup naming that variable when it is missing; the control unit's
   single `EnvironmentFile=` becomes `control.env`. No dual-accept of the
   old token — hard cutover.
2. The API keeps `API_TOKEN`/`require_auth` exactly as-is for ingestion and
   fails closed with HTTP 500 "SEA_SPEED_WORKER_CONTROL_TOKEN is not set"
   when the control token is absent, sending `Bearer {WORKER_CONTROL_TOKEN}`
   to the agent.
3. The installer refuses (exit, before rendering units) any
   `control.env` that is missing, not a regular file, a symlink, not mode
   exactly 600, or lacking a non-empty `SEA_SPEED_WORKER_CONTROL_TOKEN`
   value — parsed silently, never printed.
4. Pre-merge provisioning is an operator action: create
   `control.env` on the worker from `control.env.example` before the merged
   deploy activates the new control unit; the bounded two-job deploy gap
   (API job and worker job activate at slightly different moments) is
   explicitly accepted while both tokens are present.

## User scenarios

- US-1: An operator provisions `control.env` (0600, non-empty token) on the
  Ubuntu worker before merging; after deploy the root control agent
  authenticates VPS control calls with the dedicated control token.
- US-2: The operator forgets to provision `control.env`; the next worker
  install fails closed before any unit is rendered or installed, with an
  error that names the missing file/mode/token requirement but never prints
  file contents.
- US-3: The VPS API is deployed without `SEA_SPEED_WORKER_CONTROL_TOKEN`;
  operator control requests through the API fail with HTTP 500 naming the
  unset variable, and the ingestion endpoints keep working unchanged.
- US-4: A data-plane worker token (equal to `SEA_SPEED_API_TOKEN`) is
  presented to the control agent as a bearer; the agent rejects it.
- US-5: A rollback to a previous release restores the previous control unit
  bytes; `SEA_SPEED_API_TOKEN` is never removed, and the control token is
  removed only after a full rollback decision.

## Requirements

- R-1: `SEA_SPEED_WORKER_CONTROL_TOKEN` is the only accepted control-plane
  credential on the agent side: `token()`/`authorized()` read it, the
  startup fail-closed message names it specifically, and the source contains
  no fallback to `SEA_SPEED_API_TOKEN` (no dual-accept).
- R-2: The control unit template carries exactly one
  `EnvironmentFile=` pointing at `__INSTALL_ROOT__/control.env`;
  the direct `SEA_SPEED_WORKER_INSTALL_ROOT` and `SEA_SPEED_SOURCE_COMMIT`
  `Environment=` injections are unchanged; the agent needs nothing else from
  `worker.env`.
- R-3: `deploy/worker/ubuntu/control.env.example` documents
  `SEA_SPEED_WORKER_CONTROL_TOKEN=` and, comment-style, the optional
  `SEA_SPEED_WORKER_CONTROL_LISTEN=10.123.239.102:19001`; it contains no
  HLS/media-auth/model knobs or API URLs (those remain worker.env/road
  provisioning).
- R-4: `api/app/main.py` adds
  `WORKER_CONTROL_TOKEN = os.environ.get("SEA_SPEED_WORKER_CONTROL_TOKEN", "")`;
  `call_worker_control()` fails closed with HTTP 500
  `SEA_SPEED_WORKER_CONTROL_TOKEN is not set` (mirroring the
  `require_auth` 500 pattern) and builds
  `Authorization: Bearer {WORKER_CONTROL_TOKEN}`. The ingestion path
  (`API_TOKEN`, `require_auth`, all ingestion endpoints) stays
  byte-unchanged.
- R-5: `install-systemd.sh` gains a fail-closed gate before rendering or
  installing any unit: `control.env` must exist, be a regular file, not a
  symlink, have mode exactly 600 and contain a non-empty
  `SEA_SPEED_WORKER_CONTROL_TOKEN` value parsed silently; error messages
  name the requirement without leaking file contents.
- R-6: `update-exact.sh` gains no backup/restore entry for `control.env`
  (operator-owned, never deploy-mutated); the existing install-systemd
  failure path (abort + `restore_previous_control`) is the protection.
  `configure-analytics-profiles.py` and `worker/**` are not modified.
- R-7: Tests lockstep: the pinned tests are updated (agent bearer acceptance
  under the control token plus explicit rejection of the ingestion token,
  startup fail-closed message, API contract source markers, control unit
  env-file references, ops-doc pins, absence assertions) and a separation
  matrix plus installer-gate and example-hygiene tests are added.
- R-8: Docs lockstep: `docs/operations/SEA_SPEED_AUTH_V1.md` documents the
  two-token model, pre-merge provisioning, hard cutover/no dual-accept, the
  bounded two-job deploy gap acceptance and rollback semantics
  (`SEA_SPEED_API_TOKEN` never removed; control token removal only after
  full rollback). `deploy/vps/README.md` documents the new VPS env var and
  that deploys never overwrite operator-managed env files.

## Acceptance criteria

- AC-001: The control agent accepts only `SEA_SPEED_WORKER_CONTROL_TOKEN`
  bearers and explicitly rejects a bearer equal to `SEA_SPEED_API_TOKEN`;
  startup without the control token exits naming
  `SEA_SPEED_WORKER_CONTROL_TOKEN`.
  Validation: `python3 -m unittest tests.test_worker_operator_control -v`.
- AC-002: The control unit references `control.env` and does not reference
  `worker.env`; the installer gate rejects missing/non-regular/symlink/
  non-0600/empty-token control.env before rendering units.
  Validation: `python3 -m unittest tests.test_ubuntu_worker_systemd -v`.
- AC-003: The API ingestion path is byte-unchanged (pinned `require_auth`
  block), `call_worker_control` raises 500 naming
  `SEA_SPEED_WORKER_CONTROL_TOKEN` when unset and sends the control token
  bearer; the API source keeps exactly one `Bearer {API_TOKEN}` (ingestion).
  Validation: `python3 -m unittest tests.test_393_control_token_separation -v`.
- AC-004: Example hygiene: `worker.env.example` and
  `road-worker.env.example` contain no `SEA_SPEED_WORKER_CONTROL_TOKEN`;
  `control.env.example` contains no HLS/media-auth/model/API-URL knobs.
  Validation: `python3 -m unittest tests.test_worker_operator_control -v`.
- AC-005: The full behavioral suite passes on CPython 3.14 with no
  regression against the documented baseline (649 passed / 2 skipped),
  plus the new #393 tests. Validation: full unittest/pytest run recorded
  in the PR.
- AC-006: SDD, repository, contract and quality validators pass with the
  new specs directory present. Validation:
  `python3 scripts/ci/validate_sdd.py && python3 scripts/ci/validate_repo.py`
  (+ contracts/quality contracts validators).

## Runtime feedback

- RF-001: Operator actions expected before merge: provision
  `<install-root>/control.env` (mode 0600, root:root, under the root-owned
  install root and outside the `shared/` tree, non-empty
  `SEA_SPEED_WORKER_CONTROL_TOKEN`) on the Ubuntu worker and set
  `SEA_SPEED_WORKER_CONTROL_TOKEN` in the VPS API environment. Both are
  protected-channel operator steps; values never enter chat, Git or CI.
- RF-002: Deployment timing: the API deploy and the worker deploy are two
  jobs; between them exactly one side may already require the control
  token. The gap is accepted and bounded: the ops runbook requires the
  operator to provision both sides before either deploy starts, and the
  old token remains valid for ingestion throughout.
- RF-003: Rollback: `SEA_SPEED_API_TOKEN` is never removed. The control
  token may be removed only after a full rollback; unit rollback restores
  the previous control unit via the existing `restore_previous_control`
  path, and `control.env` (operator-owned) is left in place.
- RF-004: Evidence recorded in the PR: full local battery outputs
  (validators, ruff, mypy, full suite) and CI run links at exact-green-head.

## NFR assessment

- NFR-SEC-1 | Area: Security | Target: control-plane and ingestion credentials are fully disjoint; no dual-accept of `SEA_SPEED_API_TOKEN` on the control path; fail-closed on missing control token on both API (HTTP 500) and agent (startup exit) | Validation: separation-matrix unit tests (tests/test_393_control_token_separation.py, tests/test_worker_operator_control.py) plus source absence assertions for the old token in agent/control-unit control context | Evidence: unittest output recorded in the PR | Status: PASS
- NFR-SEC-2 | Area: Security | Target: installer never prints or echoes the control token value and never creates or mutates `control.env`; gate errors name only paths/mode/variable requirements | Validation: installer gate source review + gate marker tests in tests/test_ubuntu_worker_systemd.py | Evidence: unittest output | Status: PASS
- NFR-COMPAT-1 | Area: compatibility | Target: ingestion behavior byte-identical (pinned `require_auth` block and single `Bearer {API_TOKEN}` occurrence in api/app/main.py); `worker/**` and `configure-analytics-profiles.py` untouched | Validation: byte-pin test + `git diff --stat` review | Evidence: diff review recorded in the PR | Status: PASS
- NFR-OPS-1 | Area: operability | Target: operator can provision both token sides before merge from two example files with no secret material in Git; deploy tooling never writes operator-owned env files | Validation: docs review (SEA_SPEED_AUTH_V1.md, deploy/vps/README.md) + update-exact.sh source review (no control.env backup/restore entry) | Evidence: docs diff in PR | Status: PASS
