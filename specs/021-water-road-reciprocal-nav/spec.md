# Feature Specification: Reciprocal Water/Road navigation toggle

- Feature: 021-water-road-reciprocal-nav
- Issue: #209
- Status: Implementing
- Owner outcome: Make the protected Water and Road Operator pages directly reciprocal through one highlighted context-switch pill while preserving all existing Operator behavior and runtime boundaries.

## Product outcome

The protected Water Operator page at `/sea-speed/` shows one highlighted `Дорога` navigation pill immediately after `Камеры`, linking to `/sea-speed/road/`. The protected Road Operator page at `/sea-speed/road/` shows one highlighted `Вода` navigation pill immediately after `Камеры`, linking to `/sea-speed/`.

`Реестр объектов` and `Камеры` remain unchanged. No API, Worker, analytics, camera, Authentik, MediaMTX, private M2M, session/logout, stream-control, worker-control, calibration, event, or model behavior changes.

## User scenarios

### Scenario 1 - Water operator opens Road

Given an authenticated operator is on `/sea-speed/`, when the operator selects the highlighted `Дорога` pill beside `Камеры`, then the browser navigates to `/sea-speed/road/` without changing the authenticated session contract.

### Scenario 2 - Road operator returns to Water

Given an authenticated operator is on `/sea-speed/road/`, when the operator selects the highlighted `Вода` pill beside `Камеры`, then the browser navigates to `/sea-speed/` without changing the authenticated session contract.

### Scenario 3 - Existing navigation and controls remain stable

Given either Operator page is open, the existing `Реестр объектов` and `Камеры` navigation, session/logout controls, stream controls, worker controls, analytics controls and runtime endpoints remain unchanged.

## Requirements

- FR-001: `/sea-speed/` MUST contain exactly one highlighted reciprocal context link with text `Дорога` and target `/sea-speed/road/`, positioned in the header navigation after `Камеры`.
- FR-002: `/sea-speed/road/` MUST contain exactly one highlighted reciprocal context link with text `Вода` and target `/sea-speed/`, positioned in the header navigation after `Камеры`.
- FR-003: The reciprocal context links MUST use the existing pill styling and active/highlight state; no new navigation component or JavaScript routing layer may be introduced.
- FR-004: Existing `Реестр объектов`, `Камеры`, session identity and logout markup MUST remain unchanged on both pages.
- FR-005: Existing Water/Road API endpoints, Worker controls, analytics behavior, ROI/speed configuration, cameras, RTSP sources, MediaMTX/relay topology, private M2M routes and Authentik/session semantics MUST remain unchanged.
- FR-006: Source integration MUST not mutate production. Runtime activation is VPS-only and requires a separate exact-SHA production safety envelope after exact-green merge and post-merge Quality.
- FR-007: Ubuntu Worker/relay source and runtime MUST NOT be updated for this change. VPS execution capability remains `CONNECTOR` with zero operator actions expected.

## Acceptance criteria

- AC-001: `tests/test_frontend_contract.py` proves Water contains exactly one highlighted `Дорога` link to `/sea-speed/road/` and Road contains exactly one highlighted `Вода` link to `/sea-speed/`, each adjacent to `Камеры` in the header navigation.
- AC-002: Existing frontend and analytics-profile contract assertions continue to prove Objects/Cameras navigation, authenticated session markers, logout semantics, Water/Road runtime controls, private-source/M2M boundaries and mobile baseline remain intact while recognizing the reciprocal Road→Water link.
- AC-003: The final source diff is exactly the seven authorized paths, linked SDD validation passes, PR Validation and aggregate Quality integration are green on the same exact head, expected-head merge succeeds, and post-merge main Quality is green.
- AC-004: After a separate exact-SHA production authorization, VPS-only deployment succeeds with exact release evidence and authenticated browser smoke proves Water→Road and Road→Water navigation both work while the same protected session remains usable.

## NFR assessment

- NFR-001 | Area: USABILITY | Target: exactly one obvious reciprocal Water/Road context switch is highlighted beside Cameras on each protected Operator page | Validation: frontend contract plus authenticated browser smoke | Evidence: tests/test_frontend_contract.py and Issue #209 runtime evidence | Status: CONCERNS
- NFR-002 | Area: COMPATIBILITY | Target: existing Objects/Cameras/session/logout/runtime-control and protected-source/M2M contracts remain unchanged by the navigation-only diff | Validation: repository behavioral contract tests and exact-head Quality | Evidence: tests/test_frontend_contract.py, tests/test_analytics_profiles.py and GitHub Actions | Status: PASS
- NFR-003 | Area: RELEASE_PROVENANCE | Target: VPS-only runtime activation uses the exact merged main SHA, separate production authorization, exact release evidence and rollback target | Validation: post-merge Quality, production authorization verifier and VPS deployment manifest | Evidence: Issue #209 deployment evidence | Status: CONCERNS

## Runtime feedback

- Initial PR #210 product changes were limited to the two Operator HTML files and the focused frontend regression.
- Quality integration #377 failed closed before behavioral tests because `frontend/**` is classified as significant and therefore requires a linked `specs/<feature>/spec.md` with the current delivery-quality layer.
- Product behavior did not fail that validation; the Change Contract derived `Production impact: VPS` correctly. The source scope was therefore expanded only by the mandatory `spec.md`, `plan.md` and `tasks.md` triplet.
- Fresh exact six-path source authorization was durably recorded on Issue #209 comment `5316246154`.
- On exact head `0460ab1bfc1df8b0e51f03990228248161526119`, PR Validation #435 / run `32032076813` and Quality #385 / run `32032076857` both reached behavioral tests and failed on the same stale historical assertion in `tests/test_analytics_profiles.py`: it required `/sea-speed/road/` to appear in the Road page even though the approved reciprocal design intentionally renders `Вода` linking to `/sea-speed/` there. The focused reciprocal-navigation frontend test passed.
- Fresh exact seven-path source authorization, limited to synchronizing that stale assertion while preserving its private-source/M2M/control checks, is durably recorded on Issue #209 comment `5316347354`.
- No production mutation is part of source integration. Final runtime work remains separately authorized, VPS-only, Connector-executed and followed by authenticated browser acceptance.
