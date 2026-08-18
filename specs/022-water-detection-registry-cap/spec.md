# Feature Specification: Water detection activation and registry cap

- Feature: 022-water-detection-registry-cap
- Issue: #212
- Status: Implementing
- Owner outcome: Keep the bounded newest-100 registry behavior and correct the production-observed Water detection regression without changing Road semantics.

## Product outcome

Water analytics continues to use `water-v1`: `cam1`, `models/yolo26x.pt`, `imgsz=960`, confidence `0.15`, ByteTrack, `SAMPLE_FPS=5`, accepting model class `boat` as domain object `vessel`. For `water-v1`, YOLO inference runs on every sampled ROI-bounded frame instead of being gated by legacy motion contours. Motion remains available as telemetry but is not an admission gate or post-detection filter for Water. A newly tracked Water `vessel` emits one event per ByteTrack track without requiring a speed estimate.

`road-v1` remains explicitly selected and retains its existing motion-gated inference, motion-box filtering, speed estimation and event readiness semantics.

The existing shared SQLite Objects Registry remains capped at the newest 100 rows across Water and Road, ordered deterministically by `detected_at DESC, object_id DESC`. API/schema and snapshot/media retention remain unchanged.

## User scenarios

### Scenario 1 - small or distant vessel is not suppressed by motion preprocessing
Given a real vessel is inside the active Water ROI on a sampled frame, Water runs YOLO even when the legacy motion detector reports `motion_now=false`, has no accepted motion boxes, or reports `MOTION idle`.

### Scenario 2 - Water detection remains ROI bounded
Given Water runs continuous sampled-frame inference, pixels outside the active ROI remain masked and resulting detections still pass the final ROI guard before they enter tracking/event telemetry.

### Scenario 3 - Water event does not require road-oriented speed readiness
Given ByteTrack assigns a track ID to a Water `vessel`, the first accepted detection for that live track can create a Water event even when calibrated speed, pixel speed, or speed-line readiness is unavailable. The same active track does not create duplicate Water events.

### Scenario 4 - Road behavior remains unchanged
Given `road-v1` is active, YOLO remains motion-gated, detections remain motion-box filtered, and the existing Road speed/event readiness rules continue to decide event posting.

### Scenario 5 - registry remains bounded
Given Water and Road events continue arriving, the persistent SQLite registry keeps no more than the newest 100 rows using the already accepted deterministic ordering.

## Requirements

- FR-001: `water-v1` MUST remain `cam1`, `models/yolo26x.pt`, `imgsz=960`, `conf=0.15`, `bytetrack.yaml`, `SAMPLE_FPS=5.0`, and `boat -> vessel`.
- FR-002: `road-v1` detector/profile values MUST remain unchanged.
- FR-003: On `water-v1`, every sampled processing frame MUST be passed to YOLO regardless of current motion activity.
- FR-004: Water raw detections MUST NOT be rejected solely because they do not intersect a legacy motion box.
- FR-005: Water detections MUST remain constrained to the ROI snapshot bound to the sampled processing frame.
- FR-006: Water motion detection MUST remain available for `motion_now` and `motion_area` telemetry.
- FR-007: A Water event MUST require a tracked `vessel` with a non-null ByteTrack track ID.
- FR-008: A Water event MUST NOT require `speed_ready`, calibrated speed, or minimum pixel speed.
- FR-009: At most one successful Water event MUST be posted for one active ByteTrack track; a failed post MAY be retried because the track is not marked posted until transport succeeds.
- FR-010: `road-v1` MUST preserve the existing motion gate, motion-box filter and speed/event readiness semantics.
- FR-011: SQLite Objects Registry MUST remain capped at the newest 100 rows across Water and Road after initialization and successful insertions.
- FR-012: API routes/schema, camera/RTSP/MediaMTX topology, Auth/private M2M, ROI editor/coordinates, snapshots/media retention and JSON event history MUST remain unchanged.
- FR-013: Production deployment of the remediation MUST require a new exact-SHA production authorization for the merged executable release.
- FR-014: Ubuntu runtime acceptance MUST preserve the current Road desired state and verify sustained Water inference health at the existing 5 FPS sampling rate.

## Acceptance criteria

