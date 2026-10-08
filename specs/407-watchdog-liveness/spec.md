# Spec: Watchdog liveness input and fail-safe freshness

- Issue: #407
- Specification: specs/407-watchdog-liveness/spec.md

## Product outcome

The camera1-h264 freshness watchdog's ONLY freshness input is the MediaMTX
REST API (`http://127.0.0.1:9997/v3/paths/get/cam1-h264`). In the deployed
environment that API is disabled (the repo-rendered config never carried an
`api` block), so `_path_ready` always answered False and the watchdog
deterministically false-positived STALE — restarting the transcode in a loop
whenever the timer is enabled. Hand-editing the box config is rejected: it is
wiped on the next re-render.

This change makes the liveness input durable and fail-safe:

1. The canonical renderer's ubuntu-relay profile
   (`scripts/operations/mediamtx_path_config.py`) durably renders the loopback
   API profile documented in
   `docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md`: `api: yes`,
   `apiAddress: "127.0.0.1:9997"` and one loopback `authInternalUsers` rule
   (`- user: any / ips: ["127.0.0.1"] / permissions: [- action: api]`). The
   block is idempotent (preserved across re-renders like the other top-level
   scalars), drift-checked (a diverging existing rule is a ConfigError), and
   bound to loopback only. `camera-relay.sh` needs no wiring change: its
   `prepare`/`activate` already render and verify through the
   `ubuntu-relay`/`verify-reader-auth` modes, and the reader-auth verification
   stays valid next to the api rule.
