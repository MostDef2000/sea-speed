# Tasks — Issue #626 CSP-ready frontend: inline scripts → external files

- Issue: #626
- Specification: specs/626-csp-external-scripts/spec.md

## Delivery tasks

- T-1: frontend/sea-speed/index.html — extract inline block :93-124 to
  crossing-line.js (src tag at the same position, before hls.js CDN) and
  inline block :127-216 to main.js (src tag at the same position, after
  overlay-canvas.js, before live-sync.js); verbatim move. DONE — roundtrip
  reconstruction (blocks re-inserted into the new HTML) reproduces the
  original file byte-for-byte; tags at :93/:107, CDN :105, overlay :106,
  live-sync :108.
- T-2: frontend/sea-speed/cameras/index.html — extract inline block :101+
  to cameras/cameras.js (src tag at the same position); verbatim move.
  DONE — roundtrip EXACT; tag at :101 after CDN :100.
- T-3: frontend/sea-speed/road/index.html — extract inline cfg block :62-72
  to road/config.js and inline main block :76+ to road/main.js (src tags at
  the same positions); verbatim move. DONE — roundtrip EXACT once the main
  block's trailing blank line (orig :160) is restored (it collapses into the
  file-terminating newline, repo convention per live-sync.js); tags at :62/:69.
- T-4: frontend/sea-speed/unavailable.html — onclick attribute →
  id="retry-button" + unavailable.js (addEventListener), script before
  </body>. DONE — exact expected shape; script tag at :21 before </body>.
- T-5: deploy/vps/deploy.sh — add crossing-line.js, main.js,
  cameras/cameras.js, road/config.js, road/main.js, unavailable.js to the
  front copy list. DONE — full lifecycle wiring: 6 env-overridable target
  vars, release_complete() `-f` pins, download_release required list, release
  staging installs, bootstrap_current_release entries (with .absent markers),
  install_release `.next` staging + mv/rm activation; unavailable.js targets
  the web root (/var/www/mostdef.ru/unavailable.js, page served from root).
  Transactional pins restored per orchestrator decision after the
  fixture-break diagnosis (see T-9).
- T-6: tests/test_626_csp_no_inline_scripts.py — guard oracle (no inline
  scripts / no on* attributes in the 4 HTML files; 6 new .js exist
  non-empty; deploy.sh references each); RED on base 8f409d2 verified,
  byte-identical through the fix. DONE — sha256
  09ba135058843b6236a57d178ee54dad9871cfe17cbc0b084009c5a01b6f2ef9 unchanged
  from RED through GREEN.
- T-7: specs/626-csp-external-scripts/ trio (this spec/plan/tasks) —
  evidence fields filled with observed runs. DONE (this update).
- T-8: tests/support/frontend_html.py — harness adaptation: when a page has
  no inline <script> blocks left, run_inline_scripts() executes the page's
  connected LOCAL external .js bodies in document order
  (external_local_scripts: relative src= resolved source-dir-first, real
  page dir fallback via page_key; CDN/absolute paths excluded; fail-closed
  on missing files); page_live_source() helper exposes the same surface for
  structural pins. Same return contract; no assertion weakened. DONE.
- T-9: tests/test_vps_deploy_transaction.py — fixture-only update per the
  #396 convention: write_release() carries the 6 new .js (release_complete
  requires them like the real tree), setUp gains the 6 live Path attributes
  and the 6 SEA_SPEED_*_TARGET env overrides; zero assertion/test-logic
  changes. DONE — `Ran 18 tests ... OK`.
- T-10: seven test location-move updates (scan/mutation surfaces only;
  assertions byte-identical in all seven): test_line_crossing
  (CrossingPanelDomGuardTests reads road/config.js), test_frontend_contract
  (StreamRetryLadder scans HTML + external_local_scripts), test_398_wave2_demo
  (mutation surface → road/main.js written next to tmp copies; pins scan
  HTML + executed .js), test_398_wave4_demo (same via WATER_MAIN_JS),
  test_water_live_sync_guard (setUpClass source = page_live_source),
  test_api_contract (freshness-aware counters scan page_live_source),
  test_water_passage (passage lifecycle scan page_live_source). DONE.

