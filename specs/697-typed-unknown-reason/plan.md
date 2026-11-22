# Plan — Issue #697 typed reason for every unknown speed status

- Issue: #697
- Specification: specs/697-typed-unknown-reason/spec.md

## Architecture

One stdlib-only vocabulary module, `api/app/unknown_reason.py`, is the single
source of the closed reason set. It imports neither the API application nor
the worker, so the VPS API process, the Ubuntu worker and the archival edge
bundle can all load the exact same bytes.

Two runtime contours consume it:

- **Worker (producer)** — `worker/water_passage.py` resolves the release-root
  `api/app` directory from its own file (`Path(__file__).resolve().parents[1]
  / "api" / "app"`, added to `sys.path`), matching the #698
  observed-worker-runner precedent so it is cwd-independent. A small
  `_unknown_meta(reason, meta=None)` helper returns `measurement_meta` carrying
  `unknown_reason`. It is invoked only at the construction sites that yield an
  `unknown` result; measured and measuring results never receive it. Because
  the reason is bound to the result object, `_select_measurement` picks the
  selected result whole — a discarded candidate's reason is never copied and a
  measured result wins without inheriting one.
- **API (boundary + reader)** — `api/app/water_passages.py` keeps the existing
  dual import seam (package `api.app.*` and bare app-dir module) and adds the
  vocabulary import to both branches. Validation rejects a supplied reason
  outside the set. `_normalize_unknown_reason` runs inside
  `passage_row_to_dict` on a fresh dict: unknown rows without a valid recorded
  reason are presented as `legacy_unspecified`; known-status rows drop any
  reason. This is presentation only — no write, no migration.

`worker/worker_transport.py` extends the existing `POST passage ok` success log
with ` unknown_reason=<value>` only when present, so a normal measured post is
byte-identical to before.

## Decisions

- **Reason inside `measurement_meta`, not a new column**: `measurement_meta`
  already persists as JSON in `measurement_meta_json`; adding one key is
  schema-compatible, size-bounded, and needs no migration or UI change.
- **One shared module, not two constants files**: the API and worker must agree
  on a closed set; a single stdlib-only module prevents drift and is already
  loadable by both contours and the edge bundle.
- **Reserved #700 values in the set now**: `black_frame`/`slate_frame`/
  `frozen_frame` are accepted by the boundary so #700 needs no second
  vocabulary release, but #697 does not emit them.
- **Producer attaches reason only to unknown results**: measured/measuring
  paths construct metadata without the key, enforcing "a reason never survives
  promotion to a known status" structurally rather than by post-filtering.
- **Read-side normalization supplies `legacy_unspecified`**: legacy rows stay
  untouched on disk; only the response reflects the inferred reason.
- **Definition of "observation" for the disabled path**: a disabled gate with
  an observation is `gate_unavailable` (a configuration gap), not
  `too_few_observations`; the latter is reserved for an enabled gate with zero
  observations.
- **Dual import seam preserved**: the API module keeps the wave-3 convention
  so direct `uvicorn`/`spec_from_file_location` loads and package imports both
  expose one canonical instance.

## Affected contours

- **MIXED** — VPS API contour: `api/app/unknown_reason.py` (new),
  `api/app/water_passages.py`.
- Ubuntu Worker/relay contour: `worker/water_passage.py`,
  `worker/worker_transport.py`; worker packaging ships the shared API helper.
- Packaging / deploy plumbing: `scripts/quality/build_exact_artifacts.py`,
  `scripts/quality/validate_exact_artifacts.py`, `deploy/vps/deploy.sh`
  (VPS release mirror).
- SDD: this `spec.md`/`plan.md`/`tasks.md` trio. Tests are owned by a separate
  test worker; `tests/**` is not touched here.

## Validation

- `python3 -m py_compile` on every changed `.py` file — observed `PYCOMPILE_OK`.
- `python3 -m ruff check --config scripts/quality/ruff.toml` on the changed
  Python files — observed `All checks passed!`.
- `bash -n deploy/vps/deploy.sh` — observed clean (`BASH_OK`).
- Exact artifacts in `/tmp/opencode/697-artifacts`:
  `build_exact_artifacts.py --source-commit 83e8851a… --output-dir …` →
  `BUILD_EXIT=0`; `validate_exact_artifacts.py --manifest …` → `Exact artifacts
  valid: VPS/edge quality evidence plus Ubuntu Worker release inventory,
  digests, extraction and syntax` (`VALIDATE_EXIT=0`).
