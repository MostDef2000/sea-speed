# Tasks: Watchdog liveness input and fail-safe freshness

- Specification: specs/407-watchdog-liveness/spec.md

## Delivery tasks

- T-407-001: RECON the freshness chain: renderer scalar/rule machinery,
  camera-relay.sh install path, ubuntu watchdog liveness flow, documented
  loopback api profile (docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md),
  existing renderer/watchdog test batteries, and the change-control
  classification for the changed-file set; record findings in the durable
  progress file
- T-407-002: Add the durable loopback api profile to the canonical renderer's
  ubuntu-relay mode: constants, `_require_internal_auth_method`,
  `_api_rule_lines`, `verify_internal_api_rule`, `ensure_internal_api_rule`
  (idempotent top-of-block insertion, drift → ConfigError), wiring in
  `render_ubuntu_relay` (api/apiAddress scalars + api rule +
  `api=loopback-watchdog` evidence token); keep every other mode
  byte-identical; zero camera-relay.sh change
- T-407-003: Harden the ubuntu watchdog fail-safe: `_path_state` tri-state
  (READY/STALE/UNAVAILABLE) with transport-exit-code and evidence-validity
  classification, fail-safe UNKNOWN/UNAVAILABLE/NOOP branch in `run_once`
  (no probe, no restart, no state write), post-restart verification
  distinguishing UNAVAILABLE from STALE; preserve cooldown/precheck/restart
  flow and #412 precheck-before-enable untouched
- T-407-004: Update `tests/test_camera1_h264_freshness_watchdog.py` to the
  tri-state semantics (classification table, unavailable-wins, fail-safe
  noop scenarios) while keeping the live-API STALE/cooldown/restart and
  route/source pins green
- T-407-005: Add `UbuntuRelayApiBlockTests` to
  `tests/test_camera1_live_replacement.py` (api block rendered and verified,
  re-render idempotency, drift rejection on an api-less baseline, non-relay
  modes api-less); apply the one documented anchor update in
  `tests/test_vps_transcode_to_ubuntu.py::test_missing_source_fails_before_restart`
  (legacy corrupt payload → affirmative stale payload, intent preserved)
- T-407-006: Run the verification battery (full pytest, new/changed batteries
  verbose, `bash -n` on changed shell files — none expected, ruff on changed
  Python files, `scripts/ci/validate_sdd.py`) and commit locally with the
  approved author identity; leave the branch unpushed for orchestrator
  admission

## Completion gate

- [ ] T-407-001
- [ ] T-407-002
- [ ] T-407-003
- [ ] T-407-004
- [ ] T-407-005
- [ ] T-407-006
- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned (worker relay re-render installs the api block; watchdog UNKNOWN/NOOP evidence verified post-deploy)
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-004 mitigated or disclosed in plan.md
- [ ] Waivers resolved or current — none

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (watchdog rides the #406 installed-copy refresh; api block rides the operator-scheduled relay re-render)
- [ ] Runtime acceptance resolved — orchestrator-owned (loopback API observed live by the watchdog; NOOP-on-unavailable evidence verified on the worker)
- [ ] Deferred work recorded — none (preview api enablement stays deferred to #373 follow-up by design)
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-004 in plan.md Risk profile
- [ ] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-407-002,T-407-005 | Evidence: test_ubuntu_relay_renders_loopback_api_block (rendered candidate carries api yes + loopback apiAddress + api rule; verify_internal_api_rule + verify_internal_reader_rule pass) | Coverage: COVERED
- AC-2 | Task: T-407-002,T-407-005 | Evidence: test_api_block_survives_re_render_idempotently (byte-identical second render) + test_api_rule_drift_is_rejected (drifted action/ip/authMethod → ConfigError) | Coverage: COVERED
- AC-3 | Task: T-407-002,T-407-005 | Evidence: test_non_relay_modes_do_not_render_the_api_block (reader-rule rendering and vps-switch CLI output api-less) | Coverage: COVERED
- AC-4 | Task: T-407-003,T-407-004 | Evidence: test_connection_refused_is_fail_safe_no_restart + test_connection_timeout_is_fail_safe_no_restart (UNKNOWN/UNAVAILABLE/NOOP, no ffmpeg, no restart, no state write) | Coverage: COVERED
- AC-5 | Task: T-407-003,T-407-004 | Evidence: test_non_object_body_is_fail_safe_no_restart + test_path_state_classification_table (live 404/not-ready/frozen bytes → STALE) + preserved test_curl_failure_without_state_recovers_and_verifies_growth / test_identical_inbound_bytes_recovers_via_restart | Coverage: COVERED
- AC-6 | Task: T-407-006 | Evidence: full pytest suite green; changed batteries verbose green; bash -n clean (no shell file changed — camera-relay.sh zero-diff verified in T-407-002); ruff clean on changed Python files; validate_sdd.py green | Coverage: COVERED
