# Plan: Water passages extraction — api/app/water_passages.py (Wave 3)

- Issue: #396
- Specification: specs/396-wave3-water-passages/spec.md

## Implementation approach

1. `api/app/water_passages.py` (new) — byte-range extraction of
   main.py:269-606 at base 38595d32 in 8 regions (`open_passages_db` with
   its `@contextmanager` decorator, `cleanup_passage_media`,
   `prune_water_passages`, `initialize_water_passages_db`,
   `_validate_passage_payload`, `passage_row_to_dict`,
   `upsert_water_passage`, `list_water_passages`), in original order.
   Header imports `json`/`sqlite3`/`sys`/`contextlib.contextmanager`/
   `pathlib.Path`/`typing`/`fastapi.HTTPException` plus the dual-idiom
   `config`/`identity`/`objects_registry`/`passage_mirrors` seam (explicit
   name lists, sys.path-anchored absolute fallback for direct-file loads).
   The extraction is performed by scripted line-range copy from the base
   `main.py` (never retyped); an automated audit asserts every moved region
   appears byte-identical in the new module and that the binding line
   survives in `main.py` byte-identical.
2. `api/app/main.py` — delete the moved blocks (with their preceding blank
   separator lines, keeping exactly two blank lines between survivors);
   insert the wave-3 seam after the wave-2 seam (try/except dual idiom,
   explicit re-export name lists, `# noqa: F401`); update the binding
   comment to the wave-3 shape while keeping the binding LINE
   `passage_mirrors.open_passages_db = open_passages_db` byte-identical;
   drop the now-unused `import sqlite3` and
   `from contextlib import contextmanager`.
3. Tests — extend the multi-source AST readers to walk
   `(main.py, objects_registry.py, passage_mirrors.py, water_passages.py[,
   identity.py, config.py])` in that order (the `api_sources()`
   block-scan `build_objects_where → analytics_identity` requires the
   registry modules before identity; water_passages carries no ordering
   constraint and walks after passage_mirrors); add `water_passages.py` to
   the synthetic release fixtures; extend `tests/test_route_table.py` to
   pin `(handler_name, method, path)` fingerprints (hardening A).
4. `deploy/vps/deploy.sh` — add `WATER_PASSAGES_TARGET` and mirror the
   wave-1/wave-2 pattern through all seven sites (see Decision D-3).
5. `scripts/quality/build_exact_artifacts.py` — converge the vps required
   list with deploy.sh (hardening B); `scripts/ci/validate_sdd.py` —
   grandfather the wave set (Decision D-4).

## Architecture

One new leaf module under `api/app/`, deployed before `main.py`:

- `api/app/water_passages.py` — water-passages SQLite store; depends on
  `config` (constants), `identity.now_iso`,
  `objects_registry.optional_float`/`optional_int`,
  `passage_mirrors._delete_passage_mirrors`, `fastapi.HTTPException`.
- `api/app/main.py` — unchanged logic; thin explicit re-exports keep the
  historical import surface (`main.open_passages_db`,
  `main.upsert_water_passage`, ...) working for callers and AST harnesses;
  keeps the binding line that injects the factory into `passage_mirrors`.

