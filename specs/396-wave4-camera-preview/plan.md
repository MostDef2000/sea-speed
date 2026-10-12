# Plan: Camera preview/snapshot extraction — api/app/camera_preview.py (Wave 4)

- Issue: #396
- Specification: specs/396-wave4-camera-preview/spec.md

## Implementation approach

1. `api/app/camera_preview.py` (new) — byte-range extraction of
   main.py:477-763 at base 5cad94c6 as ONE contiguous region (15 functions
   in original order: `validate_camera_preview_source`,
   `load_camera_preview_catalog`, `camera_snapshot_path`,
   `camera_snapshot_public_metadata`, `build_camera_snapshot_extract_args`,
   `camera_snapshot_luma_spread`, `camera_snapshot_candidate_is_usable`,
   `commit_camera_snapshot_locked`, `camera_preview_public_state`,
   `camera_preview_pid_matches`, `cleanup_camera_preview_media`,
   `terminate_camera_preview_locked`, `active_camera_preview_locked`,
   `build_camera_preview_ffmpeg_args`, `start_camera_preview_locked`).
   Header imports the stdlib set the bodies use (`ipaddress`, `json`, `os`,
   `re`, `signal`, `subprocess`, `sys`, `time`, `uuid`,
   `datetime`/`timezone`, `pathlib.Path`, `typing`,
   `urllib.parse.urlsplit`), `fastapi.HTTPException`, plus the dual-idiom
   `config` (14 camera/preview constants) and `store` (`read_json_file`,
   `write_json_file`; `store.JSON_READ_ERRORS` resolved through the module
   exactly as before) seam — explicit name lists, sys.path-anchored
   absolute fallback for direct-file loads. The extraction is performed by
   scripted line-range copy from the base `main.py` (never retyped); an
   automated audit asserts the moved region appears byte-identical in the
   new module (full-region + 15/15 per-function).
2. `api/app/main.py` — delete the moved blocks (keeping exactly two blank
   lines between survivors); insert the wave-4 seam after the wave-3 seam
   (try/except dual idiom, explicit re-export name lists,
   `# noqa: F401`); drop the now-unused `import ipaddress`, `import re`,
   `import signal`, `import subprocess` and
   `from urllib.parse import urlsplit`. No binding line is added — the
   state-closure trace (Decision D-1) shows no shared mutable state needs
   injection. Routes and all other logic untouched this wave.
3. Tests — extend the gallery source walk in
   `tests/test_camera_preview_gallery.py` to join `camera_preview.py` right
   after `main.py` (D-4); add `camera_preview.py` to the synthetic release
   fixtures in `tests/test_vps_deploy_transaction.py`. All other readers
   verified unaffected by grep over every moved name.
4. `deploy/vps/deploy.sh` — add `CAMERA_PREVIEW_TARGET` and mirror the
   wave-1/2/3 pattern through all seven sites (see Decision D-3).
5. `scripts/quality/build_exact_artifacts.py` — vps required list gains
   `api/app/camera_preview.py` (deploy.sh convergence, wave-3 precedent);
   `scripts/ci/validate_sdd.py` — grandfather the wave set (Decision D-5).

## Architecture

One new leaf module under `api/app/`, deployed before `main.py`:

- `api/app/camera_preview.py` — camera-preview/snapshot service; depends
  on `config` (constants), `store` (stateless JSON persistence helpers),
  `fastapi.HTTPException` and stdlib. Carries NO mutable module state:
  the `*_locked` functions are lock-free primitives whose callers hold
  `config.CAMERA_PREVIEW_LOCK`; preview runtime state persists in
  `CAMERA_PREVIEW_STATE_FILE` via `store.read_json_file`/`write_json_file`.
- `api/app/main.py` — unchanged logic; thin explicit re-exports keep the
  historical import surface (`main.load_camera_preview_catalog`,
  `main.start_camera_preview_locked`, ...) working for callers and test
  readers; the six camera routes keep acquiring
  `with CAMERA_PREVIEW_LOCK:` around the moved primitives.

Import-cycle rule: the new module never imports `main`. Its dependency
edges (`config`, `store`, `fastapi`) are all one-directional leaves, so no
sentinel/binding mechanism is needed — unlike wave 2/3, where
`passage_mirrors` needed the `open_passages_db` injection because
`prune_water_passages → _delete_passage_mirrors` would close a cycle. Dual
try/except idiom is replicated exactly so all modules share one instance of
every dependency per import mode (package mode: relative imports;
direct-file mode: sys.path anchor + absolute imports reusing the
sys.modules cache).

## Decisions

