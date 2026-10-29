# Tasks — Issue #398 wave 4

- Issue: #398
- Specification: specs/398-wave4/spec.md

## Delivery tasks

- T-1: RECON + baseline: cluster 126 passed / 18 subtests on base fe45e8b (repo 1191 / 2 / 294); feasibility probes (water/road/cameras/objects page boots under the shim, timers record-but-never-fire, worker-op userns pattern, per-page redirect semantics). DONE.
- T-2: tests/support/frontend_html.py extensions (additive, regression-checked after each step): location fields + replace recording + window.top aliasing, programmable __responses/__setResponse, recorded listeners/timers/HLS/overlay-canvas, ready_state, drain_timeouts, location_overrides, referrer, DOMString value accessor, createElement/append/appendChild, history/scrollTo/confirm/CSS.escape/FormData/rAF, per-page location defaults with content-marker page_key. DONE.
- T-3: test_autonomous_execution_policy.py — YAML SS parsed-structure twins (router/sync/deploy-vps/deploy-ubuntu-worker incl. the verify-exact-release composite action) + AST evaluator scan; executed evaluator tests unchanged. DONE (9 passed).
- T-4: test_auth_logout_contract.py — blueprint yaml.safe_load twins (local BlueprintLoader for !KeyOf/!Find) + executed water/cameras/objects logout twins + executed worker dispatch via relay_shell userns (+9 net (10 added, 1 retired), incl. secret-ban + rc62 POST-apply mode-drift twin). DONE (15 passed / 3 subtests).
- T-5: test_auth_session_frontend_contract.py — executed all-4-pages session twins (SESSION_SCENARIO) + executed water HLS media-path twin + parsed-attribute anchor twins. DONE (4 passed / 8 subtests).
- T-6: test_roi_normalization.py — executed water/road ROI twins (saveRoi/loadRoi POST bodies parsed from recorded fetches) + executed deploy.sh migration twin (extracted function vs tmp sqlite fixtures); 3 executed helper tests kept verbatim. DONE (6 passed).
- T-7: test_analytics_profiles.py — AST twins via worker_source(paths=...) + direct ast.parse + api/app walk + executed road boot; regex security bans SP. DONE (15 passed / 13 subtests; CC-1: orchestrator applied 2 diagnosed one-line fixes + harness drain_timeouts mid-conversion).
- T-8: test_camera_preview_gallery.py — AST function-slice twins on api/app sources + executed cameras boot/batch-preview flow + SP (relay/VPS evidence literals) + NO-CHANGE (SDD prose). DONE (20 passed).
- T-9: test_line_crossing.py — AST twins (legacy-kind, VLZ summary) + executed crossing-panel delete/toggle on both pages + executed DOM-guard (water ready_state="loading") + executed objects speed/scope twins + SS markup keeps. DONE (45 passed).
- T-10: test_frontend_contract.py — executed HLS/worker/fallback/stats/registry twins (water+road+objects) + frontend_node overlay-gate twin + SS structural keeps (incl. the stream retry-ladder literal SS twin) + NO-CHANGE refs to wave-1 executed tests. DONE (23 passed; CC-3 DOMString accessor, CC-4 bodyless-response quirk).
- T-11: Demo tests/test_398_wave4_demo.py — two-direction proof on water-page tmp copies. DONE (1 passed).
- T-12: Grandfather line (validate_sdd.py "398" set += "398-wave4", one line) + this trio + full battery + validators + allowed-paths self-check. DONE.

## Completion gate

- Cluster `pytest tests/<8 files> tests/test_398_wave4_demo.py -q` green: observed 138 passed /
  24 subtests in 22.99s (baseline 126 / 18 on fe45e8b; identity: 126 + 8 auth_logout_contract
  + 1 roi_normalization + 1 demo = 136, + 1 rc62 POST-apply mode-drift twin + 1 retry-ladder SS
  twin (peer-review fix round) = 138; subtests 18→24).
