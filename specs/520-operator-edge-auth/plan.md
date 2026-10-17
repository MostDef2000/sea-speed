# Plan: #520 — operator identity: edge-secret enforcement at the API

- Specification: specs/520-operator-edge-auth/spec.md

## Architecture

`api/app/identity.py` is the single trust-primitive module (extracted in
#396 wave 1; imports only `config` + `fastapi`, never `main`). The edge
check therefore lives inside `require_operator_identity`, and every
operator-identity route inherits enforcement without touching route logic.
The secret is a config constant (`EDGE_AUTH_SECRET`), mirroring
`API_TOKEN`/`WORKER_CONTROL_TOKEN`. The edge header travels as an ordinary
FastAPI `Header(None)` parameter alongside `x_authentik_username`, so no
middleware, no dependency rewrite and no OpenAPI response changes are
introduced. `/api/session` (currently inline-duplicating the trust rule)
delegates to the primitive — one enforcement point for all seven call
sites.

## Decisions

- D-1 (env-gated transitional mode, not fail-closed-500): API deploys from
  `main` happen independently of the edge phase; a hard fail-closed on
  unset secret would break the operator UI on an unrelated deploy.
  Transitional mode = today's exact behavior + warning, documented and
  time-boxed (removed in the post-phase-3 cleanup). Strict mode is what
  ships once the edge injects the secret.
- D-2 (403 before username check): header mismatch raises 403
  "Forbidden" (mirrors `require_auth`) before the username is read, so a
  forged request reveals nothing. Missing username under strict mode with
  a correct secret keeps the existing 503 semantics.
- D-3 (constant-time compare): `hmac.compare_digest(expected, provided)`
  on the edge secret; the secret value is never logged or echoed.
- D-4 (single enforcement point): `/api/session` calls
  `require_operator_identity` instead of inline duplication. The existing
  AST pin (`tests/test_auth_session_identity.py:66-88`) requires the first
  parameter name `x_authentik_username` and route path `/api/session` —
  both preserved; the second header parameter is additive.
- D-5 (edge half is PR-2 with fresh admission): codifying the live vhosts
  (basic-auth `3d.mostdef.ru`, worker-private 18080) into the renderer plus
  the injection/strip directives is a control-plane change with its own
  risk surface; it does not ride in this API PR.
- D-6 (fingerprint discipline): `test_route_table.py` /
  `test_api_contract.py` are updated only if the new Header parameter
  changes their fingerprints; any such update is deliberate and listed in
  the PR Change Contract, never silent.

## Affected contours

- VPS: `api/**` — code rides the `deploy-vps.yml` contour (Change Contract
  declares VPS REQUIRED), but deployment is NOT dispatched until the edge
  phase (2) is complete and the API env carries the secret (phase 3);
  rollout order is recorded on #520 (comment 6217745201). ИБ-этап applies
  to the deployment phases (полоса C).
- Repo CI: full battery + validators on exact head.
- Ubuntu Worker/relay: none (worker contour untouched; `call_worker_control`
  outbound Bearer path unchanged).

## Validation

- Focused: `python3 -m pytest tests/test_auth_session_identity.py
  tests/test_worker_operator_control.py tests/test_route_table.py
  tests/test_api_contract.py -q`.
- Full battery: `python3 -m pytest tests/ -q`.
- `python3 scripts/ci/validate_sdd.py`; `python3 scripts/ci/validate_repo.py`.
- RED authenticity: strict-mode tests executed at base `2f24669` in a
  clean worktree MUST fail before the fix (orchestrator-verified).
- PR Change Contract: exact changed-file match; VPS REQUIRED; Risk profile
  REQUIRED (security); CI green on exact head before merge.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: SEC | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: env-gated transitional mode keeps the merge inert at runtime; documented rollout order (edge phase injects the header BEFORE the API env deploys strict mode); instant rollback by unsetting SEA_SPEED_EDGE_AUTH_SECRET without redeploy | Validation: PR rollout order field; issue design comment 6217745201; runtime acceptance probes AC-005 | Residual risk: an operator setting the env secret out of order 403s all browser traffic until the env var is unset — procedural, documented | Owner: delivery-orchestrator | Status: OPEN
- RISK-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: client-controlled header values are compared as UTF-8 bytes (constant-time), so any input — absent, blank, wrong, non-ASCII — yields 403, never an unhandled TypeError/500 | Validation: non-ASCII behavioral pin + wrong/absent/blank pins before username handling | Residual risk: none known | Owner: delivery-orchestrator | Status: OPEN
- RISK-003 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: transitional mode is byte-identical to base 2f24669 and pinned by unchanged legacy tests running env-independently; one-shot warning is the standing signal until cleanup | Validation: legacy pins byte-identical to base, full battery green | Residual risk: strict-vs-transitional probeable with a wrong ASCII header (403 vs 200/503) — inherent to env-gating, accepted in the issue design comment | Owner: delivery-orchestrator | Status: OPEN

## Test design

- TEST-001 | Covers: R-1, R-2 | Level: unit | Priority: P0 | Evidence: transitional legacy pins (:44-64 region) byte-identical to base and green; one-shot warning test (exactly once, set-but-blank vs unset distinguished, no identity material in message)
- TEST-002 | Covers: R-1, R-3 | Level: unit | Priority: P0 | Evidence: strict-mode ordering pins in both directions (absent/blank/wrong/non-ASCII header → 403 before username; correct header + blank username → 503); correct header → trimmed identity; non-ASCII pin
- TEST-003 | Covers: R-3, R-4 | Level: unit | Priority: P0 | Evidence: AST wiring pin over all seven operator handlers (declare + pass x_sea_speed_edge_auth); legacy AST pins (arg name, route path) preserved
- TEST-004 | Covers: R-5 | Level: unit | Priority: P1 | Evidence: hmac.compare_digest over UTF-8 bytes in the extracted verbatim primitive; warning content pin (no secret/header values)
- TEST-005 | Covers: AC-005 | Level: runtime-manual | Priority: P1 | Evidence: sysadmin acceptance probes through the live front after phases 2-3 (forged → 403, normal flow OK) on #520

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

Phase 3 VPS application of the merged API (deploy-vps.yml on the exact
merged main, AFTER edge phase 2 injects the header; DEPLOY-TRIGGER owner
gate in chat, standing lane-A dispatch, ИБ-этап applies to phases 2-3).

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no deploy started; runtime stays on the previous SHA in transitional mode (env secret not yet set) | Retry: after fresh DEPLOY-TRIGGER confirmation | Rollback: not applicable (no mutation) | Evidence: edge phase 2 handoff result on #520 (header injected + client X-Authentik-* stripped + API env secret set) + exact 40-hex SHA from origin/main + trusted CI on that SHA
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: running API untouched (previous SHA) | Retry: yes after evidence re-read | Rollback: not applicable | Evidence: deploy-vps.yml preflights (ancestry check, auth-boundary preflights, workflow policy evaluation) pass on the exact SHA
- TX-003 | Stage: MUTATION | Mutation: YES | Mutation detail: deploy-vps.yml ships the merged code to the VPS and restarts the sea-speed API service | Failure disposition: CONDITIONAL | State after failure: workflow fail-closed — previous release stays authoritative on deploy failure; unit/start gates prevent a half-applied state | Retry: one bounded retry after root-cause read | Rollback: redeploy of the previous SHA; env-level rollback (unset SEA_SPEED_EDGE_AUTH_SECRET) restores legacy mode without redeploy | Evidence: deploy-vps.yml run + service status in run log
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: new code active but not accepted; rollback executed | Retry: after remediation | Rollback: as TX-003 | Evidence: acceptance probes through the live front — forged X-Authentik-Username without edge secret → 403; normal operator UI flow → OK; /api/session → identity
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: n/a (VPS release state is the deploy itself; no separate state commit) | Retry: as TX-003 | Rollback: as TX-003 | Evidence: DEPLOY-TRIGGER probe results recorded on #520
- TX-006 | Stage: HOUSEKEEPING | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: runtime correct; secret lives only as env pointers (SEA_SPEED_EDGE_AUTH_SECRET in API env + edge secret file); no repo artifacts | Retry: next sysadmin session | Rollback: not applicable | Evidence: sysadmin tx log; no secret values in chat or issue (pointers only)
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime correct; evidence gap closes on next session | Retry: yes | Rollback: not applicable | Evidence: #520 phase-2 and phase-3 comments with probe outputs; JOURNAL entry per phase
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: previous SHA redeployed, service active, probes re-run | Retry: one bounded retry then hold for owner decision | Rollback: previous-SHA deploy via deploy-vps.yml (standing rollback contract) | Evidence: probe results after rollback on #520 (rollback `ready_not_used` unless triggered)

## Runtime feedback

- Failure mode "secret set, edge not injecting": operator routes 403 for
  all browser traffic — that is the documented phase-ordering hazard; the
  mitigation is procedural (phase 2 before phase 3) plus instant rollback
  by unsetting the env var (legacy mode without redeploy).
- Transitional warning volume: once per process (module-level latch), so
  logs stay quiet while still proving the mode.