- AC-001: Automated regression proves `water-v1` calls detector inference when `motion_now=false`, motion AI activity is false, and `motion_boxes=[]`.
- AC-002: Automated regression proves Water detections bypass `filter_detections_by_motion` but still pass the ROI filter.
- AC-003: Existing ROI masking, ROI-change baseline reset and bound-frame ROI guard tests remain green.
- AC-004: Automated regression proves `road-v1` does not invoke inference while motion AI activity is false and still invokes the motion-box filter when active.
- AC-005: Automated regression proves a tracked Water `vessel` is eligible for an event with no speed readiness or pixel-speed value.
- AC-006: Automated regression proves a posted Water track is not selected for a second event and an untracked detection is not event eligible.
- AC-007: Analytics profile tests prove YOLO26x, `imgsz=960`, `conf=0.15`, ByteTrack, 5 FPS, Water class mapping and Road profile values are unchanged.
- AC-008: Existing newest-100 SQLite registry behavior and API contracts remain green without source changes to API/storage paths.
- AC-009: Exact PR diff contains only the six newly authorized repository paths and passes exact-head PR Validation plus aggregate Quality.
- AC-010: Expected-head merge is followed by successful exact-main Quality before any production decision.
- AC-011: After separate exact-SHA production authorization, Ubuntu exact-release acceptance proves `water-v1` provenance, running service, sustained sampled-frame inference/telemetry without unacceptable degradation, and preservation of the Road desired state.
- AC-012: Final functional production acceptance requires a real naturally occurring moving vessel inside the Water ROI to produce non-zero `DETECTIONS`/`TRACKS` and a new `vessel` event in the operator event view; synthetic production events are not acceptable evidence.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: a valid small/distant Water target is not suppressed before YOLO by legacy contour thresholds | Validation: focused Water policy tests plus real-vessel runtime acceptance | Evidence: `tests/test_water_detection_pipeline.py` and Issue #212 runtime evidence | Status: CONCERNS
- NFR-002 | Area: BACKWARD_COMPATIBILITY | Target: Road motion/speed/event semantics and protected Water model/profile values remain unchanged | Validation: focused Road policy regression plus analytics-profile suite | Evidence: `tests/test_water_detection_pipeline.py`, `tests/test_analytics_profiles.py` | Status: PASS
- NFR-003 | Area: PERFORMANCE | Target: continuous Water inference at existing 5 FPS does not cause sustained GPU/service degradation on the production RTX 5070 | Validation: separately authorized Ubuntu runtime telemetry and service acceptance | Evidence: Issue #212 production acceptance | Status: CONCERNS
- NFR-004 | Area: DATA_SAFETY | Target: existing newest-100 registry retention remains deterministic and API-compatible | Validation: unchanged API contract suite | Evidence: `tests/test_api_contract.py` | Status: PASS
- NFR-005 | Area: RELEASE_PROVENANCE | Target: source merge and any later Ubuntu mutation are exact-SHA, quality-gated and separately authorized | Validation: PR/main Quality plus production admission and exact runtime evidence | Evidence: GitHub Actions and Issue #212 | Status: CONCERNS

## Runtime feedback

- Original product source was merged through PR #213 as executable runtime `9e0cd96aa2f790f1ba806299c3dd4019e5572899`; the subsequent PR #214 was specs-only production-learning evidence and current source/control-plane main became `f3febcd6d9ae6a57e052f6b4a50bf3ec9f75fdf1` without changing executable runtime bytes.
- VPS and Ubuntu infrastructure acceptance for `9e0cd96...` proved exact source/profile/model readiness, service/telemetry progression and newest-100 registry behavior, but bounded acceptance observed no natural vessel event.
- Fresh production observation later showed a real small moving vessel visually inside Camera 1 ROI while telemetry remained `MOTION idle`, `AI idle`, `DETECTIONS 0`, `TRACKS 0`. Exact-source review showed YOLO was gated by `MotionDetector` and detections were filtered again by current motion boxes. This invalidates the prior claim of functional Water detection acceptance while leaving the already proven infrastructure/runtime provenance evidence intact.
- Issue #212 was reopened and the regression was recorded durably. Fresh source authorization for this six-path remediation is Issue #212 comment `5323802105`, based on current-main SHA `f3febcd6d9ae6a57e052f6b4a50bf3ec9f75fdf1` and operator reply `OUTCOME APPROVED`.
- This source authorization does not authorize production. The future exact merged executable SHA requires a new production safety envelope before Ubuntu mutation.