- Full battery `python3 -m pytest tests/ -q -p no:cacheprovider
  --basetemp=/tmp/opencode/398-w4/pytest-tmp` green: observed 1203 passed / 2 skipped /
  300 subtests (baseline 1191 / 2 / 294; the identity holds: 1191 + 11 cluster tests
  + 1 demo = 1203, subtests +6).
- Demo inverted-mutation proof observed: `python3 -m pytest tests/test_398_wave4_demo.py -q` →
  1 passed (refactor tolerance AND dead-marker intolerance; real-page sanity).
- `validate_sdd.py` bare informational run for the trio after the grandfather line: observed
  clean (NOT a gate at worker level — the orchestrator runs `--event` mode on the fresh
  commit, which also picks up the untracked trio).
- ruff clean on changed files (`ruff check scripts/ci/validate_sdd.py --config
  scripts/quality/ruff.toml` → All checks passed; test files ruff-clean per focused runs).

## Requirements traceability

- AC-001 | Task: T-2, T-3, T-4, T-5, T-6, T-7, T-8, T-9, T-10 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-3, T-4, T-5, T-6, T-7, T-8, T-9, T-10, T-11 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-11 | Evidence: TEST-003 | Coverage: COVERED
- AC-004 | Task: T-1, T-12 | Evidence: TEST-004 | Coverage: COVERED
- AC-005 | Task: T-12 | Evidence: TEST-004, TEST-005 | Coverage: COVERED
- AC-006 | Task: T-12 | Evidence: TEST-005 | Coverage: COVERED

