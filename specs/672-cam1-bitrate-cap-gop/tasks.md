# Tasks: cam1 transcode bitrate cap + pinned 2 s GOP (worker-side)

- Spec: specs/672-cam1-bitrate-cap-gop/spec.md

## Delivery tasks
- [x] Add the bitrate-cap triple and pinned GOP to deploy/worker/ubuntu/camera1-h264-transcode.sh: `-b:v 1500k -maxrate 1600k -bufsize 3200k` and `-g 30 -keyint_min 30` between `-tune zerolatency` and the `-f rtsp` publish line
- [x] Add the executed twin tests/test_camera1_live_replacement.py TranscodeRunExecutedTests.test_run_publishes_capped_720p_with_pinned_gop (real script bytes, recording fake ffmpeg; ordered cap triple, -g 30, -keyint_min 30, intact chain, publish target rtsp://10.0.0.8:8554/cam1-h264)
- [x] RED proof: the twin fails on the pre-fix base 0fe06f4 with ValueError '-b:v' not in list
- [x] Full battery green: 1397 tests OK (skipped=2) = baseline 1396 + 1 new; bash -n on the script OK
- [x] Write the SDD trio specs/672-cam1-bitrate-cap-gop/{spec,plan,tasks}.md and pass scripts/ci/validate_sdd.py
- [ ] Peer verification of the combined diff (independent second worker)
- [ ] CI green on the cam1 cap PR
- [ ] Merge the cam1 cap PR to main
- [ ] Lane-B worker activation on the Ubuntu worker (script update + transcode unit restart, owner-gated SSH batch) — deferred follow-up, outside this chain
- [ ] Runtime acceptance probe after lane-B activation (live BANDWIDTH ≈ 1.5 Mbps, TARGETDURATION ≈ 2–3, EXTINF ≈ 2 s, 10-min viewer probe) — deferred until activation

## Completion gate
- Peer verification of the cam1 cap diff complete
- CI green on the cam1 cap PR
- PR merged to main
- Lane-B worker activation and the post-activation runtime acceptance probe explicitly deferred to their own follow-up chains (not gates for this PR)

## Requirements traceability
- AC-001 | Task: executed-twin run argv pin | Evidence: TranscodeRunExecutedTests.test_run_publishes_capped_720p_with_pinned_gop in tests/test_camera1_live_replacement.py asserts the ordered cap triple -b:v 1500k / -maxrate 1600k / -bufsize 3200k | Coverage: COVERED
- AC-002 | Task: executed-twin GOP pin | Evidence: the same executed twin asserts -g 30 and -keyint_min 30 (30 frames @ 15 fps) | Coverage: COVERED
- AC-003 | Task: executed-twin chain + publish pin | Evidence: the same executed twin asserts fps=15,scale=-2:720, libx264, veryfast, zerolatency and rtsp://10.0.0.8:8554/cam1-h264 | Coverage: COVERED
- AC-004 | Task: full battery + bash -n | Evidence: python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py' output (1397 tests OK, skipped=2) and bash -n result in the PR delivery record | Coverage: COVERED
- AC-005 | Task: RED proof on the pre-fix base | Evidence: twin run on base 0fe06f4 fails with ValueError '-b:v' not in list, recorded in the PR delivery record | Coverage: COVERED
- AC-006 | Task: runtime acceptance probe after lane-B activation | Evidence: live cam1 master BANDWIDTH ≈ 1.5 Mbps, media TARGETDURATION ≈ 2–3, EXTINF ≈ 2 s, 10-minute viewer probe with 0 stall→seek→reconnect cycles | Coverage: RUNTIME-MANUAL | Reason: requires the lane-B worker activation (owner-gated SSH batch) before the live playlists exist with the cap; measured on the Ubuntu worker after that follow-up

## Definition of Done
- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current
