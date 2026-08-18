# Delivery Tasks: Reciprocal Water/Road navigation toggle

- Specification: specs/021-water-road-reciprocal-nav/spec.md
- Issue: #209
- Status: Implementing

## Delivery tasks

- T-001 [x] Update `frontend/sea-speed/index.html` so Water shows one highlighted `Дорога` link to `/sea-speed/road/` beside `Камеры`.
- T-002 [x] Update `frontend/sea-speed/road/index.html` so Road shows one highlighted `Вода` link to `/sea-speed/` beside `Камеры`.
- T-003 [x] Extend `tests/test_frontend_contract.py` with exact reciprocal navigation assertions while preserving existing authenticated navigation/runtime contracts.
- T-004 [x] Add the mandatory `specs/021-water-road-reciprocal-nav/{spec,plan,tasks}.md` delivery-quality layer after CI exposed significant-frontend SDD linkage.
- T-005 [x] Synchronize `tests/test_analytics_profiles.py` so Water/Objects/Cameras retain Road navigation while the Road page asserts reciprocal `Вода` navigation to `/sea-speed/`; preserve all private-source, M2M and bounded Road-control assertions.
- T-006 [x] Verify the original product diff is exactly the seven authorized paths and ahead-only from authorization base `dc0d09143b171a0c2846076db6555569988ff011`.
- T-007 [x] Require linked SDD validation, PR Validation and aggregate Quality integration on the same original exact head: PR Validation #441 / `32032753264` and Quality #391 / `32032753207` succeeded on final head `114221486c3cdd24ce1f063f09e55bb517a0e917`.
- T-008 [x] Refresh main/head/scope/reviews and merge PR #210 with expected-head protection; exact product runtime merge is `e4183d329ef970160582021a2b6ed4608822c907`.
- T-009 [x] Require post-merge Quality on exact product main and persist source integration evidence: Quality #392 / `32032834524` succeeded and Issue #209 comment `5316405026` records acceptance.
- T-010 [x] Obtain separate exact-runtime production authorization: Issue #209 comment `5321867764` authorizes `e4183d329ef970160582021a2b6ed4608822c907` with fingerprint `38f6346631f398363b4205dc9ae2e23b52aeff432dd17ea41934de9bbf5b4835` and `Execution-Intent: EXECUTE`.
- T-011 [x] Record production learning from the root-owned Auth privileged boundary: comment `5321895134` establishes that exact `e4183d...` requires VPS `ONE_COMMAND_FALLBACK`, operator actions expected `1`, Ubuntu Worker/relay NOT REQUIRED, and no accepted live-source mutation is claimed before bootstrap.
- T-012 [ ] Integrate this exact three-path production-learning SDD correction under source authorization comment `5321926492`; require exact 3/3 diff, machine-valid `PRODUCTION_LEARNING` adjacent-stage audit, PR Validation + aggregate Quality on one exact head, fresh merge gate, expected-head merge and post-merge Quality. The corrective merge is source/control-plane evidence only and MUST NOT replace runtime target `e4183d...`.
- T-013 [ ] Execute the single repository-owned root privilege-boundary bootstrap on the canonical VPS from an exact `e4183d329ef970160582021a2b6ed4608822c907` checkout for deployment user `sea-speed-deploy`; require exact-source admission, `SEA_SPEED_AUTH_PRIVILEGE_INSTALL=PASS`, fixed helper/no-args scope, no root shell, fixed topology and transactional PASS evidence.
- T-014 [ ] After T-013 PASS, retry the canonical Connector VPS deployment for exact runtime target `e4183d329ef970160582021a2b6ed4608822c907` under existing production authorization; require exact release/deployment evidence with `runtimeVerified=true`, `state=runtime_verified`, preserved protected Auth/private-M2M boundary and no Ubuntu Worker/relay update.
- T-015 [ ] Complete authenticated browser smoke: Water shows highlighted `Дорога`, Road shows highlighted `Вода`, both directions navigate correctly, and the protected session remains usable.
- T-016 [ ] Persist final corrective-source/bootstrap/Connector/browser evidence and close Issue #209 only after every applicable gate passes.

## Requirements traceability

- AC-001 | Task: T-001,T-002,T-003,T-005 | Evidence: tests/test_frontend_contract.py reciprocal Water/Road navigation contract plus synchronized tests/test_analytics_profiles.py navigation regression | Coverage: COVERED
- AC-002 | Task: T-003,T-005,T-007 | Evidence: existing frontend authenticated navigation/runtime contract, analytics-profile protected-source/M2M/control regression and original exact-head repository behavioral tests | Coverage: COVERED
- AC-003 | Task: T-004,T-006,T-007,T-008,T-009,T-011,T-012 | Evidence: original exact seven-path compare, PR Validation #441, Quality #391, merge `e4183d...`, post-merge Quality #392, production-learning Issue evidence, exact three-path corrective compare/SDD validation/CI/merge/post-merge Quality | Coverage: COVERED
- AC-004 | Task: T-010,T-011,T-012,T-013,T-014,T-015,T-016 | Evidence: Issue #209 production authorization, production-learning capability correction, exact-source root privilege-bootstrap PASS, exact Connector VPS deployment manifest and authenticated Water↔Road browser smoke | Coverage: RUNTIME-MANUAL | Reason: root-owned production privilege state, protected production session behavior and deployed exact-release navigation require live VPS/operator evidence after the separately authorized runtime release

## Definition of Done

- [ ] Issue/spec/plan/tasks current — production-learning correction is prepared but must merge and receive post-merge Quality before main is current.
- [ ] Exact changed-file scope verified — original seven-path source is accepted; corrective branch must remain exactly the authorized three SDD paths through merge.
- [ ] Required tests and evidence complete — original source CI is complete; corrective CI, root bootstrap, Connector deployment and browser acceptance remain.
- [ ] Required CI green — original PR/post-main CI is green; corrective exact-head and post-merge Quality remain.
- [ ] Exact-green-head merge complete — original PR #210 is complete; corrective three-path PR remains.
- [ ] Deployment state resolved — exact runtime `e4183d...` still requires root bootstrap followed by Connector VPS deployment.
- [ ] Runtime acceptance resolved — authenticated reciprocal-navigation browser smoke remains.
- [x] Deferred work recorded — no hidden product/runtime expansion is deferred; only the explicit correction/bootstrap/deployment/browser sequence remains.
- [x] Risks resolved or explicitly accepted — Risk profile remains NOT REQUIRED; the observed operational privilege-boundary constraint is addressed fail-closed by the production-learning transaction audit and existing transactional installer.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`COMPLETE` is forbidden until the original exact seven-path product source remains accepted as runtime target `e4183d329ef970160582021a2b6ed4608822c907`, the exact three-path production-learning SDD correction is merged from an exact-green head with post-merge Quality, the single root privilege-boundary bootstrap passes for exact `e4183d...`, the subsequent canonical Connector VPS retry produces an accepted `runtime_verified` deployment manifest without an Ubuntu update, authenticated Water↔Road browser smoke passes, and Issue #209 contains terminal sanitized evidence.
