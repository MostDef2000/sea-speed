# Spec: #633 — water page stream reconnect retries indefinitely

- Issue: #633
- Specification: specs/633-water-stream-infinite-reconnect/spec.md
- Authorization: commit approved (owner admission in the dev-chat delivery
  session, 2026-11-10, for the #633 scope: water stream infinite reconnect +
  structural test + SDD trio, chain through merge, deploy and probes);
  base 8e8a77f

## Product outcome

The water page (frontend/sea-speed/main.js) no longer gives up on the HLS
stream permanently. Before the fix, `scheduleStreamReconnect` exhausted its
4-step retry ladder (`STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000]`, ~15s
total), set the stream status to `error` and stopped scheduling any further
attempt — every recovery path (playback watchdogs waiting/stalled/error,
fatal HLS network/media errors, the ended event, the play-rejected path)
feeds the same ladder, so any relay/CDN transient longer than ~15s left the
main page dead until a manual click. After the fix the water page retries
indefinitely with the delay index capped at the last ladder rung (8s max
between attempts) — behaviorally identical to the road page
(frontend/sea-speed/road/main.js `scheduleReconnect`, line 37), which
already retries forever in production. A successful playback still resets
the attempt counter (`markStreamOnline`), so healthy sessions restart the
ladder from the shortest delay.

## User scenarios

- SC-1: the cam1 relay or its upstream hiccups for longer than ~15s while
  the owner watches the water page — before the fix the page showed
  `error` and stayed dead until a manual click; after the fix the page
  keeps retrying every ≤8s and recovers automatically once the relay
  serves segments again.
- SC-2: a transient HLS network/media error fires mid-playback — the
  reconnect ladder schedules the next attempt with a capped delay; the
  status line shows the attempt count without a meaningless "/4"
  denominator.
- SC-3: the stream comes back after N failed attempts — `markStreamOnline`
  resets `reconnectAttempt` to 0, so the next outage starts from the
  shortest delay (unchanged behavior).
- SC-4: the owner stops the stream deliberately (`disconnectStream`) — no
  reconnect is scheduled and the counter resets (unchanged behavior).

## Requirements

- R-1: `frontend/sea-speed/main.js` — `scheduleStreamReconnect` removes
  the exhaustion early-return branch (the old
  `if(reconnectAttempt>=STREAM_RETRY_DELAYS_MS.length){...error...return}`)
  and caps the delay index exactly like the road page:
  `STREAM_RETRY_DELAYS_MS[Math.min(reconnectAttempt,STREAM_RETRY_DELAYS_MS.length-1)]`.
  Status/log strings drop the `/${STREAM_RETRY_DELAYS_MS.length}`
  denominator (status `reconnecting ${attempt}`, log
  `HLS reconnect ${attempt} in ${delay}ms: ${reason}`). No other function
  in the file changes.
- R-2: `tests/test_frontend_contract.py` — a new structural test class
  `StreamReconnectSemanticsStructuralTests` (same live-source assertion
  style as `StreamRetryLadderStructuralTests`) pins: (a) the water page
  caps the delay index with `Math.min(reconnectAttempt,...)`; (b) the
  water page has no terminal exhaustion (`HLS reconnect exhausted` absent,
  no `reconnectAttempt>=STREAM_RETRY_DELAYS_MS.length` terminal); (c) the
  road page keeps its `Math.min` delay cap (symmetry guard).
- R-3: forbidden surfaces stay byte-untouched:
  `frontend/sea-speed/road/**` (read-only reference),
  `frontend/sea-speed/cameras/**`, `api/**`, `worker/**`, `deploy/**`,
  `contracts/**`, `.github/**`, `scripts/**`, `specs/631-*/**`.

## Acceptance criteria

- AC-001: the water page's `scheduleStreamReconnect` contains no terminal
  exhaustion branch and caps the delay index at the last ladder rung —
  pinned by the new structural tests, which fail against the base source
  (RED authenticity observed: 2 of 3 tests fail on base 8e8a77f).
- AC-002: the road page's infinite-retry semantics stay pinned — its
  `Math.min` delay cap remains asserted live source.
- AC-003: full battery green with exactly the three new structural tests
  added (1429 OK, skipped=2; baseline 1426 OK skipped=2); pytest on
  tests/test_frontend_contract.py green (28 passed + 6 subtests);
  `node --check frontend/sea-speed/main.js` clean; validate_sdd passed.

## Runtime feedback

- RF-001: production effect requires the VPS front deploy (deploy-vps.yml)
  after merge — the fixed main.js rides the release tarball; acceptance
  probes verify the deployed main.js contains the
  `Math.min(reconnectAttempt` cap and the cam1 playlist stays live.
- RF-002: the fix is rollback-safe by construction — reverting to the
  previous main SHA restores the previous main.js byte-for-byte; no state,
  schema, API, or auth surface is involved. During a prolonged relay
  outage the page now retries every ≤8s (one playlist fetch per attempt) —
  the same load profile the road page has shown in production without
  pathology.

## NFR assessment

- NFR-001 | Area: stream availability | Target: the water page recovers from any relay/CDN transient regardless of duration — reconnect attempts never terminate, delay capped at 8000ms | Validation: tests/test_frontend_contract.py StreamReconnectSemanticsStructuralTests — delay-index cap asserted on live source, exhaustion terminal asserted absent; RED authenticity observed on base 8e8a77f | Evidence: RED 2 failed / 1 passed on base; green focused run 28 passed + 6 subtests; full battery 1429 OK (skipped=2) | Status: PASS
- NFR-002 | Area: behavioral symmetry | Target: water reconnect semantics match the road page (infinite retry, capped backoff, reset on success) with no residual asymmetry in the retry ladder | Validation: structural road-cap guard test; peer traced all 6 scheduleStreamReconnect call-sites for liveness (no silent hang, no retry storm) and confirmed markStreamOnline/disconnectStream reset the counter | Evidence: peer verification verdict APPROVE (independent second worker, 2:0) | Status: PASS
- NFR-003 | Area: change discipline | Target: the fix lands as one line in one served file plus the appended test class, every forbidden surface byte-untouched | Validation: git diff scope check (exactly 2 files before the trio); node --check clean; validate_sdd green | Evidence: recorded in tasks.md Completion gate | Status: PASS
