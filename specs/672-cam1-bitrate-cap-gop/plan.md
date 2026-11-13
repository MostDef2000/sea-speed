# Plan: cam1 transcode bitrate cap + pinned 2 s GOP (worker-side)

- Spec: specs/672-cam1-bitrate-cap-gop/spec.md

## Architecture
Worker-side (Ubuntu) change to the existing cam1 transcode: `deploy/worker/ubuntu/camera1-h264-transcode.sh run` keeps pulling the cam1 relay source over TCP and publishing H264 720p15 to `rtsp://<publish-address>:8554/cam1-h264` on the same MediaMTX. The only change is the ffmpeg argv: between `-tune zerolatency` and the `-f rtsp` publish line it gains the road1-proven bitrate-cap triple (`-b:v 1500k -maxrate 1600k -bufsize 3200k`) and a pinned 2 s GOP (`-g 30 -keyint_min 30`, 30 frames @ 15 fps). MediaMTX remuxes the publish into HLS with ~2 s / ~375 KB segments. Later (outside this chain): lane-B activation updates the script on the Ubuntu worker and restarts the transcode unit; runtime acceptance is measured on the live playlists after that.

## Decisions
- The cap reuses road1's proven triple `-b:v 1500k -maxrate 1600k -bufsize 3200k`: road1 live BANDWIDTH=1485418 proves ~1.5 Mbps delivery through the worst-case pipe, while cam1's uncapped CRF-23 output measured BANDWIDTH=3937309.
- The GOP is pinned to 30 (`-g 30 -keyint_min 30`): at 15 fps that is a 2 s segment cadence, replacing the default libx264 keyint 250 (EXTINF 16.66667, TARGETDURATION:17) that made every fMP4 segment 7.4–8.1 MB; a 2 s ~375 KB segment downloads in ~2 s on the 190 KB/s worst-case pipe.
- Two argv lines only — the smallest complete change: no script restructuring, no renderer/frontend/worker changes, publish path and transaction shape untouched.
- Lane-B activation and runtime acceptance are deferred follow-ups with their own gates; this chain is repo-only.

## Affected contours
- UBUNTU_WORKER: `deploy/worker/ubuntu/camera1-h264-transcode.sh` (two added ffmpeg argv lines in the run exec block)
- `tests/test_camera1_live_replacement.py` (new executed twin TranscodeRunExecutedTests.test_run_publishes_capped_720p_with_pinned_gop)
- `specs/672-cam1-bitrate-cap-gop/` (spec, plan, tasks)
- Explicitly unchanged: `frontend/**`, `worker/**`, `deploy/vps/**`, the road1 transcode script (its GOP is a follow-up candidate), the MediaMTX renderer and relay rules.

## Validation
- Executed twin on the real script bytes with a recording fake ffmpeg: tests/test_camera1_live_replacement.py TranscodeRunExecutedTests.test_run_publishes_capped_720p_with_pinned_gop asserts the ordered cap triple 1500k/1600k/3200k, `-g 30`, `-keyint_min 30`, the intact encoding chain (fps=15,scale=-2:720, libx264, veryfast, zerolatency) and the publish target rtsp://10.0.0.8:8554/cam1-h264.
- RED authenticity: the twin fails on the pre-fix base 0fe06f4 with ValueError '-b:v' not in list.
- Full battery: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` green — 1397 tests OK (skipped=2) = baseline 1396 + 1 new; `bash -n` on the script OK.
- `python3 scripts/ci/validate_sdd.py` green with the new trio.

## Runtime feedback
- Issue #672: the uncapped cam1 publish measured live master BANDWIDTH=3937309 (~3.9 Mbps), media TARGETDURATION:17, every EXTINF 16.66667 (default keyint 250 @ 15 fps), fMP4 segments 7.4–8.1 MB.
- Worst-case pipe 190 KB/s ≈ 1.5 Mbps (issue #659 measurements): an 8 MB segment needs ~43 s → viewer starvation; the cap + 2 s GOP bring segments to ~2 s / ~375 KB.

## Risk profile
- Risk profile: REQUIRED
- RISK-001 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the lane-B activation batch restarts the cam1 transcode unit with systemd Restart=always plus the freshness watchdog recovering the publish, and the previous script bytes are kept for rollback before the restart | Validation: the activation batch verifies the unit active and HLS freshness after the restart; the rollback path is the previous script digest | Residual risk: a seconds-long cam1 HLS blip during the restart window | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED

## Test design
- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: TranscodeRunExecutedTests.test_run_publishes_capped_720p_with_pinned_gop asserts the ordered cap triple -b:v 1500k / -maxrate 1600k / -bufsize 3200k in the executed run argv
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: the same executed twin asserts -g 30 and -keyint_min 30 (pinned 2 s GOP)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: the same executed twin asserts the intact chain (fps=15,scale=-2:720, libx264, veryfast, zerolatency) and publish target rtsp://10.0.0.8:8554/cam1-h264
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: full unittest battery green (1397 tests OK, skipped=2) plus bash -n on the script
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: RED run on base 0fe06f4 fails with ValueError '-b:v' not in list
- TEST-006 | Covers: AC-006 | Level: runtime-manual | Priority: P1 | Evidence: post-activation probe of the live cam1 playlists (BANDWIDTH ≈ 1.5 Mbps, TARGETDURATION ≈ 2–3, EXTINF ≈ 2 s) and a 10-minute viewer stall probe

## Correct-course check
- Trigger: NONE
- Issue impact: requirements stable since issue #672 opened; the starvation measurements predate this spec and motivate it without changing its shape
- Specification impact: none — the spec matches the locked design (argv-only cap + GOP pin, activation deferred)
- Plan impact: none — no deviation discovered during implementation
- Tasks impact: none — delivery tasks executed as written
- Authorization impact: NONE
- Follow-up: lane-B worker activation (script update + transcode unit restart, owner-gated SSH batch), post-activation runtime acceptance probe, road1's own GOP pin (its script keeps the default keyint — follow-up candidate), and the hls.js player config / viewer-lag 17–34 s concern — each outside this chain

## Deployment transaction audit
- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged, no changes applied | Retry: N/A | Rollback: N/A | Evidence: SDD validators green on the cam1 cap PR
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: Worker unchanged, transcode unit still running the previous script | Retry: N/A | Rollback: N/A | Evidence: this chain ships script+test+specs only; lane-B activation is a deferred follow-up with its own gates
- TX-003 | Stage: MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: No server state touched in this chain | Retry: N/A | Rollback: N/A | Evidence: changed-file scope limited to deploy/worker/ubuntu/camera1-h264-transcode.sh, tests/test_camera1_live_replacement.py, specs/672-cam1-bitrate-cap-gop/
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged | Retry: Re-run suite | Rollback: N/A | Evidence: bash -n, full unittest battery (1397 OK, skipped=2), RED proof on 0fe06f4, scripts/ci/validate_sdd.py
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Merge commit recorded in git | Retry: Re-merge | Rollback: Revert merge commit | Evidence: Merge commit SHA on main
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: JOURNAL entry pending | Retry: Re-record | Rollback: N/A | Evidence: JOURNAL.md entry
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Test logs missing | Retry: Re-run suite | Rollback: N/A | Evidence: unittest output captured in the PR delivery record
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: N/A in this chain (no server mutation) | Retry: N/A | Rollback: Revert merge commit | Evidence: git revert on main
