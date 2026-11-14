# Plan: road1 transcode GOP pin + hls.js live-sync tuning (worker + viewer)

- Spec: specs/675-road1-gop-viewer-lag/spec.md

## Architecture
Two-sided but minimal change. Worker-side (Ubuntu): `deploy/worker/ubuntu/road1-h264-transcode.sh run` keeps pulling the road1 relay source over TCP and publishing H264 720p15 to `rtsp://<publish-address>:8554/road1-720p` on the same MediaMTX; the only change is one ffmpeg argv line — the pinned 2 s GOP (`-g 30 -keyint_min 30`, 30 frames @ 15 fps) inserted after the #659 cap triple, making the encoder tail identical to cam1's #672 fix. MediaMTX remuxes the publish into HLS with ~2 s / ~300–400 KB segments and an honest `TARGETDURATION:2`. Viewer-side: the three live pages share one hls.js config literal; it gains `liveSyncDurationCount:2` (player targets ~2 segments ≈ 4 s behind live), `liveMaxLatencyDurationCount:5` (hard ceiling ~10 s, hls.js seeks to the live edge beyond it — anti-drift) and `maxBufferLength:10` (forward buffer tightened to the shorter segment cadence). Later (outside this repo-only change): the authorized chain deploy replaces the script on the Ubuntu worker, restarts `sea-speed-road1-h264`, redeploys the frontend on the VPS, and runtime acceptance is measured on the live playlists and a viewer probe.

## Decisions
- The GOP pin reuses cam1's #672 values `-g 30 -keyint_min 30`: at 15 fps that is a 2 s segment cadence, replacing the default libx264 keyint 250 (EXTINF 16.66667, TARGETDURATION:17) that made every road1 segment ~3.2 MB; a 2 s ~300–400 KB segment downloads in ~2 s on the 190 KB/s worst-case pipe.
- `liveSyncDurationCount:2` targets ~4 s behind the live edge at the pinned 2 s cadence — inside the ≤ ~6 s acceptance bound with headroom for the worst pipe; `liveMaxLatencyDurationCount:5` bounds pathological drift at ~10 s with an automatic seek to live (the anti-drift ceiling the issue requires); `maxBufferLength` tightens 20→10 so the forward buffer matches the shorter segments instead of over-buffering past the latency target.
- The issue's documented fallback stands: if the tighter sync regresses stalls on the worst pipe (AC-004 probe), fall back to the default sync count keeping the anti-drift ceiling — decided at runtime acceptance, not in this change.
- One argv line + one config literal per page — the smallest complete change: no script restructuring, no renderer/MediaMTX config changes, publish path and transaction shape untouched, `enableWorker:false` retained (CSP blocks blob: workers).
- Chain deploy and runtime acceptance are the orchestrator's authorized-chain steps after merge; this chain is repo-only.

## Affected contours
- UBUNTU_WORKER: `deploy/worker/ubuntu/road1-h264-transcode.sh` (one added ffmpeg argv line in the run exec block)
- VPS: `frontend/sea-speed/main.js`, `frontend/sea-speed/road/main.js`, `frontend/sea-speed/cameras/cameras.js` (hls.js config literal only)
- `tests/test_road1_h264_transcode.py` (extended executed-twin run-argv pin: ordered GOP pair)
- `specs/675-road1-gop-viewer-lag/` (spec, plan, tasks)
- Explicitly unchanged: `deploy/worker/ubuntu/camera1-h264-transcode.sh` and `tests/test_camera1_live_replacement.py` (cam1 fix is test-protected), `frontend/**` beyond the three config literals, `worker/**`, `deploy/vps/**`, the MediaMTX renderer and relay rules, `.github/**`, `contracts/**`.