Import-cycle rule: the new module never imports `main`. The mirror
dependency is one-directional: `prune_water_passages` calls
`_delete_passage_mirrors` (passage_mirrors), while `passage_mirrors`
resolves `open_passages_db` through its wave-2 sentinel. A direct
`passage_mirrors → water_passages` import would close a cycle
(water_passages → passage_mirrors → water_passages), so the wave-2
sentinel + main binding line is preserved: `main.py` imports the factory
from `water_passages` and binds it into `passage_mirrors` right after the
seam — the same function object, at the same point of the import sequence
as in wave 2, before any mirror caller (all callers are main.py route
handlers or main.py's module-level import tail, both executed after the
binding). A main-ward import from `passage_mirrors` remains rejected for
the same reason wave 2 rejected it (the roi-normalization standalone-exec
harness re-enters main's module scope). Dual try/except idiom is
replicated exactly so all modules share one instance of every dependency
per import mode (package mode: relative imports; direct-file mode:
sys.path anchor + absolute imports reusing the sys.modules cache).

## Decisions

- D-1 (slice boundary): `clean_points_list` and the ROI
  normalization helpers/constants stay in `main.py`. The work order listed
  them "if their closure is water-passage-specific"; dependency tracing
  shows their only callers are the analytics ROI / speed-lines /
  crossing-line handlers (main.py:1418-1665 at base) — the closure is
  analytics-specific, not water-passage-specific, so the condition is not
  met and the functions stay put. `open_passages_db` DOES move (its
  callers are exclusively the water-passage store functions plus the
  binding line, all moving or remaining on the water contour).
- D-2 (binding semantics): `open_passages_db` relocates to
  `water_passages.py`; `passage_mirrors` keeps its sentinel and `main.py`
  keeps the wave-2 binding line byte-identical, now binding the imported
  factory. Relocation + retained binding (instead of re-importing from
  the mirror or duplicating the factory) is the minimal change that keeps
  both import modes and the standalone-exec harness green with no
  behavioral drift.
- D-3 (deploy envelope, wave-1/wave-2 precedent): `deploy.sh` is extended
  through all seven sites of the established module pattern for
  `water_passages.py`: (1) `WATER_PASSAGES_TARGET` next to `API_TARGET`;
  (2) `release_complete` existence check; (3) download required list;
  (4) release install; (5) `bootstrap_current_release` capture of the live
  copy; (6) `install_release` staging to `.next`; (7) activation mv/rm
  **before** the `main.py` promotion, bound to the release's content
  (store.py soft pattern: staged copy promoted only when the release ships
  the module, otherwise live copy + stale `.next` removed so a pre-wave-3
  rollback boots cleanly).
- D-4 (grandfather update): `scripts/ci/validate_sdd.py` grandfathers
  `396-wave3-water-passages` in the `"396"` set of
  `GRANDFATHERED_PREFIX_COLLISIONS` (exact-set equality; any other
  duplicate prefix still fails closed). Authorized by the wave-3 work
  order (standing directive 2026-10-12: autonomous continuation).
- D-5 (hardening A, wave-2 peer-review follow-up): `test_route_table.py`
  pins `(handler_name, method, path)` for all 61 endpoints, frozen at the
  wave-3 base; still import-free AST, still exactly 1 test method, so the
  suite count is unchanged.
- D-6 (hardening B, wave-2 peer-review follow-up): the exact-artifact vps
  required list converges with deploy.sh's required `api/app` modules
  (store.py/config.py/identity.py from waves 0-1,
  objects_registry.py/passage_mirrors.py from wave 2,
  water_passages.py from wave 3). `validate_exact_artifacts.py` uses a
  subset check (required ⊆ manifest) and stays untouched; the convergence
  is verified by an actual build + validate run in the battery.
- D-7 (imports dropped from main): `import sqlite3` and
  `from contextlib import contextmanager` lose their last consumers with
  this move (verified by grep over the post-move main.py) and are dropped
  to keep ruff F401 clean — the wave-2 `import hashlib` precedent.

## Affected contours

- VPS only (`api/**` + `deploy/vps/deploy.sh` + quality scripts/tests):
  deploy envelope REQUIRED; deploy rides the merge via deploy-vps.yml
  (orchestrator DEPLOY-TRIGGER, полоса A). No Ubuntu worker, no edge, no
  frontend change.

## Validation

- Full suite `python3 -m unittest discover -s tests` green (baseline: 908
  tests / 4 skipped; expected head: 908 / 4 — no test count change).
- `python3 scripts/ci/validate_repo.py` green (~653 files).
- `python3 scripts/ci/validate_sdd.py` green (grandfathered #396 wave set).
- `ruff check . --config scripts/quality/ruff.toml` clean.
- `bash -n deploy/vps/deploy.sh` clean.
- Byte-identity audit: all 8 moved regions byte-identical to
  `git show 38595d32:api/app/main.py`, binding line byte-identical and
  unique; route table 61 == 61 vs base with unchanged handler names.
- VPS deploy transaction suite green (23 tests).
- Exact artifacts: build from the converged vps list +
  `validate_exact_artifacts.py` green; every deploy.sh-required
  `api/app/*` module present in the built payload.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: deploy.sh extended through all seven module-pattern sites with staging+activation of water_passages.py BEFORE main.py; bootstrap capture keeps rollback releases bootable; a missing module fails the release before any live mutation | Validation: deploy transaction suite (23 tests) + bash -n + release-shape fixtures | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: AST-harness readers extended to a main→objects_registry→passage_mirrors→water_passages→identity→config resolution order with combined-source text readers, so assertions are re-pointed, never weakened; route table pinned by the handler-name fingerprint | Validation: focused run of the touched suites (124 tests) green; full suite green on head | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: the passage_mirrors sentinel + main binding line is preserved byte-identically because water_passages → passage_mirrors (_delete_passage_mirrors) would close an import cycle; the binding runs at main import time before any mirror caller, in package, direct-file and roi-mock load modes | Validation: package import smoke; tests/test_roi_normalization.py green; mirrors suites green | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: extraction done by scripted byte-range copy from the base commit with an automated byte-identity audit of all 8 regions plus the binding line; blank-line layout preserved; main.py diff limited to deletions + seam + binding comment + dropped imports | Validation: byte-identity audit PASS (8/8); git diff --stat review; ruff clean | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: validate_sdd grandfather is an exact-set match for the three registered #396 wave dirs only; any other duplicate prefix still fails closed | Validation: python3 scripts/ci/validate_sdd.py green on head; prefix-uniqueness unit behavior unchanged | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-006 | Category: DATA | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: move-only extraction — SQL, retention limits, validation rules and status ranks are byte-identical; no schema or data migration; the water_passages DDL keeps its exact text (pinned by the schema source walk in test_water_passage.py) | Validation: byte-identity audit; harness retention/upsert tests against the extracted module green | Residual risk: LOW | Owner: Worker | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001, AC-002, AC-004, AC-005 | Level: unit | Priority: P1 | Evidence: python3 -m unittest discover -s tests (expected 908 tests / 4 skipped; baseline 908/4)
- TEST-002 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: tests/test_vps_deploy_transaction.py (23 tests; synthetic releases carry water_passages.py)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P1 | Evidence: bash -n deploy/vps/deploy.sh
- TEST-004 | Covers: AC-002 | Level: unit | Priority: P1 | Evidence: python3 scripts/ci/validate_repo.py; python3 scripts/ci/validate_sdd.py
- TEST-005 | Covers: AC-004, AC-006, AC-007 | Level: unit | Priority: P1 | Evidence: tests/test_route_table.py (61-route frozen fingerprint with handler names, 1 test); byte-identity audit of the 8 moved regions vs 38595d32
- TEST-006 | Covers: AC-004 | Level: unit | Priority: P1 | Evidence: tests/test_api_contract.py, tests/test_unified_registry.py, tests/test_storage_retention.py, tests/test_water_passage.py, tests/test_line_crossing.py, tests/test_analytics_profiles.py (124 focused tests observed green)
- TEST-007 | Covers: AC-005 | Level: unit | Priority: P2 | Evidence: tests/test_roi_normalization.py (mocked standalone exec of main.py; seam import chain exercised)
- TEST-008 | Covers: AC-008 | Level: integration | Priority: P1 | Evidence: build_exact_artifacts.py + validate_exact_artifacts.py on the converged vps list; deploy.sh-required api/app modules verified present in the built payload

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
  release via install_release(previous) — for a pre-wave-3 previous release
  water_passages.py is removed from live (the old main.py does not import
  it); bootstrap releases capture the live copy when present.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: work order for #396 wave 3 (extraction-only scope, standing directive 2026-10-12 autonomous continuation); branch sdd/396-wave3-water-passages from 38595d32
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged VPS state | Retry: NO | Rollback: NONE | Evidence: release_complete and the download required list now also require api/app/water_passages.py; the gate exits before any mutation of the live tree
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next copies discarded; live API unchanged | Retry: NO | Rollback: install_release stages water_passages.py to .next and promotes via mv only after all copies stage successfully; the mv precedes the main.py mv (the new main imports it at boot) | Evidence: install_release soft pattern; test_vps_deploy_transaction behavioral suite (23 tests, write_release fixtures carry the new file)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: restart_and_verify health gate unchanged by wave 3
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: dual-write window semantics untouched; wave 3 moves no state-mutation code (persistence primitives keep their exact bodies and call graphs)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: deploy.sh staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: DEPLOYMENT_ACCEPTED line from the autonomous chain at exact-green-head merge
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour unchanged; activation is bound to the selected release content for water_passages.py exactly as for store.py — staged .next promoted only when the release ships the module, otherwise the live copy and any stale .next are removed so a pre-wave-3 rollback boots cleanly; bootstrap capture preserves a live water_passages.py alongside the captured main.py | Evidence: deploy.sh activation + bootstrap capture sites + test_vps_deploy_transaction rollback tests

## Deviations from the work order

- D-1: slice boundary — clean_points_list and the ROI normalization
  helpers/constants NOT moved (work order listed them conditionally; their
  closure is analytics-specific, traced to the ROI/speed-lines/crossing-line
  handlers only).
- D-2: open_passages_db relocation + retained binding — the factory moves
  to water_passages.py; the wave-2 binding line in main.py is kept
  byte-identical (now binding the imported factory) because
  prune_water_passages → _delete_passage_mirrors closes a cycle otherwise.
- D-5/D-6: the two wave-2 peer-review follow-ups (route-name pinning,
  exact-artifact convergence) are delivered as declared in the wave-3
  Change Contract; neither changes the test count.
- D-4: one-line grandfather entry in scripts/ci/validate_sdd.py for the
  #396 wave set; authorized by the wave-3 work order.
