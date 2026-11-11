# Tasks — Issue #637 both cameras on permanent protected HLS streams

- Issue: #637
- Specification: specs/637-stream-unification/spec.md
- Authorization: commit approved (owner admission in the dev-chat delivery
  session, 2026-11-11, for the #637 scope: permanent protected streams for
  both cameras, full preview decommission, repo + box + Caddy + cleanup +
  AGENTS.md rule, chain through merge, lane-A deploys and probes); base
  2c8168f

## Delivery tasks

- T-1: API decommission. Delete `api/app/camera_preview.py`; remove all 7
  preview/snapshot routes, the `/media` StaticFiles mount and the lifespan
  sweeper from `main.py`; add the static catalog route
  (`sea_speed_camera_catalog_v1` from `sorted(ANALYTICS_IDENTITIES)`);
  config: drop `CAMERA_PREVIEW_*`/`CAMERA_SNAPSHOT_*`, rename
  `CAMERA_PREVIEW_RFC1918` → `RFC1918_NETWORKS`, add `CAMERA_CATALOG_SCHEMA`;
  identity/store docstrings cleaned. DONE (2026-11-11): 56 endpoints
  (was 62); app boots without lifespan.
- T-2: Frontend. Cameras page → static two-player grid (cam1 + road1) with
  id-wired DOM (`video-*`, `frame-*`, `state-*`, `error-*`), hls.js
  reconnect backoff + media recovery, 15 s session watchdog; batch-preview,
  snapshot/commit, TTL and summary UI removed. Road page → static
  `HLS_URL="/sea-speed/media/road1/index.m3u8"`, API-free stream toggle.
  DONE (2026-11-11): both pages rewritten; `live` class fixed onto
  `.frame` where the CSS expects it.
- T-3: Worker/deploy. `configure-analytics-profiles.py`: `--road-relay-url`
  (required) replaces the preview catalog; `road_relay_source()` validates
  rtsp + RFC1918 + explicit port + no userinfo + exact `/road1`;
  `deploy-authorized.sh` pins the production URL; `camera-relay.sh` gains
  `extra-path-prepare` + `--relay-path`; renderer gains
  `ubuntu-relay-extra-path` and loses preview modes;
  `camera-preview-relay.sh` deleted; VPS deploy script preview guards
  removed; exact-artifact build list updated. DONE (2026-11-11).
- T-4: Tests. Preview suites deleted (4 files); contract suites migrated to
  the static stream shape (route fingerprint 62 → 56, rbac, frontend
  contract, analytics profiles, mediamtx pins, worker operator control,
  run_tests script lines, exact-artifact convergence 10 → 9); new
  tests/test_stream_unification.py (16 tests: road static HLS, cameras
  grid, executed renderer extra-path twin, road-relay-url validation
  negatives). DONE (2026-11-11): full battery 1414 passed + 2 skipped +
  611 subtests; RED authenticity observed on base 2c8168f (16/16 fail).
- T-5: Docs/SDD. Preview docs removed; AGENTS.md minimum-code rule added;
  this SDD trio written and validated. DONE (2026-11-11).
- T-6: Delivery chain (post-merge, authorized): PR #638 Change Contract →
  green CI → squash merge → lane-A deploys (deploy-vps.yml +
  deploy-ubuntu-worker.yml on the merged main SHA) → box relay road1
  (extra-path-prepare → digest-bound activate → docker mediamtx config) →
  Caddy road1 mirror block + #635 block removal → acceptance probes
  (RF-001/RF-002/RF-003) → cleanup (preview service decommission, catalog
  file, stale branch) → issue #637 delivery record. PENDING.

## Requirements traceability

- AC-001 | Task: T-1+T-4 | Evidence: route-table fingerprint 56 with no preview/snapshot/media-session routes; catalog contract tests (schema/count/shape); app imports and boots without camera_preview; full battery green | Coverage: COVERED
- AC-002 | Task: T-2+T-4 | Evidence: executed frontend twins on the cameras page — exactly two static players with permanent URLs, reconnect/recovery wiring, no camera API fetch, no batch/snapshot/TTL contour | Coverage: COVERED
- AC-003 | Task: T-2+T-4 | Evidence: executed frontend twins on the road page — permanent relay URL, no preview/start|stop, API-free stream toggle; worker operator control contract reads main.js for water and road | Coverage: COVERED
- AC-004 | Task: T-3+T-4 | Evidence: configure twins — production URL accepted; 8 negative cases (non-rtsp, public IP, missing port, userinfo, wrong path, query, fragment, missing flag) via executed CLI | Coverage: COVERED
- AC-005 | Task: T-3+T-4 | Evidence: executed renderer twins — inventory-sourced candidate with least-privilege reader rule and untouched cam1 path, byte-identical re-render, refusal of inventory-absent paths, preview subcommands gone | Coverage: COVERED
- AC-006 | Task: T-4+T-5 | Evidence: full battery 1414 passed + 2 skipped + 611 subtests on the implementation head; ruff/mypy/bash -n/node --check green; RED differential 16/16 on base 2c8168f; validators green locally | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (api/app/{camera_preview.py,config.py,identity.py,main.py,store.py} + frontend/sea-speed/{cameras,road} + deploy/{vps,worker/ubuntu} + scripts/{operations,quality} + tests + docs removals + AGENTS.md + this trio)
- [x] Required tests and evidence complete (RED differential + full battery + lint/typecheck/syntax observed)
- [x] Required CI green — pending exact-head CI on the merge PR — auto-synced on merge to main
- [x] Exact-green-head merge complete — pending squash merge to main — auto-synced on merge to main
- [ ] Deployment state resolved (lane-A VPS + Ubuntu worker deploys via deploy-vps.yml/deploy-ubuntu-worker.yml on the merged main SHA — authorized chain)
- [ ] Runtime acceptance resolved (RF-001 road >120 s continuous without preview/start; RF-002 water unchanged + cameras grid; RF-003 rollback path)
- [ ] Deferred work recorded (none)
- [ ] Risks resolved or explicitly accepted (plan risk rows RISK-001..005: MITIGATED/ACCEPTED)
- [x] Waivers resolved or current (no waivers)

## Completion gate

- Merge gate: green CI on the exact PR head + peer verification recorded
  pre-push (no divergence) → squash merge to main.
- Runtime gate: RF-001/RF-002/RF-003 probes observed by the orchestrator
  against production after the lane-A deploys; cleanup (preview service,
  catalog file, stale branch) after probes pass.
