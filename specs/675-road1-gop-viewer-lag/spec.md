# Spec: road1 transcode GOP pin + hls.js live-sync tuning (worker + viewer)

- Issue: #675

## Product outcome
The viewer-facing road1 HLS stream is segment-pinned and all three live viewer pages get explicit live-sync knobs: the existing road1 transcode (`deploy/worker/ubuntu/road1-h264-transcode.sh`) keeps pulling the credential-free road1 relay path and republishing H264 720p15 as `road1-720p` on the Ubuntu MediaMTX with its #659 bitrate cap, but its ffmpeg argv now also carries the cam1-proven pinned 2 s GOP (`-g 30 -keyint_min 30`, 30 frames @ 15 fps — the encoder tail becomes identical to cam1's #672 fix), turning the measured 16.7 s / ~3.2 MB segments (default x264 keyint 250) into ~2 s / ~300–400 KB segments. At the same time the shared hls.js config on the three live pages (`frontend/sea-speed/main.js` water, `frontend/sea-speed/road/main.js`, `frontend/sea-speed/cameras/cameras.js`) gains `liveSyncDurationCount:2` (target ~4 s behind the live edge), `liveMaxLatencyDurationCount:5` (hard 10 s ceiling with seek-to-live-edge anti-drift) and a tightened `maxBufferLength:10`, addressing the observed 17–34 s viewer live lag. The viewer URLs, the publish path `rtsp://<publish-address>:8554/road1-720p`, and the AI road worker's full-res road1 consumption are unchanged; the chain deploy (VPS frontend + Ubuntu worker script/unit restart) and post-activation runtime acceptance happen in the authorized delivery chain after merge, outside this repo-only change.

## User scenarios
- Owner opens any live page (unchanged URLs) and the road1 stream plays without multi-second segment stalls: a ~2 s ~300–400 KB segment downloads in ~2 s on the worst-case 190 KB/s pipe, instead of ~17 s for the previous 3.2 MB segments.
- The viewer sits at most ~6 s behind the live edge instead of the observed 17–34 s: `liveSyncDurationCount:2` targets ~2 segments (≈4 s at the pinned 2 s cadence) behind live, and `liveMaxLatencyDurationCount:5` seeks back to the live edge if drift ever exceeds ~10 s.
- The road1 transcode unit keeps its existing transaction shape (run/prepare/activate/status) and publish target; only the ffmpeg encoding argv changes (one added line).
- The chain deploy replaces the road1 script on the Ubuntu worker and restarts `sea-speed-road1-h264` (brief stream blip normal) and redeploys the frontend files on the VPS; runtime acceptance is measured on the live playlists and viewer probe after that deploy.

## Requirements
1. The run exec ffmpeg block gains exactly one line between the `-b:v 1500k -maxrate 1600k -bufsize 3200k \` cap triple and the `-f rtsp` publish line: `-g 30 -keyint_min 30 \`.
2. The rest of the encoding chain is unchanged: `-rtsp_transport tcp` before `-i`, `-an`, `-vf fps=15,scale=-2:720`, `-c:v libx264 -preset veryfast -tune zerolatency`, the #659 cap triple, published as `-f rtsp rtsp://<publish-address>:8554/road1-720p`; the encoder tail is now byte-identical to cam1's (#672).
3. All three live pages replace the shared config literal `new Hls({enableWorker:false,lowLatencyMode:true,backBufferLength:10,maxBufferLength:20})` with `new Hls({enableWorker:false,lowLatencyMode:true,backBufferLength:10,maxBufferLength:10,liveSyncDurationCount:2,liveMaxLatencyDurationCount:5})` — nothing else in those files changes; `enableWorker:false` stays (site CSP blocks blob: workers, prod incident 2026-11-12).
4. The executed-twin pin in `tests/test_road1_h264_transcode.py` extends the existing run-argv test with the ordered GOP pair (`-g` then `30`, `-keyint_min` then `30`); purely additive assertions, no existing test weakened, skipped or mocked.
5. Chain deploy (VPS frontend lane-A + Ubuntu worker road1 script/unit restart) and post-deploy runtime acceptance are the orchestrator's authorized-chain steps after merge, each with its existing gates; this change is repo-only.

