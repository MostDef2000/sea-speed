# Tasks: road1 transcode GOP pin + hls.js live-sync tuning (worker + viewer)

- Spec: specs/675-road1-gop-viewer-lag/spec.md

## Delivery tasks
- [x] Add the pinned GOP to deploy/worker/ubuntu/road1-h264-transcode.sh: `-g 30 -keyint_min 30` between the `-b:v 1500k -maxrate 1600k -bufsize 3200k \` cap triple and the `-f rtsp` publish line (encoder tail now identical to cam1's #672)
- [x] Extend the executed twin tests/test_road1_h264_transcode.py Road1TranscodeRunExecutedTests.test_run_publishes_capped_720p_from_the_relay_path with the ordered GOP pair (-g 30, then -keyint_min 30); purely additive assertions
- [x] RED proof: the twin fails on the pre-fix base df51cb7 with ValueError list.index(x): x not in list at argv.index("-g") (throwaway worktree, removed after the proof)
- [x] Replace the shared hls.js config literal with `new Hls({enableWorker:false,lowLatencyMode:true,backBufferLength:10,maxBufferLength:10,liveSyncDurationCount:2,liveMaxLatencyDurationCount:5})` in frontend/sea-speed/main.js, frontend/sea-speed/road/main.js and frontend/sea-speed/cameras/cameras.js (config object only)
- [x] Full battery green: 1397 tests OK (skipped=2), exit 0; bash -n on the script OK; node --check on the three frontend files OK
- [x] Write the SDD trio specs/675-road1-gop-viewer-lag/{spec,plan,tasks}.md and pass scripts/ci/validate_sdd.py
- [ ] Peer verification of the combined diff (independent second worker)
- [ ] CI green on the 675 PR
- [ ] Merge the 675 PR to main
- [ ] Chain deploy on the merged main SHA: VPS frontend (lane-A) + Ubuntu worker road1 script update and `sea-speed-road1-h264` restart (brief stream blip normal)
- [ ] Runtime acceptance after the chain deploy: road1 media playlist TARGETDURATION:2, EXTINF:2.00000, fresh segment ≈ 300–400 KB, unit active (AC-005); 10-minute water viewer probe with lag ≤ ~6 s and 0 stall/error cycles, fallback to default sync count documented if stalls regress (AC-004)

## Completion gate
- Peer verification of the 675 diff complete
- CI green on the 675 PR
- PR merged to main
- Chain deploy and the post-deploy runtime acceptance probes executed in the authorized chain (owner `commit approved` 2026-11-14 covers issue → PR → merge → deploy dispatch → acceptance probes)

## Requirements traceability
- AC-001 | Task: executed-twin GOP pin + RED proof | Evidence: Road1TranscodeRunExecutedTests.test_run_publishes_capped_720p_from_the_relay_path asserts the ordered -g 30 / -keyint_min 30 pair in the real script bytes' run argv; RED on base df51cb7 (ValueError '-g' not in list) recorded in the PR delivery record | Coverage: COVERED
- AC-002 | Task: full battery | Evidence: python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py' output (1397 tests OK, skipped=2, exit 0) in the PR delivery record; no test weakened, skipped or mocked | Coverage: COVERED
- AC-003 | Task: frontend config literals | Evidence: diff review plus literal grep — the new config literal present exactly once in each of frontend/sea-speed/main.js, road/main.js, cameras/cameras.js; old literal zero times; node --check OK ×3 | Coverage: COVERED
- AC-004 | Task: runtime viewer probe after the chain deploy | Evidence: 10-minute water probe — lag ≤ ~6 s, 0 stall/error cycles; fallback to default sync count keeping the anti-drift ceiling documented if stalls regress | Coverage: RUNTIME-MANUAL | Reason: requires the chain deploy (VPS frontend + worker restart) before a live probe exists; measured after that authorized-chain step
- AC-005 | Task: runtime playlist probe after the chain deploy | Evidence: live road1 media playlist TARGETDURATION:2, EXTINF:2.00000, fresh segment ≈ 300–400 KB; unit sea-speed-road1-h264 active | Coverage: RUNTIME-MANUAL | Reason: requires the Ubuntu worker script update and unit restart before the live playlists exist with the GOP pin; measured on the Ubuntu worker after that authorized-chain step

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
