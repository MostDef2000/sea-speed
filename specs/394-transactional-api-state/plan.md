# Plan: Transactional mutable API state persistence

- Issue: #394
- Specification: specs/394-transactional-api-state/spec.md

## Implementation approach

1. `api/app/store.py` (new, standard library only):
   - `read_json_file(path, default)` — missing file returns the default;
     `OSError`/`ValueError` (JSON/Unicode decode) escape so callers can
     fail loud. `write_json_file(path, data)` — per-file flock on a
     `<name>.lock` sibling, uuid-unique tmp, `os.replace`, tmp cleanup.
   - SQLite hot state: `initialize_state_db` (WAL, idempotent),
     `open_state_db` (per-op connection, commit/rollback/raise),
     `append_crossing`/`read_crossings` (cap 5000, newest-first),
     `append_event`/`read_events` (cap 500), `upsert_camera_state`
     (single-statement ON CONFLICT upsert), `read_camera_state`,
     `import_legacy_records`/`import_legacy_camera_state` (idempotent,
     newest-first order preserved, never overwrite existing rows).
2. `api/app/main.py` rewire — every hot-state mutation commits to SQLite
   first, then mirrors the committed projection to the legacy JSON file
   (best-effort, stderr log on failure); reads come from SQLite. Config
   GETs (speed-config/speed-lines/crossing-line) and camera-preview reads
   wrap `read_json_file` in `except store.JSON_READ_ERRORS` → HTTP 500.
   Startup calls `import_legacy_state_store()` after the existing DB
   initialisations; `CROSSINGS_STORE_LIMIT` moves to the top constants
   block because the startup migration runs at import time.
3. Tests — `tests/test_api_state_transaction.py` extracts the real
   main.py functions (AST, like the existing harnesses) and asserts the
   behavioral contract: fail-loud reads (RED on base), no lost updates
   (barrier-forced RMW interleaving, RED on base), unique-tmp collision
   (deterministic RED on base), caps 5000/500, camera-state upsert,
   idempotent/fail-closed/non-destructive migration. Tests that exercise
   main.py functions which only exist post-fix are `skipUnless`-gated so
   the base run shows clean RED failures rather than collection errors.
