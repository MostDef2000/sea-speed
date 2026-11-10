# Spec: #631 — bootstrap capture of the overlay-canvas module state

- Issue: #631
- Specification: specs/631-bootstrap-overlay-canvas-capture/spec.md
- Authorization: commit approved (owner admission in the dev-chat delivery
  session, 2026-11-10, for the #631 scope: bootstrap overlay-canvas capture +
  verify_frontends smoke check + SDD trio, chain through merge, deploy and
  probes); base 2d0873e

## Product outcome

The VPS deploy pipeline's bootstrap rollback path captures an explicit
overlay-canvas module state: when the first deploy on a fresh tree captures
the live code as the bootstrap rollback release and the live tree lacks
`overlay-canvas.js`, the capture records the `overlay-canvas.js.absent`
marker instead of nothing. A later re-activation of that bootstrap release —
notably as the automatic rollback target of a failed deploy — therefore
passes `install_release`'s module-state validation instead of failing with
`Release <name> has no overlay-canvas module state`, which previously left
the rollback path dead for such trees. Post-activation verification gains
the missing overlay-canvas smoke check, closing the last gap against the
#626/#629 module-check coverage: a present live module is non-empty and
publicly reachable, an absent module is logged as expected in a rollback
release.

## User scenarios

- SC-1: an operator runs the first deploy on a VPS whose live tree predates
  overlay-canvas.js (no `current-release` state file) — the bootstrap
  capture records `frontend/sea-speed/overlay-canvas.js.absent` in the
  captured rollback release; the deploy proceeds normally.
- SC-2: that deploy (or a later one) fails post-mutation and rolls back to
  the bootstrap release — `install_release` accepts the marker state, the
  activation removes the live overlay-canvas module for a clean downgrade,
  and `verify_frontends` logs `Overlay canvas module is absent in this
  rollback release` instead of failing the rollback re-activation.
- SC-3: a healthy deploy activates a release carrying overlay-canvas.js —
  the post-activation verification smoke-checks it through its
  env-overridable public URL, next to the existing module checks.
- SC-4: a live overlay-canvas file exists but is empty — the post-activation
  check fails closed with the same message style as the other module checks.

## Requirements

- R-1: `deploy/vps/deploy.sh` — `bootstrap_current_release` gains the
  overlay-canvas capture branch in the exact idiom of the sibling modular
  `.js` branches (live-sync.js, crossing-line.js, main.js, cameras.js,
  road/config.js, road/main.js, unavailable.js): when
  `$OVERLAY_CANVAS_TARGET` exists, `install -m 0644` it into the bootstrap
  release as `frontend/sea-speed/overlay-canvas.js`; otherwise `touch`
  `frontend/sea-speed/overlay-canvas.js.absent`. Placed after the
  road/main.js branch and before the unavailable.js branch, matching the
  existing branch ordering.
- R-2: `deploy/vps/deploy.sh` — `verify_frontends` gains the post-activation
  overlay-canvas check in the healthy path, presence-conditional exactly like
  the six #626 module checks from #629: an empty live file fails closed, a
  present file is smoke-checked through `verify_public_url "Overlay canvas
  module" "$OVERLAY_CANVAS_URL"`, an absent file is logged as absent in this
  rollback release. Placed after the road-main check and before the
  unavailable check; the Authentik-outage fallback branch is unchanged.
- R-3: `deploy/vps/deploy.sh` — env-overridable URL constant
  `OVERLAY_CANVAS_URL="${SEA_SPEED_OVERLAY_CANVAS_URL:-https://mostdef.ru/sea-speed/overlay-canvas.js}"`
  next to the other module URL constants (after `LIVE_SYNC_URL`, mirroring
  the `*_TARGET` ordering).
- R-4: `tests/test_vps_deploy_transaction.py` — the fixture env gains the
  `SEA_SPEED_OVERLAY_CANVAS_URL` override and two tests: a bootstrap-capture
  test (live tree without overlay-canvas.js and no current-release state →
  bootstrap release carries the `.absent` marker → the failed candidate
  deploy rolls back to the bootstrap release successfully, with the
  absent-module log and a rolled_back manifest) and a healthy-deploy smoke
  check for the overlay-canvas module, in the existing fixture idioms.
- R-5: forbidden surfaces stay byte-untouched: `api/**`, `frontend/**`,
  `worker/**`, `scripts/renderers/**` (notably
  `scripts/operations/nginx_sea_speed_auth.py`), `tests/test_589*`,
  `tests/test_618*`, edge-vhost tests,
  `tests/test_626_csp_no_inline_scripts.py`,
  `tests/test_auth_session_frontend_contract.py`,
  `tests/support/frontend_html.py`, `.github/workflows/**`,
  `scripts/ci/**`, `contracts/**`, `specs/629-*/**`.

## Acceptance criteria

- AC-001: the bootstrap capture of a live tree without overlay-canvas.js
  records `overlay-canvas.js.absent` in the captured release, and a
  subsequent install/activation of that bootstrap release succeeds — the
  deploy completes its rollback with a `rolled_back` manifest and the
  absent-module log instead of failing with `has no overlay-canvas module
  state`.
- AC-002: `verify_frontends` smoke-checks a present overlay-canvas module
  through the env-overridable `OVERLAY_CANVAS_URL`, fails closed on an empty
  live file, and logs the absent module in a rollback release; the
  Authentik-outage fallback branch is unchanged.
- AC-003: full battery green with exactly the two new transaction tests
  added; ruff, validate_sdd and `bash -n deploy/vps/deploy.sh` pass.

## Runtime feedback

- RF-001: production effect requires the VPS front deploy (deploy-vps.yml)
  after merge — out of scope for this repository change; the bootstrap
  capture branch and the smoke check run on the next deploy invocation on
  the VPS. Trees already carrying a `current-release` state file never
  re-enter the bootstrap path, so the fix matters for fresh-tree first
  deploys and their later rollback re-activations.
- RF-002: both additions are strictly additive capture/verification: the
  bootstrap branch only adds a file-or-marker record to the captured
  release, and the verify check never mutates release or live state; the
  marker-tolerant and presence-conditional shapes keep pre-existing
  rollback re-activation working.

## NFR assessment

- NFR-001 | Area: deploy robustness | Target: every bootstrap-captured release carries an explicit overlay-canvas module state so its re-activation cannot fail with `has no overlay-canvas module state` | Validation: tests/test_vps_deploy_transaction.py — bootstrap-capture test asserting the marker, the successful rollback re-activation and the rolled_back manifest; RED-authenticity recorded in plan.md | Evidence: observed RED failure line and green focused run recorded in plan.md | Status: PASS
- NFR-002 | Area: rollback verification quality | Target: post-activation verification covers overlay-canvas.js like the other frontend modules (empty fails closed, present smoke-checked, absent logged) without breaking the Authentik-outage fallback branch | Validation: transaction tests — healthy-deploy smoke check for the overlay-canvas module and the absent-module log in the bootstrap rollback scenario | Evidence: focused run recorded in plan.md | Status: PASS
- NFR-003 | Area: change discipline | Target: the fix lands as two idiomatic insertions plus fixture coverage, with every forbidden surface byte-untouched | Validation: git diff scope check against the forbidden-path list; ruff, validate_sdd and bash -n observed | Evidence: recorded in tasks.md Completion gate | Status: PASS
