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
  idiom + __all__. PENDING.
- T-3: api/app/camera_preview.py — ffmpeg args use the backstop constant
  for `-t`; renew_camera_preview_locked (sliding expiry, 5 s debounce,
  expires_epoch+expires_at together, identity untouched); sweep entry for
  the lifespan task; import-seam updates. PENDING.
- T-4: api/app/main.py — camera_preview_media route (session-bound, 404 +
  no-store, lock released before streaming); mount moved below all explicit
  routes; lifespan sweeper task (startup sweep, 5 s interval, worker-thread
  sweep, shutdown cleanup); import-seam updates. PENDING.
- T-5: specs/635-preview-ttl-renew/ trio (this spec/plan/tasks) — evidence
  fields filled with observed runs. PENDING.

## Battery identity

- Baseline (base 450b317d): 1429 OK, skipped=2 (recorded at #633).
- Post-implementation: PENDING (expected 1429 + new tests, skipped=2).

## Completion gate

- [x] RED observed on base for new/updated tests (DONE: 11 ran / 8 failures
  new suite, route-table 2/2, gallery pins 2/2; battery 1441 ran,
  failures=12 = exactly new/updated tests; re-observed by orchestrator)
- [ ] Full battery green on the implementation head (PENDING)
- [ ] validate_sdd / validate_repo / validate_contracts green (PENDING)
- [ ] validate_change_contract green (PENDING)
- [ ] Peer verification verdict recorded (PENDING)
- [ ] CI green on the PR head (PENDING)
- [ ] Outcome Contract present in issue #635 before deploy dispatch (PENDING)
- [ ] Deploy run green on merged main SHA + RF probes observed (PENDING)
