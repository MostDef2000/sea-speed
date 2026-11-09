# Spec: #629 — deploy validation coverage for the #626 external scripts

- Issue: #629
- Specification: specs/629-deploy-validation-coverage/spec.md
- Authorization: commit approved (owner admission in the dev-chat delivery
  session, 2026-11-09, for the #629 scope: deploy.sh validation coverage +
  vacuum-scan fix + SDD trio, chain through merge, deploy and probes);
  base b21629e

## Product outcome

The VPS deploy pipeline validates the six external `.js` files introduced by
#626 (crossing-line.js, main.js, cameras/cameras.js, road/config.js,
road/main.js, unavailable.js) across the whole release lifecycle: a release
that carries neither the file nor its `.absent` marker is rejected before any
activation, and after activation each live module is smoke-checked through
its public URL (or logged as absent in a rollback release). The frontend
session-contract scan covers the shipped external scripts, so the
identity-from-session-payload invariant stays load-bearing after #626 moved
the page wiring out of the inline blocks. Pre-#626 rollback re-activation
keeps working: the new checks tolerate the `.absent` marker state that the
bootstrap capture path records for a live tree lacking the modules.

## User scenarios

- SC-1: an operator rolls the VPS back to a pre-#626 release (for example
  ba590050) whose six external `.js` entries exist only as `.absent` markers
  in the release layout — `install_release` accepts the marker state, the
  activation removes the live modules for a clean downgrade, and
  `verify_frontends` logs each absent module instead of failing the rollback.
- SC-2: a malformed release that carries neither the file nor the marker for
  any #626 module is rejected by `install_release` before any live source
  mutation, with the same message style as the existing module-state checks.
- SC-3: a healthy deploy activates a release carrying all six modules — the
  post-activation verification smoke-checks each of them through its
  env-overridable public URL, directly after the existing live-sync check.
- SC-4: a future edit ships a script that reads the spoofable
  `X-authentik-username` request header — the session-contract test fails
  because its scan surface now includes every connected local external `.js`
  body, not only inline scripts.

## Requirements

- R-1: `deploy/vps/deploy.sh` — `install_release` gains pre-activation
  validation for the six #626 external modules (crossing-line.js, main.js,
  cameras/cameras.js, road/config.js, road/main.js, unavailable.js) using the
  same `.absent`-tolerant idiom and message style as live-sync.js and
  overlay-canvas.js: file OR `<name>.absent` marker required, otherwise
  `Release ${release_name} has no <name> module state` and return 1 before
  any staging or activation.
- R-2: `deploy/vps/deploy.sh` — `verify_frontends` gains post-activation
  checks for the six targets in the healthy path, directly after the
  live-sync check and outside the Authentik-outage fallback branch:
  presence-conditional like objects/cameras/road — an empty live file fails
  closed, a present file is smoke-checked through `verify_public_url`, an
  absent file is logged as absent in this rollback release.
- R-3: `deploy/vps/deploy.sh` — six env-overridable URL constants following
  the LIVE_SYNC_URL pattern: `CROSSING_LINE_URL`, `MAIN_JS_URL`,
  `CAMERAS_JS_URL`, `ROAD_CONFIG_URL`, `ROAD_MAIN_URL` (mostdef.ru/sea-speed
  paths) and `UNAVAILABLE_JS_URL` (mostdef.ru/unavailable.js), each with a
  `SEA_SPEED_*_URL` override.
- R-4: `tests/test_auth_session_frontend_contract.py` — the
  X-authentik-username scan repoints from inline-script extraction to
  `frontend_html.page_live_source(path)` (page HTML plus all connected local
  external `.js` bodies); the comment keeps the identity-from-session-payload
  intent and reflects the new surface; no other assertion in the file
  changes.
- R-5: `tests/support/frontend_html.py` — `page_live_source` tolerates a page
  that still ships only inline scripts (the objects page) by scanning its
  HTML; a referenced but missing local script still fails closed.
- R-6: `tests/test_vps_deploy_transaction.py` — the deploy-transaction
  fixtures gain the six module URL env overrides and three tests exercising
  the new checks on both paths: a rollback release without file or marker
  fails closed pre-activation; a pre-#626 rollback release carrying only
  `.absent` markers re-activates with absent-module logs; a healthy deploy
  smoke-checks all six modules.
- R-7: forbidden surfaces stay byte-untouched: `api/**`, `frontend/**`,
  `worker/**`, `scripts/renderers/**` (notably
  `scripts/operations/nginx_sea_speed_auth.py`), `tests/test_589*`,
  `tests/test_618*`, edge-vhost tests, `tests/test_626_csp_no_inline_scripts.py`,
  `.github/workflows/**`, `scripts/ci/**`, `contracts/**`.

## Acceptance criteria

- AC-001: `install_release` rejects a release missing both the file and the
  `.absent` marker for any of the six #626 modules before any activation,
  and accepts a pre-#626 rollback release that carries only the markers.
- AC-002: `verify_frontends` fails closed on an empty live module file,
  smoke-checks each present module through its public URL, and logs each
  absent module in a rollback release; the Authentik-outage fallback branch
  is unchanged.
- AC-003: the six module URLs are env-overridable constants following the
  LIVE_SYNC_URL pattern (`SEA_SPEED_CROSSING_LINE_URL`,
  `SEA_SPEED_MAIN_JS_URL`, `SEA_SPEED_CAMERAS_JS_URL`,
  `SEA_SPEED_ROAD_CONFIG_URL`, `SEA_SPEED_ROAD_MAIN_URL`,
  `SEA_SPEED_UNAVAILABLE_JS_URL`).
- AC-004: the session-contract identity invariant is load-bearing over the
  shipped external scripts — injecting `X-authentik-username` into a shipped
  external `.js` fails the test (demonstrated and reverted), and the
  inline-only objects page still scans.
- AC-005: full battery green with exactly the new transaction tests added;
  ruff and validate_sdd pass.

## Runtime feedback

- RF-001: production effect requires the VPS front deploy (deploy-vps.yml)
  after merge — out of scope for this repository change; the new checks run
  on the next deploy or rollback invocation on the VPS.
- RF-002: both check sets are strictly additive validation: they never
  mutate release or live state, and the `.absent`-tolerant and
  presence-conditional shapes keep pre-#626 rollback re-activation working.

## NFR assessment

- NFR-001 | Area: deploy robustness | Target: no release lacking an explicit #626 module state can activate, and no pre-#626 rollback re-activation is blocked by the new validation | Validation: tests/test_vps_deploy_transaction.py — malformed-release rejection, marker-tolerant rollback and healthy smoke paths | Evidence: focused run recorded in plan.md | Status: PASS
- NFR-002 | Area: security / test authenticity | Target: the identity-from-session-payload invariant stays load-bearing over the shipped external scripts after #626 removed the inline blocks | Validation: RED-authenticity demonstration (header string injected into a shipped external .js fails the test) plus focused green run after revert | Evidence: observed FAIL line recorded in plan.md | Status: PASS
- NFR-003 | Area: rollback verification quality | Target: post-activation verification degrades gracefully for absent modules in rollback releases (log, not failure) while empty live files fail closed | Validation: transaction test asserting the six absent-module logs with a rolled_back manifest state | Evidence: focused run recorded in plan.md | Status: PASS
