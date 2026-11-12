# Tasks: road1 native HLS first + MediaSource reset

- [x] Modify `attachHls()` to try native HLS before hls.js fallback
- [x] Modify `destroyMedia()` to use `roadMainVideo.src=""` instead of `removeAttribute("src")`
- [x] Apply same fix to server file `/var/www/mostdef.ru/sea-speed/road/main.js`
- [x] Verify with Playwright: readyState 4, 12/12 segments 200, zero 404
- [ ] CI green on PR #651
- [ ] Merge PR to main
- [ ] Lane-A deploy on merged main SHA
- [ ] Acceptance probes on production