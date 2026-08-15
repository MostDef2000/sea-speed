# Feature Specification: Calibration Overlay Ownership

- Feature: 007-calibration-overlay-ownership
- Issue: #159
- Status: Source authorized
- Owner outcome: Keep the operator's current saved ROI and speed lines visible over the main AI frame while removing stale calibration geometry baked into worker-generated images.

## Product outcome

The main Camera 1 AI monitoring frame must have one authoritative visual calibration layer. The worker supplies AI annotations such as detections, tracks, status text and speed labels, while the browser frontend renders the current persisted ROI and speed-line calibration above that image. Saved calibration remains visible during normal monitoring and after saving; edit mode only enables editing affordances.

This supersedes the frontend-only assumption from the first Issue #159 implementation, where canvases were hidden outside edit mode while the worker still embedded legacy ROI and A/B lines into JPEG pixels.

## User scenarios

### Scenario 1 - Normal monitoring with saved calibration

Given a saved enabled ROI and saved enabled Line A/Line B configuration, when the operator opens or reloads the Sea Speed Operator page, then the current ROI and speed lines are visible over the main AI frame without entering edit mode, and no second legacy copy is baked into the underlying worker image.

### Scenario 2 - Edit and save without losing visibility

Given saved calibration is visible, when the operator enters ROI or Line A/Line B edit mode, then the same calibration remains visible with editing handles enabled. When the operator saves or leaves edit mode, the saved geometry remains visible in its non-editing presentation.

### Scenario 3 - Clear calibration

Given visible saved ROI or speed lines, when the operator uses the existing Clear action, then that calibration is disabled through the existing API and its frontend geometry disappears.

### Scenario 4 - Worker computations continue unchanged

Given persisted ROI and speed-line configuration, when the worker processes detections, then ROI filtering and calibrated speed estimation continue using the same persisted values and formulas even though the worker no longer draws those calibration shapes into latest-overlay or event JPEG pixels.

## Requirements

- FR-001: The frontend MUST be the sole owner of visible ROI polygon and Line A/Line B calibration geometry on the operator AI frame.
- FR-002: Saved enabled ROI geometry MUST remain visible during normal monitoring, after `Save ROI`, and after page reload.
- FR-003: Saved enabled Line A/Line B geometry MUST remain visible during normal monitoring, after `Save`, and after page reload.
- FR-004: ROI and speed-line edit modes MUST change interactivity/editing handles without being required for saved geometry visibility.
- FR-005: Existing ROI and speed-line Clear actions MUST continue to disable the corresponding persisted configuration and remove its frontend geometry.
- FR-006: Worker-generated latest-overlay and event JPEGs MUST NOT add ROI polygon or speed-line A/B graphics to image pixels.
- FR-007: Worker ROI filtering MUST continue to consume the persisted ROI configuration without formula or inclusion-rule changes.
- FR-008: Worker calibrated speed estimation MUST continue to consume the persisted speed-line configuration without formula, sampling, tracking or event-semantics changes.
- FR-009: Existing ROI, speed-line and speed-configuration API paths and persisted state schemas MUST remain unchanged.
- FR-010: Camera 1 media transport, Authentik/session boundaries, detection history, tracking labels and live-stream controls MUST remain unchanged.

## Acceptance criteria

- AC-001: With enabled saved ROI, a fresh/reloaded operator page shows the ROI in normal monitoring before ROI edit mode is entered.
- AC-002: With enabled saved Line A/B, a fresh/reloaded operator page shows both lines in normal monitoring before speed-line edit mode is entered.
- AC-003: Entering ROI or line edit mode exposes editing handles; saving or leaving edit mode keeps the saved geometry visible.
- AC-004: Clearing ROI or speed lines disables it via the existing API and removes the corresponding frontend geometry.
- AC-005: Source inspection/tests prove the worker main JPEG path no longer invokes ROI/speed-line drawing on the generated overlay used for latest state and event snapshots.
- AC-006: Source inspection/tests prove `filter_detections_by_roi` and `update_speed_lines_estimate` remain on the worker processing path.
- AC-007: Focused frontend and worker tests, PR Validation and Quality integration pass on the exact final PR head.
- AC-008: After separate production authorization, runtime acceptance proves the worker image has no baked calibration copy and the VPS frontend shows exactly the current saved calibration persistently.

## Compatibility and boundaries

- Stable public interfaces: `/sea-speed/`, `/sea-speed/api/cam1/roi`, `/sea-speed/api/cam1/speed-lines`, `/sea-speed/api/cam1/speed-config`, Camera 1 state/events/media URLs and existing Authentik-protected session behavior.
- Out of scope: calibration data migration/deletion, ROI filtering redesign, speed formula redesign, detection/tracking/event redesign, Camera 1 transport changes, Authentik/nginx changes, API schema changes, Objects/Cameras/root-page redesign.
- Security constraints: no new credentials, secrets, public paths or trust boundaries; protected runtime state remains outside Git.

## Runtime feedback

- Runtime acceptance: PENDING for the revised mixed VPS + Ubuntu worker outcome.
- Accepted production behavior: PENDING.
- Regressions/learning: The first Issue #159 production acceptance proved calibration had two visual owners: frontend canvases were hidden after save while worker JPEGs retained legacy geometry. The revised design assigns visual ownership exclusively to the frontend.
- Follow-up work: NONE YET.
