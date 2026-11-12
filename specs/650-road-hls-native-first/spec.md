# Spec: road1 native HLS first + MediaSource reset

- Issue: #637

## Product outcome
road1 video plays in browser without black screen / Stream retrying loop. Native browser HLS decodes mediamtx fMP4 stream instead of failing hls.js.

## User scenarios
- Owner opens https://mostdef.ru/sea-speed/road/ and sees live video playing (not black screen, not "retrying" loop).
- Video readyState reaches 4 (HAVE_ENOUGH_DATA), currentTime increases, videoWidth/Height = 1920x1080.
- All HLS segments return 200, zero 404.

## Requirements
1. `attachHls()` must try native HLS (`canPlayType("application/vnd.apple.mpegurl")`) before hls.js fallback.
2. `destroyMedia()` must use `roadMainVideo.src=""` instead of `removeAttribute("src")` to fully release MediaSource.
3. cam1 stream must remain unaffected (already works).
4. No backend or config changes required.

## Acceptance criteria
- Playwright in real Chromium: readyState 4, videoWidth 1920, videoHeight 1080, 12/12 segments 200, zero 404.
- Server file `/var/www/mostdef.ru/sea-speed/road/main.js` updated and verified.
- CI green on PR, merge to main, lane-A deploy, acceptance probes pass.

## Runtime feedback
- hls.js v1.5.7 cannot decode mediamtx fMP4 stream (readyState 0, waiting timeout loop).
- Native browser HLS decodes fMP4 fine (readyState 4, 1920x1080).
- `removeAttribute("src")` does not release old MediaSource/blob URL; `src=""` + `load()` does.

## NFR assessment
- NFR-001: Area: Security | Target: No new attack surface | Validation: Code review | Evidence: Frontend-only JS change, no backend or config changes | Status: PASS
- NFR-002: Area: Reliability | Target: Video decodes and plays (readyState 4) | Validation: Playwright verification | Evidence: readyState 4, 12/12 segments 200, zero 404 | Status: PASS
- NFR-003: Area: Performance | Target: No regression vs current delivery | Validation: Same HLS segments, same Caddy delivery path | Evidence: No change to segment count or encoding | Status: PASS
- NFR-004: Area: Compatibility | Target: Works in modern browsers; hls.js fallback for older | Validation: canPlayType check before native HLS | Evidence: Native HLS first, hls.js fallback preserved | Status: PASS
- NFR-005: Area: Maintainability | Target: Simpler code path, no hls.js for road1 | Validation: Code review | Evidence: attachHls tries native first, hls.js as fallback | Status: PASS