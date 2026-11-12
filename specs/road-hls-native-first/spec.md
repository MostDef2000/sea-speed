# Spec: road1 native HLS first + MediaSource reset

## Problem
road1 video does not decode in browser (readyState 0, waiting timeout loop) despite all HLS segments returning 200. hls.js v1.5.7 cannot decode mediamtx fMP4 stream; native browser HLS decodes fine.

## Root cause
`attachHls()` tried hls.js first, which fails silently on fMP4. `destroyMedia()` used `removeAttribute("src")` which does not fully release the old MediaSource/blob URL, causing hls.js to attach to a stale source.

## Fix
1. `attachHls()`: try native HLS (`canPlayType("application/vnd.apple.mpegurl")`) before hls.js fallback.
2. `destroyMedia()`: use `roadMainVideo.src=""` instead of `removeAttribute("src")` to fully release MediaSource.

## Verification
- Playwright in real Chromium: readyState 4, videoWidth 1920, videoHeight 1080, 12/12 segments 200, zero 404.
- Server file `/var/www/mostdef.ru/sea-speed/road/main.js` already updated and verified.

## Scope
- `frontend/sea-speed/road/main.js` only.
- cam1, worker service, analytics API out of scope.