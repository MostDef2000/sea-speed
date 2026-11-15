# Tasks: login popup replaces the full-page auth redirect

- Spec: specs/710-login-popup/spec.md

## Delivery tasks
- [x] Public helper: new `frontend/sea-speed/login-popup.js` (deploys to the public web root as `/login-popup.js`, mirroring `unavailable.js`) — IIFE exposing `window.SeaSpeedAuth = {openLogin, showOverlay, loginUrl}`; `loginUrl()` = `/outpost.goauthentik.io/start?rd=` + encoded target; `openLogin()` opens the 520×680 `sea-speed-login` popup and polls `/sea-speed/api/session` every 1500 ms (max 200 attempts), then reloads into `/sea-speed/` on a truthy `username`
- [x] Session-expiry overlay: `showOverlay()` idempotent (`#seaSpeedLoginOverlay` existence guard), role=dialog + aria-modal, `#seaSpeedLoginBtn` «Войти» wired via addEventListener (no inline handlers — CSP unchanged); `#loginBtn` auto-wired on DOMContentLoaded
- [x] Landing: `frontend/root/index.html` gains `<button id="loginBtn" type="button">Войти</button>` after the primary link + `<script src="/login-popup.js"></script>`
- [x] In-app retarget: the four app pages load `/login-popup.js` immediately before their own page script; the four `redirectForReauthentication()` bodies call `SeaSpeedAuth.showOverlay()` instead of `location.assign(...)`/`window.top.location.replace(...)`
- [x] Deploy contour: `deploy/vps/deploy.sh` mirrors every `unavailable.js` touchpoint for the helper (TARGET/URL vars, release_complete, required loop, install-to-release, bootstrap capture with `.absent`, module-state check, staging, promote, smoke); both exact-artifact vps lists carry `frontend/sea-speed/login-popup.js`
- [x] Tests: new `tests/test_login_popup.py` (`LoginPopupContract`, 9 tests — source pins + three node behavioural twins with fake timers); `tests/support/frontend_html.py` gained `WEB_ROOT_SCRIPTS` and a DOM-faithful `getElementById` stub; four oracles retargeted without weakening any assertion (`test_auth_session_frontend_contract.py`, `test_auth_logout_contract.py`, `test_vps_deploy_transaction.py`, `test_665_water_page_assets.py`)
- [x] RED proof: 9/9 login-popup tests failed before implementation
- [x] GREEN: `tests/test_login_popup.py` 9 passed; the four retargeted oracles 52 passed + 20 subtests
- [x] Full battery green: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` (documented runner) — Ran 1429, OK (skipped=2); no existing test weakened, skipped or mocked
- [x] Validators and lint: validate_repo (957 tracked files), validate_contracts, validate_quality_contracts, validate_workflow_policy, validate_token_preflight — all PASS; ruff PASS; `bash -n deploy/vps/deploy.sh` OK
- [x] Write the SDD trio `specs/710-login-popup/{spec,plan,tasks}.md` per the `scripts/ci/validate_sdd.py` rules (markers and record rows verified against the validator; the validator run itself executes in the PR gate)
- [ ] CI green on the #710 PR
- [ ] Merge the #710 PR to main
- [ ] VPS redeploy (lane-A) on the merged main SHA so the login popup, the landing button and the session-expiry overlay ship to production (orchestrator-owned authorized chain)

## Completion gate
- CI green on the #710 PR
- PR merged to main
- VPS redeploy executed in the authorized chain; the public landing shows the «Войти» button opening the authentik popup, a successful login returns the user into `/sea-speed/`, session loss inside the app shows the idempotent overlay with no navigation, and `/login-popup.js` is served from the public web root

## Requirements traceability
- AC-001 | Task: landing «Войти» button + popup to the outpost start URL carrying rd= | Evidence: tests/test_login_popup.py — test_landing_has_login_button_and_loads_helper + test_open_login_opens_popup_with_outpost_url (window.open exactly once with the outpost URL carrying rd=); RED before implementation (9/9 failed), GREEN after | Coverage: COVERED
- AC-002 | Task: poll-based completion — reload into /sea-speed/ after a successful session poll | Evidence: tests/test_login_popup.py::test_open_login_navigates_after_session_success (location.reload() under /sea-speed/ or location.href="/sea-speed/"; fake timers keep the twin deterministic) | Coverage: COVERED
- AC-003 | Task: in-app overlay on session loss instead of navigation | Evidence: tests/test_login_popup.py — test_app_pages_use_overlay_instead_of_redirect (all four redirectForReauthentication bodies call SeaSpeedAuth.showOverlay(), no location.assign/location.replace) + test_show_overlay_creates_single_overlay_with_login_button; retargeted executed twins tests/test_auth_session_frontend_contract.py + tests/test_auth_logout_contract.py green | Coverage: COVERED
- AC-004 | Task: idempotent overlay and CSP-safe wiring | Evidence: tests/test_login_popup.py::test_show_overlay_creates_single_overlay_with_login_button (showOverlay twice — exactly one overlay, one «Войти» button) + helper source pins (addEventListener-only, no inline handlers); tests/test_665_water_page_assets.py allows the web-root absolute /login-popup.js | Coverage: COVERED
- AC-005 | Task: deploy contour ships /login-popup.js at every lifecycle touchpoint; battery and validators green with no assertion weakened | Evidence: tests/test_login_popup.py — test_deploy_script_copies_login_popup + test_exact_artifact_lists_carry_login_popup; tests/test_vps_deploy_transaction.py (new file in the synthetic release + promotion/smoke/rollback/bootstrap enumerations); full battery Ran 1429 OK (skipped=2); validators PASS; ruff PASS | Coverage: COVERED

## Definition of Done
- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current
