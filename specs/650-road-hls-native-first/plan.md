# Plan: road1 native HLS first + MediaSource reset

## Steps
1. Modify `frontend/sea-speed/road/main.js`:
   - In `attachHls()`: try native HLS (`canPlayType("application/vnd.apple.mpegurl")`) before hls.js fallback.
   - In `destroyMedia()`: use `roadMainVideo.src=""` instead of `removeAttribute("src")`.
2. Commit and push to branch `fix/road-hls-native-first`.
3. Create PR, pass CI, merge to main.
4. Lane-A deploy on merged main SHA.
5. Run acceptance probes on production.

## Rollback
Revert to main SHA `6020fc400f43ff5b6638ed8bb63538393ce59514` (pre-fix server config already applied separately on server).