Requirement notes: R-1 → the mapping table in plan.md (all 8 files adjudicated pin-group by
pin-group; every removed assertion has a twin, SP retention, or NO-CHANGE rationale) + the
battery-delta ledger below; R-2 → SP pins kept verbatim carry in-code justification comments or
mapping-table rationale (deploy-transaction evidence literals; regex security bans; deliberate
markup stubs; prose SDD documents); R-3 → the demo's inverted-mutation proof recorded below;
R-4 → no production file touched (git status limited to tests/**, tests/support/frontend_html.py,
specs/398-wave4/** + the recorded validate_sdd.py exception); R-5 → the shim is offline
(stubbed fetch/Hls/timers, programmable responses, tmp copies only) and root-gated shell twins
skip gracefully where user namespaces are unavailable; R-6 → battery green with per-file deltas
accounted; validators green (orchestrator --event gate after commit).

## Battery-delta ledger (per-file test counts counted from base fe45e8b; identity: 1191 + 9 + 1 + 1 + 1 demo = 1203 passed, skips 2→2; subtests 294→300)

| File | Delta (base→now) | Retired assertions → covering twin (same commit) |
|------|------------------|--------------------------------------------------|
| test_autonomous_execution_policy.py | 0 (9→9) | router/sync/deploy-vps/deploy-ubuntu-worker/zero-touch text pins → yaml.safe_load parsed-structure twins (trigger wiring, job-if conditions, step order/gating/env chain, run-text literals from PARSED steps — comment-blind); deploy-workflow source-protection pins → verify-exact-release composite-action parsed twin (verify_source_protection before evaluate_production_policy, --require-allow, delegation env) — stronger than the comment-passable text pins; evaluator text pins → AST constant/identifier scan; executed evaluator tests unchanged |
| test_auth_logout_contract.py | +9 (6→15; 3 subtests) | blueprint text pins → yaml.safe_load twins with local BlueprintLoader (!KeyOf/!Find): logout-v1 flow slug/designation, userlogoutstage+redirectstage (static, target_static root), bindings order 10→20, provider forward_single + invalidation_flow !KeyOf, no host keys, default flow absent; rollback blueprint single-proxyprovider !Find twin; frontend logout/session pins → executed water/cameras/objects twins (watchdog re-fetch, storage typeof, identity-loss replace, sign_out anchor regex); worker-op evidence pins → executed userns dispatch twins (usage rc0, unknown rc2, bad sha rc42, happy apply with real blueprint sha256 read-back, idempotent ALREADY_APPLIED, rollback-only restore, mode drift rc61 pre-mutation, mode drift rc62 POST-apply PROVIDER_MODE_DRIFT_ after a real blueprint apply, unknown current flow rc54, verify-fail auto-rollback rc56, credential-material never in docker log); bash -n kept |
| test_auth_session_frontend_contract.py | 0 (4→4; subtests +8) | all-pages session text pins → executed 4-page SESSION_SCENARIO twins (same-origin session API, redirect assign/replace per page, watchdog re-fetch, credentials include, identity population, storage typeof); media-path pin → executed water HLS twin (attach waterMainVideo, MEDIA_ATTACHED → loadSource /sea-speed/media/cam1/index.m3u8, window.hls===window.waterHls); sign_out/project-home anchors → parsed-attribute regex twins (order-independent) |
| test_roi_normalization.py | +1 (5→6) | frontend normalized-ROI text pins → executed water page twin (saveRoi POST polygon_norm + reference_width/height 1920/1080 + enabled; legacy loadRoi normalization vs inferred 704x576) and road page twin (roiSaveBtn.onclick POST; loadRoiConfig legacy via sourceDims); deploy.sh migration presence pin → executed twin (extracted log()+migrate_legacy_roi_to_normalized run against tmp sqlite fixtures: legacy normalized with 1920-compat re-denorm, already-normalized untouched, crossing-line line_norm, ROI_MIGRATED total=2); 3 executed API/worker helper tests kept verbatim |
| test_analytics_profiles.py | 0 (15→15; subtests +13) | worker profile-boundary text pins → AST via worker_source(paths=...) (normalize_model_class/analytics_profile/object_type/model_class references); entrypoint/child wiring pins → direct ast.parse (--analytics-profile constant, profile=get_profile assign, **semantic keyword None, no yolo11s.pt constant); API route pins → ast walk of api/app modules (decorator path constants); configure/prepare-yolo/build/validate pins → AST string constants; frontend road pins → executed road boot (recorded fetch URLs) + DOM scan; regex security bans SP kept |
| test_camera_preview_gallery.py | 0 (20→20) | API source text pins → ast.parse at import + function slices by stable def name on api/app/camera_preview.py+main.py (routes, commit/get snapshot slices, public-state slices, validate source slice, Popen args, no shell=True, mkdir mode); operator/cameras page pins → executed cameras boot + end-to-end batch-preview flow (sequential startPreview POSTs, playback-progress wait, error isolation, commit/stop); relay/VPS deploy shell pins SP kept (deploy-transaction evidence literals); SPEC/PLAN/TASKS/QUICKSTART prose pins NO-CHANGE (the prose IS the artifact) |
| test_line_crossing.py | 0 (45→45) | cam1 legacy-kind pin → AST contains_expr on analytics.py; VLZ summary pins → AST (signature-defaults tail-alignment, vlz_days dict-key walk, VLZ_TIMEZONE dump compare); crossing-panel delete/toggle pins → executed on BOTH pages (handlers via __record.elements.cxOffBtn/cxUndoBtn.onclick, mid-scenario response swaps); DOM-guard pin → executed water (ready_state="loading", no crossing-line GET until recorded DCL) + SS road keep (crossingCard block is a deliberate e793332 stub; real road handlers proven executed); objects speed-card/scope pins → executed (renderObjects speed_kmh; ?scope=road via location_overrides); markup order pins SS kept; detector/API executed tests unchanged |
| test_frontend_contract.py | +1 (22→23; +7 new executed twins replacing in-place pins) | water/road HLS wiring pins → executed single-player twins (attach main video only, window.hls publish, protected loadSource, media-event listeners, watchdog/retry rungs, recovery/reconnect branches, toggle destroy); retry-ladder literal STREAM_RETRY_DELAYS_MS=[1000,2000,4000,8000] (old text pins, both pages) → SS twin StreamRetryLadderStructuralTests (comment-stripped water+road sources must carry the full ladder as live code; executed twins prove the first 1000 ms rung); worker lifecycle pins → executed page-scoped POST twins (+foreign-target refusal, no unscoped URLs); fallback-overlay pins → executed (last_overlay_url/snap rev-buster → overlayImg.src only while NOT advancing, per-URL dedup, reconnect re-arms); stats/crossings/events card pins → executed (KPIs, rows, event cards, query params); objects registry pins → executed (?scope/referrer/domain-filter scope, URL sync, same-origin PATCH/DELETE writes); overlay worker-inactive gate → executed via frontend_node render calls; layout/markup pins SS kept (no AST for CSS/markup); live-sync/overlay module pins NO-CHANGE → wave-1 executed tests (protected); session pins NO-CHANGE → same-wave executed auth_session twins |
| demo tests/test_398_wave4_demo.py | +1 | new two-direction regression demonstration (additive) |

Arithmetic note: per-file deltas are test-count deltas vs the base commit (git-counted);
cluster Σ = +11 (auth_logout_contract +9, roi_normalization +1, frontend_contract +1 ladder SS
twin; five files converted in place at 0 count delta); the demo adds +1; passed total is
1191 + 11 + 1 = 1203, skipped unchanged 2→2, subtests 294→300 (auth_logout_contract +3,
auth_session_frontend_contract +8, analytics_profiles +13 net of baseline distribution).
Conversions-in-place keep counts while replacing text pins with executed/structural twins —
the coverage became observable (subtests +6) without new test names. Peer-review fix round
(2026-10-29): +1 executed rc62 POST-apply PROVIDER_MODE_DRIFT_ twin (auth_logout_contract,
retired rc62 guard's twin) and +1 SS retry-ladder twin (frontend_contract, retired ladder text
pins' twin) — zero coverage loss vs the retired pins restored.

## Demo — inverted-mutation proof (observed output)

`python3 -m pytest tests/test_398_wave4_demo.py -q` → **1 passed**:

- Direction A (refactor tolerance): tmp copy of the real water operator page with the wiring
  lines rewritten behavior-preservingly (spaces around operators on the attach/publish/
  fallback-gate lines; `connectStream` renamed to `openMediaStream`;
  `notePlaybackProgress` renamed to `noteMediaProgress`) → the executed HLS check PASSES
  (exactly one HLS instance attached to waterMainVideo only, published as window.hls ===
  window.waterHls, protected /sea-speed/media/cam1 path loaded via the MEDIA_ATTACHED
  handler); the 4 retired text pins would all fail on it.
- Direction B (dead-marker intolerance): tmp copy keeping every retired marker byte-for-byte
  but with broken wiring (a stray second `instance.attachMedia(document.getElementById("overlayImg"))`
  after the verbatim attach) → retired pins PASS (the false-green), executed check FAILS
  (two attached elements instead of one).
- Sanity: the real page satisfies the executed check (tmp copies only; frontend/ never
  modified).

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [x] Deployment state resolved — NOT REQUIRED (tests-only + one validator line = CONTROL_PLANE; no runtime artifact changes)
- [ ] Runtime acceptance resolved — runtime acceptance = exact-head CI green on the merge PR (RF-001)
- [x] Deferred work recorded — remaining #398 raw-text clusters outside this 8-file scope stay in the issue backlog
- [x] Risks resolved or explicitly accepted — plan.md Risk profile REQUIRED with RISK-001..005 MITIGATED
- [x] Waivers resolved or current — no waivers

Wave record: all 8 cluster files adjudicated (mapping table in plan.md); battery delta +11
cluster tests (+1 demo; skips unchanged) with recorded twins, no assertion weakened or
skipped; the demo proves the conversion property in both directions on the real water page;
four course corrections recorded (CC-1 step-limit incident with orchestrator one-line fixes +
drain_timeouts harness addition, CC-2 road boot drain discovery, CC-3 DOMString value
accessor, CC-4 bodyless ok:false quirk); peer-review fix round added the rc62 POST-apply
mode-drift twin and the SS retry-ladder twin (both findings LOW, coverage gaps vs retired
pins — closed); observed totals 138 passed / 24 subtests (cluster)
and 1203 passed / 2 skipped / 300 subtests (battery); validate_sdd.py grandfather entry
`398-wave4` added (one line, orchestrator-recorded exception).
