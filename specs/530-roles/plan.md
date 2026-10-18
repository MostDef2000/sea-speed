# Plan: #530 — server-side role authorization

- Specification: specs/530-roles/spec.md
- Status: IMPLEMENTED — source and tests complete; full suite 1097 passed,
  4 skipped, 260 subtests passed (101.87s) and ruff clean observed at the
  working tree on 2026-10-18; commit/PR and runtime acceptance pending

## Architecture

Keep config.py as the environment owner, identity.py as the trust/policy
module, and main.py as HTTP wiring. Neither config nor identity imports main
(config.py:1-17; identity.py:1-13). Preserve package and direct-file loading.

Use concrete APIs:

    resolve_role(username: str, x_authentik_groups: Optional[str]) -> str

    require_role(
        x_authentik_username: Optional[str],
        x_sea_speed_edge_auth: Optional[str],
        x_authentik_groups: Optional[str],
        *,
        minimum: str,
        action: str,
    ) -> str

resolve_role is an internal-policy helper whose username precondition is
"already verified by require_operator_identity". It implements spec R-2.

require_role:
1. Calls require_operator_identity first.
2. Resolves role using that returned username.
3. Checks the static minimum, operator or admin; unsupported minima fail
   closed as a programming/configuration error.
4. On insufficient role raises 403 "Forbidden".
5. On authorization emits a safely encoded mutation-attempt record with
   verified username, role and static action.
6. Returns username, preserving worker requested_by behavior.

Do not log unverified usernames on identity failures, raw groups, edge
headers, payloads or configured lists. Escape control characters in audit
identity rendering. Do not describe an authorization event as successful
completion of a mutation.

Keep require_operator_identity unchanged, including transitional behavior.
No Depends, APIRouter, middleware, database roles or role cache.

Extend identity.py __all__ (:59-67) and both main.py identity import seams
(:72-80 and :131-139) together with resolve_role and require_role.

## Configuration

Add ADMIN_USERS and OPERATOR_USERS constants from SEA_SPEED_ADMIN_USERS and
SEA_SPEED_OPERATOR_USERS, default empty, parsed at import time using
whitespace/comma separators into immutable sets. Export through config
__all__; import in both identity config branches.

Correction: config.py:149-154 is TTL parsing. There is no existing
SEA_SPEED_OPERATOR_USERS parser in this checkout. Follow config's existing
environment ownership, but implement the requested list syntax as new code.

No deployment/env files change. Changes to configured memberships take
effect after process restart; live administration is a separate operational
action.

## HTTP wiring and session

Every changed mutation handler adds:

    x_authentik_username: Optional[str] = Header(None)
    x_sea_speed_edge_auth: Optional[str] = Header(None)
    x_authentik_groups: Optional[str] = Header(None)

Worker handlers already have the first two. Preserve existing business
argument order and defaults; append headers. Keep session's first parameter
named x_authentik_username.

The spec's 19-row route table is the complete handler change list:
- operator: patch_cam1_object, patch_object, commit_camera_snapshot,
  start_camera_preview, stop_camera_preview;
- admin: delete_cam1_object, delete_object;
- admin: post_cam1_roi, post_cam1_speed_config, post_cam1_speed_lines,
  post_cam1_crossing_line, post_analytics_roi,
  post_analytics_speed_config, post_analytics_speed_lines,
  api_post_crossing_line;
- admin: start_worker_control, stop_worker_control,
  start_road_worker_control, stop_road_worker_control.

Place the role guard first in each mutation handler, before catalog access,
locks, validation helpers with side effects, persistence, process operations
or call_worker_control. Framework request validation may still produce 422
before handler execution; denial tests must use structurally valid inputs.

Calibration aliases need explicit argument forwarding:
post_cam1_roi/speed_config/speed_lines currently call their decorated
analytics handlers (main.py:569-591). Preserve delegation and pass all
three header values explicitly. Both entry points remain guarded.
This smallest design can emit two authorization-attempt records for those
aliases; records must not be counted as two completed mutations.
Avoid a "skip_auth" flag or trusting Header default objects.

