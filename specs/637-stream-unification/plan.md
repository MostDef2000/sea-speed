# Plan: #637 — both cameras on permanent protected HLS streams

- Issue: #637
- Specification: specs/637-stream-unification/spec.md
- Authorization: commit approved (owner admission in the dev-chat delivery
  session, 2026-11-11, for the #637 scope); base 2c8168f

## Architecture

The unification deletes a mechanism instead of adding one. Both cameras are
served by permanent protected mediamtx relay paths behind the Caddy edge;
the operator pages play them statically; every session-preview mechanism is
removed end to end.

1. **API.** `api/app/camera_preview.py` is deleted with all 7
   preview/snapshot routes and the `/media` StaticFiles mount; the lifespan
   sweeper loop disappears from `main.py` (the app boots with no lifespan).
   `GET /api/cameras` becomes a static catalog derived from
   `sorted(ANALYTICS_IDENTITIES)` under `CAMERA_CATALOG_SCHEMA =
   sea_speed_camera_catalog_v1` — no state file, no lock, no I/O. Config
   constants `CAMERA_PREVIEW_*`/`CAMERA_SNAPSHOT_*` are removed;
   `CAMERA_PREVIEW_RFC1918` is renamed to `RFC1918_NETWORKS` (the constant
   survives because worker-control origin validation still needs the
   RFC1918 set).
2. **Frontend.** The cameras page is a static two-player grid: both
   `<video>` elements and their state/error nodes are authored in HTML with
   stable ids (`video-cam1`, `video-road1`, `frame-*`, `state-*`,
   `error-*`); `cameras.js` attaches hls.js to both permanent URLs with the
   reconnect backoff ladder [1s, 2s, 4s, 8s], a media-recovery cooldown and
   the 15 s session-identity watchdog. Batch-preview, snapshot/commit, TTL
   and summary UI are gone; the only fetch on the page is
   `/sea-speed/api/session`. The road page plays
   `HLS_URL="/sea-speed/media/road1/index.m3u8"` statically; the stream
   toggle is a pure local player control (no API call); worker control
   stays on `/sea-speed/api/worker/control/road1`.
3. **Worker/deploy.** `configure-analytics-profiles.py` replaces the
   preview-catalog input with a required, validated `--road-relay-url`
   (`road_relay_source()`: rtsp scheme, RFC1918 IPv4 host, explicit port,
   no userinfo, no query/fragment, exact `/road1` path);
   `deploy-authorized.sh` pins
   `road_relay_url="rtsp://10.123.239.102:8554/road1"`. The renderer gains
   `ubuntu-relay-extra-path` — one inventory-sourced permanent relay path
   rendered as a digest-bound candidate on top of an already converged
   config (source-on-demand + tcp + least-privilege reader rule + loopback
   API rule, global scalars untouched) — and loses every preview mode.
   `camera-relay.sh` gains `extra-path-prepare` and `--relay-path` for
   activate; `camera-preview-relay.sh` is deleted. The VPS deploy script
   drops all camera_preview guards and removes stale served copies during
   activate.
4. **Box topology (runtime, outside this repo diff).** The box relay
   (docker-mediamtx on 10.123.239.102) gains the `road1` path sourced from
   the protected preview inventory
   (`/var/lib/sea-speed-camera-preview/active/camera-preview-inventory.json`)
   via `extra-path-prepare` + digest-bound activate; Caddy on lifesim
   mirrors `/sea-speed/media/road1/*` → `10.123.239.102:18889` (mirroring
   the cam1 block) and the #635 preview block is removed. The preview
   inventory file itself is decommissioned after the cutover.

## Decisions

- D-1: snapshots die with sessions — the cameras page plays both live
  streams statically; batch-preview, snapshot/commit, TTL and summary UI
  are deleted rather than ported. Owner decision 1(a), 2026-11-11.
- D-2: `fix/635-preview-ttl-renew` is not merged — the #635 fix is already
  in main (`2c8168f`); the branch is deleted in cleanup. Owner decision 2.
- D-3: the catalog route shape is
  `{ok, schema, count, cameras: [{camera_id, display_name, available}]}` —
  a static projection of `ANALYTICS_IDENTITIES`, not a probe of relay
  health; `available: true` is structural (the relay paths are permanent).
- D-4: the route-table fingerprint moves 62 → 56 deliberately; the preview
  routes are removed, not replaced.
- D-5: `RFC1918_NETWORKS` keeps the old constant's role (worker-control
  origin validation) under a name that no longer claims preview ownership.
