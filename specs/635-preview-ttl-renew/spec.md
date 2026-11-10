# Spec: #635 — camera preview lives while watched (TTL-renew), cleaned up when abandoned

- Issue: #635
- Specification: specs/635-preview-ttl-renew/spec.md
- Authorization: commit approved (owner admission in the dev-chat delivery
  session, 2026-11-10, for the #635 scope: preview TTL-renew + sweeper +
  behavioral/structural tests + SDD trio, chain through merge, deploy and
  probes); base 450b317d

## Product outcome

The road page no longer freezes for ~3.5–10.5 s every ~2 minutes. Today a
camera preview session is hard-bounded by `CAMERA_PREVIEW_TTL_SEC=120`
(`ffmpeg -t 120`, `expires_epoch = started + TTL`): the encode self-terminates
at 120 s, the road page (which never polls preview state while playing)
detects the stall after its 2.5 s grace and reconnects through the retry
ladder — a periodic self-healing stutter by design. The TTL exists to prevent
abandoned tabs from accumulating eternal ffmpeg processes; naively removing
it would trade a cosmetic freeze for a resource leak.

After the fix the preview session is kept alive by evidence of actual
viewing: successful HTTP fetches of the session's HLS playlist, init segment,
or media segments slide the session expiry forward (`now + TTL`, debounced).
A session nobody fetches from expires exactly as before and is terminated by
a periodic sweeper (plus the existing lazy expiry on every state-touching
route), so an abandoned tab still ends with a killed ffmpeg process, removed
media, and an empty state file. A hard process backstop
(`ffmpeg -t CAMERA_PREVIEW_MAX_LIFETIME_SEC`, default 3600 s) bounds the
worst-case encode lifetime even if the sweeper or the whole API misbehaves.
Terminate-first and the one-active-slot invariant are untouched.

## User scenarios

- SC-1: the owner watches the road page continuously — the preview session
  no longer dies at 120 s; `session_id` stays stable, the playlist keeps
  advancing, and the periodic freeze disappears (worst case: one
  self-healing reconnect per `CAMERA_PREVIEW_MAX_LIFETIME_SEC`).
- SC-2: the owner closes the tab — media fetches stop, the sliding window
  lapses, the sweeper terminates ffmpeg and removes the session media and
  state without any further HTTP traffic.
- SC-3: another operator starts a preview for a different camera —
  terminate-first kills the previous session exactly as today; the new
  session is the only active one.
- SC-4: a viewer opens the cameras gallery — status polling (every 3 s)
  shows the active session but never extends it; only real media fetches
  renew.

## Requirements

- R-1: a decorator-visible API route serves preview media
  (`GET /media/camera-preview/{session_id}/{filename}`), registered before
  the `/media` StaticFiles mount (the mount moves below all explicit
  routes); events/passages/overlays media keep flowing through the mount
  unchanged.
- R-2: the media route is session-bound: session id must full-match
  `CAMERA_PREVIEW_SESSION_RE`, must equal the active session (validated
  through the existing expiry/pid check), the filename must be a generated
  HLS artifact (`index.m3u8`, `init.mp4`, `segment_*.m4s`), and the file
  must be a regular file inside that session's directory; everything else
  is 404. No application-level role check (reproduces today's mount
  posture; edge auth guards `/sea-speed/*`).
- R-3: successful media responses renew the session: proposed expiry
  `now + CAMERA_PREVIEW_TTL_SEC`, persisted only when it exceeds the
  persisted expiry by at least `CAMERA_PREVIEW_RENEW_MIN_INTERVAL_SEC = 5`
  (write debounce); `expires_epoch` and `expires_at` move together;
  `session_id` and `started_at` never change; `ttl_sec` stays the
  configured inactivity TTL.
- R-4: ffmpeg no longer self-terminates at the TTL: `-t` binds to the new
  `CAMERA_PREVIEW_MAX_LIFETIME_SEC` (default 3600, env
  `SEA_SPEED_CAMERA_PREVIEW_MAX_LIFETIME_SEC`, clamped) as a hard backstop;
  the API-side sliding expiry becomes the primary life control.
- R-5: a periodic sweeper (FastAPI lifespan-managed background task,
  `CAMERA_PREVIEW_SWEEP_INTERVAL_SEC = 5`, startup sweep included)
  terminates expired sessions via the existing locked termination path; the
  synchronous sweep runs off the event loop; per-iteration failures are
  logged and retried; shutdown stops the loop and terminates any active
  preview.
- R-6: preview media responses carry `Cache-Control: no-store` (success,
  range, and 404) — CF must never serve cached preview bytes (KB: CF caches
  static up to 4 h even for authorized requests).
- R-7: public API contract stays additive: start/stop/state/commit response
  shapes unchanged; `expires_at` advances on renewal; `session_id` stable
  while watched (cameras.js treats a change as restart).

## Acceptance criteria

- AC-001: continuous media fetches across several original TTL windows keep
  the same session and pid alive (behavioral, TestClient harness).
- AC-002: after fetches stop, the session is terminated (ffmpeg killed,
  media directory removed, state `{}`) within TTL + sweep interval +
  termination grace — without any HTTP request (sweeper test).
- AC-003: status polling and snapshot reads never renew; expired sessions
  cannot be resurrected through any route.
- AC-004: invalid/stale session ids, traversal attempts, unsupported
  filenames and missing files return 404 without renewal; preview media
  responses (200/206/404) carry `Cache-Control: no-store`; unrelated media
  paths still serve through StaticFiles.
- AC-005: terminate-first / one-slot semantics and the pid-cleanup pins are
  unchanged; the route-table fingerprint is consciously updated (61 → 62)
  with the preview route asserted before the mount.
- AC-006: full battery green (baseline 1429 OK skipped=2 + new tests),
  focused preview suites green, validators green.

## Runtime feedback

- RF-001: on production, watching the road page continuously for > 3
  original TTL periods (> 6 min) shows a stable `session_id` and advancing
  segments — no TTL-induced reconnect (probe: authenticated playlist
  samples + session id from the start response).
- RF-002: after the owner stops watching, the ffmpeg process for the
  session disappears and the preview state clears within the abandonment
  bound (probe: `pgrep ffmpeg` on the VPS via deploy logs / operator
  check).
- RF-003: unrelated media (events/passages/overlays) and the water page are
  unaffected (probe: public smoke checks in the deploy run + water page
  probe from #633).

## NFR assessment

- NFR-001 | Performance | media route adds one state read + occasional state write per fetch | Validation: debounce caps writes at 1 per 5 s per session | Evidence: behavioral test on write cadence | Status: PASS
- NFR-002 | Reliability | orphan ffmpeg impossible: sliding expiry + sweeper + `-t` hard backstop + terminate-first | Validation: sweeper test + backstop constant pin | Evidence: test suite | Status: PASS
- NFR-003 | Security | media route adds session binding (stricter than today's bare mount), no-store, no new role surface | Validation: 404/binding tests | Evidence: test suite | Status: PASS
- NFR-004 | Compatibility | single-process uvicorn deployment with threading.Lock + JSON state is a pre-existing invariant (start/stop/commit already share it); this change does not add cross-process state | Validation: unchanged deployment shape | Evidence: deploy.sh restarts the same unit | Status: PASS
