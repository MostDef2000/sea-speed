# Plan: road1 viewer transcode 1080p->720p bandwidth cap (box-side)

- Spec: specs/659-road1-viewer-transcode/spec.md

## Architecture
Box-side (Ubuntu worker) transcode: `road1-h264-transcode.sh run` pulls `rtsp://<relay-host>:<port>/road1` (the box's own credential-free relay path; rtspAddress is pinned to the ZeroTier IP, so the source is the relay listen address, not loopback) over TCP and publishes H264 720p15 to `rtsp://<publish-address>:8554/road1-720p` on the same MediaMTX. The renderer mode `ubuntu-transcode-reader` (unchanged, path-generic) adds the `road1-720p` publisher path plus the combined read+publish rule (VPS reader IP + Ubuntu publisher IP) to the relay config through the same digest-bound prepare/activate transaction as cam1. Later (outside this chain): the box activation installs the unit and config, and the VPS retargets the road1 viewer source to a sourceOnDemand pull of `rtsp://10.123.239.102:8554/road1-720p`; the viewer URL `/sea-speed/media/road1/` and the frontend stay unchanged.

## Decisions
- The bitrate-cap triple `-b:v 1500k -maxrate 1600k -bufsize 3200k` is mandatory and pinned by executed twins: cam1's transcode script lacks it, and capping the viewer delivery is the entire point of this script (pipe measured 183–413 KB/s vs road1's ~4.1 Mbps).
- No freshness watchdog in this change: the cam1 watchdog installation block is deliberately omitted and the omission is made explicit by the `WATCHDOG=DEFERRED` activation evidence line (deferred follow-up).
- No renderer change: `ubuntu-transcode-reader` already takes a generic `--path` and renders the publisher path + combined read+publish rule; a renderer-compat regression twin pins that existing road1/cam1/cam1-h264 rules survive.
- The source is pulled via the relay listen address (`--private-rtsp-address`, e.g. 10.123.239.102:8554), not loopback, because the relay's rtspAddress is pinned to the ZeroTier IP; the URL is derived as `rtsp://<host>:<port>/road1` and is credential-free (MediaMTX auth is IP-rule-based), so unlike cam1 there is no env file, no ffconcat handoff and no secret handling.
- The publish port stays the literal 8554 (same as cam1); the unit clones cam1's hardening line-for-line minus `EnvironmentFile` (nothing to source).

## Affected contours
- UBUNTU_WORKER: `deploy/worker/ubuntu/road1-h264-transcode.sh` (new systemd-managed box-side script)
- `tests/test_road1_h264_transcode.py` (executed twins, source pins, renderer-compat regression)
- `specs/659-road1-viewer-transcode/` (spec, plan, tasks)
- Explicitly unchanged: `scripts/operations/mediamtx_path_config.py` (renderer), `frontend/**`, `worker/**`, `deploy/vps/**`, the cam1 transcode script and its watchdog.

## Validation
- Executed twins on the real script bytes via tests/support/relay_shell.py: `run` with a recording ffmpeg stub asserts the full argv (input transport placement, derived road1 source URL, 720p15 chain, ordered bitrate-cap triple, road1-720p publish target) and the exit-2 refusal without `--publish-address`; `prepare` under `unshare --user --map-root-user` with the real renderer asserts the rendered candidate (parsed YAML: publisher path, single combined rule with exact ips, preserved rules), the 0600 candidates and digests, and the unit shape (no `EnvironmentFile`, cam1 hardening intact); `activate` is exercised only on the digest-mismatch refusal path (exit 7, no install).
- Source-scan pins: the script text contains `-b:v 1500k`, `-maxrate 1600k`, `-bufsize 3200k`, `road1-720p`, `fps=15,scale=-2:720` and contains neither `HLS_URL` nor `ffconcat`; `bash -n` passes.
- Renderer-compat regression twin mirrors test_ensure_cam1_reader_is_subset_safe_when_adding_cam1_h264 for `road1-720p`.
- Full suite: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` green (baseline ~1400 tests, skipped=2, plus the new twins); `python3 scripts/ci/validate_sdd.py` green with the new trio.

## Runtime feedback
- Delivery pipe measured 183–413 KB/s vs road1's ~4.1 Mbps (issue #659) — the motivation for the box-side cap.
- cam1 pattern proves ~1.47 Mbps at 720p15 libx264 veryfast zerolatency through the same pipe.

## Risk profile
- Risk profile: NOT REQUIRED

This PR ships a new script, its tests and the SDD trio only — nothing is executed on any server in this chain (box activation and VPS retarget are deferred follow-ups with their own gates), so no risk-profile rows are required here.

## Test design
- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: Road1TranscodeRunExecutedTests executed twins (full ffmpeg argv incl. bitrate-cap triple; exit-2 refusal with zero ffmpeg invocations)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: Road1TranscodePrepareExecutedTests.test_prepare_renders_road1_720p_candidate_and_unit (real renderer under user namespace; parsed candidate assertions; 0600 candidates; unit shape)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: Road1TranscodePrepareExecutedTests.test_activate_digest_mismatch_refuses_fail_closed (exit 7, no unit installed, live config byte-identical)
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: full unittest suite green (unittest discover, offline and deterministic)

## Correct-course check
- Trigger: NONE
- Issue impact: requirements stable since issue #659 opened; the delivery-pipe measurement predates this spec and motivates it without changing its shape
- Specification impact: none — the spec matches the locked design (box-side transcode, renderer unchanged, activation deferred)
- Plan impact: none — no deviation discovered during implementation
- Tasks impact: none — delivery tasks executed as written
- Authorization impact: NONE
- Follow-up: box-side activation (prepare/activate on the Ubuntu worker), VPS sourceOnDemand retarget to road1-720p, and the deferred freshness watchdog — each with its own delivery gate

## Deployment transaction audit
- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged, no changes applied | Retry: N/A | Rollback: N/A | Evidence: SDD validators green on the road1 transcode PR
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: Box unchanged, no transcode unit installed | Retry: N/A | Rollback: N/A | Evidence: this chain ships script+tests+specs only; activation is a deferred follow-up with its own gates
- TX-003 | Stage: MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: No server state touched in this chain | Retry: N/A | Rollback: N/A | Evidence: changed-file scope limited to deploy/worker/ubuntu/road1-h264-transcode.sh, tests/test_road1_h264_transcode.py, specs/659-road1-viewer-transcode/
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged | Retry: Re-run suite | Rollback: N/A | Evidence: bash -n, full unittest suite, scripts/ci/validate_sdd.py
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Merge commit recorded in git | Retry: Re-merge | Rollback: Revert merge commit | Evidence: Merge commit SHA on main
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: JOURNAL entry pending | Retry: Re-record | Rollback: N/A | Evidence: JOURNAL.md entry
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Test logs missing | Retry: Re-run suite | Rollback: N/A | Evidence: unittest output captured in the PR delivery record
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: N/A in this chain (no server mutation) | Retry: N/A | Rollback: Revert merge commit | Evidence: git revert on main
