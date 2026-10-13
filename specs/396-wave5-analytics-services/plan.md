# Plan: Analytics services extraction — api/app/analytics.py (Wave 5)

- Issue: #396
- Specification: specs/396-wave5-analytics-services/spec.md

## Implementation approach

1. `api/app/analytics.py` (new) — byte-range extraction of THREE regions of
   main.py at base beea1067 as verbatim copies in original order:
   286-329 (events sweep block: `EVENTS_MEDIA_GRACE_SECONDS`,
   `EVENTS_SWEEP_INTERVAL_SECONDS`, `_events_sweep_state`,
   `sweep_events_media`), 342-511 (analytics state layer + ROI constants +
   the wave-3-deferred point-normalization helpers: `default_state`,
   `analytics_data_file`, `analytics_default_state`, `analytics_state`,
   `clean_points_list`, ROI constants, `_is_normalized_point`,
   `_clean_norm_points`, `_infer_legacy_ref_w_h`, `_normalize_from_absolute`,
   `_denormalize_to_absolute`, `_normalize_legacy_polygon`), 1051-1218
   (crossing services: `get_analytics_crossing_line`,
   `post_analytics_crossing_line`, `CROSSING_DIRECTIONS`,
   `append_crossing_record`, `post_analytics_crossing`, `VLZ_TIMEZONE`,
   `_vlz_day_bounds`, `get_analytics_crossings_summary`). The
   `passage_mirrors.open_passages_db` binding (332-339) and the module-tail
   init calls (514-519, incl. `sweep_events_media(force=True)`) stay in
   `main.py` between/after the regions. Header imports the stdlib set the
   bodies use (`json`, `os`, `sys`, `time`, `uuid`,
   `datetime`/`timezone`, `pathlib.Path`, `typing`), `fastapi.HTTPException`,
   plus the dual-idiom `config` (12 constants), `identity`
   (`analytics_identity`, `now_iso`), `objects_registry`
   (`open_objects_db`, `optional_float`, `optional_int`,
   `persist_object_event`) and `store` (`read_json_file`, `write_json_file`)
   seam — explicit name lists, sys.path-anchored absolute fallback for
   direct-file loads. The extraction is performed by scripted line-range
   copy from the base `main.py` (never retyped); an automated audit asserts
   the moved regions appear byte-identical in the new module (full-region
   + 18/18 per-function + constants).
2. `api/app/main.py` — delete the moved blocks; insert the wave-5 seam after
   the wave-4 seam (try/except dual idiom, explicit re-export name lists of
   all 27 names, `# noqa: F401`); drop the now-unused config seam names
   (`STATE_FILE`, `EVENTS_FILE`, `ROI_FILE`, `SPEED_CONFIG_FILE`,
   `SPEED_LINES_FILE`, `DATA_DIR`, `CROSSINGS_STORE_LIMIT` — both seam
   branches), the `date`/`timedelta` datetime names and `typing.List`.
   No binding line is added — the state-closure trace (Decision D-1) shows
   the only mutable object moves with its exclusive consumer. Routes and all
   other logic untouched this wave.
3. Tests — walk extensions only: `tests/test_api_state_transaction.py`
   (multi-source `_extract_functions`/`_API_TREES`; teeth preserved:
   real store append/persist paths and byte-pinned legacy mirrors;
   `post_analytics_event` is still extracted from `main.py`),
   `tests/test_line_crossing.py` (`ANALYTICS_SOURCE` + `tree_candidates` +
   the VLZ-summary and cam1-legacy-kind text joins, assertions
   byte-unchanged), `tests/test_storage_retention.py` (`load_functions`
   walk), `tests/test_api_contract.py` (`api_sources` + `load_functions`
   walks, positioned after `water_passages` and before `identity`),
   `tests/test_analytics_profiles.py` (additive/camera-isolated source
   walk), `tests/test_vps_deploy_transaction.py` (fixture). All other
   readers verified unaffected by grep over every moved name.
4. `deploy/vps/deploy.sh` — add `ANALYTICS_TARGET` and mirror the
   wave-1/2/3/4 pattern through all seven sites (see Decision D-3).
5. `scripts/quality/build_exact_artifacts.py` — vps required list gains
   `api/app/analytics.py` (deploy.sh convergence, wave-3/4 precedent);
   `scripts/ci/validate_sdd.py` — grandfather the wave set (Decision D-5).

## Architecture

One new leaf module under `api/app/`, deployed before `main.py`:

- `api/app/analytics.py` — analytics services; depends on `config`
  (constants), `identity` (`analytics_identity`, `now_iso`),
  `objects_registry` (objects DB layer + event persistence + numeric
  coercion), `store` (camera-state/events/crossings persistence + stateless
  JSON helpers), `fastapi.HTTPException` and stdlib. Carries exactly one
  module-level mutable object: `_events_sweep_state`, a dict referenced
  exclusively by `sweep_events_media` (both move together).
