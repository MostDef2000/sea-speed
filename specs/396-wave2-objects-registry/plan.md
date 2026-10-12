# Plan: Objects registry extraction — api/app/objects_registry.py + api/app/passage_mirrors.py (Wave 2)

- Issue: #396
- Specification: specs/396-wave2-objects-registry/spec.md

## Implementation approach

1. `api/app/objects_registry.py` (new) — byte-range extraction of
   main.py:170-352 (`open_objects_db` with its `@contextmanager`,
   `prune_objects_registry`, `initialize_objects_db`, `optional_float`,
   `optional_int`, `stable_object_id`, `prune_snapshotless_objects`,
   `persist_object_event`, `import_existing_events`), 852-917
   (`object_row_to_dict`, `build_objects_where`) and 1622-1679
   (`patch_object_record`, `delete_object_record`) at base f863f1ca, in
   original order. Header imports `hashlib`/`json`/`sqlite3`/`typing`/
   `fastapi.HTTPException` plus the dual-idiom `config`/`identity`/`store`
   seam (explicit name lists, sys.path-anchored absolute fallback for
   direct-file loads). The extraction is performed by scripted line-range
   copy from the base `main.py` (never retyped); an automated audit asserts
   every moved region appears byte-identical in the new module.
2. `api/app/passage_mirrors.py` (new) — byte-range extraction of
   main.py:355-431 (`persist_passage_object`, `import_existing_passages`)
   and 439-474 (`_delete_passage_mirrors`, `reconcile_passage_mirrors`).
   Header imports `json`/`sys`/`typing` + dual-idiom `identity`/
   `objects_registry`; declares the `open_passages_db = None` sentinel.
3. `api/app/main.py` — delete the moved blocks (with their preceding blank
   separator lines, keeping exactly two blank lines between survivors);
   insert the wave-2 seam after the wave-1 identity seam (try/except dual
   idiom, explicit re-export name lists, `# noqa: F401`); add the one-line
   binding `passage_mirrors.open_passages_db = open_passages_db`
   immediately after the `open_passages_db` definition (before the
   module-level mirror backfill at the import tail); drop the now-unused
   `import hashlib`.
4. Tests — extend the five multi-source AST readers to walk
   `(main.py, objects_registry.py, passage_mirrors.py[, identity.py,
   config.py])` in that order (order matters: the `api_sources()`
   block-scan `build_objects_where → analytics_identity` requires the new
   modules before identity); repoint the `test_endpoint_requires_snapshot`
   source read to `api_sources()`; add both modules to the synthetic
   release fixtures; add `tests/test_route_table.py` (import-free AST
   fingerprint freezing the 61-endpoint table).
5. `deploy/vps/deploy.sh` — add `OBJECTS_REGISTRY_TARGET`/
   `PASSAGE_MIRRORS_TARGET` and mirror the wave-1 config/identity pattern
   through all seven sites (see Decision D-1).

## Architecture

Two new leaf modules under `api/app/`, deployed before `main.py`:

- `api/app/objects_registry.py` — objects SQLite layer; depends on
  `config` (constants), `identity.now_iso`, `store.read_json_file`,
  `fastapi.HTTPException`; owns the shared numeric coercion helpers.
- `api/app/passage_mirrors.py` — mirror layer; depends on
  `objects_registry` and the `open_passages_db` binding supplied by main;
  never imports `main`.
- `api/app/main.py` — unchanged logic; thin explicit re-exports keep the
  historical import surface (`main.open_objects_db`,
  `main.persist_passage_object`, ...) working for callers and AST
  harnesses; keeps `open_passages_db` and the whole water-passages store.

Import-cycle rule: neither new module imports `main`. The water-passages
connection factory stays in `main.py` this wave, so `passage_mirrors`
resolves it through a module-level binding that main.py assigns right
after the factory's definition — before any caller can run (all callers
are main.py route handlers or main.py's module-level import tail, both
executed after the binding). A real `from .main import open_passages_db`
was rejected: under `tests/test_roi_normalization.py` (which execs
main.py under a second module name with mocked stdlib), a main-ward
import re-enters main.py's module scope and fails at its module-level
`import_existing_passages()` call; the binding design keeps that harness
green. Dual try/except idiom is replicated exactly so both modules share
one instance of every dependency per import mode (package mode: relative
imports; direct-file mode: sys.path anchor + absolute imports reusing the
sys.modules cache).

