# Tasks: fix two ReferenceErrors in the road operator page script

- Spec: specs/679-680-road-main-js/spec.md

## Delivery tasks
- [x] Fix issue #679 in `frontend/sea-speed/road/main.js` `loadSpeedConfig()`: the status expression reads the declared payload variable — `d.enabled` → `f.enabled` and `Number(d.kmh_per_px_s)` → `Number(f.kmh_per_px_s)`; no rename of `f`, no other token touched
- [x] Fix issue #680 in `frontend/sea-speed/road/main.js` `cxOffBtn.onclick` else-branch: re-enable POST body `{enabled:true,line}` → `{enabled:true,line:crossingCfg.line}`; no other token touched
- [x] Add the behavioural oracle `tests/test_679_680_road_main_js.py` (stdlib Python + `subprocess.run(["node", "-e", …])`, Node 22): marker locate + brace-matched extraction of the real `loadSpeedConfig` and `cxOffBtn.onclick` sources, eval under Node with stubbed DOM/`jsonReq`/`postJson`, assertions on observed value/status/payload; module docstring states both bugs and RED on base 30773ae; missing node fails loudly, never skips
- [x] RED proof: the oracle fails on base 30773ae in a throwaway detached worktree (`/tmp/opencode/679-base`, 2 failed; diagnostics surface `ReferenceError: d is not defined` and `ReferenceError: line is not defined`); worktree removed, tree clean afterwards
- [x] GREEN: `python3 -m pytest tests/test_679_680_road_main_js.py -v` — 2 passed
- [x] Diff-shape proof: `git diff frontend/sea-speed/road/main.js` shows exactly the two identifier corrections (2 insertions, 2 deletions); `frontend/sea-speed/main.js`, `deploy/**`, `scripts/**`, `.github/**` and other tests untouched
- [x] Full battery green: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` (documented runner) — Ran 1403, OK (skipped=2); no existing test weakened, skipped or mocked
- [x] Write the SDD trio `specs/679-680-road-main-js/{spec,plan,tasks}.md` and pass `python3 scripts/ci/validate_sdd.py`
- [ ] Peer verification of the combined diff (independent second worker)
- [ ] CI green on the 679/680 PR
- [ ] Merge the 679/680 PR to main
- [ ] VPS frontend redeploy (lane-A) on the merged main SHA so the fix ships to production (orchestrator-owned authorized chain)

## Completion gate
- Peer verification of the 679/680 diff complete
- CI green on the 679/680 PR
- PR merged to main
- VPS frontend redeploy executed in the authorized chain; the road operator page shows the live Speed config state instead of the stuck "ошибка загрузки", and a crossing line can be re-enabled after being turned off

## Requirements traceability
- AC-001 | Task: d→f reads in loadSpeedConfig + behavioural oracle (enabled variant) | Evidence: tests/test_679_680_road_main_js.py test_679_load_speed_config_uses_declared_payload — input "12.500", status contains "включен", exit 0; RED on base 30773ae (status fallback "Speed config: ошибка загрузки", diagnostic ReferenceError: d is not defined), GREEN with the diff (2 passed) | Coverage: COVERED
- AC-002 | Task: same fix, disabled-state behaviour pinned | Evidence: same test, enabled:false variant — status contains "выключен"; RED on base 30773ae (fallback status), GREEN with the diff | Coverage: COVERED
- AC-003 | Task: line→line:crossingCfg.line in the cxOffBtn re-enable branch + behavioural oracle | Evidence: tests/test_679_680_road_main_js.py test_680_cx_off_reenable_posts_persisted_line — exactly one POST deep-equal {"enabled":true,"line":[{"x":10,"y":20},{"x":30,"y":40}]}; RED on base 30773ae (0 calls, status "ошибка переключения", diagnostic ReferenceError: line is not defined), GREEN with the diff | Coverage: COVERED
- AC-004 | Task: diff discipline + full battery | Evidence: git diff frontend/sea-speed/road/main.js (2 insertions, 2 deletions — the two identifier corrections only) + git status --porcelain (no stray files; water page, deploy/**, scripts/**, .github/** untouched) + full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` green (Ran 1403, OK, skipped=2) with the new oracle included | Coverage: COVERED

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
