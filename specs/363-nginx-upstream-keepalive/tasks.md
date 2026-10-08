# Tasks: NGINX upstream keepalive for Camera 1 HLS

- Issue: #363
- Specification: specs/363-nginx-upstream-keepalive/spec.md

## Delivery tasks

- T-363-001: `scripts/operations/nginx_cam1_direct_h264.py` — add
  constants `CAM1_BACKEND`/`HLS_UPSTREAM`/`PROXY_PASS`, `_remove_upstream()`
  helper, render the `upstream sea_speed_cam1_hls { server 127.0.0.1:18889;
  keepalive 8; }` block immediately before the managed server block, switch
  the managed location to `proxy_pass http://sea_speed_cam1_hls/cam1/;`
  with `proxy_http_version 1.1;` and `proxy_set_header Connection "";`,
  preserving the existing rendering style, marker lifecycle and no-store
  directives
- T-363-002: extend `verify()` so it fails loudly (deterministic,
  self-contained `ConfigError`) when the `sea_speed_cam1_hls` upstream
  block is missing or duplicated, its body lacks `server 127.0.0.1:18889;`
  or `keepalive 8;`, or the managed block lacks `proxy_pass
  http://sea_speed_cam1_hls/cam1/;`, `proxy_http_version 1.1;` or
  `proxy_set_header Connection "";`
- T-363-003: sync test pins — update
  `tests/test_camera1_direct_h264_cutover.py` to the new canonical render
  (and strengthen it with the upstream/keepalive/Connection assertions);
  audit the whole `tests/` and `scripts/` trees for other pins of this
  renderer (`18889`, `proxy_pass`, `sea_speed_cam1`, `nginx_cam1_direct`):
  `tests/test_sea_speed_auth_v1.py` ~:50 is the legacy input fixture
  (unchanged, full suite green), `tests/quality/test_quality_architecture.py`
  and `scripts/quality/{validate,build}_exact_artifacts.py` are path-only
  pins (unaffected); the `docs/operations/CAMERA1_DIRECT_H264_CUTOVER.md`
  pin (cutover test :148) still passes because the doc is untouched
- T-363-004: write the SDD trio under `specs/363-nginx-upstream-keepalive/`
  and run the verification battery (full pytest, renderer CLI render+verify,
  negative-verify loud-fail cases, ruff on changed py files, validate_sdd)

## Completion gate

- [x] T-363-001
- [x] T-363-002
- [x] T-363-003
- [x] T-363-004
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [x] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main (a996d665)
- [x] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main (a996d665)
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned (TIME-WAIT churn drop verified on the VPS after the next deploy)
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — informative risk analysis (prose, no formal register per NOT REQUIRED derivation) in plan.md Risk profile
- [x] Waivers resolved or current — none

## Definition of Done

- [x] Issue/spec/plan/tasks current — this trio delivered on branch
  `sdd/363-nginx-upstream-keepalive` from main @ ed92ae6
- [x] Exact changed-file scope verified — only
  `scripts/operations/nginx_cam1_direct_h264.py`,
  `tests/test_camera1_direct_h264_cutover.py`,
  `specs/363-nginx-upstream-keepalive/**`; forbidden paths (`api/`,
  `deploy/`, `.github/`, other scripts/tests, operations doc) untouched
- [x] Required tests and evidence complete — full suite 777 passed /
  4 skipped / 119 subtests; CLI CAM1_PROTECTED_H264_RENDER=PASS +
  CAM1_PROTECTED_H264_CONFIG=PASS; NEGATIVE-VERIFY=PASS (four loud-fail
  cases); ruff All checks passed! on changed py files; `bash -n` not
  applicable (no shell files changed)
- [x] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main (a996d665)
- [x] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main (a996d665)
- [ ] Deployment state resolved — orchestrator-owned (next VPS deploy
  renders the config through this script; nginx -t gates reload)
- [ ] Runtime acceptance resolved — orchestrator-owned (TIME-WAIT churn
  toward 127.0.0.1:18889 drops after the next deploy)
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — informative risk analysis in
  plan.md Risk profile, all MITIGATED
- [x] Waivers resolved or current — none

## Requirements traceability

- AC-001 | Task: T-363-001 | Evidence: test_renderer_moves_cam1_under_sea_speed_and_preserves_h264_upstream asserts "upstream sea_speed_cam1_hls {", "server 127.0.0.1:18889;" and "keepalive 8;" in the rendered config; CLI render PASS transcript | Coverage: COVERED
- AC-002 | Task: T-363-001 | Evidence: same test asserts "proxy_pass http://sea_speed_cam1_hls/cam1/;", "proxy_http_version 1.1;" and 'proxy_set_header Connection "";' in the rendered config | Coverage: COVERED
- AC-003 | Task: T-363-002 | Evidence: NEGATIVE-VERIFY=PASS — verify() raises ConfigError for missing upstream block, missing keepalive 8, missing Connection "" header and legacy direct proxy_pass (deterministic, self-contained) | Coverage: COVERED
- AC-004 | Task: T-363-001,T-363-002 | Evidence: test_renderer_is_idempotent (byte-identical re-render) + test_renderer_is_idempotent legacy-marker path + CLI render/verify PASS on a fresh fixture | Coverage: COVERED
- AC-005 | Task: T-363-003,T-363-004 | Evidence: full suite 777 passed / 4 skipped / 119 subtests with updated pins; ruff All checks passed! on changed py files; python3 scripts/ci/validate_sdd.py green; pin audit results recorded in plan.md Correct-course | Coverage: COVERED
