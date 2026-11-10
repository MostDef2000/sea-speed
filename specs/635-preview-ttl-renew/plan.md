# Plan: #635 — camera preview TTL-renew

- Issue: #635
- Specification: specs/635-preview-ttl-renew/spec.md
- Authorization: commit approved (owner admission in the dev-chat delivery
  session, 2026-11-10, for the #635 scope); base 450b317d

## Architecture

The preview lifecycle keeps its single JSON state file, `CAMERA_PREVIEW_LOCK`
(threading.Lock) and one-active-slot terminate-first semantics. Three
mechanisms compose the new lifetime model:

1. **Renew point (media fetches).** A new sync route
   `GET /media/camera-preview/{session_id}/{filename}` (handler
   `camera_preview_media` in `api/app/main.py`) validates the request under
   `CAMERA_PREVIEW_LOCK`: session regex, equality with the active session
   (via the existing expiry/pid-validating primitive), filename allowlist
   (`index.m3u8`, `init.mp4`, `segment_%05d.m4s` shape), regular-file check
   inside the session directory. On success it renews (sliding
   `now + CAMERA_PREVIEW_TTL_SEC`, persisted only when the proposed expiry
   exceeds the persisted one by ≥ `CAMERA_PREVIEW_RENEW_MIN_INTERVAL_SEC = 5`)
   and returns the file with `Cache-Control: no-store`; failures are 404
   (also `no-store`). The lock is released before the response streams.
2. **Sweeper (abandonment bound).** FastAPI lifespan starts exactly one
   background task per app instance: startup sweep, then every
   `CAMERA_PREVIEW_SWEEP_INTERVAL_SEC = 5` it offloads a synchronous sweep to
   a worker thread; the thread takes `CAMERA_PREVIEW_LOCK` and calls the
   existing expiry/pid-validating primitive (which terminates expired
   sessions). Per-iteration exceptions are logged and retried; shutdown
   stops the loop and terminates any active preview through the same locked
   path. This is the codebase's first background task; it exists because the
   road page never polls preview state, so lazy expiry alone cannot bound an
   abandoned tab's leak.
3. **Hard backstop.** `build_camera_preview_ffmpeg_args` emits
   `-t str(CAMERA_PREVIEW_MAX_LIFETIME_SEC)` (new config constant, default
   3600, env `SEA_SPEED_CAMERA_PREVIEW_MAX_LIFETIME_SEC`, clamped) instead of
   `-t CAMERA_PREVIEW_TTL_SEC`. Even if the sweeper dies or the API hangs,
   ffmpeg self-terminates at the backstop; the next start (terminate-first)
   or any state-touching route cleans the stale state.

Registration order: the mount `app.mount("/media", ...)` moves from
main.py:369 to below all explicit routes; the new `@app.get` route is
declared among the routes. Empirically proven (starlette 1.10.0 in-memory
probe, exploration report): a route registered before the mount wins for its
path while all other media paths still hit the mount.

## Decisions

- D-1: Renew signal = successful fetch of the session's playlist, init
  segment, or media segment through the new route. Status polling, snapshot
  reads/commits, HEAD and unknown paths never renew (the cameras gallery
  polls status every 3 s and must not keep an abandoned session alive).
  HEAD note (peer-verified 2026-11-10): FastAPI's APIRoute does not auto-add
  HEAD, so HEAD requests to the preview media path fall through to the
  StaticFiles mount exactly as on base — "HEAD never renews" holds by
  construction; the no-store scope is GET responses (the CF-caching
  rationale targets GET bytes; hls.js fetches with GET only). Adding HEAD
  to the route would make HEAD execute the handler and renew, contradicting
  this decision — left as base behavior deliberately.
- D-2: Serving point = decorator-visible `@app.get` route + mount moved
  below all routes. Rejected: narrowing the mount into sub-mounts (wider
  compatibility surface for zero benefit); programmatic Route insertion
  (bypasses the route-table fingerprint scanner — stealth surface).
- D-3: Auth posture = session-bound, NO application role check (reproduces
  today's mount behavior; edge auth guards `/sea-speed/*`; hls.js fetches
  must keep working for Viewer role). Stricter than today: media is served
  only for the ACTIVE session id.
- D-4: ffmpeg lifetime = `-t CAMERA_PREVIEW_MAX_LIFETIME_SEC` hard backstop
  retained (deviation from the architect's "remove `-t` entirely"
  recommendation). Rationale: the architect gated no-cap on demonstrated
  service-level child containment; the production unit
  (`sea-speed-api.service`) is not managed in this repo (deploy.sh only
  restarts it), its KillMode is not verifiable from here, and sandbox SSH to
  the VPS is dead (KB, #593 entry) — the containment evidence cannot be
  produced in this change. The backstop makes orphan ffmpeg impossible
  regardless of sweeper/API fate at the cost of at most one self-healing
  reconnect per backstop period of truly continuous viewing. The
  `test_camera_preview_gallery.py` AST pin (:690) is consciously re-pointed
  from `CAMERA_PREVIEW_TTL_SEC` to `CAMERA_PREVIEW_MAX_LIFETIME_SEC`.
- D-5: Sweeper = lifespan asyncio task + sync sweep in a worker thread
  (never block the loop on the threading.Lock or process waits); interval 5
  s; startup sweep; shutdown cleanup. Rejected: lazy-only (insufficient for
  the road tab), threading.Timer (unmanaged lifecycle).
- D-6: Renewal window = full TTL re-arm per eligible fetch with a 5 s
  persistence debounce; effective persisted inactivity window is TTL−5…TTL
  (documented, not claimed as exact). No new env knobs beyond the backstop
  constant.
- D-7: Contract = additive only; `session_id`/`started_at` immutable,
  `expires_at` advances, `ttl_sec` unchanged; status reads validate but
  never renew.

## Affected contours

- `api/app/camera_preview.py` — ffmpeg args backstop constant; new
  `renew_camera_preview_locked`; sweeper entry (`sweep_camera_preview`);
  dual-import seam extensions.
- `api/app/main.py` — new media route (before the moved mount); lifespan
  with the sweeper task; both import seams; route-table surface +1.
- `api/app/config.py` — `CAMERA_PREVIEW_MAX_LIFETIME_SEC` (env
  `SEA_SPEED_CAMERA_PREVIEW_MAX_LIFETIME_SEC`, default 3600, clamped) in the
  established idiom + `__all__`.
- `tests/test_camera_preview_gallery.py` — conscious pin updates (:690
  constant, route-path pins, policy expression unchanged) + new structural
  assertions (backstop present, no TTL in ffmpeg args, route-before-mount).
- `tests/test_route_table.py` — fingerprint 61 → 62.
- NEW behavioral tests (TestClient harness per
  `tests/test_api_http_integration.py`): renew/expiry/sweeper/binding/
  no-store/mount-compat coverage per spec AC-001..004.
- `specs/635-preview-ttl-renew/` — this trio.

## Risk profile

- Orphan ffmpeg (leak): bounded three ways (sliding expiry + sweeper;
  `-t` backstop; terminate-first). The sweeper dying degrades cleanup to the
  backstop bound instead of unbounded encode.
- Lock contention: media fetches take the lock briefly (validate + renew);
  state writes debounced to 1 per 5 s; response streaming happens outside
  the lock.
- Route-table stealth surface: decorator-visible route only; fingerprint
  updated deliberately (61 → 62) with a route-before-mount assertion.
- CF caching stale playlists: `no-store` on every preview media response.
- Multi-worker state races: pre-existing invariant (single-process uvicorn,
  threading.Lock + JSON state already shared by start/stop/commit); not
  worsened; deployment shape unchanged.
- Auth regression: no new role check; session binding is strictly tighter
  than the bare mount; Viewer media access preserved.

## Transaction records

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no change lands | Retry: correct authorization/scope evidence then re-enter | Rollback: NOT REQUIRED before mutation | Evidence: owner `commit approved` (2026-11-10, #635 scope, one-key-whole-chain), base 450b317d
- TX-002 | Stage: TEST-RED | Mutation: YES | Failure disposition: FATAL | State after failure: red suite on base is the expected signal, branch not mergeable | Retry: fix test harness errors only (never weaken assertions to obtain green) | Rollback: revert test commit | Evidence: new/updated tests observed RED on base 450b317d, all other battery tests green on base
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: implementation incomplete or battery red | Retry: only with the full battery green on the exact head | Rollback: revert the commit | Evidence: code commit + battery run record
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate not accepted | Retry: resolve CI/validator failures on the branch | Rollback: NOT REQUIRED | Evidence: CI green on exact head, validate_sdd + validate_change_contract green, peer review verdict
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: previous deploy behavior remains | Retry: re-dispatch deploy-vps.yml after fixing (Outcome Contract must exist in #635 first) | Rollback: redeploy previous main SHA via deploy-vps.yml | Evidence: deploy-vps.yml run on the merged main SHA (full 40-hex)
- TX-006 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but acceptance incomplete | Retry: replay probes without redeployment when the deployed SHA is unchanged | Rollback: decide from actual served behavior, not evidence alone | Evidence: RF-001/RF-002/RF-003 probes observed post-deploy
- TX-007 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if the previous deployed release cannot be restored or verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: use the protected previous deployed release | Evidence: existing VPS rollback logs and verified origin/public health

## Runtime feedback

- RF-001: after merge → deploy-vps.yml dispatch (full merged-main SHA) →
  the API rides the release tarball; RF-001 probe of the spec (road page
  watched continuously > 6 min: stable session_id, advancing segments, no
  TTL reconnect) verifies the renewal behavior on production.
- RF-002: abandonment probe — after fetches stop, the ffmpeg process for
  the session is gone and preview state clears within TTL + sweep interval
  + termination grace (operator/pgrep check via deploy evidence).
- RF-003: rollback = redeploy previous main SHA via deploy-vps.yml; the
  change is rollback-safe (single API process, no schema, no data
  migration; the old code restores the exact 120s hard-TTL behavior).

## Validation

- RED authenticity (new/updated tests against base): OBSERVED — 11 ran /
  8 failures (3 guards green), route-table 2/2, gallery pins 2/2; battery
  on base+tests 1441 ran, failures=12 = exactly the new/updated tests
  (test worker + orchestrator re-observation).
- Full battery after implementation: OBSERVED — 1441 ran, OK (skipped=2)
  + quality 8 OK (implementation worker, peer verifier, orchestrator).
- validate_sdd / validate_repo / validate_contracts: OBSERVED green by the
  orchestrator; validate_change_contract runs in CI on the PR.
- Peer verification: OBSERVED — independent read-only audit (Qwen3.8
  family): lock handling, time/constant patchability, traversal, route/
  mount ordering, test integrity (git diff 02b3cd9 -- tests/ specs/ empty),
  RED authenticity per-test analysis, battery green. One LOW finding
  (HEAD fall-through to mount, base-identical) accepted and documented in
  D-1.
