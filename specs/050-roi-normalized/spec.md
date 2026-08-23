# Spec: Normalized ROI model 0..1 for HD 1920 and future 4K

- Issue: #294
- Status: ACTIVE
- Runtime contour: MIXED (VPS + Ubuntu Worker/relay + Frontend)

## Product outcome

After HD enforcement (#291) ROI polygons/lines drift. Store ROI, speed_lines and crossing_line normalized `x_norm,y_norm ∈ [0,1]` + `reference_width/height` (default 1920×1080) and scale on read to current frame size. Existing absolute polygons recorded on 704×576 must be migrated once to same relative road location on 1920×1080. Frontend click → normalize by displayed-to-source scale; Worker mask → scale normalized to current `FRAME_WIDTH×HEIGHT`. Single model covers future 4K without further data migration.

## User scenarios

- Operator with legacy ROI (704) opens editor after upgrade — polygon covers same lane on 1920 preview (not shrunk).
- Operator draws new ROI on HD preview — after save+reload polygon stays 1:1 (±1px).
- Worker on 1920 frame masks/detects with same relative polygon; on future 3840 frame same normalized ROI still correct.

## Requirements

- R1: API accepts both legacy absolute `{x,y}` and normalized `{x_norm,y_norm}` for `polygon`, `line_a/line_b`, `line`; persists normalized plus reference (`reference_width=1920 reference_height=1080` or client-provided reference); returns normalized shape plus scaled absolute for current reference for backwards-compat.
- R2: Read path transparently migrates legacy file without `x_norm`/`reference_width` by inferring source 704×576 if `max≤704` else current reference, converting `x_norm=x/704` etc., persisting migrated shape.
- R3: Worker `fetch_remote_roi / fetch_speed_lines / fetch_crossing_line` scale normalized → absolute via current `FRAME_WIDTH/HEIGHT` (env/profile) with `round` and clamp; `mask_frame_to_roi` uses scaled polygon.
- R4: Frontend both contours normalize click: `x_norm = round((clientX-left)*reference_width/displayWidth)/reference_width` using `state.frame_width` (or `naturalWidth`) as reference; `toDisplay` scales `x_norm*displayWidth`; CSS `aspect-ratio: 16/9` (1920/1080) not 704/576.
- R5: VPS deploy runs one-shot migration for `cam1_roi.json, road1_roi.json, *_speed_lines.json, *_crossing_line.json` if legacy; idempotent, logs `ROI_MIGRATED`.
- R6: No detection/speed formula change; coordinates after scaling remain integer pixel; calibration distance unaffected.

## NFR assessment

- NFR-050-001 | Area: correctness | Target: legacy 704 polygon after migration/ scaling matches HD position within ±1px | Validation: unit test absolute→norm→scale roundtrip 704→1920→704 | Evidence: tests/test_roi_normalization.py | Status: PASS
- NFR-050-002 | Area: compatibility | Target: old absolute payloads still accepted, new normalized payloads accepted | Validation: api main test both schemas | Evidence: tests/test_roi_normalization.py | Status: PASS
- NFR-050-003 | Area: reliability | Target: worker never blacks out 60% frame due to stale small polygon | Validation: mask scaling test | Evidence: tests/test_roi_normalization.py | Status: PASS
- NFR-050-004 | Area: performance | Target: scaling O(N) <1ms, no extra HTTP | Validation: code review | Evidence: single pass map | Status: PASS

## Acceptance criteria

- AC-001: `POST /api/cam1/roi` with legacy `[{x:352,y:288}]` on 704 is stored/read as `x_norm≈0.5` and displayed on 1920 editor at same relative lane.
- AC-002: New `POST` with `x_norm` roundtrips and worker mask uses scaled 1920 coords.
- AC-003: Existing `704` file after first GET/migration or deploy shows `reference_width 1920` and polygon scaled.
- AC-004: Frontend `state.frame_width` drives `toDisplay/toImage` (no 704 hardcode).
- AC-005: Worker `mask_frame_to_roi` with migrated polygon covers lane on 1920 frame (center test passes).
- AC-006: Suite + validators PASS; MIXED runtime_verified.

## Runtime feedback

To be recorded after MIXED deployment acceptance (visual ROI checks water+road).
