# Spec: #520 — operator identity: edge-secret enforcement at the API

- Issue: #520

Design + phase plan: issue comment 6217745201. App-layer half of the fix.
Edge half (live vhost codification in the nginx renderer) is a follow-up
admission (PR-2); rollout phases 2-3 are sysadmin lanes, not repo scope.

## Product outcome

The API stops trusting a bare client-supplied `X-Authentik-Username` as an
operator identity. Today `require_operator_identity`
(`api/app/identity.py:89-93`) accepts ANY non-empty `X-Authentik-Username`
header, and the live front (`3d.mostdef.ru`, auth_basic, no `auth_request`,
no header scrub) forwards client headers verbatim to the API — so one
basic-auth holder can impersonate any operator on the worker-control routes
(`main.py:1013-1056`) and `/api/session` (`main.py:1061`). After this
change the API accepts operator identity only when the request carries the
edge-injected shared secret `X-Sea-Speed-Edge-Auth` equal to
`SEA_SPEED_EDGE_AUTH_SECRET`. Enforcement is env-gated: while the secret is
unset the API keeps today's exact behavior (documented transitional mode
with a warning log), so an unrelated deploy from `main` cannot break the
operator UI before the edge phase injects the header.

## User scenarios

- Transitional (secret unset): operator UI and analytics work exactly as
  today; the API logs a warning that operator trust is running unverified.
- Strict (secret set, edge injects): a crafted request with a forged
  `X-Authentik-Username` and no/incorrect `X-Sea-Speed-Edge-Auth` gets 403
  before the username is read; the normal browser flow through nginx keeps
  working because nginx overwrites the header with the secret.
- Direct API access (VPS loopback) without the secret: 403 on operator
  routes; Bearer-contour routes (`require_auth`) and analytics ingestion
  are untouched.

## Scope

- `api/app/config.py`: new `EDGE_AUTH_SECRET` constant (env
  `SEA_SPEED_EDGE_AUTH_SECRET`, default empty) — same env pattern as
  `API_TOKEN` / `WORKER_CONTROL_TOKEN`.
- `api/app/identity.py`: `require_operator_identity` gains a second
  optional parameter (the edge header value). Strict mode (secret set):
  header must equal the secret exactly (constant-time compare), else 403
  before any username handling; missing username stays 503. Transitional
  mode (secret unset/blank): legacy semantics + warning at least once per
  process.
- `api/app/main.py`: the six `/api/worker/control*` routes (:1013-1056) and
  `/api/session` (:1061) add `x_sea_speed_edge_auth: Optional[str] =
  Header(None)` and pass it through; `/api/session` is unified to call
  `require_operator_identity` (single trust primitive; its AST pins — first
  arg name `x_authentik_username`, route path `/api/session` — are
  preserved).
- `tests/test_auth_session_identity.py`: behavioral tests for both env
  states using the existing dynamic-load infrastructure; existing pins
  (:44-88) remain green as transitional-mode pins.
- `tests/test_route_table.py`, `tests/test_api_contract.py`: updated ONLY
  if their fingerprints require it (deliberate fingerprint bump, noted in
  the PR).
- `specs/520-operator-edge-auth/{spec,plan,tasks}.md`: this trio.

Out of scope: nginx renderer codification of the live vhosts and the
`X-Sea-Speed-Edge-Auth` injection/strip directives (PR-2, fresh admission);
basic-auth → forward-auth migration (owner model decision); app-layer auth
for `PATCH/DELETE /api/objects*`, `/media` and preview mutations (separate
issue after merge); Bearer token on the browser contour; any production
deployment/edge change (phases 2-3 run through sysadmin handoffs, полоса C);
worker contour; secrets or env values in the repo.

## Requirements

- R-1: strict mode (secret set) — operator routes require
  `X-Sea-Speed-Edge-Auth` to equal `SEA_SPEED_EDGE_AUTH_SECRET`; mismatch
  or absence → 403 "Forbidden" before the username is inspected; correct
  secret + valid username → identity returned; correct secret + missing
  username → 503 (unchanged semantics).