## Acceptance criteria
- AC-001: road1 run argv carries `-g 30 -keyint_min 30` (executed twin on real script bytes); RED authenticity — the twin fails on base (no keyint in real argv).
- AC-002: full battery green, no existing test weakened/skipped/mocked.
- AC-003: all three pages carry `liveSyncDurationCount:2`, `liveMaxLatencyDurationCount:5`, `maxBufferLength:10`.
- AC-004: live viewer lag ≤ ~6 s and 0 stall/error cycles in a 10-min probe on water (fallback to default sync count documented if stalls regress).
- AC-005: post-deploy road1 media playlist `TARGETDURATION:2` with `EXTINF:2.00000`, fresh segment ≈ 300–400 KB; unit `sea-speed-road1-h264` active.

## Runtime feedback
- Issue #675 (live, 2026-11-14): the road1 transcoder has the #659 cap but not the GOP pin — master playlist `BANDWIDTH=1481658` (cap works), media playlist `TARGETDURATION:17` with every `EXTINF:16.66667` (default x264 keyint 250 @ 15 fps), fresh segment 3 201 207 B (~3.2 MB per 16.7 s) — the exact starvation pattern cam1 had before #672 (fixed there: TARGETDURATION 2, EXTINF 2.00000, ~370 KB segments).
- Viewer live lag 17–34 s (observed pre-#672 on water): hls.js `liveSyncPosition = playlist end − liveSyncDurationCount × TARGETDURATION`; a lying playlist (`TARGETDURATION:4` with 16.7 s EXTINF) parks the player 1–2 real segments behind. road1 still has the lying playlist (17/16.67); water is honest now (2/2.0) — the GOP pin fixes road1's lie at the source, the sync knobs bound the player-side lag on all three pages.
- Worst-case delivery pipe (issue #659 measurements) is 190 KB/s ≈ 1.5 Mbps: a 3.2 MB segment needs ~17 s, so viewers starve; a 2 s ~300–400 KB segment downloads in ~2 s.

## NFR assessment
- NFR-001 | Area: Security | Target: No new credentials, endpoints or exposure; publish path, relay rules and env handling unchanged | Validation: Diff review plus executed-twin argv pin | Evidence: the change touches only the ffmpeg argv inside the existing run exec block and the hls.js config literal; no new env, ports, paths or relay rules | Status: PASS
- NFR-002 | Area: Performance | Target: road1 segments ~2 s / ~300–400 KB (vs 16.7 s / ~3.2 MB) and viewer live lag bounded (~4 s target, 10 s hard ceiling) vs the observed 17–34 s | Validation: Executed argv twin pinning the GOP; config diff pinning the sync knobs | Evidence: -g 30 -keyint_min 30 asserted in the executed twin; liveSyncDurationCount:2 / liveMaxLatencyDurationCount:5 / maxBufferLength:10 in all three pages; live segment/lag numbers measured post-deploy (AC-004/AC-005) | Status: PASS
- NFR-003 | Area: Compatibility | Target: Encoding chain, publish target and consumers unchanged (AI worker full-res road1, viewer URLs, MediaMTX paths); hls.js worker stays disabled | Validation: Executed-twin chain and publish-target assertions plus the retained `enableWorker:false` prefix | Evidence: fps=15,scale=-2:720, libx264, veryfast, zerolatency, cap triple and rtsp://10.123.239.102:8554/road1-720p asserted intact; `new Hls({enableWorker:false,` prefix retained on all three pages (tests/test_frontend_contract.py guard stays green) | Status: PASS
- NFR-004 | Area: Maintainability | Target: GOP pinned by an executed twin on real script bytes with a RED proof; road1 and cam1 encoder tails identical | Validation: unittest executed twin | Evidence: tests/test_road1_h264_transcode.py Road1TranscodeRunExecutedTests.test_run_publishes_capped_720p_from_the_relay_path asserts the ordered GOP pair; RED on base df51cb7 (ValueError '-g' not in list) | Status: PASS
