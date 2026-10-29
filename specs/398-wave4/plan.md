# Plan — Issue #398 wave 4

- Issue: #398
- Specification: specs/398-wave4/spec.md

## Architecture

Follow the wave-1/2/3 house model: RB (execute the real thing) > SS (structured parse:
`ast.parse` / `yaml.safe_load`) > SP (STATIC_POLICY pins kept verbatim with justification) >
NO-CHANGE (recorded rationale) > redundant retirement (only with a recorded same-commit twin).
The wave-4 surface is the browser page layer: the four protected pages boot their REAL inline
scripts under the extended html shim (`tests/support/frontend_html.py`) — pages boot against
programmable API responses (`__responses`/`__setResponse`, swappable mid-scenario), timers
record-but-never-fire (with a `drain_timeouts` boot parameter for boot-batch timers), listeners
and HLS/overlay-canvas calls are recorded, and per-page location defaults (+`location_overrides`,
`referrer`, `ready_state`) model the real redirect semantics. Python sources parse via the
generic `tests/support/worker_source.py` AST helpers; deploy workflows and Authentik blueprints
parse via `yaml.safe_load` (local SafeLoader subclass for `!KeyOf`/`!Find`); the logout worker
operation dispatches through `tests/support/relay_shell.py` (user namespace, stubbed
docker/hostname PATH — import only, file untouched); the deploy ROI migration is extracted and
executed against tmp fixtures. CSS and markup have no AST — layout/markup pins stay source
scans (SS) or retire against executed DOM twins. No new frameworks or patterns.

## Decisions

- **Executed twins over page text**: assertions read RECORDED behavior (fetch URLs/bodies,
  HLS attach/loadSource, POST payloads, overlay state, redirect calls), not page text — a
  reformatted page passes, a rewired page fails.
- **Per-page redirect semantics are real**: road redirects via `location.assign`; water/
  cameras/objects via `window.top.location.replace(pathname+search+hash)` — the harness records
  replaces and aliases `window.top = window` (wave-2 harness only exercised the road path).
- **Timers record-but-never-fire by default**; scenarios drain recorded timeouts explicitly.
  `drain_timeouts=True` fires the boot-batch timeouts (microtask-ordered before the scenario) —
  required because the road page's `preview/start` POST fires from `setTimeout(0)` at boot.
- **Bodyless `ok:false` responses throw**: the pages' `api()` does a JSON parse, so a bodyless
  `{ok:false}` fixture makes the page throw TypeError — response fixtures always supply a json
  body, at boot too (the road fallback page needs an EVENTS response or `Promise.all` rejects
  before render).
- **Element `.value` is a Web IDL DOMString accessor** (get/set coerce to String, null→"") —
  the objects page writes a numeric speed into `editSpeed.value` and calls `.trim()`; a plain
  string stub threw.
- **Workflow assertions run on PARSED structure** (`yaml.safe_load`, comment-blind): trigger
  wiring, job `if` conditions, step order/gating/env chains and run-text literals come from
  parsed steps, so comment-only compliance fails. The deploy workflows' real source-protection
  checks live in the `verify-exact-release` composite action — the twin parses that action too
  (verify_source_protection step BEFORE evaluate_production_policy, `--require-allow`
  conditional, delegation env), which is STRONGER than the text pins it replaces.
- **Blueprints parse with a local `BlueprintLoader(yaml.SafeLoader)`** (`!KeyOf`→tagged scalar,
  `!Find`→deep sequence) so Authentik tags load without the runtime; assertions pin the tagged
  structures (flow slug/designation, stage order 10→20, provider mode/invalidation_flow).
- **AST via worker_source helpers**: `contains_expr` is EXACT subtree equality — multi-key dict
  snippets use dict-key walks instead; entrypoint/child/API modules parse directly or via
  `worker_source(paths=...)`.
- **SP keeps**: deploy-transaction evidence literals (relay/VPS shell pins), regex security
  bans (protected road source), the deliberate road `crossingCard` script stub (e793332 — the
  real road handlers live in the main script and are proven executed), markup order pins.
