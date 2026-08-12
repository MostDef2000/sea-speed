# Implementation Plan: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Issue: #103
- Status: Release recovery before production rollout

## Architecture

```text
protected Ubuntu camera inventory
  -> dedicated MediaMTX preview relay on private ZeroTier address
     -> one source-on-demand path per camera candidate
        -> sanitized VPS catalog with credential-free relay URLs
           -> Sea Speed API validates catalog camera_id
              -> one temporary VPS FFmpeg process at a time
                 -> reduced H.264 / no-audio HLS under /sea-speed/media/camera-preview/
                    -> /sea-speed/cameras/ active card
```

The accepted Camera 1 production path is a separate contour and is not modified:

```text
physical Camera 1 -> accepted Ubuntu relay -> VPS Camera 1 H.264 compatibility service
-> exact nginx /cams/hls/cam1/ route -> browser
```

## Decisions

### D-001 - On-demand instead of a permanent camera wall

- Decision: keep zero preview processes at rest and start a single temporary VPS transcode only when the operator selects a camera.
- Reason: the gallery is an identification tool, not a monitoring wall; permanent transcodes would waste camera sessions, edge bandwidth, ZeroTier bandwidth and VPS CPU.
- Rejected: 33 always-running HLS/FFmpeg pipelines.

### D-002 - Dedicated Ubuntu preview relay contour

- Decision: generate a separate MediaMTX configuration/service for camera previews on its own private RTSP listener.
- Reason: adding/restarting preview paths must not mutate or restart the accepted Camera 1 relay/service.
- Rejected: generalizing the current Camera-1-specific relay configuration in place.

### D-003 - Credentials stay on Ubuntu

- Decision: native camera RTSP URLs with credentials exist only in a root-protected Ubuntu inventory/config. VPS receives only credential-free private relay URLs.
- Reason: repository, browser, API responses and VPS preview argv do not need native camera credentials.

### D-004 - Browser normalization remains on the VPS

- Decision: VPS FFmpeg converts the selected relay stream to H.264 HLS with reduced preview settings.
- Reason: it reuses the proven Camera 1 separation between source acquisition and browser compatibility while avoiding codec assumptions for newly discovered devices.

### D-005 - One active preview plus hard TTL

- Decision: server state permits one active preview, replacement is atomic at the API lock, and FFmpeg receives a bounded `-t` duration (120 seconds by default, max 600 seconds).
- Reason: prevents resource accumulation from multiple tabs and cleans up abandoned sessions without relying on browser lifecycle events.

### D-006 - Runtime catalog rather than committed LAN inventory

- Decision: `/api/cameras` loads a sanitized deployment-local JSON catalog.
- Reason: the discovered device set and protected relay identity are runtime facts. Production source and credentials do not belong in GitHub.

### D-007 - Exact VPS artifact must cover every repository-owned deployed page

- Decision: `frontend/sea-speed/cameras/index.html` is a required member of the deterministic VPS exact artifact and of exact-artifact validation, alongside the operator, objects and root pages.
- Reason: the production deploy script installs the Cameras page, so release provenance is incomplete if the exact VPS artifact omits that file even when the deploy script can download it from the exact commit.
- Regression rule: quality tests must assert that the built VPS artifact inventory contains the Cameras page; exact-artifact validation must also parse it as HTML.

## API design

Additive endpoints:

- `GET /api/cameras` -> sanitized camera list and current active identity.
- `GET /api/cameras/preview` -> current active preview public state or idle.
- `POST /api/cameras/{camera_id}/preview/start` -> validate catalog identity, replace existing preview, wait for initial HLS playlist, return public preview state.
- `POST /api/cameras/preview/stop` -> terminate active preview and remove temporary media.

The browser never supplies a source URL. The API validates the selected catalog entry and a credential-free RFC1918 RTSP relay URL whose path matches that camera identity.

## Preview media policy

Default FFmpeg intent:

