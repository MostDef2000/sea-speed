# Camera 1 direct H264 browser cutover

Issue #87 now uses a deliberately smaller browser path for Camera 1. The physical camera remains behind the Ubuntu private RTSP relay, but the VPS browser-facing path no longer depends on VPS MediaMTX.

Canonical media path:

`new camera -> Ubuntu private RTSP relay -> VPS FFmpeg H264 fallback -> 127.0.0.1:18889/cam1/ -> nginx -> /cams/hls/cam1/index.m3u8 -> Hls.js`

The public Camera 1 identity remains `/cams/hls/cam1/index.m3u8`. `sea-speed-worker.service` is not started, stopped, restarted, or otherwise controlled by this cutover. MediaMTX may remain active for unrelated runtime use, but it is not the browser upstream for Camera 1 after this cutover.

The motivation is the runtime evidence from Issue #87: the browser reported `manifestIncompatibleCodecsError` for HEVC `hvc1.1.6.L120.0`, while the proven fallback at `127.0.0.1:18889/cam1/index.m3u8` decodes as H264 1280x720 at 15 fps. The direct nginx route removes the stale/wrong HEVC manifest path instead of adding more frontend recovery logic.

## Activate

From exact merged repository source on the VPS, run as root:

```bash
./deploy/vps/camera1-direct-h264-cutover.sh activate
```

The script discovers the active `mostdef.ru` nginx site containing the existing `/cams/hls/` location. `--nginx-site PATH` is available only if discovery is ambiguous.

Before changing nginx it requires the loopback fallback playlist and `ffprobe` H264 codec check to pass. It then inserts one managed `location ^~ /cams/hls/cam1/` block that proxies only Camera 1 to `http://127.0.0.1:18889/cam1/`, disables proxy buffering/cache and response caching, copies any `auth_basic` and `auth_basic_user_file` directives from the existing `/cams/hls/` location, validates nginx, and reloads nginx.

A root-only backup of the prior nginx site is written below `/var/lib/sea-speed-hls-fallback/backups/`. Automatic rollback is not performed. If nginx validation or reload fails, the existing nginx process is not intentionally stopped; the script prints the backup path and stops for an explicit operator decision.

## Acceptance

After `READY_FOR_BROWSER_RETEST`, hard-refresh `https://mostdef.ru/sea-speed/`. Product acceptance is advancing video from the new physical Camera 1 in **LIVE CAMERA** while the AI worker remains inactive.
