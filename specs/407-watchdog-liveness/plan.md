# Plan: Watchdog liveness input and fail-safe freshness

- Issue: #407
- Specification: specs/407-watchdog-liveness/spec.md

## Implementation approach

1. RECON-established facts: the canonical renderer
   (`scripts/operations/mediamtx_path_config.py`) managed top-level scalars
   rtsp/rtspAddress/rtmp/hls/webrtc/srt via `set_top_level_scalar` but no
   `api` block; `docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md`
   documents the intended loopback api profile; `camera-relay.sh` renders via
   `ubuntu-relay` and verifies via `verify-reader-auth`; the preview relay
   never invokes the renderer (inline config), so preview behavior cannot
   change; the watchdog conflated "API unavailable" with "path stale" in one
   boolean.
2. Renderer: add `API_RULE_MARKER`/`LOOPBACK_API_ADDRESS`/`LOOPBACK_IP`
   constants, `_require_internal_auth_method`, `_api_rule_lines`,
   `verify_internal_api_rule` (authMethod internal, api yes, apiAddress
   loopback literal, exactly one marker, loopback ip subset, api action) and
   `ensure_internal_api_rule` (insert at the top of `authInternalUsers`,
   idempotent, drift → ConfigError). Wire into `render_ubuntu_relay` after
   the reader rule; extend the RENDERED evidence line with
   `api=loopback-watchdog`.
3. Watchdog: replace `_path_ready` (bool) with `_path_state` (READY / STALE /
   UNAVAILABLE). curl exit codes 6/7/28/35/56 (transport-level: resolve,
   refused, timeout, TLS, recv) → UNAVAILABLE; any other non-zero exit with
   --fail is an HTTP-level response from a live endpoint (e.g. 404) → STALE;
   non-JSON / non-object / corrupt ready·available·inboundBytes fields →
   UNAVAILABLE; valid object not ready/available → STALE; growth → READY.
   `run_once` gains the fail-safe UNKNOWN/UNAVAILABLE/NOOP branch (no probe,
   no restart, no state write); post-restart verification distinguishes
   UNAVAILABLE (WatchdogError) from STALE (existing message). #412
   precheck-before-enable is not touched.
4. Tests: extend the watchdog battery with the tri-state classification table
   and fail-safe run_once scenarios; add `UbuntuRelayApiBlockTests` to the
   renderer battery (render/idempotency/drift/non-relay-modes); keep the
   live-API rc=22 STALE cooldown/restart scenarios pinned unchanged.
5. `camera-relay.sh`: zero change — verified by reading the install path;
   `verify-reader-auth` is marker-scoped and passes next to the api rule.

## Architecture

- The api profile is data rendered by the existing scalar/rule machinery:
  `api`/`apiAddress` ride `set_top_level_scalar` (inserted before `paths`,
  idempotent like the other scalars) and the api rule reuses the
  authInternalUsers block bounds/parse helpers, inserted at the top of the
  block so existing reader-rule parsing (marker-scoped) is unaffected.
- The watchdog classification is a pure function of the two API samples:
  transport failure and uninterpretable evidence collapse to UNAVAILABLE
  (fail-safe NOOP); only affirmative live-API evidence can produce STALE.
  The restart flow, cooldown and state file semantics are unchanged.
- Loopback-only exposure is enforced in two layers: the rendered
  `apiAddress` literal (127.0.0.1:9997) and the rule-level loopback ip subset
  check in `verify_internal_api_rule`.

## Decisions

