# Implementation plan — retire Windows Worker production contour

Specification: `specs/019-remove-windows-worker-contour/spec.md`
Issue: #199

## Architecture

The active topology is reduced from three historical runtime labels to two actual production contours: VPS and Ubuntu Worker/relay. The change is implemented at the control-plane boundaries that derive runtime applicability, validate Change Contracts, bind production authorization, route execution, build exact artifacts/releases and describe release evidence.

Classification order is deliberate: Windows-specific `.ps1`/`.cmd`/`worker/windows/**` plus `worker/README.txt` and `worker/UPDATE.md` are matched as CONTROL_PLANE/archive before the generic `worker/**` rule; generic executable Worker source therefore maps to Ubuntu Worker/relay.

The legacy manifest schemas remain untouched. New release creation removes `windows-worker` from builder choices, but existing validators continue reading historical Windows records. Authorization fingerprint compatibility is similarly read-only: modern PRs produce a two-contour payload; old PR bodies that contain a legacy Windows field reproduce the historical field in the fingerprint payload.

## Decisions

- D-001: Retire Windows Worker as a production/runtime contour rather than keep a fake `NOT REQUIRED`/fallback field in new contracts.
- D-002: Keep Windows scripts in Git as deprecated non-production local/archive tooling; do not conflate portable source with supported runtime architecture.
- D-003: Delete `.github/workflows/package-worker.yml` because it creates a Windows-target package from shared Worker changes and therefore preserves a false production lifecycle.
- D-004: Shared executable `worker/**` maps to Ubuntu Worker/relay. `MIXED` is derived only when both VPS and Ubuntu runtime paths appear in one exact diff.
- D-005: Do not change `schemas/release-manifest.schema.json` or `schemas/deployment-manifest.schema.json`; persisted historical Windows evidence must remain readable.
- D-006: New release builder rejects `windows-worker`; exact edge quality artifact excludes Windows scripts entirely.
- D-007: `verify_production_authorization.py` uses conditional legacy payload shape only when an immutable historical PR body actually contains the legacy Windows field; modern fingerprints contain no Windows field.
- D-008: Issue #199 is CONTROL_PLANE only. No production authorization or runtime command is part of the migration.

## Affected contours

- VPS: NOT REQUIRED for this source migration.
- Ubuntu Worker/relay: NOT REQUIRED for this source migration.
- Production safety envelope: NOT REQUIRED.
- Operator actions expected: 0.
- Windows Worker: RETIRED / historical evidence only; not an active contour field.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: Keep Change Contract validation fail closed and add two-contour routing/authorization regressions | Validation: unit tests plus aggregate static-contract-security | Residual risk: A stale undocumented consumer could still expect a Windows field | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: Preserve historical schema/validator readability and conditionally reproduce legacy authorization payload shape | Validation: historical authorization and manifest compatibility tests | Residual risk: Very old external evidence outside repository fixtures may require manual audit | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: Remove package workflow/runtime fallback and assert their absence in workflow policy/architecture tests | Validation: workflow policy plus Quality integration | Residual risk: Local Windows scripts may be mistaken for supported production tooling | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: Exclude Windows files from exact edge artifact and keep deterministic artifact tests | Validation: exact-artifact E2E and validator | Residual risk: Future rules could accidentally reintroduce Windows content unless tests remain active | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001,AC-002,RISK-001 | Level: unit | Priority: P0 | Evidence: `tests/test_change_contract.py`
- TEST-002 | Covers: AC-003,AC-004,RISK-003 | Level: integration | Priority: P0 | Evidence: `tests/test_delivery_contract_convergence.py` and `scripts/quality/validate_workflow_policy.py`
- TEST-003 | Covers: AC-005,RISK-001,RISK-002 | Level: unit | Priority: P0 | Evidence: `tests/test_production_authorization.py`
- TEST-004 | Covers: AC-006,RISK-002 | Level: unit | Priority: P0 | Evidence: `tests/test_release_manifest.py`
- TEST-005 | Covers: AC-007,RISK-004 | Level: end-to-end | Priority: P0 | Evidence: `tests/quality/test_quality_architecture.py` plus exact-artifact Quality domain
- TEST-006 | Covers: AC-008 | Level: integration | Priority: P1 | Evidence: exact PR diff, PR Validation, aggregate Quality, expected-head merge and post-merge checks

