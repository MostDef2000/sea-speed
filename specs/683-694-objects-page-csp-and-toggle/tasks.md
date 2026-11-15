# Tasks: extract objects-page inline scripts for the strict CSP and keep one crossing-toggle writer

- Spec: specs/683-694-objects-page-csp-and-toggle/spec.md

## Delivery tasks
- [x] Issue #683: move both inline `<script>` blocks of `frontend/sea-speed/objects/index.html` verbatim into new `frontend/sea-speed/objects/crossings.js` (crossings-layer IIFE, 56 lines) and `frontend/sea-speed/objects/registry.js` (registry script, 50 lines); reference them as external scripts in the original order (`crossings.js` at line 53 before `registry.js` at line 74); no CSP change (no hashes, no unsafe-inline)
- [x] Prove byte-identity of both extracted files against base `282fe49d` (byte-identical modulo leading/trailing whitespace); ordering safety holds — `crossings.js` reads `registryScopeKey` only inside `camFor()` at call time and `initCxLayer` defers to `DOMContentLoaded` while `readyState` is `"loading"`
- [x] Issue #694: remove the 21-line duplicate `cxOffBtn.onclick` block from `frontend/sea-speed/road/config.js`; keep the boot-status writes (`cxStatus.textContent` / `cxOffBtn.textContent`) and the init GET fetch; `frontend/sea-speed/road/main.js` untouched
- [x] Deploy contour: wire both new files through the full #626 module lifecycle in `deploy/vps/deploy.sh` (+53 lines) — `OBJECTS_CROSSINGS_TARGET` / `OBJECTS_REGISTRY_JS_TARGET` (JS suffix avoids the API-side `OBJECTS_REGISTRY_TARGET` collision), URL vars, `release_complete -f` checks, `download_release` required loop, install-to-`TARGET_RELEASE`, bootstrap capture with file-level `.absent` markers, `install_release` module-state fail-closed checks, conditional staging, `mv`-promote, `verify_frontends` smoke; extend the vps required lists in `scripts/quality/build_exact_artifacts.py` and `scripts/quality/validate_exact_artifacts.py`
- [x] Tests: extend `tests/test_626_csp_no_inline_scripts.py` (objects page in `HTML_PAGES`, both scripts in `NEW_EXTERNAL_SCRIPTS`); add `tests/test_694_single_toggle_writer.py` (exactly one `cxOffBtn.onclick` writer = `road/main.js`; `config.js` must not assign it and must keep the `cxStatus` boot write); retarget `tests/test_unified_registry.py` JS assertions from the HTML to the `registry_js`/`crossings_js` class attributes (markup assertions stay on the HTML); extend `tests/test_vps_deploy_transaction.py` (release_files/setUp/env/install_live/promotion/smoke/rollback-fail-closed/bootstrap-capture)
- [x] RED proof on base `282fe49d`: 7 failed / 5 passed across the two phase-A oracles (`test_626` + `test_694`)
- [x] GREEN: 7 passed + 26 subtests on the two oracles; `tests.test_vps_deploy_transaction` + `tests.test_unified_registry` — 34 tests OK
- [x] Full battery green: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` (documented runner) — Ran 1406, OK (skipped=2); no existing test weakened, skipped or mocked
- [x] Validators and lint: validate_repo (947 tracked files), validate_contracts (66 canonical, 9 entrypoints), validate_quality_contracts (7 contracts, 6 fixtures), validate_workflow_policy, validate_token_preflight — all PASS; ruff PASS; `bash -n deploy/vps/deploy.sh` OK
- [x] Browser probe under an enforcing CSP (`script-src 'self'`): objects page — zero CSP violations, both scripts executed, `#cxViewBtn` produced `?scope=water&view=crossings`; road page — two `media-src blob:` messages only (probe-CSP artifact; production CSP includes `media-src 'self' blob:`, `scripts/operations/nginx_sea_speed_auth.py:86`); screenshot `shared/wave1-683-objects-csp-probe.png`
- [x] Peer review by an independent reviewer (different model family): verdict REQUEST_CHANGES on two points, both resolved — (a) verbatim extraction unproven → byte-identity against base `282fe49d` proven; (b) env override name `SEA_SPEED_OBJECTS_REGISTRY_TARGET` read as the API module → renamed to `SEA_SPEED_OBJECTS_REGISTRY_JS_TARGET`, zero occurrences of the old name remain
- [x] Write the SDD trio `specs/683-694-objects-page-csp-and-toggle/{spec,plan,tasks}.md` and pass `python3 scripts/ci/validate_sdd.py`
- [ ] CI green on the 683/694 PR
- [ ] Merge the 683/694 PR to main
- [ ] VPS frontend redeploy (lane-A) on the merged main SHA so both external objects scripts and the single toggle writer ship to production (orchestrator-owned authorized chain)

## Completion gate
- Peer review of the 683/694 diff complete (both REQUEST_CHANGES points resolved)
- CI green on the 683/694 PR
- PR merged to main
- VPS frontend redeploy executed in the authorized chain; the objects registry page renders and operates under the production CSP (both external scripts served, crossings view toggle works), and the road page crossing toggle keeps exactly one writer

## Requirements traceability
- AC-001 | Task: verbatim extraction of both inline blocks into objects/crossings.js + objects/registry.js with preserved script order | Evidence: tests/test_626_csp_no_inline_scripts.py — objects page in HTML_PAGES, both scripts in NEW_EXTERNAL_SCRIPTS, zero inline script bodies, non-empty external files; byte-identity against base 282fe49d proven; RED on base 282fe49d (inline blocks present, files absent), GREEN after the change | Coverage: COVERED
- AC-002 | Task: remove the duplicate cxOffBtn.onclick writer from road/config.js + single-writer guard | Evidence: tests/test_694_single_toggle_writer.py — exactly one frontend file assigns cxOffBtn.onclick and it is frontend/sea-speed/road/main.js; config.js keeps the cxStatus.textContent boot write and its init GET; RED on base 282fe49d (two writers), GREEN after the fix | Coverage: COVERED
- AC-003 | Task: full #626 deploy lifecycle for both new files + exact-artifact vps lists | Evidence: tests/test_vps_deploy_transaction.py extended across release_files/setUp/env/install_live/promotion/smoke/rollback-fail-closed/bootstrap-capture + vps required lists in scripts/quality/build_exact_artifacts.py and validate_exact_artifacts.py; a release missing either file fails closed before any live mutation; bash -n deploy/vps/deploy.sh OK | Coverage: COVERED
- AC-004 | Task: full battery + validators + browser probe | Evidence: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` — Ran 1406, OK (skipped=2), no existing test weakened/skipped/mocked; validate_repo (947), validate_contracts (66 canonical, 9 entrypoints), validate_quality_contracts (7, 6 fixtures), validate_workflow_policy, validate_token_preflight all PASS; ruff PASS; browser probe under enforcing script-src 'self' CSP — zero violations on the objects page (shared/wave1-683-objects-csp-probe.png) | Coverage: COVERED

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