Crossing-line aliases call the un-decorated analytics helper
(main.py:599-601,920-922); guard each HTTP handler, then leave that helper
unchanged.

get_session_identity retains its direct require_operator_identity call,
adds x_authentik_groups, then calls resolve_role. Exact payload becomes
{"ok": True, "username": username, "role": role}. Do not enforce operator
minimum on session or on either worker-status GET.

## Decisions and rejected alternatives

- D-1: Imperative guard plus Header parameters preserves established test
  and extraction conventions. Reject Depends/middleware/router migration.
- D-2: Reuse verified identity; reject a second independent edge verifier.
- D-3: Exact env/group resolution; reject substring matching, case folding,
  delimiter guessing and default-operator behavior.
- D-4: Preserve aliases with explicit forwarding and repeated checks;
  reject bypass flags and broad analytics extraction for this feature.
- D-5: UI hiding is deferred; it cannot replace server authorization.
- D-6: M2M remains Bearer-only; reject requiring browser claims on workers.

Binding inputs: issue #530 comment 6236142800 (owner decision, 2026-10-18)
and #520 phase-3 strict-mode evidence (verified live 2026-10-18).

## Affected contours

VPS API only. No worker executable, frontend, edge, blueprint, deployment
workflow, schema or migration change.

This changes an authorization boundary. Existing workflow transport remains
deploy-vps.yml, but "app-only" must not be interpreted as routine lane-A
security classification. Apply the governing security-sensitive handoff and
ИБ acceptance requirements (security-PR checklist). Repository workflow
policy/delegation gates remain mandatory; this document grants no
deployment authority.

## Validation

Executed verification (observed by the orchestrator at the working tree,
2026-10-18): focused RBAC + pinned suites, then the full battery
`python3 -m pytest tests/ -q` → 1097 passed, 4 skipped, 260 subtests passed
in 101.87s (93.86s on the final rerun after artifact repair);
`ruff check --config scripts/quality/ruff.toml .` (the CI Quality lint
command) → All checks passed;
`python3 scripts/ci/validate_repo.py` passed (755 tracked files);
`python3 scripts/ci/validate_sdd.py` green after this artifact repair.
Runtime probes through the existing edge remain a post-merge acceptance
step.

Use import-free AST extraction or existing safe fixtures; config imports
create /opt directories (config.py:159-164).

## Test design

- TEST-001 | Covers: AC-001, AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_sea_speed_rbac.py 19-route x 3-role matrix with real guards and side-effect collaborators, green
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: resolver tests for blank/absent/unknown groups, exact/case/near-match, whitespace, duplicates, env whitespace/comma parsing, both-list membership, operator-over-admin override, green
- TEST-003 | Covers: AC-002, AC-003 | Level: unit | Priority: P0 | Evidence: identity-first pins (invalid/missing edge with privileged identities rejected; correct edge + blank username 503; basic-auth viewer), green
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: session exact-shape pins with role field, extraction-namespace update, three-handler identity-only and 19-handler guard wiring pins with exact minima and forwarded headers, green
- TEST-005 | Covers: AC-004 | Level: unit | Priority: P1 | Evidence: Header and require_role bindings added to test_api_contract.py objects namespace; business-contract tests with authorized stubs, green
- TEST-006 | Covers: AC-004 | Level: unit | Priority: P1 | Evidence: snapshot signature pin replaced with AST extraction in test_camera_preview_gallery.py; catalog/session/snapshot assertions retained, green
- TEST-007 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: 61-entry route fingerprint unchanged; three-role read-family tests; nine ingestion routes Bearer-only, green
- TEST-008 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: mutation-attempt audit capture for every authorized route incl. aliases; trimming, control-char encoding, no secret/header/payload material, green
- TEST-009 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: full suite 1097 passed, 4 skipped, 260 subtests passed; ruff clean; validators; runtime probes deferred to post-merge acceptance (runtime-manual)

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: identity-first guard and exact group parsing; per-route denial tests | Validation: TEST-001..003 green | Residual risk: transitional mode remains intentionally unchanged outside confirmed-strict production | Owner: delivery-orchestrator | Status: OPEN
- RISK-002 | Category: OPS | Probability: 3 | Impact: 2 | Score: 6 | Mitigation: verify live group emission and memberships; default viewer fail-closed | Validation: runtime role probes (pending post-merge) | Residual risk: legitimate mutations denied until operational configuration is corrected | Owner: delivery-orchestrator | Status: OPEN
- RISK-003 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: explicit alias header forwarding and exact extraction-test repairs | Validation: TEST-004..007 green | Residual risk: additional direct caller harnesses may need narrowly admitted fixture changes | Owner: delivery-orchestrator | Status: OPEN
- RISK-004 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: rollback only under existing protected rollback gates; document restored vulnerability | Validation: rollback evidence (pending post-merge) | Residual risk: previous release reopens mutation access | Owner: delivery-orchestrator | Status: OPEN

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: correct "19 ungated + 4" to "15 ungated + 4"; remove claimed
  existing env-list parser and existing mutation logging