2. Every other renderer mode (vps-switch, vps-cleanup, vps-set-hls-address,
   verify-reader-auth, ubuntu-transcode-reader) and the preview-relay context
   keep byte-identical output: the preview profile stays api-less (#373).
3. The Ubuntu watchdog
   (`deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py`) is hardened to
   fail safe: liveness-input-unavailable (connection refused, timeout,
   unresolvable host) or uninterpretable evidence (non-JSON/non-object body,
   corrupt ready/available/inboundBytes fields) reports
   `CAMERA1_H264_FRESHNESS=UNKNOWN` + `CAMERA1_H264_LIVENESS_INPUT=UNAVAILABLE`
   + `CAMERA1_H264_RECOVERY=NOOP` and never restarts the transcode. Only an
   affirmative answer from a LIVE API (valid path object that is not
   ready/available, does not grow inboundBytes between samples, or an
   HTTP-level error response such as 404 path-not-found from the live
   endpoint) classifies the path STALE and may drive recovery. The #412
   precheck-before-enable discipline is untouched.

## User scenarios

- US-1: The timer is enabled on the worker; the rendered MediaMTX config
  durably serves the loopback REST API; the watchdog observes the live
  cam1-h264 path and reports PASS/NOOP on a healthy stream — no restart loop.
- US-2: The MediaMTX REST API is down or unreachable (connection refused /
  timeout): the watchdog logs UNKNOWN/UNAVAILABLE/NOOP and never restarts the
  transcode — a disabled liveness input can no longer manufacture a
  false-positive STALE.
- US-3: The API is live and affirmatively reports the path stale (not ready,
  or inboundBytes frozen between samples): the watchdog follows the existing
  cooldown → source precheck → restart flow.
- US-4: A re-render of the relay config (operator re-runs
  `camera-relay.sh prepare`/`activate`) preserves the api block byte-identically
  and refuses drifted hand-edits of the api rule.
- US-5: The preview relay (api-less profile) re-renders: its output is
  unchanged — no api key, no api block.

## Scope

- `scripts/operations/mediamtx_path_config.py`: loopback API profile
  constants, `verify_internal_api_rule`, `ensure_internal_api_rule`, and the
  ubuntu-relay render wiring (`api`/`apiAddress` scalars + api rule +
  `api=loopback-watchdog` evidence token). Other modes untouched.
- `deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py`: tri-state
  liveness classification (`_path_state`: READY/STALE/UNAVAILABLE), fail-safe
  NOOP branch in `run_once`, post-restart verification distinguishing
  UNAVAILABLE from STALE, module docstring contract.
- `tests/test_camera1_h264_freshness_watchdog.py`: tri-state classification
  table, fail-safe noop tests (refused/timeout/non-object), updated
  `_path_ready`→`_path_state` pins; live-API STALE/restart tests preserved.
- `tests/test_camera1_live_replacement.py`: new
  `UbuntuRelayApiBlockTests` (api block rendered, idempotent across
  re-render, drift rejected, non-relay modes api-less).
- `tests/test_vps_transcode_to_ubuntu.py`: one documented anchor update in
  `test_missing_source_fails_before_restart` — the stubbed curl payload
  changes from a legacy corrupt body (`{"state": "ready", "lastFrameTime":…}`)
  to an affirmative stale v1.19.1 body, because the #407 fail-safe now
  classifies corrupt/legacy evidence as UNAVAILABLE (NOOP) rather than STALE;
  the test's intent (a failed source precheck blocks the restart) is
  preserved and no assertion is weakened.
- `deploy/worker/ubuntu/camera-relay.sh`: no change (zero-diff verified:
  render/verify modes already cover the new block).
- This SDD trio and the durable progress file.
- Out of scope: `deploy/vps/**` (the VPS watchdog copy is a separate contour),
  `api/**`, `frontend/**`, `.github/**`, preview-relay api enablement (#373
  keeps preview api-less), hand-edited box configs.

## Requirements

- R-1: The ubuntu-relay rendered config durably carries `api: yes`,
  `apiAddress: "127.0.0.1:9997"` and exactly one loopback api rule in
  `authInternalUsers`, bounded to the documented profile.
- R-2: The api block is idempotent across re-renders (byte-identical second
  render) and drift of an existing api rule fails the render closed
  (ConfigError).
- R-3: Non-relay renderer modes and the preview-relay context keep
  byte-identical output (no api block, no api key).
- R-4: When the liveness input is unavailable (curl exit 6/7/28/35/56) the
  watchdog reports UNKNOWN/UNAVAILABLE/NOOP, writes no restart state, and
  never restarts the transcode.
- R-5: Uninterpretable evidence from a 2xx response (non-JSON, non-object,
  corrupt ready/available/inboundBytes) is treated as UNAVAILABLE, never as
  STALE.
- R-6: Only an affirmative answer from a LIVE API classifies STALE: a valid
  path object that is not ready/available, does not grow inboundBytes, or an
  HTTP-level error response (e.g. 404) from the live endpoint; the existing
  cooldown → source precheck → restart flow and the #412 precheck-before-enable
  discipline are preserved.

## Acceptance criteria

- AC-1: The ubuntu-relay candidate contains the documented loopback api block
  and passes `verify_internal_api_rule` plus `verify_internal_reader_rule`.
- AC-2: A second render over a rendered candidate is byte-identical
  (idempotent) and a drifted api rule is rejected with ConfigError.
- AC-3: vps-switch output and direct reader-rule rendering contain no api
  block and no api marker (preview profile stays api-less).
- AC-4: Connection refused and connection timeout produce
  UNKNOWN/UNAVAILABLE/NOOP with no ffmpeg probe and no systemctl restart.
- AC-5: A live API with a non-object body produces UNKNOWN/UNAVAILABLE/NOOP;
  live-API stale evidence (frozen inboundBytes, not-ready path, 404) still
  drives the existing cooldown/restart flow.
- AC-6: Full pytest suite green; `bash -n` clean on changed shell files (none
  changed — zero-diff verified for camera-relay.sh); ruff clean on changed
  Python files; `validate_sdd.py` green.

## Runtime feedback

- RF-001: Operator actions expected: 0 on deploy — the api block reaches the
  worker through the existing `camera-relay.sh prepare`/`activate` render flow
  and the watchdog through the #406 installed-copy refresh; a config
  re-render is operator-scheduled as today.
- RF-002: Failure evidence: watchdog lines
  `CAMERA1_H264_FRESHNESS=UNKNOWN` + `CAMERA1_H264_LIVENESS_INPUT=UNAVAILABLE`
  + `CAMERA1_H264_RECOVERY=NOOP` when the input is down (previously a
  false-positive STALE restart); success evidence is
  `CAMERA1_H264_FRESHNESS=PASS` + `api=loopback-watchdog` in the renderer
  output.

## NFR assessment

- NFR-001 | Area: reliability/operations | Target: the transcode is never restarted because the liveness input is down — a disabled/refused/timed-out REST API yields UNKNOWN/UNAVAILABLE/NOOP, and only a live-API affirmative answer can drive STALE recovery (issue #407 false-positive STALE class closed) | Validation: executed tri-state classification table (transport exit codes 6/7/28 vs live HTTP 22; corrupt-evidence cases) plus run_once fail-safe scenarios (refused, timeout, non-object body — no ffmpeg, no restart, no state write) | Evidence: tests/test_camera1_h264_freshness_watchdog.py — test_path_state_classification_table, test_connection_refused_is_fail_safe_no_restart, test_connection_timeout_is_fail_safe_no_restart, test_non_object_body_is_fail_safe_no_restart, test_unavailable_input_wins_over_stale_second_sample | Status: PASS
- NFR-002 | Area: configuration durability | Target: the loopback api profile is durably rendered by the canonical renderer (not hand-edited on the box) and survives re-renders idempotently; drifted existing rules fail the render closed | Validation: executed CLI renders (first render, re-render byte-identical, drift/loopback/authMethod rejection) | Evidence: tests/test_camera1_live_replacement.py — test_ubuntu_relay_renders_loopback_api_block, test_api_block_survives_re_render_idempotently, test_api_rule_drift_is_rejected | Status: PASS
- NFR-003 | Area: security | Target: the REST API binds loopback only (`apiAddress: "127.0.0.1:9997"`) with a loopback-source-ip-only api permission inside authInternalUsers; no credential material is introduced; every other renderer mode and the preview profile stay byte-identical and api-less | Validation: rendered-candidate pins (apiAddress literal, ips loopback subset check in verify_internal_api_rule, action api only) plus non-relay-mode negative assertions | Evidence: tests/test_camera1_live_replacement.py — test_ubuntu_relay_renders_loopback_api_block, test_non_relay_modes_do_not_render_the_api_block | Status: PASS
- NFR-004 | Area: compatibility | Target: existing watchdog semantics are preserved where the API is live — READY/NOOP on growth, COOLDOWN suppression, STALE → source precheck → restart with post-restart growth verification, #412 precheck-before-enable untouched, VPS watchdog module untouched | Validation: full existing watchdog battery (rc=22 cooldown/restart scenarios, growth pins, route pins, source pins) plus full-suite green | Evidence: tests/test_camera1_h264_freshness_watchdog.py — test_curl_failure_within_cooldown_is_stale_without_restart, test_curl_failure_without_state_recovers_and_verifies_growth, test_identical_inbound_bytes_recovers_via_restart, test_growing_inbound_bytes_is_pass_noop, test_v1191_source_pins | Status: PASS

## Deviations from the work order

- None in scope. `deploy/worker/ubuntu/camera-relay.sh` was listed as allowed
  but needs no change: the api block is rendered inside the canonical
  `ubuntu-relay` mode the script already invokes, and `verify-reader-auth`
  remains valid next to the api rule (documented in this spec's Scope).
