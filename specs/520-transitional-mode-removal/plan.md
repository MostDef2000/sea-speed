# Plan — #520 residual: transitional edge-auth mode removal (fail-closed 503)

- Issue: #520
- Specification: specs/520-transitional-mode-removal/spec.md
- Date: 2026-10-24

## Architecture

Single trust-primitive change. `require_operator_identity` collapses to two
branches: strict compare (secret set) and fail-closed 503 (secret unset or blank).
The one-shot transitional latch and both WARNING branches are deleted; the module
logger stays (other use sites may need it; the extraction harness keeps it).
Route behavior above the primitive is untouched: `require_role` and the operator
routes keep their ordering (identity first, role second), the existing 403/503
detail strings stay the only externally visible failure shapes, and the frontend
already renders 503 as "identity unavailable" (no detail-string coupling found in
frontend/**).

## Decisions

- D-520-601 | DELETE the transitional branch, do not keep it behind a flag. The
  strict posture is the only supported posture since 2026-10-18; the transitional
  branch is a documented fail-open risk (a blank/unset secret silently trusts
  client usernames). A flag would keep the risk reachable by misconfiguration —
  fail-closed is the smallest safe state space.
- D-520-602 | Reuse the existing 503 detail "Trusted Authentik identity is
  unavailable" for the unconfigured-secret case instead of introducing a new
  detail string: one externally observable "identity unavailable" shape, no
  frontend/message-schema change, strict-mode 503 semantics unchanged.
- D-520-603 | No log on the fail-closed path. A per-request warning would spam;
  the one-shot latch pattern is exactly what is being removed. Misconfiguration
  is observable through the 503 on every operator route.
- D-520-604 | Migrate the incidental unconfigured-secret tests to the strict
  fixture instead of deleting them: they pin real behavior (trim, role join,
  blank-username 503) and must keep pinning it under the strict posture with the
  edge header supplied. The transitional acceptance pins are replaced by
  fail-closed pins (assertRaises 503 + assertNoLogs).
- D-520-605 | Remove the latch name from both test extraction manifests
  (`_IDENTITY_MODULE_GLOBALS`, rbac `assigns`): the harness extracts only
  existing module assigns; the base tree keeps the latch (RED authenticity), the
  fixed tree does not.

## Affected contours

- API trust primitive: `api/app/identity.py` (`require_operator_identity`,
  module latch removal, `require_role` docstring wording).
- Test harnesses: `tests/test_auth_session_identity.py`,
  `tests/test_sea_speed_rbac.py` (fail-closed pins, strict-fixture migrations,
  extraction manifests).
- Repo tooling: `scripts/ci/validate_sdd.py` — one grandfather-set entry
  (the 520 staged-PR set gains its removal PR).
- Worker / VPS deploy tooling / frontend: zero diff.

## Validation

- Focused: `python3 -m pytest tests/test_auth_session_identity.py
  tests/test_sea_speed_rbac.py` on the fix head (40 tests + subtests expected).
- RED authenticity: the new fail-closed pins must fail on base main @ 0139f3e8
  (verified in a detached worktree with only the test files copied — base still
  accepts in unconfigured mode, and with the latch dropped from the harness the
  base transitional branch itself raises NameError: behavioral failure observed).
- Full battery: `python -W error::ResourceWarning -m unittest discover -s tests
  -p 'test_*.py'` (1138 tests expected OK, skipped=4).
- Repo gates: `validate_sdd.py` (trio + PR contract), `validate_repo.py`, ruff
  with `scripts/quality/ruff.toml`; mypy strict set does not include
  identity.py (unchanged by CI definition).

## Runtime feedback

- Post-merge: VPS deploy is a separate owner gate (security-sensitive contour);
  acceptance probes (operator routes 200 with edge header; 403 without; 503
  behavior only reachable under deliberate misconfiguration) belong to that
  gate's plan, not to this PR.

## Risk profile

- Risk profile: REQUIRED

- RISK-520-601 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: strict-mode paths byte-identical (edge compare precedes username handling, unchanged from base); only the previously-unsafe unconfigured/blank-secret case changes from fail-open acceptance to fail-closed 503; both variants pinned by RED-verified fail-closed tests at primitive and require_role level, with assertNoLogs on the new path | Validation: RED on base 0139f3e8 (worktree) + GREEN focused run (40 passed, 130 subtests) + full battery 1138 OK skipped=4 + mutation pin (503→403 caught by all four pins) | Residual risk: a misconfigured secret is now a visible operator-route outage instead of a silent fail-open (intended tightening; recorded D-520-602) | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-520-602 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: production secret set since 2026-10-18, so the 503 branch is unreachable in the current prod posture; the merged code reaches production only through the separate owner-gated VPS deploy (ИБ-этап + deploy-authorized exact-SHA pipeline) with acceptance probes (operator routes 200 with edge header / 403 without) | Validation: deploy-run probes recorded at the owner-gated deploy step; unit pins cover the 503 path | Residual risk: if the VPS secret is ever lost or blanked, operator routes hard-fail 503 (fail-closed by design; runbook: restore secret, restart service) | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-520-603 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: zero worker/deploy/frontend diff; the 503 detail string is reused (no message-schema change); full battery green | Validation: git diff --name-only equals the declared 7-file scope; frontend coupling search clean ("Trusted Authentik" absent from frontend) | Residual risk: none known | Owner: delivery-orchestrator | Status: MITIGATED

## Test design

- TEST-520-601 | Covers: AC-001 | Level: unit | Priority: P1 | Evidence: tests/test_auth_session_identity.py
  OperatorEdgeAuthTests
  test_unconfigured_edge_secret_fails_closed + test_blank_edge_secret_fails_closed
  (assertRaises 503 with the canonical detail + assertNoLogs WARNING guard)
- TEST-520-602 | Covers: AC-001 | Level: unit | Priority: P1 | Evidence: tests/test_sea_speed_rbac.py
  IdentityFirstOrderingTests
  test_unconfigured_edge_secret_fails_closed (require_role-level: both blank
  variants, 503, no warning log)
- TEST-520-603 | Covers: AC-002 | Level: unit | Priority: P1 | Evidence: existing
  strict-mode suites stay green without modification (non-ASCII 403, missing
  header 403, blank username 503); incidental unconfigured-secret tests migrated
  to the strict fixture keep pinning trim/role/503 semantics

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-520-601 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: not applicable (no mutation) | Evidence: the #520 residual scope approved in the #537 Outcome Contract 2026-10-19 ("transitional-mode removal approved as a separate small PR in the same batch"); dual-accept validator honors the legacy receipt
- TX-520-602 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged; branch not created | Retry: NO | Rollback: not applicable (no mutation) | Evidence: base 0139f3e8ae52285f264b4a2e77875bc5ad2d8838 verified clean; branch 520-transitional-removal created from the exact base
- TX-520-603 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: uncommitted working tree on the task branch; main untouched | Retry: YES (re-edit in the working tree) | Rollback: discard working-tree changes (git checkout -- . + branch delete) | Evidence: api/app/identity.py, tests/test_auth_session_identity.py, tests/test_sea_speed_rbac.py, specs/520-transitional-mode-removal/**, scripts/ci/validate_sdd.py
- TX-520-604 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: implementation stays uncommitted; defect reported to the orchestrator | Retry: YES (fix + re-run) | Rollback: not applicable (no mutation) | Evidence: RED authenticity on base 0139f3e8 (detached worktree, test-only copy) + GREEN focused run + full battery (1138 OK, skipped=4) + ruff — outputs recorded in the session log
- TX-520-605 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: task branch commits rolled back to the branch point; main untouched | Retry: YES (re-commit) | Rollback: git reset to the branch point on the task branch | Evidence: commits on 520-transitional-removal (authorization: #537 Outcome Contract batch approval)
- TX-520-606 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: scratch artifacts remain in /tmp/opencode only (sandbox-ephemeral, never in git) | Retry: YES | Rollback: not required (scratch only) | Evidence: RED-check worktree removed after the run
- TX-520-607 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: prior evidence cursors remain valid | Retry: YES (re-post evidence comment) | Rollback: not required (additive audit text) | Evidence: issue #537 batch record + PR Change Contract synchronized with the exact diff
- TX-520-608 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: main unchanged until merge; after merge a revert PR restores the transitional branch (not recommended — fail-open); the VPS contour is not touched by this PR | Retry: YES | Rollback: revert per PR | Evidence: rollback = revert commit; deploy state unchanged by this PR (deploy is a separate owner gate)
