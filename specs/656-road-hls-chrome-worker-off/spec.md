# Spec: road/water/cameras hls.js first + worker off (Chrome black screen)

- Issue: #656

## Product outcome
road1, water and cameras streams play in Chrome. Chrome reports canPlayType('application/vnd.apple.mpegurl') === 'maybe' while being unable to demux native HLS, so the hls.js branch must win first whenever MSE is available; hls.js must run with enableWorker:false because the site CSP has no worker-src and blocks blob: workers.

## User scenarios
- Owner opens https://mostdef.ru/sea-speed/road/ in Chrome and sees live video playing (readyState 4, currentTime advancing, 1920x1080).
- Water page and cameras grid play in Chrome the same way.
- iOS Safari (no MSE) keeps native playback via the retained fallback branch.

## Requirements
1. `attachHls()` in `frontend/sea-speed/road/main.js` must try the hls.js branch first; native playback becomes the no-MSE fallback.
2. All three operator Hls configs (`road/main.js`, `main.js`, `cameras/cameras.js`) must ship `enableWorker:false` (site CSP has no worker-src; blob: workers are blocked at the edge).
3. No CSP/edge/auth changes in this chain; CSP `worker-src` stays a follow-up candidate (#656).

## Acceptance criteria
- AC-001: In Chrome (canPlayType lies 'maybe') the road reconnect stays on the hls.js branch with enableWorker:false and never sets the native video src.
- AC-002: With MSE unavailable the road page sets the native video src and creates no Hls instance.
- AC-003: All three operator pages ship new Hls configs with enableWorker:false (source scan).
- AC-004: Post-deploy Playwright on prod as an authenticated viewer: readyState 4, currentTime advancing, segments 200 / zero 404, console clean.

## Runtime feedback
- Chrome canPlayType('application/vnd.apple.mpegurl') === 'maybe' is a lie for demuxing purposes; the native-first branch (PR #655) stalled forever at readyState 0, networkState 2.
- hls.js 1.5.7 decodes the mediamtx fMP4 stream fine once actually used (supersedes the PR #655 runtime-feedback claim).
- Site CSP sets script-src without worker-src; the hls.js blob: worker is blocked (internalException) before any segment fetch. media-src 'self' blob: already allows MSE itself.

## NFR assessment
- NFR-001 | Area: Security | Target: No new attack surface | Validation: Code review | Evidence: enableWorker:false reduces client-side worker surface; no CSP/edge/auth changes | Status: PASS
- NFR-002 | Area: Reliability | Target: Video decodes and plays in Chrome (readyState 4) | Validation: Executed frontend twins plus post-deploy Playwright | Evidence: hls.js with enableWorker:false plays live (readyState 4, currentTime advancing, segments 200, zero 404) | Status: PASS
- NFR-003 | Area: Performance | Target: No regression vs current delivery | Validation: Same HLS segments, same Caddy delivery path | Evidence: No change to segment count or encoding | Status: PASS
- NFR-004 | Area: Compatibility | Target: iOS Safari (no MSE) keeps native playback | Validation: Executed no-MSE twin | Evidence: native src set, zero Hls instances when MSE is unavailable | Status: PASS
- NFR-005 | Area: Maintainability | Target: Branch order and worker-off config pinned by executed tests | Validation: unittest frontend contract twins | Evidence: Chrome-lie, no-MSE and source-scan twins in tests/test_frontend_contract.py | Status: PASS
