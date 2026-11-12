# Tasks: road1 viewer transcode 1080p->720p bandwidth cap (box-side)

- Spec: specs/659-road1-viewer-transcode/spec.md

## Delivery tasks
- [x] Write deploy/worker/ubuntu/road1-h264-transcode.sh cloning the cam1 transcode transaction shape (run/prepare/activate/status, digest-bound 0600 candidates) with the credential-free road1 relay source and the mandatory bitrate-cap triple
- [x] Add executed twins in tests/test_road1_h264_transcode.py: run argv (bitrate cap, transport placement, road1 source, road1-720p target), run refusal, prepare with the real renderer under a user namespace, activate digest-mismatch refusal
- [x] Add source-scan pins (bitrate cap and path literals present; no HLS_URL/ffconcat machinery) and the renderer-compat regression twin for road1-720p
- [x] Write the SDD trio specs/659-road1-viewer-transcode/{spec,plan,tasks}.md and pass scripts/ci/validate_sdd.py
- [ ] Peer verification of the combined diff (independent second worker)
- [ ] CI green on the road1 transcode PR
- [ ] Merge the road1 transcode PR to main
- [ ] Box-side activation on the Ubuntu worker (prepare/activate with digest evidence) — deferred follow-up, outside this chain
- [ ] VPS retarget of the road1 viewer source to sourceOnDemand rtsp://10.123.239.102:8554/road1-720p — deferred follow-up, outside this chain
- [ ] Freshness watchdog for the road1 transcode unit — deferred follow-up (WATCHDOG=DEFERRED)

## Completion gate
- Peer verification of the road1 transcode diff complete
- CI green on the road1 transcode PR
- PR merged to main
- Box-side activation and VPS retarget explicitly deferred to their own follow-up chains (not gates for this PR)

## Requirements traceability
- AC-001 | Task: run executed twins | Evidence: Road1TranscodeRunExecutedTests in tests/test_road1_h264_transcode.py (full argv incl. bitrate-cap triple; exit-2 refusal) | Coverage: COVERED
- AC-002 | Task: prepare executed twin + renderer-compat regression | Evidence: Road1TranscodePrepareExecutedTests.test_prepare_renders_road1_720p_candidate_and_unit and Road1TranscodeRendererCompatTests in tests/test_road1_h264_transcode.py | Coverage: COVERED
- AC-003 | Task: activate digest-mismatch executed twin | Evidence: Road1TranscodePrepareExecutedTests.test_activate_digest_mismatch_refuses_fail_closed in tests/test_road1_h264_transcode.py | Coverage: COVERED
- AC-004 | Task: full unittest suite green | Evidence: python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py' output in the PR delivery record | Coverage: COVERED

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
