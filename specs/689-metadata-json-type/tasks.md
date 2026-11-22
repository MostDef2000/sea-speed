# Tasks: metadata JSON type — reject non-object JSON at the analytics ingestion boundary

- Spec: specs/689-metadata-json-type/spec.md
- Plan: specs/689-metadata-json-type/plan.md
- Issue: #689

## Delivery tasks
- [x] Root cause confirmed on branch agent/wave4-689-metadata-type: `post_analytics_state` (POST /api/analytics/{camera_id}/state) and `post_analytics_event` (POST /api/analytics/{camera_id}/events) ran `json.loads(metadata)` and then used the parsed value as a dict, so `[]`, `null`, `42` and `"str"` raised `TypeError` at `data["camera_id"] = camera_id` and `AttributeError` at `event.get("event_id")` and surfaced as an unhandled 500, while `post_cam1_passage` and `api_post_crossing` already guarded the same parse
- [x] State guard added in `api/app/main.py`: after the existing parse `try`/`except` in `post_analytics_state` and before `data["camera_id"] = camera_id`, `if not isinstance(data, dict): raise HTTPException(status_code=400, detail="metadata must be a JSON object")`
- [x] Events guard added in `api/app/main.py`: the same `isinstance(event, dict)` guard in `post_analytics_event`, after the parse `except` and before the `#587` non-finite scan and `event.get("event_id")`
- [x] No other source change: the two pre-existing guards in `post_cam1_passage` and `api_post_crossing` are byte-identical, `require_auth` and `analytics_identity` still run before the parse, and no other route, module or deploy script was touched
- [x] New test `tests/test_689_metadata_json_type.py`: 7 tests plus 8 subtests through the real FastAPI app and the real `require_auth` (authenticated-worker fixture, `TestClient(..., raise_server_exceptions=False)`, disposable temp `SEA_SPEED_BASE_DIR`), covering non-object payloads on both endpoints (4 subtests each), malformed-JSON regression on both, valid-object side effects with GET round-trip plus the 403 boundary, and the source guard over all four `json.loads(metadata)` sites
- [x] Test-infrastructure fix in `tests/test_run_tests_script.py`: the exact-match import-hygiene oracle now lists the three new guarded-optional entries (`tests/test_689_metadata_json_type.py` lines 108, 109 and 111), with the exact-match assertion preserved
- [x] Test-infrastructure fix in `tests/test_689_metadata_json_type.py`: the `sys.modules` snapshot is taken in `setUpClass` immediately before the app import and restored to exactly that pre-import state, replacing the module-import-time snapshot that went stale in the full battery and caused 4 errors plus 1 failure inside `tests/test_api_http_integration.py`
- [x] RED then GREEN proof: RED before the guards 9 failed / 6 passed; GREEN after the guards 7 passed plus 8 subtests
- [x] Full battery and static gates green: 1439 tests OK (skipped=2); repo, contracts, quality, workflow and token validators PASS; ruff PASS
- [x] Write the SDD trio `specs/689-metadata-json-type/{spec,plan,tasks}.md`
- [ ] PR Change Contract declares exactly `Production impact: VPS`, `VPS deployment: REQUIRED`, `VPS execution capability: CONNECTOR`, `Ubuntu worker/relay update: NOT REQUIRED`, `Ubuntu worker execution capability: NOT APPLICABLE`, `Production safety envelope: REQUIRED`, `Operator actions expected: 0`, plus `Risk profile: REQUIRED` and `Specification: specs/689-metadata-json-type/spec.md`
- [ ] Exact-head CI on the PR is green, including the new test file, the SDD validator for this trio, the contracts, quality, workflow and token validators, and ruff
- [ ] Exact-green-head merge of the PR to main
- [ ] Lane-A deploy of the merged main SHA dispatched with the DEPLOY-TRIGGER evidence (repo, full 40-hex SHA from origin/main, acceptance probe, rollback target `94bce646f654340adc5ab0b1e3cc859fd19bca71`)
- [ ] Post-deploy authenticated POST to `https://mostdef.ru/sea-speed/api/analytics/cam1/state` with `metadata=[]` returns 400 with `metadata must be a JSON object` (not 500), and the deploy log carries the API origin health and public smoke pass lines

## Completion gate
- The source diff contains only the two `isinstance(dict)` guards in `post_analytics_state` and `post_analytics_event`; the two pre-existing guards, the auth order, the malformed-JSON message and every side effect are unchanged, and no other source, test or deploy file changes beyond the two declared test-infrastructure fixes
- The test diff adds `tests/test_689_metadata_json_type.py` and the three import-hygiene oracle entries only, weakens no existing assertion, and the full battery stays at 1439 tests OK (skipped=2) with validators and ruff green
- The PR Change Contract declares the VPS REQUIRED fields listed in the delivery tasks, because `api/app/main.py` is in the diff and the autonomous policy derives `VPS deployment: REQUIRED` from the path
- Exact-head CI green on the PR, PR merged to main with exact-green-head evidence, then the lane-A deploy of that merged SHA completes with the API health and public smoke lines in its log
- Runtime acceptance is the post-deploy authenticated POST with a non-object `metadata` payload returning 400, never 500; the rollback target for the deploy is the previous main `94bce646f654340adc5ab0b1e3cc859fd19bca71`

## Requirements traceability
- AC-001 | Task: non-object JSON metadata (`[]`, `null`, `42`, `"str"`) on both analytics ingestion endpoints is rejected with 400/422 and never reaches the dict operation that produced the 500 | Evidence: tests/test_689_metadata_json_type.py::MetadataJsonTypeHttpTests.test_state_rejects_non_object_metadata_400_or_422 and ::test_events_rejects_non_object_metadata_400_or_422, 4 subtests each, asserting status in (400, 422) and no `traceback` in the body; RED 9 failed / 6 passed before the guards, GREEN 7 passed plus 8 subtests after | Coverage: COVERED
- AC-002 | Task: malformed JSON keeps its 400 `metadata must be valid JSON` rejection, valid object payloads keep state upsert and event delivery with the duplicate flag unchanged, and the auth boundary still answers 403 without a header | Evidence: tests/test_689_metadata_json_type.py::MetadataJsonTypeHttpTests.test_state_rejects_malformed_json_400_or_422, ::test_events_rejects_malformed_json_400_or_422, ::test_state_valid_object_persists_state_and_keeps_auth_boundary (200, state body, GET round-trip, 403 without header) and ::test_events_valid_object_delivers_event_and_keeps_auth_boundary (200, event body, duplicate false, GET delivery, 403 without header) | Coverage: COVERED
- AC-003 | Task: all four `json.loads(metadata)` sites in `api/app/main.py` carry an `isinstance(<var>, dict)` rejection, pinned by a source-level test with anti-vacuity on the four known sites | Evidence: tests/test_689_metadata_json_type.py::MetadataJsonLoadsSourceGuardTests.test_every_json_loads_metadata_site_is_dict_checked requires at least 4 sites and a guard within 8 lines of each parse; the state and events sites were RED before the fix and now pass, and the pre-existing passage and crossing sites satisfy it unchanged | Coverage: COVERED
- AC-004 | Task: the full battery and validators stay green and the new test leaves `sys.modules` as it found it for other tests in the same process | Evidence: full Python suite 1439 tests OK (skipped=2) including `tests/test_api_http_integration.py`; repo, contracts, quality, workflow and token validators PASS; ruff PASS; `tests/test_run_tests_script.py` import-hygiene oracle lists the three new guarded-optional entries and `tests/test_689_metadata_json_type.py` restores the per-`setUpClass` module snapshot | Coverage: COVERED

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
