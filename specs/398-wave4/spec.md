# Spec: #398 wave 4 — frontend cluster raw-source-text conversion (executed/structural)

- Issue: #398
- Specification: specs/398-wave4/spec.md
- Authorization: six-field Scope for #398 approved by the owner; this wave = the 8-file
  frontend cluster of that scope (tests-only + one recorded validator line), per the wave-4
  work order (base fe45e8b, the wave-3 merge).

## Product outcome

The frontend regression cluster (8 files) stops verifying page/workflow/blueprint/analytics
behavior by reading sources as raw text and starts verifying it by executing the real thing
(RB) or parsing it structurally (SS: `ast.parse`, `yaml.safe_load`). The four protected pages
(water, road, cameras, objects) boot their REAL inline scripts under the extended html shim
(`tests/support/frontend_html.py`) against programmable API responses, and scenarios drive the
recorded handlers — HLS media events, worker toggles, fallback refreshes, registry scope
controls — exactly like an operator would; raw `assertIn` markup pins become executed twins or
structured-shape assertions. Workflow contracts assert on `yaml.safe_load`-parsed structure
(comment-blind, so comment-only compliance stops passing); Authentik blueprints parse through a
local SafeLoader with `!KeyOf`/`!Find` constructors; the deploy ROI migration is extracted and
EXECUTED against tmp fixtures. Pins whose textual presence IS the contract (deploy-transaction
evidence literals, regex security bans, deliberate markup stubs) stay verbatim as SP with
recorded justification; prose SDD documents are NO-CHANGE (the text IS the artifact). Redundant
text pins retire only against recorded same-commit twins, so the battery is never weaker. A
two-direction demo (`tests/test_398_wave4_demo.py`) proves the conversion property on the real
water operator page.

## User scenarios

- A developer reformats the water page's HLS wiring lines or renames `connectStream`:
  the converted checks stay green (old text pins would have failed — false failure
  eliminated), except where marker text IS the policy (SP pins deliberately still fail).
- A developer breaks the wiring while leaving every historical marker verbatim (a stray second
  `attachMedia` binds the HLS player to the overlay image too): the executed twin fails (old
  text pin would have passed — false pass eliminated).
- A developer makes the deploy workflows "comply" by adding a comment mentioning the required
  policy step: the parsed-structure twin still fails (the old comment-blind text pin would
  have passed).