- Specification impact: preserve capability decisions with actual routes
- Plan impact: add explicit logging, alias forwarding and harness work
- Tasks impact: trace acceptance to 19 actual browser mutations
- Authorization impact: no expanded source/runtime authority
- Follow-up: reconcile rollout classification before runtime admission;
  transitional removal and cosmetic UI remain separate

## Rollout and rollback

Ship app changes through the existing protected VPS workflow for an exact
merged, green main SHA. No schema migration or edge change is needed.
Confirm strict identity behavior remains active; validate live role claims
and /api/session for representative accounts. Unknown live group format
does not block design, but prevents declaring privileged-flow acceptance.

Rollback uses the existing protected previous-SHA rollback/redeploy path.
Do not unset the edge secret or edit nginx as an RBAC rollback. Re-run health,
identity and ingestion probes; record that previous behavior reopens the
authorization gap.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: prior release | Retry: after authority/security gates resolve | Rollback: none | Evidence: exact SHA, CI, protected policy and security handoff
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: prior release | Retry: after prerequisite repair | Rollback: none | Evidence: strict-mode/group probes and rollback identity
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: inspect actual workflow state, do not assume old or new release | Retry: only after diagnosis | Rollback: protected previous-SHA path | Evidence: workflow execution audit
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: deployed but unaccepted | Retry: bounded probes with safe fixtures | Rollback: previous SHA | Evidence: all-role mutation/read/session probes and worker-ingestion continuity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: release state unresolved | Retry: existing workflow recovery only | Rollback: protected path | Evidence: release identity and workflow state, not inferred from an HTTP success
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: cleanup outstanding | Retry: bounded authorized cleanup | Rollback: none | Evidence: fixture cleanup record
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: acceptance incomplete | Retry: evidence recovery | Rollback: based on runtime state | Evidence: issue, workflow artifacts, KB record; no credential values
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: inspect actual state | Retry: protected recovery only | Rollback: previous SHA without edge/schema edits | Evidence: restored SHA, health/identity/ingestion probes and security regression note

- Adjacent-stage review: COMPLETE
- Production-learning root cause: intake aggregates were recorded from a partial route read before the full checkout inventory; direct verification (tests/test_route_table.py and api/app/main.py) corrected the counts and disproved the claimed existing env-list parser and mutation logging
- Production-learning adjacent-stage findings: 15 ungated + 4 identity-gated = 19 browser mutations (not 19 + 4); api/app/config.py:149-154 is TTL parsing, so ADMIN_USERS/OPERATOR_USERS are new code; identity.py had no mutation-attempt audit — all three corrected in spec/plan/tasks and on #530 (comments 6236261157, 6236421791)

## Runtime feedback

Missing or unrecognized groups make legitimate users viewers. This is a
safe denial; the remedy is operational configuration (live group emission
and membership verification), never parser relaxation or client-header
trust. Env-list changes take effect after process restart.

A rollback restores the prior authorization weakness and must be recorded
as a security regression, not a neutral feature rollback. If live group
format differs from the comma-separated contract, mutations deny for all
group-based users (viewer floor); env lists remain a working elevation
path while the discrepancy is resolved.
