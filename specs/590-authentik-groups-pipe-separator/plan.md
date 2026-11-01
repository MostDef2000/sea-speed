# Plan — Issue #590 X-Authentik-Groups pipe/comma separator fix

- Issue: #590
- Specification: specs/590-authentik-groups-pipe-separator/spec.md

## Architecture

Single-choke-point parsing fix on the API identity contour. The authentik
proxy outpost joins multiple group values into ONE `X-Authentik-Groups`
header with `|` (verified production Caddy log on lifesim, 2026-11-01:
`"X-Authentik-Groups":["authentik Admins|Sea Speed Owner"]`), while duplicate
headers are joined with `,`. `resolve_role()` in `api/app/identity.py` is the
only place in the repository that splits that header (repo-wide grep: zero
other consumers parse it; `main.py` forwards the raw header, the nginx
renderer is pass-through) — so one split change there fixes every endpoint.
Matching semantics stay exactly as documented: trimmed, exact case-sensitive
whole-token match against the four recognized group names, unknown tokens
grant nothing, highest recognized role wins, absent/blank → viewer, env lists
(ADMIN_USERS/OPERATOR_USERS) remain authoritative and checked first.

## Decisions

- **Fix at the single choke point, not at callers**: `identity.py:183` is the
  only split of the header in the repo (verified by independent peer grep
  across api/, scripts/, frontend/, deploy/, worker/, contracts/).
- **`replace("|", ",").split(",")` instead of `re.split(r"[|,]", …)`**:
  `tests/test_auth_session_identity.py` AST-extracts `resolve_role` verbatim
  and execs it in a namespace containing only `{Any, Dict, Optional,
  ADMIN_USERS, OPERATOR_USERS}` — no `re` — so a `re.split` fix would
  `NameError` there (that file is outside this fix's allowed paths).
  Equivalence is proven empirically: 20,027 cases (handpicked edge cases plus
  20k random fuzz over an `ab|, \t` alphabet) — 0 mismatches, token-for-token
  identical including empty tokens. Blueprint group names
  (deploy/vps/authentik/blueprints/sea-speed-auth-v1.yaml) contain neither
  `|` nor `,`, so no legitimate token can be corrupted.
- **No env workaround in this fix**: the immediate env-var option
  (`SEA_SPEED_ADMIN_USERS=akadmin` + service restart) was offered and the
  owner chose the durable code fix ("делай сразу хорошо чтобы работало").
- **TDD**: the 4 new tests were written first and observed failing on the
  unfixed resolver (the two pipe-only-reachable cases: `'viewer' != 'admin'`
  and `'viewer' != 'operator'`); the mixed-separator case is comma-reachable
  via its comma prefix and the fail-closed case already held on base — they
  pin the fix's shape.

## Affected contours

- API (deployed to VPS — release contour): api/app/identity.py.
- Control plane: tests/test_sea_speed_rbac.py (4 new tests) and this SDD
  trio. Nothing else — no worker/, frontend/, deploy/, scripts/, .github/
  changes.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_sea_speed_rbac.py::ResolverSemanticsTests::test_pipe_separated_groups_production_format — production pipe format resolves admin; observed failing on base dc1e9f7
- TEST-002 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_sea_speed_rbac.py::ResolverSemanticsTests::test_pipe_split_highest_wins — highest role wins across pipe; observed failing on base
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P1 | Evidence: tests/test_sea_speed_rbac.py::ResolverSemanticsTests::test_mixed_separators_split — mixed `|`/`,` resolves highest role
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: tests/test_sea_speed_rbac.py::ResolverSemanticsTests::test_pipe_unknown_tokens_fail_closed — unknown pipe tokens grant nothing
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: full battery 1278 passed / 2 skipped / 357 subtests (baseline 1274/2/357 on base dc1e9f7; delta exactly +4 methods), ruff clean, validate_sdd green; pre-existing resolver tests untouched

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

This audit models the VPS-only rollout of the identity parsing fix; it does
not redeploy Ubuntu or Windows.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production VPS remains on the accepted previous release | Retry: correct exact SHA/quality/authorization evidence then re-enter the protected VPS deploy workflow | Rollback: NOT REQUIRED before mutation | Evidence: exact merged main SHA, green CI on that SHA, owner authorization `commit approved` (2026-11-01)
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate release may be staged while current VPS release remains active | Retry: verify staged exact release and previous/current identities then retry | Rollback: NOT REQUIRED while active release is unchanged | Evidence: exact VPS artifact/release manifest and current/previous release markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release may be active but is not accepted until verification succeeds | Retry: only after existing deploy transaction restores or proves a coherent current release | Rollback: existing VPS deploy rollback restores previous exact release | Evidence: repository-owned deploy-vps activation logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: resolve health/public-smoke failure after actual current release is known | Rollback: automatic previous-release verification through accepted loopback origin and protected public smoke | Evidence: origin health, public smoke, exact API release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: previous exact VPS release remains the declared rollback target | Evidence: current/previous markers plus runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but validation acceptance remains incomplete | Retry: recollect the mutation probe without redeployment when exact runtime identity is unchanged | Rollback: decide from actual API/runtime behavior, not evidence upload alone | Evidence: deployment manifest plus the owner-side dashboard probe (worker stop / ROI save return 200) and API journal excerpts
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if previous exact release cannot be restored/verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous exact VPS release | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- Focused run `PYTHONPATH=/tmp/opencode/582/pylibs:. python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/590/pytest-tmp tests/test_sea_speed_rbac.py tests/test_auth_session_identity.py -q`: OBSERVED 44 passed / 130 subtests passed.
- Base differential: the two pipe-only-reachable tests run against the
  UNFIXED resolver at dc1e9f7 → OBSERVED 2 failed (`'viewer' != 'admin'`,
  `'viewer' != 'operator'`), reproduced independently by the implementer and
  the peer reviewer in separate scratch worktrees.
- Full battery `PYTHONPATH=/tmp/opencode/582/pylibs:. python3 -m pytest -p
  no:cacheprovider --basetemp=/tmp/opencode/590/pytest-tmp tests/ -q`:
  OBSERVED 1278 passed / 2 skipped / 357 subtests (baseline 1274/2/357 on
  base dc1e9f7; delta exactly +4 methods).
- Canonical runner `PYTHONPATH=/tmp/opencode/582/pylibs:. python3
  scripts/run_tests.py --skip-install`: OBSERVED PASS 2/2 CI battery
  commands green, EXIT=0.
- Peer verification (independent read-only reviewer, separate scratch
  worktree): verdict APPROVE — 20,027-case separator-equivalence fuzz (0
  mismatches), single-choke-point grep, fail-closed semantics confirmed
  intact, RED reproduced, 0 deleted test lines.
- `python3 scripts/ci/validate_sdd.py` plain run passes with the new trio.
- `python3 scripts/ci/validate_change_contract.py` (PR body simulated):
  contract valid, derived impact VPS.

## Runtime feedback

- RF-001: Operator actions expected: 0 — the change rides the normal VPS
  release contour; runtime acceptance = exact-head CI green, lane-A deploy on
  the merged main SHA, then the production probe: owner-triggered mutations
  return 200 (worker stop, ROI save/clear); GPU worker traffic unaffected.
- RF-002: no stored-data migration is needed or performed: role resolution is
  per-request header parsing; nothing persisted changes shape.
