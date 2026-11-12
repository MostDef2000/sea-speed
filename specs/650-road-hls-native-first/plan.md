# Plan: road1 native HLS first + MediaSource reset

- Spec: specs/650-road-hls-native-first/spec.md

## Architecture
Frontend JS (`frontend/sea-speed/road/main.js`) served via Caddy to mostdef.ru/sea-speed/road/. The `attachHls()` function chooses between native browser HLS and hls.js fallback. `destroyMedia()` resets the video element's MediaSource. No backend changes.

## Decisions
- Use native HLS first (`canPlayType("application/vnd.apple.mpegurl")`) because hls.js v1.5.7 cannot decode mediamtx fMP4.
- Use `roadMainVideo.src=""` + `load()` instead of `removeAttribute("src")` to fully release the old MediaSource/blob URL.

## Affected contours
- `frontend/sea-speed/road/main.js` (VPS contour: mostdef.ru/sea-speed/road/)
- `specs/650-road-hls-native-first/` (spec, plan, tasks)

## Validation
- Playwright in real Chromium: readyState 4, videoWidth 1920, videoHeight 1080, 12/12 segments 200, zero 404.
- CI green on PR, merge to main, lane-A deploy, acceptance probes pass.

## Runtime feedback
- hls.js v1.5.7 cannot decode mediamtx fMP4 stream (readyState 0, waiting timeout loop).
- Native browser HLS decodes fMP4 fine (readyState 4, 1920x1080).
- `removeAttribute("src")` does not release old MediaSource/blob URL; `src=""` + `load()` does.