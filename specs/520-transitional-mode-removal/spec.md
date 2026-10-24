# Issue #520 residual — transitional edge-auth mode removal (fail-closed 503)

- Issue: #520
- Residual authorization: batch approval recorded in the #537 Outcome Contract (2026-10-19): "transitional-mode removal (#520 residual) approved as a separate small PR in the same batch"
- Status: ACTIVE
- Date: 2026-10-24

## Product outcome

`require_operator_identity` in `api/app/identity.py` has exactly two modes: strict
(secret set) — edge-injected shared secret verified BEFORE any username handling —
and unconfigured (secret unset or blank) — fail-closed 503 "Trusted Authentik
identity is unavailable". The transitional mode (secret unset/blank accepted a
non-blank `X-Authentik-Username` with a one-shot WARNING) is removed: the latent
fail-open (an attacker-supplied username is trusted when the edge secret is
misconfigured) becomes impossible, and the strict-mode deployment posture is the
only deployment posture. No behavior change for any healthy path: while
`SEA_SPEED_EDGE_AUTH_SECRET` is set (production state since 2026-10-18), every
request path is byte-identical.

## User scenarios

- Operator working through the edge proxy (secret set): unchanged — correct secret
  passes, forged/missing secret is 403, missing username is 503.
- Misconfigured deployment (secret unset or blank): operator routes fail closed
  with 503 instead of silently trusting client-supplied usernames; no warning
  log is emitted (the endpoint states its unavailability through the response).

## Requirements

- R-520-601: when `SEA_SPEED_EDGE_AUTH_SECRET` is unset or strips to blank,
  `require_operator_identity` must raise HTTP 503 with detail "Trusted Authentik
  identity is unavailable" before any username handling; no warning log may be
  emitted (no one-shot latch remains).
- R-520-602: strict mode must stay byte-identical: secret comparison (UTF-8 bytes,
  `hmac.compare_digest`, non-ASCII forged header surfaces as 403) precedes
  username handling; missing/blank username with a valid secret is 503 as before.
- R-520-603: the module-level latch `_EDGE_AUTH_TRANSITIONAL_WARNING_EMITTED` and
  both transitional WARNING branches are removed in full; no `transitional`
  reference remains in `api/**` or the identity test harnesses.
- R-520-604: protected surfaces stay untouched: `worker/**`, `deploy/**`,
  `frontend/**`, `data/contracts/*` — zero diff; the change touches
  `api/app/identity.py`, the two identity test harnesses, and this SDD trio (plus
  the one-line grandfather entry in `scripts/ci/validate_sdd.py`).

## Acceptance criteria

- AC-001: with the secret unset or blank, a valid username is rejected with 503
  "Trusted Authentik identity is unavailable" and no WARNING is logged (both the
  primitive-level pins in tests/test_auth_session_identity.py and the
  require_role-level pins in tests/test_sea_speed_rbac.py fail on base main @
  0139f3e8 and pass on the fix).
- AC-002: strict mode pins stay green unchanged (non-ASCII forged header 403,
  missing edge header 403, blank username 503) — the existing strict suites pass
  without modification.
- AC-003: `git diff` of the PR touches only `api/app/identity.py`,
  `tests/test_auth_session_identity.py`, `tests/test_sea_speed_rbac.py`,
  `specs/520-transitional-mode-removal/**`, and the grandfather set line in
  `scripts/ci/validate_sdd.py` — all protected surfaces zero-diff.

## NFR assessment

- NFR-601 | Area: SECURITY | Target: no operator identity can be accepted without edge verification under any configuration | Validation: fail-closed unit pins at both primitive and require_role level, including the set-but-blank case, with assertNoLogs guards | Evidence: tests/test_auth_session_identity.py OperatorEdgeAuthTests (unconfigured/blank fail-closed) + tests/test_sea_speed_rbac.py IdentityFirstOrderingTests.test_unconfigured_edge_secret_fails_closed (RED on base 0139f3e8, GREEN on the fix head) | Status: PASS
- NFR-602 | Area: MAINTAINABILITY | Target: no dead latch/warning code remains; the documented contract and the code agree | Validation: direct diff review (latch global, `global` statement and both warning branches deleted; comments/docstrings updated) | Evidence: PR diff; repo-wide grep shows zero `transitional` references in api/** and the identity test harnesses | Status: PASS

## Runtime feedback

- The change is behavior-neutral while the production secret is set (current
  state). The post-merge VPS deploy is a separate owner-gated step
  (security-sensitive contour): this PR delivers code + tests only; the deploy
  gate (ИБ-этап, exact-SHA deploy-authorized pipeline, acceptance probes on
  operator routes) runs after an explicit owner decision.
