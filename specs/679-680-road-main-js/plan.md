# Plan: fix two ReferenceErrors in the road operator page script

- Spec: specs/679-680-road-main-js/spec.md

## Architecture
Two one-token identifier corrections inside `frontend/sea-speed/road/main.js`, no structural change. (1) `loadSpeedConfig()` declares `const f=await jsonReq(SPEED_CONFIG_URL)` and reads `f.kmh_per_px_s` for the input value, but its status ternary still read the undeclared `d` — a partial rename of the water page's `loadSpeedConfig` (`frontend/sea-speed/main.js:38`, where the payload is legitimately named `d`). The status expression now reads `f.enabled` and `Number(f.kmh_per_px_s)`. (2) The `cxOffBtn.onclick` else-branch posted `{enabled:true,line}`, but `line` is a local of the neighbouring `cxSaveBtn.onclick` handler; the branch now posts `line:crossingCfg.line`, the persisted two-point line it just guard-checked. The oracle (`tests/test_679_680_road_main_js.py`) is behavioural: it extracts each real source block by marker locate + brace matching that skips string/template literals and comments, evals it under Node 22 (`subprocess.run(["node", "-e", …])`) with stubbed DOM elements and stubbed `jsonReq`/`postJson`, and asserts the observed value/status/payload; a best-effort diagnostic raw run with the swallowing catch stripped surfaces the underlying ReferenceError text on RED runs without ever affecting pass/fail.

## Decisions
- Fix the identifiers, do not restructure: both bugs are single-token scope errors; renaming the declared variable or unifying the two handlers would touch working code for zero behavioural gain and widen the diff. The minimal correction restores the intended semantics of the copy-pasted code.
- Fix both `d` reads in `loadSpeedConfig`, not only `d.enabled`: the template literal's `Number(d.kmh_per_px_s)` is the same undeclared identifier one token away; fixing only the ternary condition would still throw on the enabled path (the truthy branch evaluates the template) and the oracle's `включен` assertion would stay RED. The work order's behavioural test (status contains `включен`) is only satisfiable with both reads corrected.
- `line:crossingCfg.line` instead of hoisting a shared `line` variable: the guard immediately above already validates `crossingCfg.line`, the neighbouring handler's local must stay scoped to it, and reusing the persisted config keeps the re-enable payload identical in shape to the disable branch's `{enabled:false,line:crossingCfg.line||[]}`.
- Behavioural Node oracle instead of a source grep: the bugs are scope/identifier errors that a text assertion would happily "verify" while the runtime still threw; running the real extracted sources under Node with stubs proves the operator-visible behaviour (status text, posted body) and stays RED→GREEN honest. Stdlib Python + `subprocess` only; node is a battery prerequisite (CI installs node 22), and a missing node fails loudly rather than skipping.

## Affected contours
- VPS frontend: `frontend/sea-speed/road/main.js` (two token corrections)
- Tests: `tests/test_679_680_road_main_js.py` (new behavioural Node oracle)
- SDD: `specs/679-680-road-main-js/` (spec, plan, tasks)
- Explicitly unchanged: `frontend/sea-speed/main.js` (water page copy is correct), every other frontend file, `api/**`, `worker/**`, `deploy/**`, `scripts/**`, `.github/**`, all other tests.

