# Spec: cam1 transcode bitrate cap + pinned 2 s GOP (worker-side)

- Issue: #672

## Product outcome
The viewer-facing cam1 HLS stream is bandwidth-capped and segment-pinned: the existing cam1 transcode (`deploy/worker/ubuntu/camera1-h264-transcode.sh`) keeps pulling the cam1 relay source and republishing H264 720p15 as `cam1-h264` on the Ubuntu MediaMTX, but its ffmpeg argv now carries the road1-proven bitrate-cap triple `-b:v 1500k -maxrate 1600k -bufsize 3200k` plus a pinned 2 s GOP (`-g 30 -keyint_min 30`, 30 frames @ 15 fps). After the MediaMTX HLS remux this yields ~2 s / ~375 KB segments instead of the previous 16.7 s / 7.4–8.1 MB segments, so the stream reaches viewers over the worst-case ~1.5 Mbps delivery pipe without starvation. The viewer URL, the publish path `rtsp://<publish-address>:8554/cam1-h264`, the frontend and the AI worker's full-res cam1 consumption are unchanged; lane-B worker activation and post-activation runtime acceptance happen outside this chain.

## User scenarios
- Owner opens the cam viewer page (unchanged URL) and the cam1 stream plays without multi-second segment stalls: a ~2 s ~375 KB segment downloads in ~2 s on the worst-case 190 KB/s pipe, instead of ~43 s for the previous 8 MB segments.
- The cam1 transcode unit keeps its existing transaction shape (run/prepare/activate/status) and publish target; only the ffmpeg encoding argv changes.
- The operator later activates the updated script on the Ubuntu worker through the separate owner-gated lane-B SSH batch (script update + transcode unit restart); runtime acceptance is measured on the live playlists after that activation.

## Requirements
1. The run exec ffmpeg block gains exactly two lines between `-tune zerolatency \` and the `-f rtsp` publish line: `-b:v 1500k -maxrate 1600k -bufsize 3200k \` and `-g 30 -keyint_min 30 \`.
2. The rest of the encoding chain is unchanged: `-rtsp_transport tcp` before `-i`, `-an`, `-vf fps=15,scale=-2:720`, `-c:v libx264 -preset veryfast -tune zerolatency`, published as `-f rtsp rtsp://<publish-address>:8554/cam1-h264`.
3. No frontend changes, no worker env changes, no renderer/MediaMTX config changes; the viewer URL and the publish path are untouched.
4. Lane-B worker activation (script update + transcode unit restart on the Ubuntu worker) and post-activation runtime acceptance are deferred follow-ups outside this chain, each with its own delivery gate.

## Acceptance criteria
- AC-001: Executed twin on the real script bytes (recording fake ffmpeg) proves the ordered bitrate-cap triple `-b:v 1500k` / `-maxrate 1600k` / `-bufsize 3200k` in the run exec argv.
- AC-002: The same executed twin proves the pinned 2 s GOP: `-g 30` and `-keyint_min 30` in the run exec argv (30 frames @ 15 fps).
- AC-003: The executed twin proves the encoding chain and publish target are intact: `fps=15,scale=-2:720`, libx264, veryfast, zerolatency, and publish target `rtsp://10.0.0.8:8554/cam1-h264`.
- AC-004: The full unittest battery is green (1397 tests OK, skipped=2 = baseline 1396 + 1 new) with no test weakened, skipped or mocked to obtain green; `bash -n` passes on the script.
- AC-005: RED authenticity: the new twin fails on the pre-fix base 0fe06f4 with ValueError '-b:v' not in list, proving it pins the cap rather than the pre-existing argv.
- AC-006: Runtime acceptance after lane-B activation: live cam1 HLS master playlist BANDWIDTH ≈ 1.5 Mbps, media playlist TARGETDURATION ≈ 2–3 with EXTINF ≈ 2 s, and a 10-minute viewer probe with 0 stall→seek→reconnect cycles.

## Runtime feedback
- Issue #672: the cam1 transcoder published uncapped CRF-23 H264 — live master playlist BANDWIDTH=3937309 (~3.9 Mbps), media playlist TARGETDURATION:17 with every EXTINF 16.66667 (default libx264 keyint 250 @ 15 fps), fMP4 segments 7.4–8.1 MB.
- Worst-case delivery pipe (issue #659 measurements) is 190 KB/s ≈ 1.5 Mbps: an 8 MB segment needs ~43 s, so viewers starve. The road1 cap (road1 live BANDWIDTH=1485418) proves ~1.5 Mbps delivery through the same pipe; a 2 s ~375 KB segment downloads in ~2 s.

## NFR assessment
- NFR-001 | Area: Security | Target: No new credentials, endpoints or exposure; publish path, relay rules and env handling unchanged | Validation: Diff review plus executed-twin argv pin | Evidence: the change touches only the ffmpeg argv inside the existing run exec block; no new env, ports, paths or relay rules | Status: PASS
- NFR-002 | Area: Performance | Target: Viewer delivery capped at ~1.5 Mbps (maxrate 1600k) with ~2 s segments vs the previous ~3.9 Mbps / 16.7 s segments | Validation: Executed argv twin pinning the cap triple and the GOP | Evidence: -b:v 1500k -maxrate 1600k -bufsize 3200k and -g 30 -keyint_min 30 asserted in the executed twin; road1 live BANDWIDTH=1485418 proves ~1.5 Mbps through the same pipe | Status: PASS
- NFR-003 | Area: Compatibility | Target: Encoding chain, publish target and consumers unchanged (AI worker full-res cam1, viewer URL, MediaMTX paths) | Validation: Executed-twin chain and publish-target assertions | Evidence: fps=15,scale=-2:720, libx264, veryfast, zerolatency and rtsp://10.0.0.8:8554/cam1-h264 asserted intact | Status: PASS
- NFR-004 | Area: Maintainability | Target: Cap and GOP pinned by an executed twin on real script bytes with a RED proof | Validation: unittest executed twin | Evidence: tests/test_camera1_live_replacement.py TranscodeRunExecutedTests.test_run_publishes_capped_720p_with_pinned_gop; RED on base 0fe06f4 (ValueError '-b:v' not in list) | Status: PASS