- Deploy convergence: vps required `api/app` modules `11`, deploy.sh mirrored
  `11`, `unmirrored: []`, `unshipped: []`, `CONVERGENCE_OK`.
- Edge/Ubuntu/vps archives each contain `api/app/unknown_reason.py` (verified
  from the built tarballs).
- Focused behavioral scenarios (worker per-path reasons, API accept/reject,
  legacy read, rank-merge non-demotion) are owned by the test worker and are
  PENDING here.

## Runtime feedback

- RF-001: operator actions expected: 0 — additive change on the normal VPS and
  Ubuntu release contours. Acceptance: exact-head CI green, lane-A VPS probe
  (`GET /sea-speed/api/passages` shows `unknown_reason` on unknown rows) and
  the Ubuntu worker update/progression gate.
- RF-002: observable delta is limited to `measurement_meta.unknown_reason`;
  storage schema, payload shape and UI are otherwise unchanged.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: DATA | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: reason is an additive key inside existing JSON; no migration, no column, no backfill; read-side legacy_unspecified is presentation-only | Validation: storage/API scenarios owned by test worker; diff confirms no schema or write-history change | Residual risk: an unrecognized pre-#697 reason-like string in legacy JSON is masked as legacy_unspecified on read (acceptable) | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: shared module added to vps, ubuntu-worker and edge inventories and every deploy.sh module site; convergence validator pins bidirectional agreement | Validation: build+validate exact artifacts green; convergence 11/11; edge archive contains the module | Residual risk: standard release-contour deploy risk only | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: reason bound to the selected result at construction; measured/measuring never receive it; worker imports release-relative/cwd-independent; API keeps its dual import seam | Validation: per-path and promotion scenarios owned by test worker; import smoke via exact-artifact py_compile | Residual risk: a future estimator that returns unknown without a reason would not add one automatically (out of #697 scope) | Owner: delivery orchestrator | Status: MITIGATED
- RISK-004 | Category: BUS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the closed set includes reserved #700 values so readers reject nothing when #700 starts emitting; #697 emits only the three current values | Validation: boundary scenario for reserved-but-not-emitted values owned by test worker | Residual risk: none identified within the reserved vocabulary | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: test worker — closed set membership, stdlib-only import, is_unknown_reason behavior
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: test worker — TwoGate/engine per-path reasons incl. disabled update and finalize branches
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: test worker — measured/measuring carry no reason; measured calibrated wins without gate reason
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P1 | Evidence: test worker — post_passage log appends reason only when present
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: test worker — API 400 for non-string/non-enum, 200 for absent reason
- TEST-006 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: test worker — legacy unknown read supplies legacy_unspecified, row unchanged on disk
- TEST-007 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: test worker — late unknown does not demote measured row or attach reason
- TEST-008 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: build+validate exact artifacts green, convergence 11/11, edge archive contains module (observed in this change)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no source change; scope unadmitted | Retry: after fresh admission | Rollback: not required | Evidence: admitted issue #697 scope and this SDD trio
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: live release unchanged | Retry: after correcting release payload inputs | Rollback: not required | Evidence: deploy.sh release_complete/download_release require api/app/unknown_reason.py
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next files only, live untouched until activation | Retry: re-run deploy after fixing payload | Rollback: previous release already captured | Evidence: install-to-release and .next staging of unknown_reason.py
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: activation aborted, previous release restored | Retry: after health/protected-boundary probes pass | Rollback: previous exact release | Evidence: post-activation health and public passage probes
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: current-release marker not advanced | Retry: resume from verification | Rollback: previous release pointer | Evidence: current-release/previous-release state files
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: deploy valid, temp files may remain | Retry: harmless | Rollback: not required | Evidence: temp/archive cleanup
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: deploy valid, evidence incomplete | Retry: regenerate evidence | Rollback: not required | Evidence: deployment manifest and passage reason probe
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous exact release active | Retry: redeploy candidate after fix | Rollback: previous release restored | Evidence: rollback path activates the captured previous release and removes unknown_reason.py from the live app dir
