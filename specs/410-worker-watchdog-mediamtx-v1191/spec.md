# Spec: Ubuntu Camera 1 H264 freshness watchdog for MediaMTX v1.19.1 REST API

- Issue: #410
- Specification: specs/410-worker-watchdog-mediamtx-v1191/spec.md

## Product outcome

The deployed Ubuntu worker freshness watchdog
(`deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py`) is incompatible with
MediaMTX v1.19.1: it polls `GET /v3/paths/cam1-h264` (404 in v1.19.1) and gates on
`state == "ready"` plus `lastFrameTime`, neither of which exists in the v1.19.1
response. `_path_ready()` therefore always returns false, so the 30 s timer would
report STALE on every run and cyclically restart the Camera 1 H264 transcode
producer (the timer is currently disabled as a protective measure).

This change makes the watchdog compatible with the operator-verified v1.19.1 API:
observation via `GET /v3/paths/get/{name}` with fail-closed `ready`/`available`
gates and producer-liveness freshness proven by a strict `inboundBytes` increase
between two samples. The entry contract (root only, no arguments, no environment
overrides), source probe, cooldown/state logic, lock logic, restart boundary
(only the fixed local Camera 1 H264 transcode producer service) and printed
output labels of `run_once` stay unchanged. The legacy `cam1` relay leg remains
unconsulted.

## User scenarios

- US-1: The producer publishes normally; two API samples show `ready`,
  `available` and growing `inboundBytes`, so the watchdog reports
  `CAMERA1_H264_FRESHNESS=PASS` with `CAMERA1_H264_RECOVERY=NOOP` and performs no
  restart.
- US-2: The API is unreachable or returns 404 (as with the old route), or the
  response lacks `ready`/`available`/`inboundBytes`, or the bytes do not grow;
  the watchdog fails closed and recovery follows the unchanged cooldown and
  restart flow.
- US-3: The transcode producer dies; inboundBytes stops growing; the watchdog
  probes the source, restarts only the fixed transcode service within the
  existing cooldown discipline, and verifies recovery with two further growing
  samples.

## Requirements

- R-1: `_path_ready` must poll
  `GET {MEDIAMTX_API}/v3/paths/get/{CAMERA1_H264_PATH}` twice with
  `sleeper(SAMPLE_SECONDS)` between samples, keeping per-call
  `_run_fixed(..., timeout=10)`.
- R-2: A sample is ready only when curl succeeds, the body parses as JSON,
  `ready is True`, `available is True` and `inboundBytes` is a non-boolean,
  non-negative integer; overall readiness additionally requires the second
  `inboundBytes` to be strictly greater than the first (`readyTime` must not be
  used as a freshness signal).
- R-3: All failure modes (non-zero curl returncode, unparseable JSON, missing
  gates, missing/invalid/non-growing `inboundBytes`) fail closed to not-ready and
  reuse the unchanged cooldown/recovery semantics.
- R-4: `run_once` must pass its injectable sleeper to both `_path_ready` call
  sites; the dead `STALE_SECONDS` constant and its only consumer (the
  `lastFrameTime` age check) are removed without touching `SAMPLE_SECONDS` or
  `COOLDOWN_SECONDS` semantics.
- R-5: No change to the ffmpeg source probe, cooldown/state-file logic, lock
  logic, systemctl restart flow, printed output lines/labels of `run_once`, the
  `main()` contract, the VPS watchdog copy or its units, transcode/relay scripts,
  installer, or workflows.
- R-6: The remediation document gains the Ubuntu Worker relay API profile
  (loopback-only `api` enablement as a deliberate exception) and the feature is
  tracked by this SDD trio.

## Acceptance criteria

- AC-001: Every curl argv issued by the ubuntu watchdog contains
  `/v3/paths/get/cam1-h264` and no argv contains the exact legacy route
  `/v3/paths/cam1-h264`; these pins fail against the base script.
- AC-002: With two samples whose `inboundBytes` strictly grow, `run_once` returns
  `CAMERA1_H264_FRESHNESS=PASS` and `CAMERA1_H264_RECOVERY=NOOP`.
- AC-003: Non-zero curl returncode (simulated 404), identical `inboundBytes`,
  `ready: false`, missing `available`, non-integer `inboundBytes` and invalid
  JSON all fail closed; within cooldown no restart is attempted.
- AC-004: The diff touches only the ubuntu watchdog script, its test file, the
  remediation document and this SDD trio; ffmpeg probe, cooldown, lock, restart
  flow, output labels and `main()` are byte-identical in behaviour.
- AC-005: The remediation document documents the Ubuntu Worker relay API profile
  with loopback-only mitigation and no credentials.
- AC-006: After production deploy, the installed watchdog reports
  `CAMERA1_H264_FRESHNESS=PASS` against the live v1.19.1 API.

## Runtime feedback

- RF-001: Operator actions expected: 0; the deploy transaction refreshes the
  installed watchdog copy autonomously.
- RF-002: Health is observable via `systemctl status
  sea-speed-camera1-h264-freshness.service` and the `CAMERA1_H264_*` output
  lines of a watchdog run.

## NFR assessment

- NFR-001 | Area: reliability | Target: watchdog reports ready only on proven v1.19.1 producer liveness (ready+available+inboundBytes growth) | Validation: unit tests with the verbatim operator fixture | Evidence: tests/test_camera1_h264_freshness_watchdog.py | Status: PASS
- NFR-002 | Area: compatibility | Target: exact v1.19.1 route /v3/paths/get/{name} and response schema | Validation: route argv pins demonstrated RED against base script and GREEN after change | Evidence: UbuntuWatchdogMediaMTXV1191Tests | Status: PASS
- NFR-003 | Area: security | Target: no credentials and no new network exposure | Validation: source review; API use stays loopback read-only per remediation doc | Evidence: docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md | Status: PASS
- NFR-004 | Area: operability | Target: fail-closed on 404, no-growth, malformed or gate-missing responses with unchanged cooldown semantics | Validation: fail-closed unit tests including cooldown run | Evidence: test_curl_failure_within_cooldown_is_stale_without_restart | Status: PASS
- NFR-005 | Area: reversibility | Target: single-file behaviour change revertible without state migration | Validation: diff scope review; state file format unchanged | Evidence: PR exact changed-file list | Status: PASS