## Validation

1. Validate JSON/Python/YAML source and repository/contract/SDD validators.
2. Run the full repository unittest suite including two-contour Change Contract, historical authorization, historical manifest, contract convergence and exact-artifact coverage.
3. Build exact artifacts twice and compare byte-for-byte; validate inventories and prove no Windows script enters edge artifact.
4. Open one exact 40-path PR linked to this specification and require PR Validation + Quality integration on the exact final head.
5. Re-read fresh `main`, exact diff, reviews/threads and merge with expected-head protection.
6. Require post-merge PR Validation + Quality integration on exact new `main`.
7. Record migration evidence on Issue #199 and close it. No runtime deployment occurs.

## Correct-course check

- Trigger: ARCHITECTURE_PIVOT
- Issue impact: Issue #199 is the canonical migration from the stale three-contour governance model to the actual two-contour production architecture.
- Specification impact: New SDD 019 records active topology, historical compatibility and non-goals without rewriting Issue #197 or PR #198 history.
- Plan impact: Classification, authorization, routing, artifact and release boundaries are migrated together so one stale Windows coupling cannot survive independently.
- Tasks impact: Exact 40-path implementation and regression coverage include policy, contracts, workflows, release tooling, docs and tests.
- Authorization impact: Existing Issue #199 `OUTCOME APPROVED` covers the exact 40-path Scope; no production authorization is required for CONTROL_PLANE-only migration.
- Follow-up: Persist exact migration evidence to Issue #199 after post-merge green checks; future runtime additions require a new approved architecture outcome.

## Deployment transaction audit

Although this feature performs no production deployment, it changes deployment/release control-plane tooling; the full transaction is audited to prove fail-closed migration semantics.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: Repository and production remain unchanged | Retry: Correct source admission or Change Contract before repository continuation | Rollback: Not applicable before source mutation | Evidence: Issue #199 Scope admission and Change Contract validation
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: Existing three-contour source remains authoritative on main | Retry: Fix branch policy/tests inside approved scope | Rollback: Delete or abandon unmerged branch changes | Evidence: Fresh main, exact 40-path inventory and regression plan
- TX-003 | Stage: MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: Production runtime is untouched; only feature-branch control-plane source may differ | Retry: Remediate exact branch source inside approved scope | Rollback: Revert branch commits before merge if required | Evidence: Git diff and no VPS/Ubuntu deployment fields REQUIRED
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: Branch remains unmergeable and production unchanged | Retry: Fix failing validator/test within approved paths and rerun CI | Rollback: Not applicable to production | Evidence: PR Validation and aggregate Quality integration
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: Main remains at previous exact source if merge gate fails | Retry: Re-read main/head/scope/reviews and retry expected-head merge only when exact gates pass | Rollback: Revert merged PR only if post-merge source regression is proven | Evidence: Expected-head merge result and exact main SHA
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: Source may be merged but Issue migration evidence incomplete | Retry: Persist missing non-secret evidence and close Issue when all hard gates are satisfied | Rollback: No production rollback; source revert only for material merged defect | Evidence: Issue #199 terminal migration comment/state
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: Completion cannot be claimed; production remains unchanged | Retry: Collect exact PR/post-merge CI/diff/review evidence | Rollback: Not applicable to runtime | Evidence: Exact changed files, CI run IDs, merge SHA and Issue comment
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: Previous main remains or a source revert restores old governance; runtime hosts are unchanged | Retry: Re-authorize any material redesign beyond the approved 40 paths | Rollback: Source revert of Issue #199 merge if a control-plane regression escapes CI | Evidence: Previous main SHA `116dcf0f5f0d625f2b223a4549525ca7ddaa56d3` and merge provenance

## Runtime feedback

No runtime mutation is planned or required. The accepted result is repository governance that stops asking for nonexistent Windows deployment evidence while preserving historical read compatibility. If post-merge CI exposes a stale coupling, remediate it only if it is within the already authorized 40 paths; otherwise render a new Scope and obtain fresh authorization.