- D-6: the road worker relay URL is validated fail-closed at configure time
  (8 negative cases pinned) and pinned in `deploy-authorized.sh`; the env
  key `HLS_URL` in `road-worker.env` is preserved so the worker reads its
  source unchanged.

## Affected contours

- VPS API (uvicorn 127.0.0.1:8010 behind Caddy on lifesim): route table,
  catalog route, no lifespan.
- VPS frontend: cameras page (static grid), road page (static HLS_URL).
- Ubuntu worker/relay: `configure-analytics-profiles.py`,
  `deploy-authorized.sh`, `camera-relay.sh`, renderer subcommands;
  box relay gains the permanent `road1` path; docker-mediamtx config
  updated by hand (`/home/seaspeedadmin/mediamtx/mediamtx.yml`).
- Caddy edge (lifesim): new `/sea-speed/media/road1/*` mirror block;
  #635 preview block removed.
- Decommissioned: `sea-speed-camera-preview-relay.service`,
  `data/camera-preview-catalog.json`, preview docs, preview test suites,
  branch `fix/635-preview-ttl-renew`.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: the renderer `ubuntu-relay-extra-path` mode extends an already converged config and is digest-bound; the executed twin pins byte-identical re-render, the untouched cam1 path and the least-privilege reader rule | Validation: tests/test_stream_unification.py renderer twins (render + negative + determinism) | Residual risk: box-side activate is manual (docker config edited by hand) — covered by the runtime acceptance probes | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: road1 is reader-bound to the exact VPS reader IP(s) with a read-only rule (no publish action), source-on-demand tcp from the protected inventory; the worker relay URL is validated fail-closed (rtsp + RFC1918 + explicit port + no userinfo + exact /road1) | Validation: renderer twin asserts the reader rule and absence of publish; configure twins pin 8 negative cases | Residual risk: the reader IP must match the actual docker-mediamtx source IP — verified at activate time via mediamtx API/logs | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: the road page and worker switch to a path that does not exist until the box relay gains road1 — the deploy order is box first (extra-path-prepare → activate → docker config), then worker redeploy, then Caddy; acceptance probes gate completion | Validation: RF-001 (>120 s continuous road playlist with no preview/start) and RF-002 (water unchanged) | Residual risk: a wrong reader IP would 403 the VPS HLS fetch — detected immediately by RF-001 and fixed by re-rendering with the observed source IP | Owner: delivery orchestrator | Status: MITIGATED
- RISK-004 | Category: DATA | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: the preview state file and catalog are deleted with the mechanism; no data migration exists or is needed (sessions were ephemeral by design) | Validation: battery green after deletion; repo-wide grep shows no orphaned preview surface | Residual risk: none — preview state was never durable data | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-005 | Category: BUS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: operator-facing behavior improves (no start action, no TTL freeze); the only lost capability is snapshot/commit, which the owner explicitly retired (decision 1(a)) | Validation: SC-1/SC-2 executed frontend twins | Residual risk: none | Owner: delivery orchestrator | Status: ACCEPTED

## Test design

