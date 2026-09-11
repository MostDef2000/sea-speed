# Plan: Water camera RTSP 461 — configurable transport and credentials out of argv (#384)

- Specification: specs/384-water-rtsp-udp/spec.md
- Issue: #384
- Runtime contour: Ubuntu Worker/relay (`deploy/worker/ubuntu/**`, `worker/ubuntu_worker_entrypoint.py`); VPS NOT APPLICABLE

## Architecture

- `deploy/worker/ubuntu/camera1-h264-transcode.sh` (`run` mode): transport comes from
  `CAMERA1_RTSP_TRANSPORT` (default `udp`; strict `udp|tcp|automatic` validation).
  The credential-bearing `HLS_URL` is written into a 0600 ffconcat file
  (`/tmp/camera1-h264-input.ffconcat.XXXXXX`, PrivateTmp of the `sea-speed` service)
  with `option rtsp_transport <transport>` and `file '<url>'`; stale files are removed
  first. ffmpeg argv contains only the ffconcat path (`-f concat -safe 0 -i`), never
  the camera URL. Publish target `rtsp://<publish>:8554/cam1-h264` is credential-free.
- `worker/ubuntu_worker_entrypoint.py`: new helpers `_credential_bearing`,
  `_camera1_rtsp_transport`, `_write_rtsp_ffconcat_input`. `_spawn_rtsp_ffmpeg`
  branches: credential-bearing RTSP input → ffconcat input argv (transport inside the
  file); non-credential private-relay input → unchanged `-rtsp_transport tcp -i <url>`.
  The ffconcat file name is per-profile (`sea-speed-rtsp-input-<profile>.ffconcat`)
  so the water and road services never collide.
- `deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py`: the fixed source probe
  constant moves from the dead relay leg `cam1` to the product path `cam1-h264`
  (same target the VPS watchdog and the REST freshness check already use). The
  no-argument, no-environment-override contract is unchanged; the probe stays tcp
  against the local MediaMTX.
- `worker.env.example` documents `CAMERA1_RTSP_TRANSPORT=udp`; `road-worker.env.example`
  documents that relay reads always use tcp regardless of the knob.

## Decisions

- Transport selection rule: credential-bearing URL ⇒ direct Camera 1 read ⇒
  `CAMERA1_RTSP_TRANSPORT` (default `udp`); no credentials ⇒ private relay read ⇒
  fixed `tcp`. This keeps road/relay behavior byte-identical and satisfies the
  out-of-scope `test_worker_rtsp_media_security` contract (both `"-rtsp_transport"`
  and `"tcp"` remain in the entrypoint source).
- ffconcat (`option rtsp_transport <t>` + `file '<url>'`, ffmpeg ≥ 4.2; Worker runs
  Ubuntu 26.04 with ffmpeg 8.x) instead of passing the URL in argv. No silent
  fallback to argv: if ffconcat fails at runtime the deploy transaction surfaces it
  and rollback applies — deterministic behavior over silent security downgrade.
- URLs containing single quotes are rejected (ffconcat quoting hazard) — pathological
  for camera URLs; fails fast with a clear error.
- Watchdog probes the product path (`cam1-h264`), not the legacy `cam1` relay leg:
  the relay leg depends on MediaMTX rendering outside this scope and no longer has
  consumers after this fix; probing the product path makes the restart-recovery loop
  self-consistent.
- Reader consolidation (Variant C) stays OUT of this scope as a separate follow-up.

## Affected contours

- Ubuntu Worker/relay only: `deploy/worker/ubuntu/camera1-h264-transcode.sh`,
  `deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py`,
  `worker/ubuntu_worker_entrypoint.py`, `deploy/worker/ubuntu/worker.env.example`,
  `deploy/worker/ubuntu/road-worker.env.example`, two test files, `specs/384-water-rtsp-udp/*`.
- VPS: NOT affected. Runtime contour: Ubuntu Worker. Production safety envelope: REQUIRED.

## Validation

- `python3 -m unittest discover -s tests -p "test_*.py"` (full suite, previously 644 green).
- `python3 scripts/ci/validate_sdd.py`, `validate_repo.py`, `validate_contracts.py`,
  `scripts/quality/validate_quality_contracts.py`, `scripts/quality/validate_workflow_policy.py`.
- `bash -n deploy/worker/ubuntu/camera1-h264-transcode.sh`.
- New tests: entrypoint transport helper behavior (defaults, override, invalid value,
  ffconcat file mode/content), transcode.sh shell contract (no credentials in argv,
  ffconcat usage), watchdog source pin (`cam1-h264`).
- Operator RUNTIME-MANUAL (autonomous deploy evidence): journal without 461, service
  active without restart growth, ffprobe from VPS, dashboard cam20/cam16+, `ps` argv
  without credentials.

## Runtime feedback