- `api/app/main.py` — unchanged logic; thin explicit re-exports keep the
  historical import surface (`main.default_state`,
  `main.get_analytics_crossings_summary`, ...) working for callers and test
  readers; the analytics routes stay in `main.py` and delegate through the
  seam; the module tail keeps `sweep_events_media(force=True)` at boot.

Import-cycle rule: the new module never imports `main`. Its dependency
edges (`config`, `identity`, `objects_registry`, `store`, `fastapi`) are
all one-directional leaves, so no sentinel/binding mechanism is needed —
unlike wave 2/3, where `passage_mirrors` needed the `open_passages_db`
injection. Dual try/except idiom is replicated exactly so all modules share
one instance of every dependency per import mode (package mode: relative
imports; direct-file mode: sys.path anchor + absolute imports reusing the
sys.modules cache).

## Decisions

- D-1 (state closure — the work order's primary hazard, inverted vs wave 4):
  the mutable-state sweep found exactly one module-level mutable object in
  the slice, `_events_sweep_state` (main.py:288-290 at base), and it is
  referenced EXCLUSIVELY by `sweep_events_media` (repo-wide grep: no staying
  route, no test, no reader). It therefore moves with the slice — the
  exact opposite of the wave-2/3 injection fork, which does not arise.
  No locks/deques live in the slice; the ROAD_LIVE/WATER_LIVE locks+deques
  and live-stream handlers are a separate slice that stays in `main.py`.
  All other moved module objects are immutable constants.
- D-2 (slice boundary includes the wave-3-deferred ROI helpers): wave 3
  deferred `clean_points_list`, `_clean_norm_points`,
  `_infer_legacy_ref_w_h`, `_normalize_from_absolute`,
  `_denormalize_to_absolute`, `_normalize_legacy_polygon` on the assumption
  of non-analytics callers. Caller evidence on the wave-5 base: every
  reference is inside the moving slice — analytics ROI routes
  (get/post_analytics_roi), speed-lines routes (get/post_analytics_crossing_line)
  and the crossing-line service functions — and `get_cam1_roi`/
  `post_cam1_roi` are thin delegates to `get/post_analytics_roi`. No
  staying code calls them, so they move (with the ROI constants
  `DEFAULT_ROI_REF_W/H`, `LEGACY_ROI_W/H`).
- D-3 (deploy envelope, wave-1/2/3/4 precedent): `deploy.sh` is extended
  through all seven sites of the established module pattern for
  `analytics.py`: (1) `ANALYTICS_TARGET` next to `API_TARGET`;
  (2) `release_complete` existence check; (3) download required list;
  (4) release install; (5) `bootstrap_current_release` capture of the live
  copy; (6) `install_release` staging to `.next`; (7) activation mv/rm
  **before** the `main.py` promotion, bound to the release's content
  (store.py soft pattern: staged copy promoted only when the release ships
  the module, otherwise live copy + stale `.next` removed so a pre-wave-5
  rollback boots cleanly).
- D-4 (reader updates, minimal set, walk-extension-only): six test files
  need changes, all of them extensions of existing multi-source walks or
  text joins — `test_api_state_transaction.py` (its `_extract_functions`
  hard-fails on missing names; now walks main+analytics),
  `test_line_crossing.py` (source list + `tree_candidates` + two text joins),
  `test_storage_retention.py`, `test_api_contract.py`,
  `test_analytics_profiles.py` (the `analytics_data_file` pin moved),
  `test_vps_deploy_transaction.py` (fixture). The retirement teeth stay
  byte-effective: the state-transaction harness still exercises the real
  store append/persist code paths and its byte-pinned legacy mirrors are
  unchanged; `post_analytics_event` (staying) is still extracted from
  `main.py` with the real `write_json_file` fallback, so
  `test_road_event_hygiene.py` needs no edit at all. No assertion is
  weakened anywhere; no hardening is added this wave.
- D-5 (grandfather update): `scripts/ci/validate_sdd.py` grandfathers
  `396-wave5-analytics-services` in the `"396"` set of
  `GRANDFATHERED_PREFIX_COLLISIONS` (exact-set equality; any other
  duplicate prefix still fails closed). Authorized by the wave-5 work
  order (standing directive; wave-4 precedent 2026-10-13).
- D-6 (imports dropped from main): the config seam names `STATE_FILE`,
  `EVENTS_FILE`, `ROI_FILE`, `SPEED_CONFIG_FILE`, `SPEED_LINES_FILE`,
  `DATA_DIR`, `CROSSINGS_STORE_LIMIT` lose their last consumers with this
  move (both seam branches updated; verified by line-level scan over the
  post-move main.py), as do `date`/`timedelta` (datetime import narrows to
  `datetime, timezone` — road/water live handlers still use those) and
  `typing.List` (ruff F401; its consumers were the moved crossing fns).
  KEEP verified in use: `EVENTS_MEDIA_DIR` (post_analytics_event),
  `STATE_DB_FILE`, `EVENTS_FEED_LIMIT`, `os`/`sys`/`uuid`/`time`,
  `read_json_file`/`write_json_file`, `datetime`/`timezone`.
  The wave-1 config seam keeps its remaining name list under
  `# noqa: F401` (explicit re-export seam precedent).
- D-7 (DEFECT-1 fix — `now_iso` from `identity`): the first extraction
  imported `analytics_identity` from `identity` but missed `now_iso`, used
  at analytics.py:402 (`post_analytics_crossing_line`), :423
  (`post_analytics_crossing`) and :508 (`get_analytics_crossings_summary`)
  — an F821 at call time that the runtime suites did not surface (their
  harnesses inject `now_iso` into the exec namespace) but ruff did. Fix:
  `now_iso` is imported from `identity` in BOTH idioms (relative
  `from .identity import analytics_identity, now_iso`; absolute
  `from identity import analytics_identity, now_iso`). `now_iso` stays
  owned by `identity.py` (wave-1 shared kernel) — never moved. Follow-up:
  an AST closure audit (`/tmp/opencode/wave5_closure.py`) compiles every
  moved function's global-name usage against module imports/definitions
  (18/18 resolve) and ruff F-rules run clean tree-wide, which also caught
  the dead `typing.List` import in `main.py` (dropped, D-6).

## Affected contours

- VPS only (`api/**` + `deploy/vps/deploy.sh` + quality scripts/tests):
  deploy envelope REQUIRED; deploy rides the merge via deploy-vps.yml
  (orchestrator DEPLOY-TRIGGER, полоса A). No Ubuntu worker, no edge, no
  frontend change.

## Validation

- Full suite `python3 -m unittest discover -s tests -p 'test_*.py'` green
  (baseline: 908 tests / 4 skipped; expected head: 908 / 4 — no test count
  change).
- `python3 scripts/ci/validate_repo.py` green.
- `python3 scripts/ci/validate_sdd.py` green (grandfathered #396 wave set).
- `ruff check . --config scripts/quality/ruff.toml` clean (0 errors —
  catches F821 dependency-closure breaks and F401 dead imports).
- `bash -n deploy/vps/deploy.sh` clean.
- Byte-identity audit: the three moved regions byte-identical to
  `git show beea1067:api/app/main.py` (full-region + 18/18 per-function +
  9 constants); route table 61 == 61 vs base with unchanged handler names.
- VPS deploy transaction suite green.
- Import modes: package import smoke and the roi-normalization
  standalone-exec mock harness both green; AST dependency-closure audit
  green (18/18 functions resolve all global names).

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: deploy.sh extended through all seven module-pattern sites with staging+activation of analytics.py BEFORE main.py; bootstrap capture keeps rollback releases bootable; a missing module fails the release before any live mutation | Validation: deploy transaction suite + bash -n + release-shape fixtures | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: the dependency-closure hazard (D-7) is now guarded two ways: ruff F-rules tree-wide (F821 undefined names, F401 dead imports) and an AST closure audit compiling every moved function's globals against module imports (18/18); the runtime suites alone were shown insufficient (their ns injection masks missing module globals) | Validation: ruff exit 0; wave5_closure.py "closure OK: 18 top-level functions"; full suite green | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the mutable-state closure hazard was traced exhaustively (D-1): `_events_sweep_state` is slice-exclusive and moves with its only consumer; no locks/deques move; no injection needed; the live-stream locks/deques stay in main.py | Validation: repo-wide grep for `_events_sweep_state` (analytics.py only, referenced by sweep_events_media only); suite green | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the six reader suites re-pointed to the new module by extending existing multi-source walks/text joins only (D-4); retirement teeth preserved byte-effective (real store paths, byte-pinned legacy mirrors, post_analytics_event still extracted from main); no assertion weakened | Validation: focused runs of the six reader suites green; test_road_event_hygiene green unchanged | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-005 | Category: TECH | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: extraction done by scripted byte-range copy from the base commit with an automated byte-identity audit (3 regions + 18/18 functions + 9 constants); blank-line layout preserved; main.py diff limited to deletions + seam + dropped imports | Validation: byte-identity audit PASS; git diff --stat review; ruff clean | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-006 | Category: OPS | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: validate_sdd grandfather is an exact-set match for the five registered #396 wave dirs only; any other duplicate prefix still fails closed | Validation: python3 scripts/ci/validate_sdd.py green on head | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-007 | Category: DATA | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: move-only extraction — the crossings store protocol (append_crossing/read_crossings vs CROSSINGS_STORE_LIMIT), events sweep grace/interval constants and the VLZ day-window math are byte-identical; no schema or data migration | Validation: byte-identity audit; VLZ/date-range pins in test_line_crossing green | Residual risk: LOW | Owner: Worker | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P1 | Evidence: python3 -m unittest discover -s tests -p 'test_*.py' (expected 908 tests / 4 skipped; baseline 908/4; observed OK)
- TEST-002 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: tests/test_vps_deploy_transaction.py (synthetic releases carry analytics.py)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P1 | Evidence: bash -n deploy/vps/deploy.sh
- TEST-004 | Covers: AC-002 | Level: unit | Priority: P1 | Evidence: python3 scripts/ci/validate_repo.py; python3 scripts/ci/validate_sdd.py; build_exact_artifacts vps list contains every deploy.sh api/app module
- TEST-005 | Covers: AC-004, AC-006 | Level: unit | Priority: P1 | Evidence: tests/test_route_table.py (61-route frozen fingerprint with handler names); byte-identity audit of the moved regions vs beea1067
- TEST-006 | Covers: AC-004, AC-006 | Level: unit | Priority: P1 | Evidence: tests/test_line_crossing.py, tests/test_analytics_profiles.py (moved-code pins against the joined walks)
- TEST-007 | Covers: AC-005 | Level: unit | Priority: P2 | Evidence: tests/test_roi_normalization.py (mocked standalone exec of main.py; wave-5 seam import chain exercised) + package-import smoke + wave5_closure.py AST closure audit
- TEST-008 | Covers: AC-001, AC-005 | Level: unit | Priority: P1 | Evidence: python3 -m ruff check . --config scripts/quality/ruff.toml (0 errors — F821/F401 guard)

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
  release via install_release(previous) — for a pre-wave-5 previous release
  analytics.py is removed from live (the old main.py does not import it);
  bootstrap releases capture the live copy when present.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: work order for #396 wave 5 (extraction-only scope, standing directive autonomous continuation); branch sdd/396-wave5-analytics-services from beea1067
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged VPS state | Retry: NO | Rollback: NONE | Evidence: release_complete and the download required list now also require api/app/analytics.py; the gate exits before any mutation of the live tree
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next copies discarded; live API unchanged | Retry: NO | Rollback: install_release stages analytics.py to .next and promotes via mv only after all copies stage successfully; the mv precedes the main.py mv (the new main imports it at boot) | Evidence: install_release soft pattern; test_vps_deploy_transaction behavioral suite (write_release fixtures carry the new file)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: restart_and_verify health gate unchanged by wave 5
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: wave 5 moves no state-mutation code (persistence primitives keep their exact bodies and call graphs; the crossings store protocol and events sweep semantics are byte-identical)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: deploy.sh staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: DEPLOYMENT_ACCEPTED line from the autonomous chain at exact-green-head merge
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour unchanged; activation is bound to the selected release content for analytics.py exactly as for camera_preview.py — staged .next promoted only when the release ships the module, otherwise the live copy and any stale .next are removed so a pre-wave-5 rollback boots cleanly; bootstrap capture preserves a live analytics.py alongside the captured main.py | Evidence: deploy.sh activation + bootstrap capture sites + test_vps_deploy_transaction rollback tests

## Deviations from the work order

- D-1 (primary): state-closure decision — the ONE mutable object in the
  slice (`_events_sweep_state`) is analytics-slice-exclusive (referenced
  only by `sweep_events_media`) and moves with the slice; NO injection is
  needed. The work order's fork (slice-exclusive state moves vs shared
  state injected passage_mirrors-style) resolves to the first branch.
- D-2: the wave-3-deferred ROI helpers + ROI constants join the slice —
  caller evidence shows every caller is inside the moving code
  (analytics ROI/speed-lines routes, crossing-line services; cam1 routes
  are thin delegates). Documented with line references in spec.md.
- D-4: reader updates limited to the six files that need them, walk
  extensions only; teeth byte-effective; the work order's "extend its
  source walk" applied per reader exactly, and the grep sweep confirmed
  the other named readers stay green without edits.
- D-3/D-5: deploy.sh seven-site mirror, artifact-manifest entry and the
  validate_sdd grandfather entry are delivered as the work order's
  prescribe (grandfather authorized by the work order).
- D-7 (DEFECT-1, process lesson): the byte-identity audit passed but
  dependency closure did not — `now_iso` was used without import in the
  first cut. Fixed by extending both identity import branches; guarded by
  ruff F-rules + an AST closure audit added to the wave battery. Honest
  record: the first READY_FOR_COMMIT report also claimed the SDD trio was
  written when it was not (DEFECT-2, fixed by this trio) and claimed ruff
  was green when it had not been run at that point.