## Decisions

- D-1 (orchestrator decision, granted): `deploy.sh` is extended through
  **all seven sites** of the wave-1 config/identity pattern for both new
  modules: (1) `OBJECTS_REGISTRY_TARGET`/`PASSAGE_MIRRORS_TARGET` next to
  `API_TARGET`; (2) `release_complete` existence checks; (3) download
  required list; (4) release install; (5) `bootstrap_current_release`
  capture of live copies; (6) `install_release` staging to `.next`; (7)
  activation mv/rm **before** the `main.py` promotion, bound to the
  release's content (store.py soft pattern: staged copy promoted only when
  the release ships the module, otherwise live copy + stale `.next`
  removed so a pre-wave-2 rollback boots cleanly). The work order's "four
  sites, no more no less" wording was an orchestrator error; with only the
  four canonical sites the new main.py would boot against a live app dir
  missing the new modules and every wave deploy would fail the health gate
  and auto-rollback — the wave contract (deployable at merge) and the
  wave-1 empirical pattern (config/identity diff at 463ae37) win.
- D-2 (orchestrator decision, granted): `scripts/ci/validate_sdd.py`
  grandfathers the #396 wave pair — `"396":
  {"396-wave1-shared-kernel", "396-wave2-objects-registry"}` in
  `GRANDFATHERED_PREFIX_COLLISIONS`. The #396 program contract plans waves
  2-6 under one issue number, so the shared prefix is by design; the
  grandfather set-match keeps every future unregistered duplicate failing
  closed. Authorized for this one change only.
- D-3: `open_passages_db` stays in `main.py` and is injected into
  `passage_mirrors` (sentinel + assignment line) instead of main-ward
  importing — the only design that keeps the roi-normalization
  standalone-exec harness, the package import path and the direct-file
  path all green without relocating code (no relocation = smaller diff).
- D-4: `optional_float`/`optional_int` move with the objects layer (their
  moved callers resolve them at call time); `main.py` re-imports them
  through the seam — the ~10 remaining main.py call sites are unchanged.
- D-5: Extraction is scripted byte-range copy with an automated
  byte-identity audit of all 17 moved regions against the base commit;
  `import hashlib` is dropped from main.py (its only consumer,
  `stable_object_id`, moved) to keep ruff F401 clean.
- D-6: Exact-artifact manifest stays unchanged (store.py/wave-1
  precedent); release completeness is governed by deploy.sh, verified by
  the synthetic-release tests.

## Affected contours

- VPS only (`api/**` + `deploy/vps/deploy.sh`): deploy envelope REQUIRED;
  deploy rides the merge via deploy-vps.yml (orchestrator DEPLOY-TRIGGER,
  полоса A). No Ubuntu worker, no edge, no frontend change.

## Validation

- Full suite `python3 -m unittest discover -s tests` green (baseline: 907
  tests / 4 skipped; expected head: 908 / 4 with the new route-table test).
- `python3 scripts/ci/validate_repo.py` green.
- `python3 scripts/ci/validate_sdd.py` green (grandfathered #396 pair).
- `ruff check . --config scripts/quality/ruff.toml` clean.
- `bash -n deploy/vps/deploy.sh` clean.
- Byte-identity audit: all 17 moved regions byte-identical to
  `git show f863f1ca:api/app/main.py`; route table 61 == 61 vs base.
- VPS deploy transaction suite green (23 tests).

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: deploy.sh extended through all seven wave-1-pattern sites with staging+activation of both modules BEFORE main.py; bootstrap capture keeps rollback releases bootable; a missing module fails the release before any live mutation | Validation: deploy transaction suite (23 tests) + bash -n + release-shape fixtures | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: AST-harness readers extended to a main→objects_registry→passage_mirrors→identity→config resolution order with combined-source text readers, so assertions are re-pointed, never weakened; route table pinned by a new fingerprint test | Validation: focused run of the six touched suites (127 tests) green; full suite green on head | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: open_passages_db stays in main and is bound into passage_mirrors immediately after its definition (sentinel never observed by a caller: every caller runs after the binding); no main-ward import, so no cycle in package, direct-file or roi-mock load modes | Validation: package import smoke; tests/test_roi_normalization.py green; mirrors suites green | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: extraction done by scripted byte-range copy from the base commit with an automated byte-identity audit of all 17 regions; blank-line layout preserved; main.py diff limited to deletions + seam + injection + hashlib drop | Validation: byte-identity audit PASS (17/17); git diff --stat review; ruff clean | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: validate_sdd grandfather is an exact-set match for the two registered #396 wave dirs only; any other duplicate prefix still fails closed | Validation: python3 scripts/ci/validate_sdd.py green on head; prefix-uniqueness unit behavior unchanged | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001, AC-002, AC-004, AC-005 | Level: unit | Priority: P1 | Evidence: python3 -m unittest discover -s tests (expected 908 tests / 4 skipped; baseline 907/4)
- TEST-002 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: tests/test_vps_deploy_transaction.py (23 tests; synthetic releases carry objects_registry.py + passage_mirrors.py)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P1 | Evidence: bash -n deploy/vps/deploy.sh
- TEST-004 | Covers: AC-002 | Level: unit | Priority: P1 | Evidence: python3 scripts/ci/validate_repo.py; python3 scripts/ci/validate_sdd.py
- TEST-005 | Covers: AC-001, AC-004 | Level: unit | Priority: P1 | Evidence: tests/test_route_table.py (61-route frozen fingerprint, 1 test); byte-identity audit of the 17 moved regions vs f863f1ca
- TEST-006 | Covers: AC-004 | Level: unit | Priority: P1 | Evidence: tests/test_api_contract.py, tests/test_unified_registry.py, tests/test_storage_retention.py, tests/test_water_passage.py, tests/test_line_crossing.py (127 focused tests observed green)
- TEST-007 | Covers: AC-005 | Level: unit | Priority: P2 | Evidence: tests/test_roi_normalization.py (mocked standalone exec of main.py; open_passages_db binding exercised)

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
  release via install_release(previous) — for a pre-wave-2 previous release
  the two new modules are removed from live (the old main.py imports
  neither); bootstrap releases capture live copies when present.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: work order for #396 wave 2 (extraction-only scope, orchestrator decisions D-1/D-2 granted); branch sdd/396-wave2-objects-registry from f863f1ca
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged VPS state | Retry: NO | Rollback: NONE | Evidence: release_complete (deploy.sh:210) and download required list (deploy.sh:255) now also require api/app/objects_registry.py and api/app/passage_mirrors.py; the gate exits before any mutation of the live tree
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next copies discarded; live API unchanged | Retry: NO | Rollback: install_release stages both modules to .next and promotes via mv only after all copies stage successfully; both mv commands precede the main.py mv (the new main imports them at boot) (deploy.sh:691-701, 746-767) | Evidence: install_release soft pattern; test_vps_deploy_transaction behavioral suite (23 tests, write_release fixtures carry the new files)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: restart_and_verify health gate unchanged by wave 2
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: dual-write window semantics untouched; wave 2 moves no state-mutation code (persistence primitives keep their exact bodies and call graphs)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: deploy.sh staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: DEPLOYMENT_ACCEPTED line from the autonomous chain at exact-green-head merge
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour unchanged; activation is bound to the selected release content for both new modules exactly as for store.py — staged .next promoted only when the release ships the module, otherwise the live copy and any stale .next are removed so a pre-wave-2 rollback boots cleanly; bootstrap capture preserves live objects_registry.py/passage_mirrors.py alongside the captured main.py (deploy.sh:550-567) | Evidence: deploy.sh:746-767 (activation), deploy.sh:550-567 (bootstrap capture) + test_vps_deploy_transaction rollback tests

## Deviations from the work order

- D-1: deploy.sh extended through seven sites per module, not four — the
  work order's "no more no less" conflicted with the wave contract
  (deployability at merge) and the wave-1 empirical pattern; granted by the
  orchestrator (DECISION-1).
- D-2: one-line grandfather entry in scripts/ci/validate_sdd.py for the
  #396 wave pair; granted by the orchestrator (DECISION-2), this file
  authorized for this change only.
- D-4: optional_float/optional_int move with the objects-registry layer
  (call-time closure) and are re-exported from main — documented here
  because the work order's move list did not call out their relocation.