- TEST-001 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: route-table fingerprint 56 + no preview routes; catalog contract tests (schema/count/shape from ANALYTICS_IDENTITIES); app boots without camera_preview module (full battery 1414 passed + 2 skipped + 611 subtests on the implementation head)
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: executed frontend twins on the cameras page (frontend_html harness) — two static players, permanent URLs, reconnect/recovery wiring, no camera API fetch; RED authenticity observed on base 2c8168f (16/16 new tests fail)
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: executed frontend twins on the road page — static HLS_URL to the permanent relay path, no preview/start|stop, API-free stream toggle; worker-control contract reads main.js for both water and road
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: configure twins — production URL accepted; 8 negative cases (non-rtsp, public IP, missing port, userinfo, wrong path, query, fragment, missing flag) via executed CLI
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: executed renderer twins — inventory-sourced candidate with reader rule and untouched cam1 path, byte-identical re-render, refusal of paths absent from the inventory, preview subcommands gone from --help
- TEST-006 | Covers: AC-006 | Level: end-to-end | Priority: P1 | Evidence: ruff/mypy/bash -n/node --check green; validate_sdd/validate_repo/validate_contracts/validate_change_contract green; CI on the exact head

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no work starts; scope stays unadmitted | Retry: re-present scope and re-run admission | Rollback: not applicable (read-only) | Evidence: owner `commit approved` recorded in the delivery session; PR Change Contract fields
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: deploy blocked before any mutation | Retry: fix the failing precheck and re-run | Rollback: not applicable (read-only) | Evidence: green CI on the PR head (Repository validation, quality-integration, static-contract-security, security suite)
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: box relay without road1 (road page down, water unaffected); worker redeploy skipped | Retry: re-run extra-path-prepare/activate with corrected inputs (e.g. observed reader IP) | Rollback: previous docker mediamtx config restored from the pre-edit backup; worker redeploy of the previous main SHA | Evidence: deploy-vps.yml + deploy-ubuntu-worker.yml runs on the merged main SHA; box activate transcript with candidate digest
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: deployment stands; probes report failure and the task stays open | Retry: re-run probes after fixing the observed failure | Rollback: not applicable (read-only probes) | Evidence: acceptance probes RF-001/RF-002/RF-003 output recorded in the delivery session
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: main advanced without a verified runtime — probes fail and the rollback path executes | Retry: not applicable (merge is single-shot; failures go to rollback) | Rollback: redeploy the previous main SHA via deploy-vps.yml; revert commit if the change itself is broken | Evidence: squash-merge SHA of PR #638; deploy workflow run links
- TX-006 | Stage: HOUSEKEEPING | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: preview inventory/service remnants may survive on the box; no functional impact (paths are additive) | Retry: re-run the decommission commands in a follow-up | Rollback: not applicable (removal of already-decommissioned artifacts) | Evidence: decommission transcript (service stopped/disabled, catalog file removed, branch deleted)
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: delivery record incomplete; probes and run URLs still exist in CI/GitHub | Retry: re-post the record to issue #637 | Rollback: not applicable (append-only records) | Evidence: issue #637 delivery comment; JOURNAL entry; CI run URLs
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: previous main SHA redeployed; road page returns to the pre-#637 state only by reverting the change (deliberate decommission) | Retry: re-run the rollback deploy workflow | Rollback: redeploy previous main SHA via deploy-vps.yml; box/Caddy changes are additive and independently revertible | Evidence: rollback target SHA recorded in the delivery record before dispatch

## Validation

- Full battery on the implementation head: 1414 passed, 2 skipped, 611
  subtests (three independent observations across the session).
- RED authenticity: all 16 tests in tests/test_stream_unification.py fail
  on base 2c8168f (worktree run observed: 16 failed).
- ruff (repo config) clean; mypy strict baseline (7 files) clean;
  `bash -n` on all touched shell scripts; `node --check` on both JS files.
- validate_sdd / validate_repo / validate_contracts /
  validate_change_contract green locally before push.

## Runtime feedback

- RF-001: after the box relay gains the road1 path and the worker
  redeploys, the road playlist (`/sea-speed/media/road1/index.m3u8`)
  serves continuously for > 120 s (the old preview TTL) with no
  preview/start request ever issued.
- RF-002: the water page and cam1 stream behave exactly as before
  (playlist 200, avc1.64001f 1280x720@15fps); the cameras page plays both
  streams.
- RF-003: rollback = redeploy the previous main SHA via deploy-vps.yml;
  the preview mechanism is restorable only by reverting this change
  (deliberate decommission; the box relay path and Caddy block are
  additive and independently revertible).