- Root cause (observed 2026-09-11): camera stopped accepting TCP-interleaved RTSP
  (SETUP → 461) while UDP works; all Sea Speed readers pinned tcp. Watchdog false
  failures came from probing the dead `cam1` relay leg; transcode crash-loop from the
  tcp camera pull; credentials exposed via argv.

## Risk profile

- Risk profile: REQUIRED

- RISK-384-001 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: ffconcat 0600 file with O_NOFOLLOW|O_EXCL in service PrivateTmp; stale-file cleanup before create; URL never in argv; no single-quote URLs; no silent argv fallback | Validation: TEST-384-001/002 | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-384-002 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: ffconcat `option` directive is documented ffmpeg behavior (≥4.2; Worker has ffmpeg 8.x); deterministic failure surfaces in deploy verification; deployment rollback to previous release | Validation: TEST-384-001..004 + runtime acceptance | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-384-003 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: strict knob validation (`udp|tcp|automatic`), fail-fast error before ffmpeg start; documented in both env examples | Validation: TEST-384-003 | Residual risk: LOW | Owner: operator | Status: MITIGATED
- RISK-384-004 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: relay/road tcp path byte-identical; watchdog probe pinned to product path by unit test; out-of-scope contracts untouched and re-verified by full suite | Validation: TEST-384-004/005 | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-384-005 | Category: TECH | Probability: 1 | Impact: 1 | Score: 1 | Mitigation: two concurrent camera sessions remain until reader consolidation (accepted minimal-variant trade-off, user-informed); consolidation recorded as follow-up | Validation: scope decision in #384 | Residual risk: ACCEPTED | Owner: operator | Status: ACCEPTED

## Test design

- TEST-384-001 | Covers: AC-004, R2 | Level: unit | Priority: P0 | Evidence: tests/test_camera1_live_replacement.py::WaterRtspTransportTests::test_entrypoint_transport_helpers_behavior — defaults (relay→tcp, credential→udp), env override, invalid value raises, ffconcat file 0600 + `option rtsp_transport` + `file '<url>'`, single-quote rejection
- TEST-384-002 | Covers: AC-004, R1 | Level: integration | Priority: P0 | Evidence: tests/test_camera1_live_replacement.py::WaterRtspTransportTests::test_transcode_run_hides_credentials_and_configures_transport — `bash -n` + no `-i "$HLS_URL"` in argv, ffconcat + transport + 0600 + stale cleanup present
- TEST-384-003 | Covers: NFR-384-004, R1/R2 | Level: unit | Priority: P1 | Evidence: tests/test_camera1_live_replacement.py::WaterRtspTransportTests::test_entrypoint_transport_knob_and_ffconcat_contract — knob name, default `udp`, ffconcat markers, O_NOFOLLOW
- TEST-384-004 | Covers: R3 | Level: unit | Priority: P0 | Evidence: tests/test_camera1_h264_freshness_watchdog.py::test_worker_source_probe_targets_product_path_cam1_h264 — worker watchdog source constant pinned to `cam1-h264`
- TEST-384-005 | Covers: NFR-384-003 | Level: unit | Priority: P0 | Evidence: full unittest suite incl. unchanged `test_worker_rtsp_media_security.py` (tcp strings preserved) and `test_camera1_h264_freshness_watchdog.py`

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: reader consolidation (Variant C) as a separate future task

## Deployment transaction audit

- TX-384-01 | Stage: ADMISSION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: scope recorded in #384 | Retry: NONE | Rollback: NONE | Evidence: Sea Speed Delivery Checkpoint v2 in #384
- TX-384-02 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: branch unchanged | Retry: NONE | Rollback: NONE | Evidence: branch agent/384-water-rtsp-udp from origin/main 2a0b6f1
- TX-384-03 | Stage: MUTATION | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: working tree revertible | Retry: NONE | Rollback: git revert of the feature commit | Evidence: transcode.sh + watchdog.py + entrypoint.py + env examples + tests
- TX-384-04 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: CI red blocks merge | Retry: rerun failed jobs | Rollback: NONE | Evidence: required CI green on PR exact head
- TX-384-05 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: main protected, revert merge | Retry: NONE | Rollback: revert merge commit | Evidence: exact-green-head squash merge to main
- TX-384-06 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: issue remains open | Retry: NONE | Rollback: NONE | Evidence: #384 updated at meaningful transitions
- TX-384-07 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: re-run evidence collection | Retry: NONE | Rollback: NONE | Evidence: deployment-manifest + execution-audit v1 from deploy-ubuntu-worker; Change Contract Ubuntu REQUIRED / VPS NOT
- TX-384-08 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: previous release restored by deploy-authorized rollback target | Retry: NONE | Rollback: revert merge + redeploy prior good main commit | Evidence: deploy-authorized.sh owns target rollback; main revert restores source