## Validation
- Oracle: `cd sea-speed && python3 -m pytest tests/test_679_680_road_main_js.py -v` — 2 passed.
- RED authenticity: the oracle run on base 30773ae in a throwaway detached worktree (`/tmp/opencode/679-base`, removed after the proof) fails 2/2 — AC-001 status assertion (`'включен' not found in 'Speed config: ошибка загрузки'`, diagnostic `ReferenceError: d is not defined`) and AC-003 calls assertion (`0 != 1`, status `ошибка переключения`, diagnostic `ReferenceError: line is not defined`).
- Diff shape: `git diff frontend/sea-speed/road/main.js` — exactly two changed lines, each a single-token identifier correction; `git status --porcelain` shows only the JS file, the new test and the new specs directory.
- Full battery: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` (the repo's documented runner, `.github/workflows/quality-integration.yml`) — Ran 1403, OK (skipped=2), exit 0.
- `python3 scripts/ci/validate_sdd.py` green with the new trio.

## Runtime feedback
- Issue #679/#680 (2026-11-14): both defects verified live on base 30773ae by the RED oracle run — the load path always landed in the catch ("Speed config: ошибка загрузки") and the re-enable path never issued its POST ("ошибка переключения", zero calls).

## Risk profile
- Risk profile: NOT REQUIRED

## Test design
- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_679_680_road_main_js.py RoadMainJsReferenceErrors.test_679_load_speed_config_uses_declared_payload, enabled:true variant (input "12.500", status contains "включен", exit 0); RED on base 30773ae (fallback "Speed config: ошибка загрузки", diagnostic ReferenceError: d is not defined), GREEN after the fix
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: same test, enabled:false variant (status contains "выключен"); RED on base 30773ae (same swallowed ReferenceError → fallback status), GREEN after the fix
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_679_680_road_main_js.py RoadMainJsReferenceErrors.test_680_cx_off_reenable_posts_persisted_line (exactly one POST deep-equal {"enabled":true,"line":[{"x":10,"y":20},{"x":30,"y":40}]}); RED on base 30773ae (0 calls, status "ошибка переключения", diagnostic ReferenceError: line is not defined), GREEN after the fix
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: git diff of frontend/sea-speed/road/main.js (two token changes, nothing else) plus git status --porcelain (no stray files, forbidden paths untouched) and the full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` green with the new oracle included; no existing test modified

## Deployment transaction audit
- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged, no changes applied | Retry: N/A | Rollback: N/A | Evidence: Change Contract and SDD validators green on the 679/680 PR
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: VPS still serving the previous release; no frontend file replaced | Retry: N/A | Rollback: N/A | Evidence: changed-file scope is one frontend JS file plus the new test and specs; deploy/vps/deploy.sh untouched
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: the VPS deploy script installs each frontend file via a .next temp file and an atomic mv, so a failed install leaves the previous file in place | Retry: Re-dispatch the deploy workflow on the same SHA | Rollback: Revert the merge commit and redeploy the previous main SHA | Evidence: deploy/vps/deploy.sh install-then-mv activation block
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged | Retry: Re-run the suite | Rollback: N/A | Evidence: pytest tests/test_679_680_road_main_js.py (2 passed), RED proof on 30773ae (2 failed with both ReferenceErrors surfaced), full unittest battery (1403 OK, skipped=2), scripts/ci/validate_sdd.py
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: merge commit recorded in git | Retry: Re-merge | Rollback: Revert the merge commit | Evidence: merge commit SHA on main
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: JOURNAL entry pending | Retry: Re-record | Rollback: N/A | Evidence: JOURNAL.md entry
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: acceptance probe output missing | Retry: Re-run the probe | Rollback: N/A | Evidence: post-deploy authenticated fetch of the served road page script plus a browser probe of the road operator page (Speed config status reflects the API state instead of the stuck "ошибка загрузки"; crossing re-enable posts once)
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: N/A — rollback is the recovery path itself | Retry: N/A | Rollback: git revert of the merge commit followed by a redeploy of the previous main SHA | Evidence: previous main SHA 30773aec7a3086c0f0d9cbfbb31e3f8cf3f0b616

## Correct-course check
- Trigger: NONE
- Issue impact: none — the work order matches issues #679/#680 as opened (two undeclared-identifier ReferenceErrors in frontend/sea-speed/road/main.js, one-token fixes)
- Specification impact: none — the spec matches the locked design (identifier fixes only, behavioural Node oracle, water page untouched)
- Plan impact: none — no deviation discovered during implementation
- Tasks impact: none — delivery tasks executed as written
- Authorization impact: NONE (bounded worker work order from the delivery orchestrator on branch agent/679-680-road-main-js; the orchestrator owns the Git lifecycle)
- Follow-up: none in this change; the VPS frontend redeploy that ships the fix to production happens in the authorized delivery chain after merge (lane-A, orchestrator-owned)

## Test evidence summary
- RED (base 30773ae, detached worktree /tmp/opencode/679-base, removed after the proof): `2 failed in 0.31s` — AC-001/AC-002 status fallback "Speed config: ошибка загрузки" with diagnostic `ReferenceError: d is not defined`; AC-003 `0 != 1` calls, status "ошибка переключения" with diagnostic `ReferenceError: line is not defined`.
- GREEN (with diff): `2 passed in 0.43s` (`python3 -m pytest tests/test_679_680_road_main_js.py -v`).
- Full battery: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` — Ran 1403 tests, OK (skipped=2), exit 0.
- Diff shape: 1 file changed, 2 insertions(+), 2 deletions(-) — the two identifier corrections only.