- D-1 (state closure — the work order's primary hazard): the mutable-state
  sweep found exactly one module-level mutable object in the slice's orbit,
  `CAMERA_PREVIEW_LOCK = threading.Lock()` at config.py:145, and it is NOT
  referenced by any of the 15 moved functions — only by the five lock-acquiring route
  handlers that stay in `main.py` (`*_locked` is a caller-contract suffix,
  not an ownership claim). Runtime state lives in the JSON state file, not
  in module globals; catalog loading is stateless (no cache dict). The
  camera-preview-EXCLUSIVE vs shared-state fork therefore does not arise:
  nothing moves, and nothing needs the wave-2 `passage_mirrors`
  sentinel-injection pattern. Verified: lock singleton identity
  (`main.CAMERA_PREVIEW_LOCK is main.config.CAMERA_PREVIEW_LOCK`), package
  and direct-file import modes green, roi-normalization mock harness green
  (mocks only fastapi/Path.mkdir/sqlite3.connect; `threading` is real
  stdlib and config.py has booted under that harness since wave 1).
- D-2 (constants stay in config.py): the work order's "camera/preview
  constants consumed only by this slice" is already satisfied by wave 1 —
  all 15 camera/preview constants live in `config.py` under its
  exactly-one-owner rule; none remain in `main.py`. Re-moving them would
  contradict the wave-1 ownership decision, break the config `__all__` seam
  and split the import-time directory-creation side effects. The new module
  imports them from `config` like every other `api/app` module; the three
  constants shared with staying routes are imported by both, with no
  duplication.
- D-3 (deploy envelope, wave-1/2/3 precedent): `deploy.sh` is extended
  through all seven sites of the established module pattern for
  `camera_preview.py`: (1) `CAMERA_PREVIEW_TARGET` next to `API_TARGET`;
  (2) `release_complete` existence check; (3) download required list;
  (4) release install; (5) `bootstrap_current_release` capture of the live
  copy; (6) `install_release` staging to `.next`; (7) activation mv/rm
  **before** the `main.py` promotion, bound to the release's content
  (store.py soft pattern: staged copy promoted only when the release ships
  the module, otherwise live copy + stale `.next` removed so a pre-wave-4
  rollback boots cleanly).
- D-4 (reader updates, minimal set): only two test files need changes —
  the gallery source walk (its API string joins main+identity+config and
  pins camera-preview definitions/ordering; camera_preview.py joins right
  after main.py) and the synthetic release fixture. Grepping every moved
  name across `tests/` confirms no other reader references the slice:
  `test_api_contract.py`'s walks contain no camera names, `test_route_table.py`
  reads main.py only (routes stay), `test_roi_normalization.py` loads main
  through the seam unchanged. No hardening is added this wave (work order:
  "none new"); the wave 2-3 residuals stay informational.
- D-5 (grandfather update): `scripts/ci/validate_sdd.py` grandfathers
  `396-wave4-camera-preview` in the `"396"` set of
  `GRANDFATHERED_PREFIX_COLLISIONS` (exact-set equality; any other
  duplicate prefix still fails closed). Authorized by the wave-4 work
  order (standing directive 2026-10-12).
- D-6 (imports dropped from main): `import ipaddress`, `import re`,
  `import signal`, `import subprocess` and `from urllib.parse import
  urlsplit` lose their last consumers with this move (verified by
  line-level scan over the post-move main.py) and are dropped to keep ruff
  F401 clean — the wave-3 `import sqlite3`/`contextmanager` precedent.
  `uuid`/`threading`/`os` stay (still used by analytics/state handlers);
  the wave-1 config seam keeps its full name list under `# noqa: F401`
  (explicit re-export seam precedent).

## Affected contours

- VPS only (`api/**` + `deploy/vps/deploy.sh` + quality scripts/tests):
  deploy envelope REQUIRED; deploy rides the merge via deploy-vps.yml
  (orchestrator DEPLOY-TRIGGER, полоса A). No Ubuntu worker, no edge, no
  frontend change.

## Validation

- Full suite `python3 -m unittest discover -s tests` green (baseline: 908
  tests / 4 skipped; expected head: 908 / 4 — no test count change).
- `python3 scripts/ci/validate_repo.py` green.
- `python3 scripts/ci/validate_sdd.py` green (grandfathered #396 wave set).
- `ruff check . --config scripts/quality/ruff.toml` clean.
- `bash -n deploy/vps/deploy.sh` clean.
- Byte-identity audit: the 287-line moved region byte-identical to
  `git show 5cad94c6:api/app/main.py` (full-region + 15/15 per-function);
  route table 61 == 61 vs base with unchanged handler names.
- VPS deploy transaction suite green (23 tests).
- Import modes: package import smoke (lock singleton + one canonical
  config/store instance) and the roi-normalization standalone-exec mock
  harness both green.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: deploy.sh extended through all seven module-pattern sites with staging+activation of camera_preview.py BEFORE main.py; bootstrap capture keeps rollback releases bootable; a missing module fails the release before any live mutation | Validation: deploy transaction suite (23 tests) + bash -n + release-shape fixtures | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the mutable-state closure hazard was traced exhaustively (D-1): no moved function references module-level mutable state; the lock and all constants stay in config.py with one canonical instance per import mode; no injection needed | Validation: lock singleton identity check; package + direct-file import smoke; tests/test_roi_normalization.py green | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the gallery text-pinning suite re-pointed to the new module by joining camera_preview.py into its source walk (D-4); def-block and index-slice pins verified to resolve inside the new module with identical text; no assertion weakened | Validation: tests/test_camera_preview_gallery.py green (18 tests) | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: extraction done by scripted byte-range copy from the base commit with an automated byte-identity audit (full region + 15/15 functions); blank-line layout preserved; main.py diff limited to deletions + seam + dropped imports | Validation: byte-identity audit PASS; git diff --stat review; ruff clean | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: validate_sdd grandfather is an exact-set match for the four registered #396 wave dirs only; any other duplicate prefix still fails closed | Validation: python3 scripts/ci/validate_sdd.py green on head | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-006 | Category: DATA | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: move-only extraction — the preview state-file protocol (read_json_file/write_json_file against CAMERA_PREVIEW_STATE_FILE), session validation regexes, TTL/timeout constants and quality-gate thresholds are byte-identical; no schema or data migration | Validation: byte-identity audit; catalog/session/state-path pins in the gallery suite green | Residual risk: LOW | Owner: Worker | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P1 | Evidence: python3 -m unittest discover -s tests (expected 908 tests / 4 skipped; baseline 908/4)
- TEST-002 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: tests/test_vps_deploy_transaction.py (23 tests; synthetic releases carry camera_preview.py)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P1 | Evidence: bash -n deploy/vps/deploy.sh
- TEST-004 | Covers: AC-002, AC-007 | Level: unit | Priority: P1 | Evidence: python3 scripts/ci/validate_repo.py; python3 scripts/ci/validate_sdd.py; vps required list contains every deploy.sh api/app module
- TEST-005 | Covers: AC-004, AC-006 | Level: unit | Priority: P1 | Evidence: tests/test_route_table.py (61-route frozen fingerprint with handler names); byte-identity audit of the moved region vs 5cad94c6
- TEST-006 | Covers: AC-004, AC-006 | Level: unit | Priority: P1 | Evidence: tests/test_camera_preview_gallery.py (camera-preview pins against the joined walk)
- TEST-007 | Covers: AC-005 | Level: unit | Priority: P2 | Evidence: tests/test_roi_normalization.py (mocked standalone exec of main.py; wave-4 seam import chain exercised) + package-import smoke with lock singleton check

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Runtime feedback

- RF-001: Deploy rides the merge (deploy-vps.yml, orchestrator-owned
  DEPLOY-TRIGGER); health gate = origin + public smoke as before; no new
  operator steps.
- RF-002: If activation health fails, deploy.sh rolls back to the previous
  release via install_release(previous) — for a pre-wave-4 previous release
  camera_preview.py is removed from live (the old main.py does not import
  it); bootstrap releases capture the live copy when present.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: work order for #396 wave 4 (extraction-only scope, standing directive 2026-10-12 autonomous continuation); branch sdd/396-wave4-camera-preview from 5cad94c6
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged VPS state | Retry: NO | Rollback: NONE | Evidence: release_complete and the download required list now also require api/app/camera_preview.py; the gate exits before any mutation of the live tree
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next copies discarded; live API unchanged | Retry: NO | Rollback: install_release stages camera_preview.py to .next and promotes via mv only after all copies stage successfully; the mv precedes the main.py mv (the new main imports it at boot) | Evidence: install_release soft pattern; test_vps_deploy_transaction behavioral suite (23 tests, write_release fixtures carry the new file)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: restart_and_verify health gate unchanged by wave 4
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: wave 4 moves no state-mutation code (persistence primitives keep their exact bodies and call graphs; the preview state-file protocol is byte-identical)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: deploy.sh staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: DEPLOYMENT_ACCEPTED line from the autonomous chain at exact-green-head merge
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour unchanged; activation is bound to the selected release content for camera_preview.py exactly as for store.py — staged .next promoted only when the release ships the module, otherwise the live copy and any stale .next are removed so a pre-wave-4 rollback boots cleanly; bootstrap capture preserves a live camera_preview.py alongside the captured main.py | Evidence: deploy.sh activation + bootstrap capture sites + test_vps_deploy_transaction rollback tests

## Deviations from the work order

- D-1 (primary): state-closure decision — NO mutable state moves with the
  slice and NO injection is needed. The work order's fork
  (camera-preview-exclusive state moves vs shared state injected
  passage_mirrors-style) does not arise: the only mutable module object in
  the slice's orbit is `config.CAMERA_PREVIEW_LOCK`, referenced exclusively
  by the five lock-acquiring staying route handlers; preview runtime state is the JSON
  state file accessed through stateless store helpers; catalog loading is
  stateless. Documented in spec.md Product outcome and verified by the
  singleton/import-mode evidence.
- D-2: camera/preview constants do NOT move — they have lived in
  config.py since wave 1 (exactly-one-owner rule); the "constants consumed
  only by this slice" scope item is already satisfied upstream of main.py.
- D-3/D-5: deploy.sh seven-site mirror, artifact-manifest entry and the
  validate_sdd grandfather entry are delivered as the work order's items
  2-4 prescribe (grandfather authorized by the work order).
- D-4: reader updates limited to the two files that need them (gallery
  walk, vps fixture); the work order's "extend its source walk" is applied
  to tests/test_camera_preview_gallery.py exactly, and the grep sweep
  confirmed the other named readers stay green without edits.
