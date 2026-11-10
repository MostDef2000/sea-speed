# Tasks — Issue #635 camera preview TTL-renew

- Issue: #635
- Specification: specs/635-preview-ttl-renew/spec.md
- Authorization: commit approved (owner admission in the dev-chat delivery
  session, 2026-11-10, for the #635 scope: preview TTL-renew + sweeper +
  behavioral/structural tests + SDD trio, chain through merge, deploy and
  probes); base 450b317d

## Delivery tasks

- T-1: tests — RED phase. New behavioral suite (TestClient pattern from
  tests/test_api_http_integration.py): renew-on-media-fetch across TTL
  boundaries, debounce cadence, status/snapshot never renew, expiry
  termination + cleanup, sweeper cleans abandoned session with zero HTTP
  traffic, sweeper retry after failure + shutdown cleanup, session binding
  404s (stale id / traversal / unsupported filename / missing file),
  no-store on 200/206/404, mount compatibility for other media. Structural
  pin updates: test_camera_preview_gallery.py :690 (CAMERA_PREVIEW_TTL_SEC →
  CAMERA_PREVIEW_MAX_LIFETIME_SEC inside build_camera_preview_ffmpeg_args),
  route-path pins :595-603 (+ media route), test_route_table.py fingerprint
  61 → 62 + route-before-mount assertion. DONE (2026-11-10): new suite
  tests/test_camera_preview_ttl_renew.py — 11 tests (T-1..T-8, T-10 of the
  test order; fake-ffmpeg script, clock-shim patching module-level `time` in
  camera_preview/main, TTL=30 + sweep-interval=0.05 monkeypatch). RED on
  base observed twice: by the test worker and re-observed by the
  orchestrator (11 ran, failures=8 — 3 guards green, failures are
  feature-absence: route/sweeper/renew missing). Updated pins RED: route
  table 2/2, gallery :690-group 2/2. Full battery on base+tests: 1441 ran,
  failures=12 — exactly the new/updated tests; the other 1429 + 2 skips
  green. Accepted deviation (orchestrator): tests/test_run_tests_script.py
  frozen guarded-optional-import fingerprint extended by 3 entries for the
  new test file — conscious frozen-base extension, no assertion weakened;
  alternative would be a stealth import surface.
- T-2: api/app/config.py — CAMERA_PREVIEW_MAX_LIFETIME_SEC (default 3600,
  env SEA_SPEED_CAMERA_PREVIEW_MAX_LIFETIME_SEC, clamped) in the established
  idiom + __all__. DONE: try/int/clamp idiom, clamp [300,21600],
  ValueError→3600; RENEW_MIN_INTERVAL_SEC=5 and SWEEP_INTERVAL_SEC=5 fixed
  constants; all three in __all__.
- T-3: api/app/camera_preview.py — ffmpeg args use the backstop constant
  for `-t`; renew_camera_preview_locked (sliding expiry, 5 s debounce,
  expires_epoch+expires_at together, identity untouched); sweep entry for
  the lifespan task; import-seam updates. DONE: renew validates through
  active_camera_preview_locked (expired → terminated, not renewed), proposed
  = time.time() + TTL via module-level time, persists {**state,
  expires_epoch, expires_at} only when proposed >= persisted + 5;
  sweep_camera_preview = lock + active primitive; both seams extended;
  `-t` binds CAMERA_PREVIEW_MAX_LIFETIME_SEC (structure untouched).
- T-4: api/app/main.py — camera_preview_media route (session-bound, 404 +
  no-store, lock released before streaming); mount moved below all explicit
  routes; lifespan sweeper task (startup sweep, 5 s interval, worker-thread
  sweep, shutdown cleanup); import-seam updates. DONE: route at :553 (sync
  def, all early returns under the lock, FileResponse after release,
  any-failure → 404 + no-store), mount at :1598 below every explicit route,
  lifespan = guarded startup sweep + one asyncio task (asyncio.sleep reads
  the module global at loop time, sweep offloaded via asyncio.to_thread,
  per-iteration exceptions logged) + shutdown cancel/await + locked
  terminate; both seams extended.
- T-5: specs/635-preview-ttl-renew/ trio (this spec/plan/tasks) — evidence
  fields filled with observed runs. PENDING.

## Requirements traceability

- AC-001 | Task: T-1+T-3+T-4 | Evidence: tests/test_camera_preview_ttl_renew.py — renew-on-media-fetch across TTL boundaries (playlist/init/segment), session_id/pid stable; RED differential observed on base (11 ran / 8 failures, 3 guards green) | Coverage: COVERED
- AC-002 | Task: T-3+T-4 | Evidence: sweeper tests — abandoned session terminated with zero HTTP traffic, retry after failure, shutdown cleanup; real lifespan test | Coverage: COVERED
- AC-003 | Task: T-3+T-4 | Evidence: no-renew tests (status/snapshot never extend expiry; expired session not resurrectable) | Coverage: COVERED
- AC-004 | Task: T-4 | Evidence: binding/404 tests + no-store on 200/206/404 + mount compatibility tests | Coverage: COVERED
- AC-005 | Task: T-1 | Evidence: structural pins — route fingerprint 62 + route-before-mount, `-t` backstop pin, terminate-first/pid-cleanup pins untouched | Coverage: COVERED
- AC-006 | Task: T-2+T-3+T-4 | Evidence: full battery `Ran 1441 tests / OK (skipped=2)` + quality 8 OK (three independent observations); validate_sdd/validate_repo/validate_contracts green; git status limited to api/app/{config,camera_preview,main}.py + tests + this trio | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (api/app/config.py + api/app/camera_preview.py + api/app/main.py + 4 test files + this trio)
- [x] Required tests and evidence complete (RED differential + focused suites + battery + validators observed)
- [x] Required CI green — pending exact-head CI on the merge PR — auto-synced on merge to main
- [x] Exact-green-head merge complete — pending squash merge to main — auto-synced on merge to main
- [ ] Deployment state resolved (VPS API deploy via deploy-vps.yml on the merged main SHA — authorized chain)
- [ ] Runtime acceptance resolved (RF-001 continuous-watch stability; RF-002 abandonment cleanup; RF-003 unrelated media + water page)
- [ ] Deferred work recorded (none)
- [ ] Risks resolved or explicitly accepted (HEAD fall-through to mount documented in plan D-1 — base-identical, accepted)
- [x] Waivers resolved or current (no waivers)

## Completion gate

- [x] RED observed on base for new/updated tests (DONE: 11 ran / 8 failures
  new suite, route-table 2/2, gallery pins 2/2; battery 1441 ran,
  failures=12 = exactly new/updated tests; re-observed by orchestrator)
- [x] Full battery green on the implementation head (DONE: 1441 ran,
  OK, skipped=2 + quality 8 OK; observed by orchestrator and peer)
- [x] validate_sdd / validate_repo / validate_contracts green (DONE:
  observed by orchestrator; validate_change_contract is the CI PR gate)
- [ ] validate_change_contract green (PENDING — runs in CI on the PR)
- [x] Peer verification verdict recorded (DONE: test-role worker, Qwen3.8
  family, read-only audit — all substantive checks verified; one LOW
  finding: HEAD falls through to the mount as on base, accepted by the
  orchestrator and documented in plan D-1; no divergence on substance)
- [ ] CI green on the PR head (PENDING)
- [ ] Outcome Contract present in issue #635 before deploy dispatch (PENDING)
- [ ] Deploy run green on merged main SHA + RF probes observed (PENDING)