4. deploy.sh — the ROI migration heredoc writes through a uuid tmp +
   `os.replace`; `store.py` joins the release file set (completeness
   check, download required list, install) and is activated with the soft
   pattern (install + mv before main.py when present, `rm -f` on rollback
   to a pre-#394 release).

## Architecture

Three coordinated pieces:

- `api/app/store.py` (new, stdlib only) — the persistence seam: hardened
  JSON IO (fail-loud read, flock + uuid-tmp + `os.replace` write) and the
  WAL SQLite hot-state store (`crossings`/`event_feed`/`camera_state` with
  `camera_id`, per-op connections, single-statement mutations, same-
  transaction per-camera caps 5000/500, idempotent migration primitives).
  `api/app/main.py` depends only on this module's public surface.
- `api/app/main.py` — SQLite-authoritative reads/writes for state, events
  and crossings; every committed mutation mirrored best-effort into the
  legacy JSON projection (rollback window); config/preview reads fail
  loud as HTTP 500 via `except store.JSON_READ_ERRORS`; the startup
  migration runs after the existing DB initialisations, with
  `CROSSINGS_STORE_LIMIT` hoisted to the top constants block because the
  migration executes at import time.
- `deploy/vps/deploy.sh` — atomic uuid-tmp write in the ROI-migration
  heredoc and minimal `store.py` install plumbing following the file's
  existing conditional-file idiom (release completeness, download
  required list, install, soft activation before `main.py`, clean removal
  on pre-#394 rollback).

## Decisions

- D-1: SQLite (stdlib `sqlite3`, WAL) over file-locked JSON for hot
  state — single-statement inserts remove the RMW lost-update window that
  flock-on-JSON cannot fix without an app-level transaction log.
- D-2: SQLite authoritative + legacy JSON projection mirror (dual-write
  window) instead of a hard cutover — keeps the previous release and
  operator tooling functional for instant rollback; mirror failures are
  best-effort (stderr) so they can never fail an API request.
- D-3: Fail-loud reads with caller-chosen handling (endpoints → 500,
  migration → raise) instead of blanket `except Exception` — silent
  default-on-corruption was the defect being fixed.
- D-4: Per-camera caps enforced with same-transaction DELETEs bounded by
  the inserted row's timestamp — no separate pruning pass, no unbounded
  growth, no partial states.
- D-5: Startup migration is idempotent and never deletes legacy files —
  the previous release keeps reading them during the rollback window.
- D-6: Import-time startup call kept (matches the existing
  water-passages/ROI migration pattern) with names hoisted above the
  block; a failure fails the deploy health gate closed (accepted:
  fail-closed is the desired behaviour for corrupt legacy input).
- D-7: Tests extract the real functions from `main.py` via the existing
  AST harness idiom; head-only functions are `skipUnless`-gated so the
  base run produces clean RED failures instead of collection errors.

## Affected contours

- Sea Speed API persistence only: `api/app/store.py` (new),
  `api/app/main.py`, the new `tests/test_api_state_transaction.py`,
  minimal harness updates in `tests/test_api_contract.py`,
  `tests/test_line_crossing.py`, `tests/test_road_event_hygiene.py`,
  `tests/test_vps_deploy_transaction.py`, `deploy/vps/deploy.sh`, and
  this SDD trio.
- No change to frontend/, worker/, .github/, object registry
  (objects.sqlite3 already transactional), water-passages store, or ROI
  migration semantics beyond the atomic write.
- On-disk state layout on the VPS changes: `state.sqlite3` is
  created next to the legacy JSON stores; the legacy files are kept fresh
  by the projection mirrors, not removed.

## Validation

- Full suite on head: 764 passed, 4 skipped, 119 subtests (baseline
  745 passed / 3 skipped); new behavioral suite 19 passed / 1 skipped
  (skip = head-only collision test).
- RED-on-base (git stash → main.py @ 30ba326, untracked files survive):
  6 failed / 12 passed / 2 skipped — the six failures are exactly the
  fixed defects (4 fail-loud endpoint reads, no-lost-update RMW, fixed-tmp
  collision); stash pop restored the working tree.
- ruff (E9/F, `scripts/quality/ruff.toml`) on all seven changed Python
  files: All checks passed; `bash -n deploy/vps/deploy.sh` clean;
  `tests/test_vps_deploy_transaction.py` 18 passed (store.py install
  plumbing covered by the transaction harness).

## Runtime feedback

- RF-001: Operator actions expected: 0 — deploy stages and activates
  `store.py`; the first boot runs the legacy migration inside the deploy
  health gate (corrupt legacy input → gate fails → automatic rollback).
- RF-002: Failure evidence: HTTP 500 messages naming the corrupt store
  file; stderr lines for best-effort mirror failures; rollback removes
  `store.py` when returning to a pre-#394 release.

## Risk profile

- Risk profile: REQUIRED (derived from VPS production impact; deployment
  transaction audit below covers the contour)
- RISK-001 (main.py boot order): the startup migration runs at import
  time; names it uses (`CROSSINGS_STORE_LIMIT`, path helpers) must be
  defined above the startup block. Mitigation: constants moved to the top
  block; migration uses `analytics_data_file`; import-time NameError would
  fail the deploy health gate loudly (accepted: fail-closed).
- RISK-002 (dual-write divergence): SQLite is authoritative; the legacy
  mirror is a projection of committed rows, so drift self-heals on the next
  write. Mirror failures are best-effort (stderr) and never fail the API
  request.
- RISK-003 (rollback window): legacy JSON files are never deleted and stay
  fresh via mirrors; rollback activation removes `store.py` only when the
  target release does not ship it.
- RISK-004 (deploy.sh deviation): store.py install plumbing is a disclosed
  deviation from "No other deploy.sh changes"; it is required for boot and
  follows the file's existing conditional-install idiom.

## Test design

- Concurrency: barrier-synchronized injected readers force the base RMW
  interleaving deterministically (no-lost-update test); barrier-forced
  shared-tmp rename forces the fixed-tmp collision deterministically.
- Fail-loud: corrupt JSON stores must yield HTTP 500 (base silently
  returned defaults → RED).
- Caps: bulk-seed via one connection, then append to trigger same-
  transaction pruning (5000/500).
- Migration: idempotency, order parity, fail-closed on corrupt legacy
  input, never deletes legacy files (skipUnless guard — head-only).
- Regression: full suite (764 passed, 4 skipped) including the updated
  harnesses and the untouched `test_roi_normalization.py`.

## Correct-course check

- Public API surface unchanged; no new dependencies (stdlib only).
- The `event_feed`/`crossings` `camera_id` column and the deploy.sh install
  plumbing are recorded as deviations in spec.md.
- No commits: changes are left in the working tree for orchestrator
  admission.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: Block A owner approval (OUTCOME APPROVED session 2026-10-08) + receipts issuecomment-6051940042 (base scope) and issuecomment-6052476179 (deploy.sh install-plumbing amendment, peer rollback verdict)
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged VPS state | Retry: NO | Rollback: NONE | Evidence: release_complete + download_release required-list gate exits before rm -rf of the staged target (deploy.sh:203-286)
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next copies discarded; live API unchanged | Retry: NO | Rollback: install_release stages to .next and promotes via mv only after all copies stage successfully; store.py mv precedes main.py mv (new main cannot boot without it) | Evidence: install_release soft pattern (deploy.sh:607-641); test_vps_deploy_transaction behavioral suite (18 tests)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: restart_and_verify health gate (deploy.sh:738-753); fail-closed boot on corrupt legacy store (import_legacy_state_store propagates, deploy auto-rollback)
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: dual-write window — legacy JSON mirrors kept fresh by best-effort projection writes so install_release of the previous release sees fresh data in both directions
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: deploy.sh staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: DEPLOYMENT_ACCEPTED line from the autonomous chain at exact-green-head merge
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour unchanged; soft store handling (install-if-present / rm -f) works in both rollback directions including pre-#394 releases | Evidence: deploy.sh:634-641 + peer verification rollback verdict (receipt issuecomment-6052476179)