- R-2: transitional mode (secret unset/blank) — behavior byte-compatible
  with `2f24669`, plus a warning log emitted at least once per process.
- R-3: all operator-identity call sites (6 worker/control routes +
  `/api/session`) pass the edge header; `/api/session` delegates to
  `require_operator_identity`; route paths, methods and response shapes
  unchanged.
- R-4: existing session-identity pins (trimmed username, blank → 503,
  AST route/arg pins) stay green without weakening.
- R-5: secret comparison is constant-time (`hmac.compare_digest`); no
  secret value is logged or included in any HTTP response.

## Acceptance criteria

- AC-001: transitional mode — existing pins green unchanged; warning
  emitted (unit-verifiable).
- AC-002: strict mode — absent/incorrect edge header → 403; correct
  header + username → identity returned; correct header + blank username
  → 503. New tests RED at base `2f24669` (verified by the orchestrator on
  the base worktree, not claimed by the implementer alone).
- AC-003: full battery green; `validate_sdd.py` and `validate_repo.py`
  green; focused suites accounted.
- AC-004: PR Change Contract exact-file match; VPS contour REQUIRED; Risk
  profile REQUIRED (security); CI green on exact head.
- AC-005: runtime-manual acceptance — after phase 2 (edge injects secret + strips
  client `X-Authentik-*`) and phase 3 (API env + deploy): forged operator
  header through the live front → 403; normal UI flow works. Evidence on
  #520 via sysadmin session.

## NFR assessment

- NFR-001 | Area: security | Target: in strict mode, operator requests without the correct edge secret are rejected 403 "Forbidden" before the username is inspected (absent, blank, wrong and non-ASCII header values alike); the comparison is constant-time over UTF-8 bytes; no secret or header values are logged or echoed | Validation: behavioral ordering pins in both directions (wrong-secret+blank-username → 403 not 503; correct-secret+blank-username → 503), non-ASCII pin, warning content pin | Evidence: tests/test_auth_session_identity.py OperatorEdgeAuthTests; RED proofs at base 2f24669 | Status: PASS
- NFR-002 | Area: compatibility | Target: transitional mode (secret unset or blank) is byte-identical to base 2f24669 for every existing client and route, with only a one-shot warning added; response shapes unchanged | Validation: legacy pins (:44-64 region) byte-identical to base and green; env-independent pinning (explicit env unset); full battery | Evidence: focused suite + CI battery on exact head | Status: PASS
- NFR-003 | Area: maintainability | Target: a single trust primitive serves all seven operator-identity call sites (no duplication); the test harness extracts the verbatim function body and couples to the private latch/logger names so refactors fail loudly instead of silently weakening the pin | Validation: AST wiring pin over all 7 handlers; harness NameError/AssertionError on rename | Evidence: tests/test_auth_session_identity.py extraction + wiring pin | Status: PASS
- NFR-004 | Area: operations | Target: the rollout-order hazard (API env secret set before the edge phase injects the header → fail-closed 403 for browser traffic) is documented, and rollback is instant (unset the env var) without redeploy | Validation: plan.md Runtime feedback + PR rollout order + issue design comment 6217745201 | Evidence: specs/520-operator-edge-auth/plan.md | Status: PASS

## Runtime feedback

- Enforcement activates only when `SEA_SPEED_EDGE_AUTH_SECRET` is present
  in the API env. If the secret is set before the edge phase injects it,
  operator routes fail closed (403) for every browser request — the
  rollout order is therefore: phase 2 (edge) BEFORE phase 3 (API env +
  deploy). Rollback: previous deploy SHA, or unsetting the env var for an
  immediate legacy-mode revert.
- The transitional warning is a deprecation signal for the follow-up
  cleanup phase (transitional mode removal after phase 3 is recorded as
  deferred work in tasks).