## Battery identity

Baseline at base 8f409d2 without the new file: `Ran 1417 tests in 180.182s`
→ `OK (skipped=2)`. Delta: +4 test methods in
tests/test_626_csp_no_inline_scripts.py — expected 1421. OBSERVED after the
fix: `Ran 1421 tests in 159.716s` → `OK (skipped=2)`.

## Completion gate

- Focused `python3 -W error::ResourceWarning -m unittest tests.test_626_csp_no_inline_scripts -v`: OBSERVED — `Ran 4 tests in 0.001s / OK` (test_deploy_script_copies_every_external_script, test_every_script_tag_carries_src, test_external_script_files_exist_and_are_non_empty, test_no_on_attribute_event_handlers).
- RED differential (guard test written and run on base 8f409d2 before extraction): OBSERVED — `FAILED (failures=17)` across the 4 methods; test file sha256 09ba135058843b6236a57d178ee54dad9871cfe17cbc0b084009c5a01b6f2ef9 at RED and unchanged after the fix.
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED — `Ran 1421 tests in 159.716s / OK (skipped=2)` (baseline 1417 OK skipped=2; delta exactly +4).
- ruff (CI config, changed files): OBSERVED — `All checks passed!` on the 10 changed .py files (guard test, frontend_html.py, test_vps_deploy_transaction.py, test_line_crossing.py, test_frontend_contract.py, test_398_wave2_demo.py, test_398_wave4_demo.py, test_water_live_sync_guard.py, test_api_contract.py, test_water_passage.py).
- `python3 scripts/ci/validate_sdd.py`: OBSERVED — `Sea Speed SDD validation passed`.
- Deploy transaction (fixtures updated per #396 convention): OBSERVED — `Ran 18 tests in 5.076s / OK`.

## Requirements traceability

- AC-001 | Task: T-1+T-2+T-3+T-4+T-6 | Evidence: guard test per-file assertions — every script tag carries src, no on* attributes (RED on base: inline blocks present) | Coverage: COVERED
- AC-002 | Task: T-1+T-2+T-3+T-4+T-6 | Evidence: verbatim-move diff inspection + guard test file existence/non-emptiness; connection order preserved by same-position src tags | Coverage: COVERED
- AC-003 | Task: T-5+T-6 | Evidence: guard test asserting deploy.sh references each of the six new .js files (RED on base: copy list lacks them) | Coverage: COVERED
- AC-004 | Task: T-6 | Evidence: RED differential on base 8f409d2 (`FAILED (failures=17)`, 4 tests) → GREEN after (`Ran 4 tests / OK`); test file byte-identical through the fix, sha256 09ba135058843b6236a57d178ee54dad9871cfe17cbc0b084009c5a01b6f2ef9 | Coverage: COVERED
- AC-005 | Task: T-1+T-2+T-3+T-4+T-5+T-6 | Evidence: full battery green (`Ran 1421 tests / OK (skipped=2)`); `git diff --stat` empty on tests/test_589_security_headers_renderer.py, tests/test_618_basic_auth_hsts.py, tests/test_sea_speed_edge_vhost_renderer.py, scripts/operations/nginx_sea_speed_auth.py | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (4 HTML + 6 new .js + deploy.sh + guard test + harness + transaction fixtures + 7 location-move test updates + this trio)
- [x] Required tests and evidence complete (RED differential + battery + ruff + validate_sdd observed)
- [ ] Required CI green — pending exact-head CI on the merge PR — auto-synced on merge to main
- [ ] Exact-green-head merge complete — pending squash merge to main — auto-synced on merge to main
- [ ] Deployment state resolved (VPS front deploy via deploy-vps.yml on the merged main SHA — authorized chain)
- [ ] Runtime acceptance resolved (acceptance probes + edge CSP flip + owner browser acceptance)
- [ ] Deferred work recorded (edge CSP enforcement flip — lane B, own gates)
- [ ] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