## Validation
- Executed twin on the real script bytes with a recording fake ffmpeg: tests/test_road1_h264_transcode.py Road1TranscodeRunExecutedTests.test_run_publishes_capped_720p_from_the_relay_path asserts the ordered GOP pair `-g 30` then `-keyint_min 30` in addition to the existing cap-triple, chain and publish-target pins.
- RED authenticity: the twin fails on the pre-fix base df51cb7 with ValueError list.index(x): x not in list at argv.index("-g") (verified in a throwaway worktree at /tmp/opencode/675-red, removed after the proof).
- Full battery: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` green — 1397 tests OK (skipped=2), exit 0; `bash -n` on the script OK; `node --check` on the three frontend files OK.
- `python3 scripts/ci/validate_sdd.py` green with the new trio.

## Runtime feedback
- Issue #675 (live, 2026-11-14): road1 media playlist TARGETDURATION:17, every EXTINF 16.66667 (default keyint 250 @ 15 fps), fresh segment 3 201 207 B; master BANDWIDTH=1481658 proves the #659 cap itself works.
- Viewer live lag 17–34 s mechanism: hls.js liveSyncPosition = playlist end − liveSyncDurationCount × TARGETDURATION; the lying road1 playlist (17/16.67) parks viewers 1–2 real segments behind; the GOP pin makes the playlist honest (2/2.0) and the sync knobs bound the player-side lag.

## Risk profile
- Risk profile: REQUIRED
- RISK-001 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: the chain deploy restarts the road1 transcode unit with systemd Restart=always and the freshness watchdog recovering the publish, and the previous script bytes are kept for rollback before the restart | Validation: the deploy verifies the unit active and HLS freshness after the restart; the rollback path is the previous script digest | Residual risk: a seconds-long road1 HLS blip during the restart window | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: PERF | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: the tighter live sync (liveSyncDurationCount:2, maxBufferLength:10) could starve the player on the worst-case pipe and regress stalls; the issue documents the fallback — revert to the default sync count keeping the liveMaxLatencyDurationCount:5 anti-drift ceiling | Validation: the AC-004 10-minute viewer probe (lag ≤ ~6 s AND 0 stall/error cycles) decides between the tuned and fallback configs | Residual risk: a stall regression on the worst pipe, caught by the probe and reverted via the documented fallback | Owner: Sea Speed Delivery Orchestrator | Status: MITIGATED

## Test design
- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: Road1TranscodeRunExecutedTests.test_run_publishes_capped_720p_from_the_relay_path asserts the ordered GOP pair -g 30 then -keyint_min 30 in the executed run argv (plus the existing cap-triple/chain/publish pins)
- TEST-002 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: RED run on base df51cb7 fails with ValueError list.index(x): x not in list at argv.index("-g")
- TEST-003 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: full unittest battery green (1397 tests OK, skipped=2, exit 0) plus bash -n on the script
- TEST-004 | Covers: AC-003 | Level: static | Priority: P0 | Evidence: diff review plus literal grep — the new config literal present exactly once in each of the three frontend files, the old literal present zero times; `node --check` passes on all three
- TEST-005 | Covers: AC-004 | Level: runtime-manual | Priority: P1 | Evidence: post-deploy 10-minute viewer probe on water (lag ≤ ~6 s, 0 stall/error cycles; fallback to default sync count documented if stalls regress)
- TEST-006 | Covers: AC-005 | Level: runtime-manual | Priority: P1 | Evidence: post-deploy road1 media playlist TARGETDURATION:2, EXTINF:2.00000, fresh segment ≈ 300–400 KB, unit sea-speed-road1-h264 active

## Correct-course check
- Trigger: NONE
- Issue impact: requirements stable since issue #675 opened; the starvation and lag measurements predate this spec and motivate it without changing its shape
- Specification impact: none — the spec matches the locked design (one argv line + three config literals, deploy/acceptance in the authorized chain)
- Plan impact: none — no deviation discovered during implementation
- Tasks impact: none — delivery tasks executed as written
- Authorization impact: NONE (owner authorized the full chain with `commit approved`, 2026-11-14)
- Follow-up: chain deploy (VPS frontend lane-A + Ubuntu worker road1 script/unit restart), post-deploy runtime acceptance probes (AC-004/AC-005), and the AC-004 stall-fallback decision if the probe regresses — each inside the authorized chain after merge

## Deployment transaction audit
- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged, no changes applied | Retry: N/A | Rollback: N/A | Evidence: SDD validators green on the 675 PR
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: Worker/VPS unchanged, road1 unit still running the previous script | Retry: N/A | Rollback: N/A | Evidence: this chain ships script+test+frontend+specs only; the chain deploy is the orchestrator's post-merge authorized-chain step
- TX-003 | Stage: MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: No server state touched in this chain | Retry: N/A | Rollback: N/A | Evidence: changed-file scope limited to deploy/worker/ubuntu/road1-h264-transcode.sh, tests/test_road1_h264_transcode.py, the three frontend files, specs/675-road1-gop-viewer-lag/
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged | Retry: Re-run suite | Rollback: N/A | Evidence: bash -n, node --check ×3, full unittest battery (1397 OK, skipped=2), RED proof on df51cb7, scripts/ci/validate_sdd.py
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Merge commit recorded in git | Retry: Re-merge | Rollback: Revert merge commit | Evidence: Merge commit SHA on main
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: JOURNAL entry pending | Retry: Re-record | Rollback: N/A | Evidence: JOURNAL.md entry
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Test logs missing | Retry: Re-run suite | Rollback: N/A | Evidence: unittest output captured in the PR delivery record
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: N/A in this chain (no server mutation) | Retry: N/A | Rollback: Revert merge commit | Evidence: git revert on main
