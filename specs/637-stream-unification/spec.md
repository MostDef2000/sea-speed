# Spec: #637 — both cameras on permanent protected HLS streams

- Issue: #637
- Specification: specs/637-stream-unification/spec.md
- Authorization: commit approved (owner admission in the dev-chat delivery
  session, 2026-11-11, for the #637 scope: permanent protected streams for
  both cameras, full decommission of the session preview mechanism, repo +
  box + Caddy + cleanup + AGENTS.md minimum-code rule, chain through merge,
  lane-A deploys and acceptance probes); base 2c8168f

## Product outcome

The road camera is watched through a session-based preview relay that exists
only because the permanent relay had no road1 path: an operator action starts
an ffmpeg encode on the worker, the page polls and reconnects, and every
mechanism around it (TTL, sweeper, TTL-renew, snapshot/commit, batch
preview, gallery) exists to manage that session's lifetime. The water camera
has been on a permanent protected relay path (docker-mediamtx `cam1` ← main
relay `cam1-h264`) since the #442/#530 contour and needs none of it.

After this change both cameras are served the same way: permanent protected
mediamtx relay paths (`cam1`, `road1`) behind the Caddy edge, played
statically by the operator pages. The session preview mechanism is deleted
end to end — API routes and module, frontend session plumbing, worker
preview relay service, deploy guards, docs — and the road worker pulls its
analytics source from the permanent relay path via a validated
`--road-relay-url`. The cameras page becomes a static two-player grid; the
road page's stream toggle becomes a local player control. No preview API
surface remains to start, stop, renew, sweep or snapshot.

## User scenarios

- SC-1: the owner opens the cameras page — both cards (cam1, road1) play
  their permanent HLS streams immediately; no start action, no session id,
  no TTL; the page keeps working across tab switches and reconnects with a
  bounded backoff ladder.
- SC-2: the owner opens the road page — the stream plays from the permanent
  relay path; the stream toggle starts/stops local playback only and never
  calls a camera API; the AI worker toggle stays independent.
- SC-3: the road analytics worker boots — it reads its RTSP source from
  `road-worker.env` (`HLS_URL`), validated by `configure-analytics-profiles.py
  --road-relay-url` (rtsp, RFC1918, explicit port, no userinfo, exact
  /road1); no preview catalog exists anywhere on the box.
- SC-4: an operator calls any preview/snapshot API route — the routes do
  not exist (404 via the router); the catalog route returns the static
  camera list.

## Requirements

- R-1: `GET /api/cameras` returns the static catalog
  (`sea_speed_camera_catalog_v1`) derived from `sorted(ANALYTICS_IDENTITIES)`
  with `available: true`; all other preview/snapshot routes
  (`GET /api/cameras/preview`, `GET /api/cameras/{id}/snapshot`,
  `POST .../preview/start`, `POST /api/cameras/preview/stop`,
  `POST .../snapshot/commit`, `GET /media/camera-preview/...`) and the
  `/media` StaticFiles mount are removed; `api/app/camera_preview.py` is
  deleted; the app boots without a lifespan sweeper.
- R-2: the cameras page is a static two-player grid (cam1 + road1) with
  hls.js (pinned 1.5.7 + SRI), reconnect backoff [1s, 2s, 4s, 8s], a
  media-recovery cooldown, and the 15 s session-identity watchdog; no
  batch-preview, snapshot, TTL or summary UI; no fetch to any
  `/api/cameras*` endpoint.
- R-3: the road page plays `HLS_URL="/sea-speed/media/road1/index.m3u8"`
  statically; the stream toggle tears down/starts the local HLS instance
  without any API call; worker control stays on
  `/sea-speed/api/worker/control/road1`.
- R-4: `configure-analytics-profiles.py` takes `--road-relay-url`
  (required) instead of `--preview-catalog`; `road_relay_source()`
  validates scheme rtsp, RFC1918 IPv4 host, explicit port, no userinfo, no
  query/fragment, exact `/road1` path; `deploy-authorized.sh` pins
  `road_relay_url="rtsp://10.123.239.102:8554/road1"`.
