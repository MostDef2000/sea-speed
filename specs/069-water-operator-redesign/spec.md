# Feature Specification: Water operator dashboard redesign

- Feature: 069-water-operator-redesign
- Issue: #326
- Status: ACTIVE
- Owner outcome: Water operators get one compact dashboard where the synchronized AI feed stays dominant, overlay editors sit directly below it, and crossing statistics plus recent passages are visible without a redundant clean-stream card.

## Product outcome

Redesign `/sea-speed/` to match the approved Water Operator composition while preserving the existing Water HLS/live-overlay runtime, ROI and speed-line editing, speed calibration, crossing-line semantics, authenticated navigation, diagnostics, and passage data sources. The page becomes a compact two-column desktop dashboard: the primary AI camera and its controls on the left, and separate crossing-statistics and recent-passage cards on the right. On mobile the same information hierarchy stacks vertically with iOS-usable controls.

## User scenarios

### Scenario 1 - Observe the Water AI feed

Given an authenticated operator opens `/sea-speed/`, when the page loads, then the compact header and the large synchronized AI camera are visible first and there is no separate `LIVE CAMERA / Чистый поток` card competing for space.

### Scenario 2 - Edit Water overlays below the camera

Given the operator needs to adjust ROI, speed lines, counting line, or speed calibration, when they use the control area directly below the main camera, then the existing API operations and editor semantics are preserved and crossing statistics are not mixed into the line editor.

### Scenario 3 - Review crossing statistics

Given crossing records already exist for `cam1`, when the operator selects a date range in the `Пересечения` card, then the existing generic crossing-summary endpoint supplies IN/OUT/total and per-class counts without adding a new backend contract. The card also exposes a direct `История` link into the existing Water registry crossing view.

### Scenario 4 - Review recent passages

Given Water passages exist, when the dashboard refreshes, then up to three fresh passage records show their available snapshot, passage ID, timestamp, actual status, direction/speed context, and a link to the full Water registry.

### Scenario 5 - Use the dashboard on mobile

Given an operator opens the page on an iPhone Pro or Pro Max portrait viewport, when the responsive layout applies, then header/status, primary camera, crossing statistics, recent passages, controls, calibration, and diagnostics remain usable in that logical order with touch targets at least 44 px high where controls are interactive.

## Requirements

- R1: `/sea-speed/` MUST use a compact header band beginning with the existing clickable lighthouse/home action and keep authenticated user/logout plus Water navigation/status controls accessible.
- R2: The visible `clean-live` / `Чистый поток` card MUST be removed, while the existing HLS health/reconnect path and synchronized main Water video/live overlay behavior remain functionally intact.
- R3: The main Water AI camera MUST remain the dominant visual element and retain `overlayImg`, `waterMainVideo`, ROI canvas, speed-lines canvas, live overlay canvas, and current synchronized overlay runtime.
- R4: ROI, speed lines, crossing-line editor, speed calibration, `State JSON`, and `Operator log` MUST be placed under the primary camera; crossing statistics MUST NOT be rendered inside crossing editor controls.
- R5: A visually independent `Пересечения` card MUST use existing `cam1` crossing-summary data to show date controls, IN, OUT, total, per-class breakdown, and an honest latest-crossing indicator without inventing backend state.
- R6: `История` MUST navigate directly to the existing crossing-history UX in `frontend/sea-speed/objects/index.html` using Water scope, and that registry page MUST activate its existing crossing layer from the direct-link query state.
- R7: A separate `Последние проходы` card MUST show at most three current passage records from the existing passages endpoint, including available snapshot, ID, timestamp, actual status, and a link to the Water registry.
- R8: `frontend/sea-speed/road/index.html`, worker/detection/tracking behavior, speed/calibration formulas, crossing semantics, API/storage/telemetry schemas, authentication/media topology, and HLS/live-sync timing MUST remain unchanged.

## Acceptance criteria

- AC-001: The Water header is a compact single desktop band beginning with the clickable lighthouse; authenticated navigation, status, user, and logout controls remain accessible.
- AC-002: The visible `LIVE CAMERA / Чистый поток` block is absent, the primary AI camera is dominant, and existing HLS reconnect plus Water synchronized overlay markers remain intact.
- AC-003: ROI, speed lines, crossing-line editor, calibration, State JSON, and Operator log are under the camera; editor controls retain their existing IDs/actions and no crossing statistics element remains in the line editor.
- AC-004: The separate `Пересечения` card provides date range controls, IN/OUT/total, per-class rows, and an honest latest-crossing display from existing available client/runtime evidence.
- AC-005: `История` opens `/sea-speed/objects/?scope=water&view=crossings`, and the registry activates the same existing Water crossing layer rather than implementing a duplicate history screen.
- AC-006: The separate `Последние проходы` card renders at most three passage records with available snapshot, passage ID, timestamp, status and a full-history Water registry link.
- AC-007: Contract tests prove the Water redesign markers, direct crossing-history behavior, protected Road boundary, existing endpoint markers, unique control IDs, and responsive mobile baseline.
- AC-008: Repository/SDD/change-contract validation, required unit/quality CI, exact-green-head merge, exact-main Quality, protected VPS deployment, and Water runtime acceptance complete without an Ubuntu Worker update.

## NFR assessment

- NFR-069-001 | Area: USABILITY | Target: primary camera remains visually dominant while crossing and passage information is available without scrolling on a wide operator display where viewport height permits | Validation: structural contract checks and responsive runtime visual acceptance | Evidence: `frontend/sea-speed/index.html`, production screenshots/runtime inspection | Status: CONCERNS
- NFR-069-002 | Area: COMPATIBILITY | Target: zero backend/API/schema or Water HLS/live-sync timing changes and zero Road source changes | Validation: exact changed-file review plus existing frontend/live-overlay tests | Evidence: PR changed-file list, `tests/test_frontend_contract.py`, existing Water overlay test suite | Status: PASS
- NFR-069-003 | Area: ACCESSIBILITY | Target: interactive controls remain keyboard-focusable and mobile touch targets retain at least 44 px minimum height | Validation: CSS/static contract inspection and mobile runtime acceptance | Evidence: Water page CSS and iPhone Pro/Pro Max viewport inspection | Status: CONCERNS
- NFR-069-004 | Area: OPERABILITY | Target: dashboard continues to expose stream/worker state, diagnostics, crossing data, and recent passage evidence from existing endpoints with no new operational dependency | Validation: contract tests and protected VPS runtime acceptance | Evidence: endpoint markers, authenticated production page, API-backed widgets | Status: CONCERNS

## Runtime feedback

- Runtime acceptance: PENDING.
- Accepted production behavior: PENDING.
- Regressions/learning: none admitted; Issue #326 was clarified by the durable user comment marking the approved design as `макет для воды`.
- Follow-up work: any request for new crossing history APIs, new latest-crossing schema fields, Road redesign, or worker analytics changes requires a separate scope and authorization.
