# Delivery Tasks: Cutover tooling transcode path and HLS port

- Specification: specs/076-cutover-tooling-transcode-path-hls-port/spec.md
- Issue: #335 (follow-up)
- Status: Source implementation

## Delivery tasks

- T-001 [x] Confirm Issue #335 DONE state, current `main`, unique SDD prefix `076`, visible six-field Scope and immediately following `OUTCOME APPROVED` source authorization for this follow-up.
- T-002 [x] Add `paths: cam1-h264:` publisher block (`source: "publisher"`, `sourceOnDemand: no`) inside `render_ubuntu_transcode_reader` via the existing `set_path_source` helper.
- T-003 [x] Keep the least-privilege reader+publish rule for `cam1-h264` in `render_ubuntu_transcode_reader` and its verification.
- T-004 [x] Derive `hls_check_url` from `--hls-address` in `camera-source-switch.sh` (`:port` and `host:port` forms), overriding the `:8888` default.
- T-005 [x] Disable retired external units before `install_candidate` restarts MediaMTX in `activate` (removes `:18889` bind conflict).
- T-006 [x] Pin live config to `root:mediamtx` / `0640` in `install_candidate` before restart.
- T-007 [x] Extend `tests/test_vps_transcode_to_ubuntu.py` to assert the `cam1-h264` publisher path bytes.
- T-008 [x] Run `bash -n`, `scripts/ci/validate_repo.py`, `scripts/ci/validate_sdd.py` and the full unit suite; all pass.
- T-009 [ ] Open linked PR with Change Contract (VPS deployment NOT REQUIRED, Ubuntu worker/relay update NOT REQUIRED, production safety envelope NOT REQUIRED, operator actions expected 0).

## Requirements traceability

- AC-001 | Task: T-002,T-007 | Evidence: unit test asserts `cam1-h264:`, `source: "publisher"`, `sourceOnDemand: no` | Coverage: COVERED
- AC-002 | Task: T-004,T-005,T-006 | Evidence: `bash -n` passes; review of derivation/ordering/perms | Coverage: COVERED
- AC-003 | Task: T-008 | Evidence: `scripts/ci/validate_repo.py` passes on changed tree | Coverage: COVERED
- AC-004 | Task: T-007,T-008 | Evidence: `python3 -m unittest tests/test_vps_transcode_to_ubuntu.py` passes (6 tests) | Coverage: COVERED
- AC-005 | Task: T-009 | Evidence: PR Change Contract declares VPS/Ubuntu NOT REQUIRED, operator actions 0 | Coverage: PENDING

## Definition of Done

- [x] Issue/spec/plan/tasks current — #335 follow-up intent, two tooling defects, risk profile and correct-course record are represented.
- [x] Exact changed-file scope verified — diff is limited to `scripts/operations/mediamtx_path_config.py`, `deploy/vps/camera-source-switch.sh`, `tests/test_vps_transcode_to_ubuntu.py` and the `076` spec artifacts.
- [x] Required tests and evidence complete — renderer unit test extended; `bash -n`, `validate_repo.py`, `validate_sdd.py` and full unit suite pass.
- [ ] Required CI green — PR exact head must pass PR Validation and aggregate Quality, followed by exact-main Quality after merge.
- [ ] Exact-green-head merge complete — merge PR only after fresh base/head/scope/review gate with expected-head protection.
- [x] Deployment state resolved — no VPS/Ubuntu deployment is required; live hosts already carry equivalent manual edits.
- [x] Runtime acceptance resolved — no runtime acceptance required; CONTROL_PLANE tooling change only.
- [x] Risks resolved or explicitly accepted — Risk profile REQUIRED; change is source-only and reuses unit-tested helpers.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`DONE` is forbidden until the exact-head PR Validation and aggregate Quality pass on one head, the exact green head merges with expected-head protection, and exact-main Quality succeeds. No production deployment or runtime acceptance is required because the change is CONTROL_PLANE tooling only and the live hosts already carry equivalent manual edits; the PR simply makes the repository source correct for future cutover re-runs.