- D-1: Render the api block in the canonical `ubuntu-relay` mode rather than
  hand-editing the box config — the box config is wiped on the next re-render
  (issue #407 design-intended fix; durable).
- D-2: No new CLI flags for the api block: the profile is a fixed,
  documented constant (docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md),
  so there is no caller input to validate and no preview switch to misuse.
- D-3: Preview stays api-less: the preview relay never calls this renderer,
  and non-relay modes are pinned api-less by tests (#373 research honored).
- D-4: HTTP-level errors from a live endpoint (curl 22, e.g. 404
  path-not-found) classify STALE — the API answered, and a missing path is
  the producer being down, which the restart flow is designed to fix; this
  preserves the pre-existing rc=22 semantics and tests.
- D-5: Transport-level curl failures (6/7/28/35/56) and uninterpretable 2xx
  bodies classify UNAVAILABLE → NOOP — the #407 fail-safe mandate: never
  assume stale from a dead or unreadable input.
- D-6: `camera-relay.sh` zero-diff: the renderer change is invisible to the
  script's interface (same modes, same flags) and its verification passes
  with the extra rule.

## Affected contours

- Ubuntu Worker/relay: `deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py`
  (runtime behavior), `scripts/operations/mediamtx_path_config.py`
  (classified CONTROL_PLANE by the change-control policy; renders worker
  relay config), the two focused test files, this SDD trio (+ durable
  progress file outside the repo tree).
- `deploy/worker/ubuntu/camera-relay.sh` deliberately unchanged (D-6).
- No change to `api/**`, `frontend/**`, `worker/**`, `.github/**`,
  `deploy/vps/**`, preview-relay behavior, systemd timer/service units.

## Validation

- Full suite on head branch: green (exact counts in the verification
  transcript and tasks.md AC-6).
- New/changed batteries verbose: watchdog fail-safe + renderer api-block
  tests green.
- `bash -n` on changed shell files: none changed; zero-diff verified by
  inspection of the camera-relay.sh install path.
- ruff (`scripts/quality/ruff.toml`) on the changed Python files: clean.
- `python3 scripts/ci/validate_sdd.py`: green.

## Runtime feedback

- RF-001: Operator actions expected: 0 — the next operator-scheduled relay
  re-render (`camera-relay.sh prepare`/`activate`) durably installs the api
  block; the watchdog fail-safe takes effect on the next installed-copy
  refresh (#406).
- RF-002: Evidence: renderer `api=loopback-watchdog` token;
  watchdog `CAMERA1_H264_LIVENESS_INPUT=UNAVAILABLE` + `RECOVERY=NOOP` when
  the input is down (instead of the #407 false-positive STALE restart loop).

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from
  `scripts/ci/validate_change_contract.py` `classify_file`/`derive_impact`
  over the changed-file set —
  `deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py` and
  `deploy/worker/ubuntu/camera-relay.sh` classify UBUNTU_WORKER,
  `scripts/operations/mediamtx_path_config.py` classifies CONTROL_PLANE;
  `derive_impact` returns UBUNTU_WORKER (runtime contours {UBUNTU_WORKER}),
  matching the 406 precedent that the Ubuntu Worker contour derives a full
  risk profile.
- RISK-001 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: the fail-safe branch makes "input unavailable" a NOOP — the #407 restart-loop trigger (disabled API → deterministic false-positive STALE) is removed at the code level, and the durable api render removes the root cause at the config level; cooldown and single-restart-per-cycle semantics are unchanged for live-API staleness | Validation: executed fail-safe scenarios (refused/timeout/non-object → NOOP, no ffmpeg, no restart, no state write) and live-API STALE/restart scenarios still green | Residual risk: LOW — an operator who enables the timer before re-rendering the config now sees UNKNOWN/NOOP logs instead of restarts (honest degradation, intended) | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: SEC | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: the REST API binds 127.0.0.1:9997 only and the api permission is restricted to the loopback source ip inside authInternalUsers; no credentials are introduced; MediaMTX is loopback-exposed only per the documented remediation (no proxy tuple forwards 9997) | Validation: verify_internal_api_rule pins (apiAddress literal, loopback ip subset, api action only) executed on rendered candidates | Residual risk: LOW — any process on the worker host can query path metadata (no secrets in path state); accepted per the documented remediation profile | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: DATA | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the watchdog writes state only on an actual restart attempt (unchanged); the fail-safe branch writes nothing; the renderer only adds loopback config fields and never touches protected env sources or path sources | Validation: fail-safe scenarios assert no state.json creation; renderer idempotency asserts byte-identical re-render | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: curl exit-code classification (22 = live HTTP answer → STALE vs 6/7/28/35/56 = transport failure → UNAVAILABLE) is pinned by an executed classification table; drift of an existing api rule fails the render closed instead of silently diverging | Validation: test_path_state_classification_table (20 subTests) and test_api_rule_drift_is_rejected | Residual risk: LOW — an exotic curl failure mode outside the pinned exit codes would classify STALE (restart with cooldown) rather than NOOP; bounded by the existing cooldown | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_connection_refused_is_fail_safe_no_restart + test_connection_timeout_is_fail_safe_no_restart (UNKNOWN/UNAVAILABLE/NOOP, no ffmpeg probe, no systemctl restart, no state file)
- TEST-002 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_non_object_body_is_fail_safe_no_restart (live 2xx garbage is not an affirmative stale answer) + test_unavailable_input_wins_over_stale_second_sample
- TEST-003 | Covers: RISK-004 | Level: unit | Priority: P0 | Evidence: test_path_state_classification_table (transport codes 6/7/28 → UNAVAILABLE; live 22/404, not-ready, frozen/decreasing inboundBytes → STALE; corrupt ready/available/inboundBytes → UNAVAILABLE; growth → READY)
- TEST-004 | Covers: RISK-004 | Level: unit | Priority: P0 | Evidence: test_ubuntu_relay_renders_loopback_api_block + test_api_block_survives_re_render_idempotently (byte-identical re-render, set_top_level_scalar idempotent) + test_api_rule_drift_is_rejected (drifted action/ip/authMethod → ConfigError)
- TEST-005 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_ubuntu_relay_renders_loopback_api_block (apiAddress literal + loopback ips + action api + verify_internal_api_rule + verify_internal_reader_rule) + test_non_relay_modes_do_not_render_the_api_block (reader-rule and vps-switch outputs api-less)
- TEST-006 | Covers: RISK-001 | Level: integration | Priority: P0 | Evidence: existing live-API battery preserved green — test_curl_failure_within_cooldown_is_stale_without_restart, test_curl_failure_without_state_recovers_and_verifies_growth, test_identical_inbound_bytes_recovers_via_restart, test_growing_inbound_bytes_is_pass_noop, test_v1191_source_pins; full pytest suite green

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: canonical Issue #407 Outcome Contract scope; allowed paths (renderer, watchdog, focused tests, SDD trio, progress file) enforced before first write
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: the watchdog ships to the host through the existing #406 installed-copy refresh (backup-before-mutation) and the api block through the existing operator-scheduled camera-relay.sh prepare/activate candidate flow with root-only backups; no new deployment machinery introduced
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: prior installed watchdog bytes and prior MediaMTX config preserved | Retry: NO | Rollback: the #406 transactional refresh restores prior installed-copy bytes and aborts activation closed; the relay candidate flow preserves a root-only config backup for an explicit rollback decision (automatic rollback intentionally not authorized there) | Evidence: tests/test_ubuntu_worker_installed_copy_refresh.py (unchanged, still green) for the watchdog transport; camera-relay.sh activate backup flow unchanged
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: rendered candidate verified by verify_internal_api_rule + verify_internal_reader_rule before activation; watchdog fail-safe behavior pinned by executed tests before deploy
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: no new state — the watchdog writes restart state only on an actual restart attempt (unchanged), the fail-safe branch writes nothing
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond existing candidate/backup temporaries | Retry: NO | Rollback: NONE | Evidence: existing candidate temp-file cleanup in write_candidate and relay state-root handling unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: renderer api=loopback-watchdog token; watchdog CAMERA1_H264_FRESHNESS=UNKNOWN + CAMERA1_H264_LIVENESS_INPUT=UNAVAILABLE + RECOVERY=NOOP lines when the input is down
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: deployed watchdog rollback rides the #406 installed-copy backup/restore; config rollback rides the camera-relay.sh root-only backup; the fail-safe branch itself is restart-free so it cannot compound a failure | Evidence: unchanged #406 refresh fault-path suite + relay backup flow