- RTSP over TCP from private relay;
- map first video stream only;
- no audio;
- scale to 640px width;
- 8 fps;
- H.264 `libx264`, baseline/yuv420p, low-latency-oriented GOP;
- short fMP4 HLS list;
- hard duration 120 seconds by default;
- stdout/stderr discarded so a source URL is not copied into API logs.

## Ubuntu relay helper

`deploy/worker/ubuntu/camera-preview-relay.sh` provides:

- `prepare`: validate root-only JSON inventory, render a protected standalone MediaMTX candidate, render a sanitized VPS catalog and a dedicated systemd unit candidate; no service mutation.
- `activate`: digest-bind prepared candidates, preserve any previous preview-relay files as protected backups, install only the dedicated preview service/config, daemon-reload and restart only that preview service, then verify the private listener.
- `status`: report preview service/listener state without exposing inventory contents.

The helper never starts/stops/restarts the AI worker or the accepted Camera 1 relay service.

## Affected contours

- VPS API: additive preview orchestration.
- VPS frontend: new gallery and operator navigation.
- VPS deployment: install/rollback/smoke for the gallery page.
- Release tooling: deterministic VPS artifact inventory and validation include the Cameras page.
- Ubuntu operations: new dedicated private preview relay helper/service.
- Windows worker: unchanged.
- Camera 1 accepted live path: unchanged.

Production impact derives as `VPS` because `api/**` and `frontend/**` are present; `deploy/worker/ubuntu/**` is additionally a control-plane path but does not introduce `worker/**` changes. The release-recovery change itself is control-plane/quality tooling only and does not mutate production runtime.

## Validation

- Python syntax for `api/app/main.py` and focused tests.
- Bash syntax for preview relay and VPS deploy scripts.
- Static focused tests verify no arbitrary source URL API, one-active/TTL FFmpeg contract, credential-safe catalog response, source-on-demand relay configuration, Cameras page UI and release integration.
- Exact-artifact validation requires `frontend/sea-speed/cameras/index.html`, verifies source/archive digests and parses all repository-owned VPS HTML pages.
- Quality architecture tests assert that a freshly built VPS exact-artifact manifest contains the Cameras page.
- Existing repository/CI suites remain required.

## Rollout

1. Merge exact source after CI and separate merge approval.
2. Separately authorize production rollout.
3. Before production mutation, require a new exact-artifact/quality-evidence run for the exact merged commit and verify that its VPS inventory contains `frontend/sea-speed/cameras/index.html`.
4. On Ubuntu, create protected inventory with real sources and run `prepare` only.
5. Review candidate digest and sanitized catalog; activate the dedicated preview relay only after the runtime authorization boundary is satisfied.
6. Copy the sanitized generated catalog to the configured VPS catalog path without camera credentials.
7. Deploy the exact merged VPS source.
8. Verify operator and Cameras pages plus `/api/cameras`.
9. Start one representative camera preview, visually confirm, switch to another, then Stop.
10. Verify no preview remains active after Stop/TTL and Camera 1 still advances.

## Rollback

- VPS rollback uses the existing exact-release rollback mechanism, extended to preserve the Cameras page state. Automatic VPS safety rollback for the currently authorized rollout was separately approved after the source merge.
- Ubuntu preview relay keeps protected predecessor config/unit backups; Ubuntu rollback remains explicit, never automatic.
- Camera 1 does not require rollback because its source/config is not changed by this feature.

## Runtime feedback

- 2026-08-12 pre-release gate: post-merge quality evidence for `1767bdfea7cb91febd139e12c5fd3a6068510899` exposed an exact-artifact completeness defect: the deploy script installed the Cameras page but the VPS exact artifact builder/validator did not include it. Production mutation was stopped before SSH/deployment.
- Recovery scope: make the Cameras page a required exact VPS artifact member, add regression coverage, remove the accidental empty `__NOOP__` repository file, then obtain a new green exact merge commit before resuming rollout.
- Production acceptance remains pending.
