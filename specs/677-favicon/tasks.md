# Tasks: favicon for all six Sea Speed pages

- Spec: specs/677-favicon/spec.md

## Delivery tasks
- [x] Read the pinned tag from `shared/sea-speed-favicon/favicon-datauri.txt` (449 bytes incl. newline) and insert it verbatim as one new line inside `<head>`, immediately after `<title>`, indent-matched, in `frontend/sea-speed/index.html`, `frontend/sea-speed/road/index.html`, `frontend/sea-speed/cameras/index.html`, `frontend/sea-speed/objects/index.html`, `frontend/sea-speed/unavailable.html`, `frontend/root/index.html` (script-inserted, never hand-retyped)
- [x] Add the stdlib oracle `tests/test_677_favicon.py` (house style of test_665/test_626): AC-001 presence/type/scheme/head-placement + six-href byte equality; AC-002 minidom XML validity + ≤ 600 decoded bytes + brand colours `#041725`/`#81d5e0`; module docstring states RED on base
- [x] RED proof: oracle fails on base cefd446 in a throwaway detached worktree (`9 failed, 1 passed`; every page "found 0" favicon links); worktree removed, tree clean afterwards
- [x] Byte-equality proof: per-page extracted href and full inserted line byte-equal to the shared source line — OK ×6, all hrefs identical
- [x] XML-validity proof: decoded URI parses to root `<svg>`, 297 bytes (cap 600), brand colours present
- [x] Diff-shape proof: `git diff --stat` = 6 files changed, 6 insertions(+), 0 deletions; full diff shows exactly one added line per page; `deploy/vps/deploy.sh` and all forbidden paths untouched
- [x] GREEN: `python3 -m pytest tests/test_677_favicon.py -v` — 4 passed, 6 subtests passed
- [x] Full battery green: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` (documented runner) — no existing test weakened, skipped or mocked
- [x] Write the SDD trio `specs/677-favicon/{spec,plan,tasks}.md` and pass `python3 scripts/ci/validate_sdd.py`
- [ ] Peer verification of the combined diff (independent second worker)
- [ ] CI green on the 677 PR
- [ ] Merge the 677 PR to main
- [ ] VPS frontend redeploy (lane-A) on the merged main SHA so the icon ships to production (orchestrator-owned authorized chain)

## Completion gate
- Peer verification of the 677 diff complete
- CI green on the 677 PR
- PR merged to main
- VPS frontend redeploy executed in the authorized chain; icon visible on the live pages (browser tab shows the Sea Speed mark on all six URLs)

## Requirements traceability
- AC-001 | Task: six-page tag insertion + stdlib oracle | Evidence: tests/test_677_favicon.py test_every_page_carries_exactly_one_svg_data_uri_favicon + test_all_six_hrefs_are_byte_identical; RED on base cefd446 (9 failed, 1 passed — every page "found 0"), GREEN with the diff (4 passed, 6 subtests passed); byte-equality proof OK ×6 against shared/sea-speed-favicon/favicon-datauri.txt | Coverage: COVERED
- AC-002 | Task: oracle decode/validity/colour pins | Evidence: tests/test_677_favicon.py test_data_uri_decodes_to_valid_compact_svg (minidom root `<svg>`, 297 ≤ 600 bytes) + test_decoded_svg_keeps_brand_colours (#041725, #81d5e0); standalone decode proof prints XML VALID | Coverage: COVERED
- AC-003 | Task: one-line-per-page diff discipline | Evidence: git diff --stat (6 files, 6 insertions, 0 deletions) + full-diff review; git status shows no stray repo files; deploy/vps/deploy.sh untouched | Coverage: COVERED
- AC-004 | Task: full battery | Evidence: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` green with the new oracle included; no existing test modified | Coverage: COVERED

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