- **NO-CHANGE**: prose SDD documents (SPEC/PLAN/TASKS/QUICKSTART) — the text IS the artifact;
  live-sync/overlay module delegation pins — covered by wave-1 executed tests (referenced, not
  duplicated); session watchdog/storage pins — executed same-wave in
  test_auth_session_frontend_contract.py.

## Site-mapping table (old → replacement)

| File | Retired pin (group) | Kind | Twin / where it lives |
|------|---------------------|------|-----------------------|
| test_autonomous_execution_policy.py | deploy-runtime-autonomous router text pins (workflow_run filter, job-if event conditions, environment, step order, policy env var, no issue_comment trigger) | SS | `yaml.safe_load` parsed-structure asserts in `test_autonomous_router_uses_current_tip_quality_trusted_environment_and_source_protection` (same file) |
| test_autonomous_execution_policy.py | sync-merged-tasks text pins (tasks.md glob pathspec, no `git add -A`, sync script invocations, commit/merge subject, job-if event/head filters) | SS | parsed-structure asserts in `test_sync_merged_tasks_bot_stages_only_its_tasks_md_pathspec` |
| test_autonomous_execution_policy.py | deploy-vps/deploy-ubuntu-worker text pins (policy re-eval, source protection) — old text passed via COMMENTS only; real checks live in `.github/actions/verify-exact-release/action.yml` | SS | parsed workflow asserts `./actions/verify-exact-release` usage with `require_allow: 'true'` + composite-action structure (verify_source_protection before evaluate_production_policy, `--require-allow` conditional, delegation env) in `test_protected_deploy_workflows_re_evaluate_policy_and_source_protection` |
| test_autonomous_execution_policy.py | ubuntu zero-touch connector text pins | SS | parsed-structure asserts in `test_ubuntu_workflow_uses_zero_touch_connector` |
| test_autonomous_execution_policy.py | evaluator source-text pins (repository text as authority input) | SS | AST constant/identifier scan via worker_source helpers in `test_repository_text_cannot_become_authority_input`; executed evaluator cases unchanged (RB kept) |
| test_auth_logout_contract.py | blueprint YAML text pins (logout-v1 flow/stages/bindings/provider; rollback blueprint) | SS | `yaml.safe_load` with local `BlueprintLoader` (`!KeyOf`/`!Find`) in `AuthLogoutBlueprintTests` (3 tests) |
| test_auth_logout_contract.py | frontend logout/session text pins (sign_out href, watchdog re-fetch, storage absence, identity-loss redirect) | RB | executed water/cameras/objects page boots via frontend_html in `FrontendLogoutExecutedTests` (3 subtests) |
| test_auth_logout_contract.py | worker-operation text pins (usage/unknown/sha-gate/apply/idempotent/rollback/mode-drift rc61 pre-mutation + rc62 POST-apply PROVIDER_MODE_DRIFT_/verify-fail/secret-ban evidence literals) | RB | executed dispatch via relay_shell userns + stubbed docker/hostname PATH in `WorkerLogoutOperationExecutedTests` (10 new tests; the rc62 twin runs the apply happy path, then the post-apply verify reads a drifted mode from the stub's mode state file — rc 62 + stderr literal, mutation proven by the recorded docker cp); `bash -n` kept (SS) |
| test_auth_session_frontend_contract.py | all-pages session text pins (same-origin session API, watchdog re-fetch, credentials, identity population, storage typeof) | RB | executed 4-page `SESSION_SCENARIO` boots in `test_all_protected_frontends_use_same_origin_session_api` (subtests per page; redirect assert accepts road assign OR water/cameras/objects replace) |
| test_auth_session_frontend_contract.py | sign_out + project-home anchor text pins | SS | parsed-attribute regex twins (order-independent) in `test_logout_and_lighthouse_contract_is_preserved` |
| test_auth_session_frontend_contract.py | protected media path text pin | RB | executed water HLS twin in `test_operator_keeps_protected_camera_media_path` (drain → attachMedia(waterMainVideo) → MEDIA_ATTACHED → loadSource `/sea-speed/media/cam1/index.m3u8`; `window.hls === window.waterHls`) |
| test_auth_session_frontend_contract.py | road watchdog semantics text pin | RB | executed identity-loss twin in `test_road_session_watchdog_matches_protected_operator_semantics` (probe search/hash + failed session → replace(pathname+?probe=1+#frag)) |
| test_roi_normalization.py | frontend normalized-ROI text pins (polygon_norm / reference_width 1920 literals in page sources) | RB | executed water page (`saveRoi()` POST body parsed from recorded fetch; legacy `loadRoi` normalization) + road page (`roiSaveBtn.onclick` POST; `loadRoiConfig` legacy via sourceDims) in `test_water_page_saves_and_loads_normalized_roi` / `test_road_page_saves_and_loads_normalized_roi` |
| test_roi_normalization.py | deploy.sh migration presence text pin | RB | extracted `log()` + `migrate_legacy_roi_to_normalized` executed against tmp sqlite fixtures (ROI_MIGRATED total=2; polygon_norm outputs; already-normalized skipped) in `test_deploy_migration_normalizes_legacy_roi_state` |
| test_roi_normalization.py | API/worker helper executed tests | RB kept | 3 tests verbatim (unchanged) |
| test_analytics_profiles.py | worker profile-boundary text pins | SS | AST via `worker_source(paths=...)` (normalize_model_class / analytics_profile / object_type / model_class references) in `test_worker_and_ai_child_share_profile_boundary`, `test_worker_separates_water_continuous_detection_from_road_motion_policy` |
| test_analytics_profiles.py | entrypoint/child `--analytics-profile` wiring text pins | SS | direct `ast.parse` (`--analytics-profile` constant, `profile=get_profile` assign, `**semantic` keyword None, no `"yolo11s.pt"` constant) in `test_profile_defaults_are_exact` etc. |
| test_analytics_profiles.py | API route text pins | SS | ast walk of api/app modules (decorator path constants) in `test_api_is_additive_and_camera_isolated` |
| test_analytics_profiles.py | configure/prepare-yolo/build/validate script text pins | SS | AST string constants in `test_configure_profiles_writes_private_road_m2m_urls_and_mode_600`, `test_model_preparation_is_digest_bound_cuda_fail_closed`, `test_exact_artifacts_include_profiles_and_road_but_not_model_binaries` |
| test_analytics_profiles.py | frontend road navigation/control text pins | RB | executed road boot (recorded fetch URLs) + DOM scan in `test_frontends_have_synchronized_road_navigation_and_bounded_road_control` |
| test_analytics_profiles.py | regex security bans (protected road source) | SP kept | `test_runtime_assets_do_not_embed_protected_road_source` verbatim — the ban's textual presence IS the contract |
| test_camera_preview_gallery.py | API source text pins (routes, commit/get snapshot slices, public-state slices, validate source, Popen args, no shell=True, mkdir mode) | SS | `ast.parse` once at import + function slices by stable def name on api/app/camera_preview.py + main.py (approach recorded in the module docstring) |
| test_camera_preview_gallery.py | operator/cameras page text pins (runtime catalog, no-autostart, sequential batch, playback-progress wait, error isolation, snapshot storage) | RB | executed cameras page boot + end-to-end driven batch preview flow via frontend_html in `test_gallery_*` twins |
| test_camera_preview_gallery.py | relay/VPS deploy shell text pins (evidence literals, inventory protection, rollback/smoke lines) | SP kept | `test_ubuntu_preview_relay_*`, `test_vps_deploy_installs_*` verbatim — deploy-transaction evidence literals ARE the contract |
| test_camera_preview_gallery.py | SPEC/PLAN/TASKS/QUICKSTART prose pins (#112/#115, media paths, one-active-preview, sequential, Authentik) | NO-CHANGE | `test_sdd_links_*` — prose SDD documents are themselves the artifact under test (in-code comment at the test) |
| test_line_crossing.py | cam1 legacy-kind fallback text pin | SS | AST `contains_expr` on worker analytics.py in `Cam1LegacyKindFallbackTests` |
| test_line_crossing.py | VLZ summary text pins (signature defaults, vlz_days keys, timezone) | SS | AST signature-defaults tail-alignment + dict-key walk + VLZ_TIMEZONE dump compare in `OverlayLayoutTests`/summary twins |
| test_line_crossing.py | crossing-panel delete/toggle text pins (water+road markup handler wiring) | RB | executed on BOTH pages (page-agnostic scenarios derive the API prefix from the recorded boot GET; handlers driven via `__record.elements.cxOffBtn/cxUndoBtn.onclick`; responses swapped mid-scenario) |
| test_line_crossing.py | DOM-guard text pin (init deferred until DOMContentLoaded) | RB + SS | executed water boot with `ready_state="loading"` (no crossing-line GET until the recorded document DCL fires); road `crossingCard` script block is a DELIBERATE STUB (e793332) — SS keep, real road handlers proven by the executed toggle/delete twins |
| test_line_crossing.py | objects speed-card + scope text pins | RB | executed `renderObjects` with speed_kmh response; `?scope=road` via `location_overrides` (registryScopeKey script-scope global; fetch carries camera_id=road1&domain=road) |
| test_line_crossing.py | markup order pins (cxViewBtn / crossingsLayer / filter-actions) | SS kept | markup has no AST; element order IS the layout contract |
| test_line_crossing.py | detector/API executed tests | RB kept | CrossingDetectionTests / ApiCrossingTests / url+allowlist twins verbatim |
| test_frontend_contract.py | water HLS wiring text pins (single player, main-video attach, window.hls/waterHls publish, protected loadSource, media-event listeners, watchdog/retry rungs, stream toggle) | RB | executed water boot in `WaterStreamContractTests` (drain → 1 Hls attached to [waterMainVideo] only; MEDIA_ATTACHED → loadSource; waiting→2500 watchdog→1000 retry; toggle disconnect/reconnect) |
| test_frontend_contract.py | stream retry-ladder literal pins (STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000] on the water AND road pages) | SS | comment-stripped source scan in `StreamRetryLadderStructuralTests` (both pages must carry the full ladder literal as live code; the executed HLS twins prove the first 1000 ms rung — the full 8 s ladder has no cheap executable surface under the record-but-never-fire timers) |
| test_frontend_contract.py | water worker lifecycle text pins | RB | executed in `test_water_worker_lifecycle_only_controls_ai_overlay` (boot {ok,active}→setWorkerActive(true)+online; toggle→POST stop/start + log + overlay state; HLS instance untouched, no disconnect log) |
| test_frontend_contract.py | water fallback-overlay text pins (last_overlay_url, advancing gate, dedup) | RB | executed in `test_water_overlay_snapshot_is_bounded_fallback_only` (overlayImg.src set only while NOT advancing; same-url refresh deduped; reconnect clears the guard) |
| test_frontend_contract.py | water crossings/passages card text pins | RB | executed in `test_water_crossings_and_recent_passages_use_existing_sources` (summary→KPIs 2/1/3 + rows; passages→event cards; no-status→tracking) |
| test_frontend_contract.py | road HLS/recovery text pins | RB | executed in `RoadStreamContractTests` (preview/start → 1 Hls on roadMainVideo; MANIFEST_PARSED watchdog; mediaError→3500 recovery; networkError→reconnect; toggle→stop+destroy+window.hls null) |
| test_frontend_contract.py | road worker scoping text pins | RB | executed in `test_road_worker_control_is_road_scoped_and_media_independent` + `test_road_worker_control_rejects_foreign_target` (road-scoped POSTs only; foreign target refused; no unscoped /worker/control URLs) |
| test_frontend_contract.py | road fallback-overlay text pins | RB | executed in `test_road_overlay_snapshot_is_bounded_fallback_only` (rev-buster snap URL; dedup; advancing gate; reconnect re-arms dedup) |
| test_frontend_contract.py | road stats/events card text pins | RB | executed in `test_road_crossings_and_recent_events_are_independent_cards` |
| test_frontend_contract.py | objects registry scope text pins (?scope, referrer inference, domain filter, URL sync, same-origin writes) | RB | executed in `ObjectsRegistryExecutedTests` (3 tests: operator PATCH/DELETE writes; ?scope=road; same-origin road referrer) |
| test_frontend_contract.py | overlay worker-inactive gate text pin | RB | executed via frontend_node `overlay_render_calls` (setWorkerActive(false)+accept+render → strokeRect stays 1, clearRect≥2) in `test_overlay_render_stops_while_worker_is_inactive` |
| test_frontend_contract.py | layout/markup structural pins (data-layout markers, header order, control-id counts, grid-template-areas, @media breakpoints, viewport-fit, id uniqueness, nav reciprocity, rtsp negative, absent controls, root href) | SS kept | `WaterStructuralTests` / `RoadStructuralTests` / `CrossPageStructuralTests` — CSS/markup have no AST; the markers ARE the layout contract |
| test_frontend_contract.py | live-sync/overlay module delegation pins + include tags | NO-CHANGE | covered by wave-1 executed tests (test_live_overlay_sync, test_road_overlay_sync, test_water_live_sync_guard — protected byte-identical); referenced in the module docstring, not duplicated |
| test_frontend_contract.py | letterbox `(r.height-ch)/2` coord pin | NO-CHANGE | test_road_overlay_sync asserts the executed coords (wave-1) |
| test_frontend_contract.py | raw==null / drawLive(latest) fallback pins | NO-CHANGE | test_water_live_sync_guard executes the null-media fallback (wave-1) |
| test_frontend_contract.py | session watchdog/storage/sign_out pins | NO-CHANGE | executed same-wave in tests/test_auth_session_frontend_contract.py |
| test_398_wave4_demo.py | (new) two-direction demo | RB | compact executed HLS twin on water-page tmp copies; directions recorded in tasks.md |
| tests/test_validate_sdd.py | (out of wave-4 scope) | NO-CHANGE | validate_sdd pins the validator itself — the validator's source text IS the artifact under test (SS by design); not part of the admitted 8-file cluster |
| tests/test_vps_deploy_transaction.py | (out of wave-4 scope) | NO-CHANGE | already converted in wave 2; no raw-text pins remain to convert |

## Affected contours

- Tests only: the 8 listed test files, tests/support/frontend_html.py (extended), the demo
  test, this trio — plus the recorded one-line grandfather entry in scripts/ci/validate_sdd.py.
- Read-only inputs: api/**, worker/**, frontend/**, deploy/**, .github/**, nginx/**, and all
  wave-1/wave-2/wave-3 test files (byte-identical, including tests/support/relay_shell.py).

## Validation

- Per-file focused pytest after each conversion (all green; observed tails in the session
  checkpoint /tmp/opencode/398-w4/checkpoint.md: autonomous_execution_policy 9, auth_logout_contract
  15/3 subtests, auth_session_frontend_contract 4/8, roi_normalization 6, analytics_profiles
  15/13, camera_preview_gallery 20, line_crossing 45, frontend_contract 23, demo 1).
- Cluster: `pytest` over the 8 files + demo → 138 passed / 24 subtests in 22.99s (baseline
  126 / 18 on fe45e8b).
- Full battery: `python3 -m pytest tests/ -q -p no:cacheprovider
  --basetemp=/tmp/opencode/398-w4/pytest-tmp` → 1203 passed / 2 skipped / 300 subtests in
  75.49s (baseline 1191 / 2 / 294; cluster net +11 tests + demo +1; subtests +6).
- `python3 scripts/ci/validate_sdd.py` → informational bare run for the trio after the
  grandfather line (NOT a gate here — the orchestrator runs `--event` mode on the fresh
  commit); `validate_repo.py` unchanged-behavior read-only.
- Allowed-paths check: `git status` shows only tests/**, tests/support/frontend_html.py,
  specs/398-wave4/** plus the recorded validate_sdd.py exception.

## Runtime feedback

- RF-001: Operator actions expected: 0 — CONTROL_PLANE change (tests + one validator line);
  runtime acceptance = exact-head CI green on the merge PR.
- RF-002: post-wave battery reports 1203 / 2 / 300; all deltas recorded in the tasks.md
  battery-delta ledger (retired assertion → covering executed twin, same commit).

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: every mapping-table action's focused run green (autonomous_execution_policy 9, auth_logout_contract 15/3, auth_session_frontend_contract 4/8, roi_normalization 6, analytics_profiles 15/13, camera_preview_gallery 20, line_crossing 45, frontend_contract 23); regression trio 5 passed / 8 subtests after each extension
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: cluster 126/18 → 138/24 (incl. demo +1); battery-delta ledger in tasks.md maps every retired assertion to its recorded twin
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: tests/test_398_wave4_demo.py — both directions with recorded inverted-mutation run (stray-second-attachMedia direction fails the executed check)
- TEST-004 | Covers: AC-004, AC-005 | Level: integration | Priority: P0 | Evidence: full battery 1203 passed / 2 skipped / 300 subtests in 75.49s; validate_sdd informational run green for the trio (orchestrator --event gate after commit)
- TEST-005 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: git status shows only declared paths + the recorded validate_sdd.py grandfather-entry exception

## Correct-course check

Course correction CC-1 — analytics mid-conversion step-limit incident (worker hit the step
limit mid-conversion of test_analytics_profiles.py; the orchestrator applied the worker's 2
diagnosed one-line fixes — worker_source API_DIR parse + frontend_html import in the test
module — and added the harness `drain_timeouts` parameter; conversion landed green 15/3+13):

- Trigger: NONE
- Issue impact: NONE — the admitted 8-file tests-only scope is unchanged; the incident was execution-level (mid-file handoff), not a scope event.
- Specification impact: NONE — no requirement changed; the harness extension is recorded in Scope/plan as the additive `drain_timeouts` parameter.
- Plan impact: recorded here and in the Architecture harness summary (drain_timeouts fires the boot-batch recorded timeouts microtask-ordered before the scenario).
- Tasks impact: T-7 evidence notes the orchestrator-applied one-line fixes; per-file counts unchanged (15 passed / 13 subtests).
- Authorization impact: NONE — same admitted scope; harness file was already in scope.
- Follow-up: none — conversion completed and verified in the same wave; lesson recorded in the checkpoint.

Course correction CC-2 — road boot drain_timeouts discovery (the road page's preview/start
POST fires from a setTimeout(0) registered at boot, so boot-batch timeouts must be drained
before scenario assertions; discovered during the road HLS twin, fixed by the harness
`drain_timeouts` boot parameter):

- Trigger: NONE
- Issue impact: NONE — harness capability addition inside the admitted tests/support scope.
- Specification impact: NONE — deterministic-offline requirement (R-5) unchanged; the parameter makes boot timing explicit instead of sleep-based.
- Plan impact: Decisions bullet "Timers record-but-never-fire by default" extended with the drain_timeouts semantics.
- Tasks impact: T-2 harness extension list includes drain_timeouts; road twins use drain_timeouts=True.
- Authorization impact: NONE — tests/support/frontend_html.py is an admitted path.
- Follow-up: none — parameter regression-checked (wave-2 session+demo trio green).

Course correction CC-3 — DOMString value accessor (the harness element stub's `.value` was a
plain string; the objects page writes a numeric speed_kmh into `editSpeed.value` then calls
`.trim()`, which threw TypeError; the stub `value` became a Web IDL DOMString accessor —
get/set coerce to String, null→"" — matching real DOM behavior):

- Trigger: NONE
- Issue impact: NONE — harness fidelity fix inside the admitted scope; no test weakened.
- Specification impact: NONE — R-1 twin fidelity improved (the executed twin now exercises the page's real code path instead of tripping on a stub artifact).
- Plan impact: Decisions bullet records the DOMString accessor semantics.
- Tasks impact: T-2 harness extension list includes the value accessor; objects twins green.
- Authorization impact: NONE — same admitted scope.
- Follow-up: none — grep confirmed no other test assigns non-string .value; regression trio held.

Course correction CC-4 — bodyless ok:false quirk (bodyless `{ok:false}` responses make the
pages' `api()` throw TypeError on the JSON parse; response fixtures must always supply a json
body — including at BOOT, where the road fallback page needs an EVENTS response or
`Promise.all` rejects before any render):

- Trigger: NONE
- Issue impact: NONE — fixture-authoring discipline recorded for future scenario authors.
- Specification impact: NONE — determinism requirement unchanged.
- Plan impact: Decisions bullet records the quirk (and the boot-time variant found in the road fallback twin).
- Tasks impact: T-6/T-10 fixture notes; no count impact.
- Authorization impact: NONE — same admitted scope.
- Follow-up: none — quirk documented in the trio and the checkpoint.
