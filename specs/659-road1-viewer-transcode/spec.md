# Spec: road1 viewer transcode 1080p->720p bandwidth cap (box-side)

- Issue: #659

## Product outcome
The viewer-facing road1 stream is bandwidth-capped to ~1.5 Mbps: a new box-side transcode unit (`sea-speed-road1-h264.service`, script `deploy/worker/ubuntu/road1-h264-transcode.sh`) pulls the box's own credential-free relay path `road1` and republishes it as `road1-720p` (720p15, libx264 veryfast zerolatency, explicit `-b:v 1500k -maxrate 1600k -bufsize 3200k`) on the Ubuntu MediaMTX. The AI road worker keeps consuming full-res road1 (worker `HLS_URL` untouched); the viewer URL `/sea-speed/media/road1/` is unchanged and the frontend is unchanged — the later VPS sourceOnDemand retarget and the box activation happen outside this chain.

## User scenarios
- Owner opens the road viewer page (unchanged URL `/sea-speed/media/road1/`) and the road1 stream plays, delivered over the VPS↔box pipe at ~1.5 Mbps instead of road1's full-res ~4.1 Mbps.
- The road analytics worker on the box continues reading full-res `road1` exactly as before; nothing about the worker's environment or source changes.
- The operator prepares and activates the transcode on the box with the same digest-bound prepare/activate transaction shape as the cam1 transcode (protected 0600 candidates, explicit digests, fail-closed activate).

## Requirements
1. The new script clones the cam1 transcode transaction shape (`run`/`prepare`/`activate`/`status`; prepare/activate digest-bound with 0600 root-owned candidates; status evidence line) with a credential-free source: the box's own relay path `road1` pulled from `--private-rtsp-address` (MediaMTX authorization is IP-rule-based; no env file, no credentials in argv or files).
2. The ffmpeg encoding chain is exactly: input `-rtsp_transport tcp` before `-i`, `-an`, `-vf fps=15,scale=-2:720`, `-c:v libx264 -preset veryfast -tune zerolatency`, and the mandatory bitrate-cap triple `-b:v 1500k -maxrate 1600k -bufsize 3200k`, published as `-f rtsp rtsp://<publish-address>:8554/road1-720p`.
3. The renderer is unchanged: mode `ubuntu-transcode-reader` is already path-generic and renders the `road1-720p` publisher path plus the combined read+publish rule (VPS reader IP + Ubuntu publisher IP) preserving all existing rules.
4. No frontend changes, no worker env changes, no VPS repo changes in this chain; the viewer URL and the AI worker's full-res road1 consumption are untouched.
5. No freshness watchdog in this change (the cam1 freshness watchdog installation is deliberately omitted; deferred follow-up, made explicit by the `WATCHDOG=DEFERRED` activation evidence line).

## Acceptance criteria
- AC-001: Executed twins on the real script bytes prove the exact ffmpeg argv of the `run` flow, including `-rtsp_transport tcp` immediately before `-i`, the derived `rtsp://<host>:<port>/road1` source, and the ordered bitrate-cap triple `-b:v 1500k` / `-maxrate 1600k` / `-bufsize 3200k` ending in `-f rtsp rtsp://<publish>:8554/road1-720p`; missing `--publish-address` refuses with exit 2 and zero ffmpeg invocations.
- AC-002: Executed prepare twin (real renderer, unprivileged user namespace) renders the `road1-720p` publisher path plus exactly one combined read+publish rule carrying `[reader_ip, publisher_ip]`, preserving the existing road1/cam1/cam1-h264 rules, with both candidates 0600 and their SHA256 digests emitted; the unit carries the cam1 hardening shape without any `EnvironmentFile`.
- AC-003: Activate is digest-bound fail-closed: a wrong expected SHA256 refuses with exit 7 before any install (no unit in `/etc/systemd/system`, live config byte-identical, no `.next` residue).
- AC-004: The full unittest suite is green (offline, deterministic; no network in the new tests).

## Runtime feedback
- The delivery pipe to viewers measured 183–413 KB/s while road1 runs at ~4.1 Mbps (issue #659): the full-res 1080p road1 stream cannot reach viewers through the pipe, hence the box-side cap.
- The cam1 transcode pattern proves ~1.47 Mbps actual delivery at 720p15 libx264 veryfast zerolatency through the same pipe — the road1 viewer transcode reuses that exact encoding chain plus the explicit bitrate cap cam1's script lacks.

## NFR assessment
- NFR-001 | Area: Security | Target: No credentials in argv, files or logs; least-privilege reader+publish rule scoped to road1-720p | Validation: Executed twins plus source scan | Evidence: source is the credential-free relay path (no env-file machinery; script contains no HLS_URL/ffconcat strings); rendered rule carries exactly [reader_ip, publisher_ip] with read+publish on road1-720p | Status: PASS
- NFR-002 | Area: Reliability | Target: Transcode survives worker/relay restarts and publishes continuously | Validation: Executed twins of the transaction shape | Evidence: unit clones cam1's Restart=always/RestartSec=2s hardening; activate verifies relay and transcode active fail-closed | Status: PASS
- NFR-003 | Area: Performance | Target: Viewer delivery capped at ~1.5 Mbps (maxrate 1600k) vs road1's ~4.1 Mbps | Validation: Executed argv twins pinning the bitrate-cap triple | Evidence: -b:v 1500k -maxrate 1600k -bufsize 3200k asserted in executed twins; cam1 pattern proves ~1.47 Mbps at 720p15 | Status: PASS
- NFR-004 | Area: Compatibility | Target: AI road worker and existing relay paths unaffected | Validation: Renderer-compat regression twin | Evidence: road1/cam1/cam1-h264 rules and the full-res road1 path preserved byte-exactly when road1-720p is added | Status: PASS
- NFR-005 | Area: Maintainability | Target: Transaction shape and encoding chain pinned by executed tests | Validation: unittest executed twins | Evidence: tests/test_road1_h264_transcode.py (run/prepare/activate twins, source pins, renderer-compat regression) | Status: PASS