- A future wave touches frontend/** without behavior change: review attention goes to real
  diffs instead of markup-text churn.

## Scope

- tests/test_autonomous_execution_policy.py, tests/test_auth_logout_contract.py,
  tests/test_auth_session_frontend_contract.py, tests/test_roi_normalization.py,
  tests/test_analytics_profiles.py, tests/test_camera_preview_gallery.py,
  tests/test_line_crossing.py, tests/test_frontend_contract.py — converted per the plan.md
  mapping table (RB→exec, SS→structured parse, SP verbatim, redundant→retired with twins,
  NO-CHANGE with rationale).
- tests/support/frontend_html.py — extended additively (location fields + replace recording +
  `window.top` aliasing, programmable fetch responses with mid-scenario swaps, recorded
  listeners/timers/HLS/overlay-canvas calls, `ready_state`/`drain_timeouts`/`location_overrides`/
  `referrer` parameters, DOMString `value` accessor, `createElement`/`append`/`appendChild`,
  history/scrollTo/confirm/CSS.escape/FormData/rAF stubs); regression-checked against the
  wave-2 session+demo suites after each extension.
- tests/test_398_wave4_demo.py (new) — two-direction regression demonstration.
- specs/398-wave4/** — this trio.
- Recorded orchestrator exception: `scripts/ci/validate_sdd.py` receives `398-wave4` in the
  existing `"398"` GRANDFATHERED_PREFIX_COLLISIONS set (staged-wave precedent 396/397/520/537
  and the 398-wave1/wave2/wave3 entries) so this trio is admissible; delivery-orchestrator
  addition, documented in plan.md Correct-course and tasks.md ledger. ONE line; no other
  scripts/** surface is touched.
- NO production surface: api/**, worker/**, frontend/**, deploy/**, .github/**, nginx/**
  untouched (wave-1/wave-2/wave-3 test files also untouched, including
  tests/support/relay_shell.py).
- Out of scope (NO-CHANGE, rationale in the mapping table): tests/test_validate_sdd.py — it
  pins the validator itself, whose source text IS the artifact under test (SS by design);
  tests/test_vps_deploy_transaction.py — already converted in wave 2.
- Change classification: tests-only + 1 validator line = CONTROL_PLANE
  (contracts/runtime/RELEASE_READINESS_GATE.md) — authorized source lifecycle and PR/post-merge
  Quality only; runtime deployment NOT REQUIRED.

## Requirements

- R-1: every behavioral assertion carried by a raw text pin is replaced by an executed or
  structured twin per the plan.md mapping table; no assertion is lost without a recorded
  same-commit executed twin (redundancy ledger in tasks.md) or verbatim SP retention.
- R-2 (SP justification): STATIC_POLICY pins kept verbatim carry an in-code justification
  comment or a mapping-table rationale (deploy-transaction evidence literals; regex security
  bans; deliberate markup stubs; prose SDD documents as NO-CHANGE).
- R-3: tests/test_398_wave4_demo.py proves both directions on tmp copies of the real water
  page: (a) refactor tolerance — behavior-preserving reformat/rename passes the executed check
  while the retired text pins would fail; (b) dead-marker intolerance — markers verbatim with
  broken wiring FAILS the executed check where the retired pins pass.
- R-4 (tests-only): if any conversion requires a production change → STOP and report; none did.
- R-5: the suite stays deterministic in CI — the html shim is offline (fetch/Hls/timers are
  stubs; responses programmable; no network), tmp copies only (frontend/ never modified), and
  root-gated shell twins skip gracefully where user namespaces are unavailable (relay_shell
  discipline).
- R-6: full battery green with per-file deltas accounted (never weaker); validate_sdd and
  validate_repo green; changed files limited to the allowed set.

## Acceptance criteria

- AC-001: all 8 cluster files adjudicated in the plan.md mapping table (converted / SP-kept / retired-with-twin / NO-CHANGE) and every converted file's focused run is green, with the harness regression trio (wave-2 session+demo) green after each harness extension. → TEST-001
- AC-002: cluster delta vs baseline 126 passed / 18 subtests (base fe45e8b) equals the per-file deltas (auth_logout_contract +8, roi_normalization +1; six files converted in place at 0 count delta) plus demo +1 — the identity holds: 126 + 8 + 1 + 1 = 136 passed / 24 subtests — with the covering twin recorded in the tasks.md ledger for every retired assertion. → TEST-002
- AC-003: tests/test_398_wave4_demo.py passes with both explicit directions (refactor-tolerant AND dead-marker-intolerant), inverted-mutation run recorded in tasks.md. → TEST-003
- AC-004: full battery `pytest tests/ -q` green (observed 1201 passed / 2 skipped / 300 subtests in 75.94s; baseline 1191 / 2 / 294). → TEST-004
- AC-005: `python3 scripts/ci/validate_sdd.py` green for this trio (after the recorded grandfather line); `validate_repo.py` green. → TEST-004, TEST-005
- AC-006: `git status`/diff shows only tests/**, tests/support/frontend_html.py, specs/398-wave4/** plus the recorded orchestrator exception (one-line `398-wave4` grandfather entry in `scripts/ci/validate_sdd.py`, per Scope above). → TEST-005

## Runtime feedback

- RF-001: Operator actions expected: 0 — tests-only + one validator line (CONTROL_PLANE); no deploy and no production artifact changes. Runtime acceptance = exact-head CI green on the merge PR (the battery, including the executed page twins, runs in CI; node is a proven CI capability since wave A / PR #474; user-namespace-unavailable environments skip the root-gated shell twins exactly as before).
- RF-002: after this wave the battery reports 1201 passed / 2 skipped / 300 subtests; every count delta vs the wave baseline is recorded in the tasks.md battery-delta ledger (retired assertion → covering executed twin, same commit). Subtests grew 294→300 (executed per-page session/logout matrices) — evidence that conversion made coverage observable, not smaller.

## NFR assessment

- NFR-001 | Area: reliability | Target: converted suites are deterministic (offline shim: stubbed fetch/Hls/timers with programmable responses; tmp copies only; root-gated shell twins skip gracefully without user namespaces) | Validation: focused runs repeated across sessions and environments; demo isolates mutations in tmp with cleanup | Evidence: cluster 136 passed / 24 subtests in 22.79s; full battery 1201 / 2 / 300 | Status: PASS
- NFR-002 | Area: coverage | Target: zero coverage loss — every removed text assertion maps to an executed twin, a structured equivalent, a retained verbatim SP pin, or a recorded NO-CHANGE rationale | Validation: mapping table in plan.md; tasks.md battery-delta ledger | Evidence: ledger rows + focused run tails | Status: PASS
- NFR-003 | Area: performance | Target: cluster wall time stays bounded (22.79s for 136 tests incl. node-spawn executed page twins vs 0.87s text-only baseline; full battery 75.94s vs 48.79s wave-3) — executed coverage costs bounded node spawns per scenario | Validation: cluster and battery timing comparison vs baseline | Evidence: tests_run tails | Status: PASS
- NFR-004 | Area: maintainability | Target: ONE harness module extended (tests/support/frontend_html.py, additive, regression-checked); house conversion models only (html shim exec, worker_source AST helpers, relay_shell userns dispatch, yaml.safe_load) | Validation: reviewer check that no new framework/pattern was invented | Evidence: diff review | Status: PASS