- R-5: the renderer gains `ubuntu-relay-extra-path` (protected-inventory-
  sourced, digest-bound candidate for one extra permanent relay path,
  source-on-demand + tcp + least-privilege reader rule + loopback API rule,
  global scalars untouched) and loses every preview mode;
  `camera-relay.sh` gains `extra-path-prepare` and `--relay-path` for
  activate; `deploy/worker/ubuntu/camera-preview-relay.sh` is deleted.
- R-6: the VPS deploy script drops all camera_preview guards and removes
  stale served copies during activate; the exact-artifact build list no
  longer requires `api/app/camera_preview.py`.
- R-7: docs `CAMERA_PREVIEW_INVENTORY.md` and `CAMERA_PREVIEW_RELAY.md` are
  removed; AGENTS.md gains the minimum-code operating rule (issue #637).

## Acceptance criteria

- AC-001: the API route table has no preview/snapshot/media-session routes
  (fingerprint consciously 62 → 56) and `GET /api/cameras` serves the
  static catalog schema; the app imports and boots with no
  `camera_preview` module.
- AC-002: the cameras page boots two static players against the permanent
  HLS URLs with reconnect/recovery wiring and never calls a camera
  endpoint (executed frontend twins).
- AC-003: the road page loads the permanent relay URL, never POSTs any
  camera endpoint, and the stream toggle is API-free (executed frontend
  twins).
- AC-004: `road_relay_source` accepts the production URL and rejects
  non-rtsp schemes, public IPs, missing ports, userinfo, wrong paths and
  query/fragment; `--road-relay-url` is required (executed CLI twins).
- AC-005: the renderer `ubuntu-relay-extra-path` subcommand renders an
  inventory-sourced, byte-identical-on-re-render candidate with the reader
  rule and refuses paths absent from the inventory; preview subcommands are
  gone (executed renderer twins).
- AC-006: full battery green (baseline 1414 passed + 2 skipped + 611
  subtests on the implementation head), ruff/mypy/bash -n/node --check
  green, validators green.

## Runtime feedback

- RF-001: after the box relay gains the road1 path and the worker redeploys,
  the road playlist (`/sea-speed/media/road1/index.m3u8`) serves
  continuously for > 120 s (the old preview TTL) with no preview/start
  request ever issued.
- RF-002: the water page and cam1 stream behave exactly as before (playlist
  200, avc1.64001f 1280x720@15fps); the cameras page plays both streams.
- RF-003: rollback = redeploy the previous main SHA via deploy-vps.yml; the
  preview mechanism is restorable only by reverting this change (deliberate
  decommission; the box relay path and Caddy block are additive and
  independently revertible).

## NFR assessment

- NFR-001 | Area: performance | Target: zero per-request session state work on the media path (no locks, no JSON writes, no sweeper wakeups); static relay paths served by mediamtx/Caddy directly | Validation: route-table fingerprint (no preview routes) + executed frontend twins prove no camera API traffic during playback | Evidence: full battery 1414 passed + 2 skipped + 611 subtests on the implementation head; ruff/mypy green | Status: PASS
- NFR-002 | Area: security | Target: the road1 relay path is reader-bound to the exact VPS reader IP(s) with a least-privilege read rule, source-on-demand tcp from the protected inventory; the road worker relay URL is validated (rtsp + RFC1918 + port + no userinfo + /road1) | Validation: executed renderer twin (reader rule, no publish action) + configure validation twins (8 negative cases) | Evidence: tests/test_stream_unification.py 16 tests, all RED on base 2c8168f | Status: PASS
- NFR-002b | Area: maintainability | Target: the preview mechanism is deleted, not dormant — no orphaned constants, routes, docs, scripts or tests | Validation: repo-wide grep for preview surface (only intentional negatives and the inventory reader survive) | Evidence: grep sweep in the delivery session; battery green after deletion | Status: PASS
