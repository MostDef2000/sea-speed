# Feature Specification: Ingest frame conformance (black / slate / freeze)

- Feature: 700-ingest-frame-conformance
- Issue: #700
- Status: Source implementation
- Issue #697 already reserved `black_frame`, `slate_frame` and `frozen_frame` in
  `api/app/unknown_reason.py`; this feature is the first writer of those values.

## Product outcome

An operator cannot currently distinguish "the camera delivered black, a test
slate or a frozen image" from "the camera delivered a real frame with nothing
happening". Analytics keeps running on such frames (or on a duplicated frame
forever), and the live view silently presents unusable input as normal.

Issue #700 adds an opt-in, pixel-only frame-conformance gate at ingest. A
confirmed non-conforming frame is reported as camera state with
`frame_conforming=false` and a typed `unknown_reason` (`black_frame`,
`slate_frame` or `frozen_frame`), while normal analytics and **all new**
publications from that frame are skipped. Previously queued events are not
discarded. On recovery the worker publishes `frame_conforming=true` without the
old reason. The worker remains online throughout. The detector is disabled by
default and adds no model, reference image or new dependency.

## User scenarios

- SC-1: a camera delivers a signal-black frame; the worker keeps `worker_online`
  true, reports `frame_conforming=false` with `unknown_reason=black_frame`, and
  publishes no new analytics from that frame.
- SC-2: a camera delivers a synthetic saturated vertical-bar slate; the operator
  sees `slate_frame`, and repeated identical slate frames stay `slate_frame`.
- SC-3: a camera image stops updating; only after the configured elapsed duration
  over consecutive received frames does the worker report `frozen_frame`.
- SC-4: a dark but noisy night scene is not reported black, because the
  contrast/bright-pixel veto rejects it.
- SC-5: the camera recovers; the worker publishes `frame_conforming=true` without
  the old reason and normal analytics resumes.

## Requirements

- R-1 (opt-in): the detector is disabled by default (`FRAME_CONFORMANCE_ENABLED=0`).
  When disabled the worker prints "available but not enabled" and makes no
  `frame_conforming` claim; evaluation is a cheap pass-through.
- R-2 (bounded config): every threshold is read once at detector construction,
  clamped to a finite bounded range, and documented in both Ubuntu env examples.
- R-3 (black): `black_frame` requires near signal black **and** virtually no
  spatial variation, with a bright-pixel/contrast veto. Low average luminance
  alone is not evidence. Black takes precedence over slate and freeze.
- R-4 (slate v1): `slate_frame` recognizes a defined synthetic family only:
  full-frame saturated vertical bars whose columns are uniform down the frame,
  with multiple ordered colour transitions and strong horizontal agreement
  across rows. Repeated recognized slate stays `slate_frame`, never
  `frozen_frame`.
- R-5 (freeze): `frozen_frame` requires repeated identical/near-identical spatial
  samples across a configured **elapsed duration** over consecutive received
  frames, with a conservative differential threshold and a minimum consecutive
  frame count. A slow read or a long wall-clock gap alone is not evidence.
  Near-match freeze is disabled in low-signal scenes.
- R-6 (delivery): on confirmed entry or reason change the worker logs a typed
  diagnostic and sends a metadata-only camera state with
  `frame_conforming=false`, `unknown_reason=<enum>`, `frame_no`, `worker_online=true`,
  no fresh overlay and no `overlay_rev` for the rejected frame; the state repeats
  at the normal heartbeat cadence. Normal analytics and all new valid
  publications are skipped for that frame. Previously queued events are kept.
- R-7 (recovery): on recovery the worker publishes `frame_conforming=true`
  without the old `unknown_reason`, and normal processing resumes.
- R-8 (transport): `worker/worker_transport.py` supports a metadata-only state
  POST when the overlay is `None`; it does not stamp the last good overlay with a
  rejected frame's revision.
- R-9 (vocabulary): reasons come from the shared
  `api/app/unknown_reason.py`, loaded by file path like `worker/water_passage.py`
  (no `sys.path` mutation, one shared module object).
- R-10 (contours): both analytics profiles (`water-v1`, `road-v1`) and both
  reader types go through the same gate because evaluation happens in the worker
  main loop immediately after read, frame increment and receive timestamp.

## Supported slate family (v1)

v1 deliberately recognizes only a synthetic vertical-bar slate: a frame filled
with full-height, vertically-uniform, saturated colour bars, separated by
multiple ordered sharp colour transitions (left to right). It does not attempt
to recognize arbitrary test cards, text slates, logos, gradients or broadcast
colour-bar variants with non-uniform columns. Unrecognized content is treated as
ordinary input; it is not force-labelled slate.

## Freeze confirmation delay

Freeze is confirmed only after the reference sample has been matched within
`FRAME_CONFORMANCE_FREEZE_DIFF_MAX` for at least
`FRAME_CONFORMANCE_FREEZE_SEC` **and** at least
`FRAME_CONFORMANCE_FREEZE_MIN_FRAMES` consecutive received frames. The elapsed
duration alone is insufficient, so a long read gap cannot produce a freeze by
itself. Freeze detection is skipped entirely when scene mean luma is below
`FRAME_CONFORMANCE_FREEZE_MIN_LUMA`.

## Night negative controls

Black detection uses per-cell pixel luma statistics, not cell means. A dark but
noisy night scene has a low mean and a high within-cell standard deviation and
bright pixels, so the contrast/bright-pixel veto rejects black. A textured
low-light control is part of the observed smoke evidence. This reduces, but
cannot eliminate, night-time misclassification: a genuinely uniform,
signal-black frame is indistinguishable from a lens-capped or failed sensor.

## Recovery behavior

The detector keeps one active reason. Any frame that no longer matches the
active rule (changed sample for freeze, non-black/non-slate content) clears the
reason; the worker logs the recovery and posts `frame_conforming=true`. The
normal heartbeat then carries `frame_conforming=true` with no stale
`unknown_reason`.

## Diagnostic sink

- Worker stdout: one typed transition line per entry/reason change with
  `frame_no`, `conforming`, `reason` and a bounded metric `detail` dict.
- Camera state metadata (the ordinary state POST): `frame_conforming`,
  `unknown_reason` on rejected frames, `frame_no`, and
  `frame_conformance_detail`. No new overlay is uploaded for rejected frames.

## Pixel-only limitation (explicit)

Pixel-only detection **cannot guarantee zero night-time false positives**. A
uniform black frame can be a real black capture or a lens cap; a dark, static
but valid scene can resemble a freeze. The feature is therefore opt-in,
conservative, bounded, and reports reasons rather than claiming ground truth.

## Gherkin acceptance examples

### Rule: opt-in and bounded configuration

```gherkin
Scenario: detector not enabled
  Given FRAME_CONFORMANCE_ENABLED is unset or 0
  When the worker starts
  Then it logs "available but not enabled"
  And a black frame produces no frame_conforming=false state
```

### Rule: black needs more than low luminance

```gherkin
Scenario: true black frame
  Given the detector is enabled with default thresholds
  When a full-frame signal-black image is evaluated
  Then the reason is black_frame

Scenario: dark noisy night scene
  Given the detector is enabled with default thresholds
  When a low-mean, high-contrast textured night image is evaluated
  Then it is not black_frame
```

### Rule: slate v1 family and precedence

```gherkin
Scenario: synthetic saturated vertical bars
  Given the detector is enabled
  When a frame of full-height saturated vertical bars with uniform columns and at least two sharp colour transitions is evaluated
  Then the reason is slate_frame
  And repeated identical slate frames keep slate_frame rather than frozen_frame
```

### Rule: freeze needs elapsed duration over received frames

```gherkin
Scenario: static bright scene past the confirmation delay
  Given the detector is enabled with a 10 second freeze confirmation and 8 minimum frames
  When 11 near-identical bright frames arrive across 10 elapsed seconds
  Then the reason becomes frozen_frame

Scenario: long gap without repeated frames
  Given the detector is enabled
  When only two identical frames arrive with a long wall-clock gap between them
  Then frozen_frame is not confirmed
```

### Rule: state-only delivery and recovery

```gherkin
Scenario: non-conforming frame skips analytics and new publications
  Given the detector is enabled and a confirmed black frame is read
  When the worker handles that frame
  Then it posts camera state with frame_conforming=false and unknown_reason=black_frame
  And no fresh overlay or rejected-frame overlay_rev is sent
  And analytics and new publications from the frame are skipped
  And worker_online remains true

Scenario: recovery clears the old reason
  Given a non-conforming reason is active
  When a conforming frame arrives
  Then the worker publishes frame_conforming=true without the old unknown_reason
```

## Acceptance criteria

- AC-001: With `FRAME_CONFORMANCE_ENABLED` unset/0 the detector is disabled, startup logs "available but not enabled", and no `frame_conforming` claim is emitted.
- AC-002: Black classification requires near-black mean, no spatial variation, and passes the bright-pixel veto; a low-luminance noisy night scene is not classified black.
- AC-003: Saturated synthetic vertical bars with uniform columns and multiple ordered transitions classify as `slate_frame`; black wins when both could match; repeated slate does not become `frozen_frame`.
- AC-004: Freeze requires the configured elapsed duration plus the minimum consecutive received frames; a slow read/long gap alone cannot confirm freeze; low-signal scenes are excluded from near-match freeze.
- AC-005: A confirmed non-conforming frame produces a metadata-only state with `frame_conforming=false`, the typed enum reason, `frame_no`, no fresh overlay/overlay_rev, `worker_online=true`, skips analytics and all new publications, and retains queued events.
- AC-006: `post_state(metadata, None)` performs a metadata-only POST and the rejected frame does not inherit or overwrite the last good overlay revision.
- AC-007: Both Ubuntu env examples document the same opt-in semantics and bounded thresholds; repairs cover both worker profiles/reader types.
- AC-008: Verification evidence is observed: `py_compile`, `ruff check --config scripts/quality/ruff.toml`, `python3 scripts/ci/validate_sdd.py`, git scope inspection, and the scratch smoke outputs; `tests/**` is untouched by this worker.

## NFR assessment

- NFR-001 | Area: OPERABILITY | Target: opt-in detector disabled by default with bounded, finite thresholds read once | Validation: code inspection of FrameConformanceDetector plus startup log | Evidence: scratch smoke startup line lists clamped black/slate/freeze thresholds | Status: PASS
- NFR-002 | Area: RELIABILITY | Target: no detector crash on the synthetic family and no runtime NameError | Validation: py_compile and scratch smoke execution | Evidence: observed py_compile OK and smoke outputs for black/night/slate/freeze/recovery | Status: PASS
- NFR-003 | Area: DATA | Target: rejected frames create no new analytics, live, event, passage or snapshot publication and no fresh overlay revision | Validation: main-loop guard inspection and metadata builder inspection | Evidence: guard `continue` before ROI processing; `build_frame_conformance_state` omits `overlay_rev`; `post_state(None)` branch | Status: PASS
- NFR-004 | Area: SECURITY | Target: no new credentials, public exposure, authority or dependency | Validation: diff inspection | Evidence: only stdlib imports, cv2 already present, shared vocabulary loaded by path | Status: PASS
- NFR-005 | Area: OBSERVABILITY | Target: typed diagnostic per transition and state reason visible to the operator | Validation: scratch smoke transition logs | Evidence: observed lines `Frame conformance: ... reason=black_frame/slate_frame/frozen_frame` and recovery | Status: PASS
- NFR-006 | Area: RELIABILITY | Target: document residual night-time false-positive risk; a textured low-light control is rejected by the veto | Validation: scratch smoke with dark random-noise frame; documented limitation | Evidence: observed `night(scene) -> None`; spec states pixel-only detection cannot guarantee zero night false positives | Status: CONCERNS

## Runtime feedback

- Runtime acceptance: PENDING — opt-in default OFF; no production enablement is part of this change.
- Accepted production behavior: unchanged while disabled; when enabled, rejected frames produce state-only diagnostics and skip new publications.
- Regressions/learning: the first implementation used cell means only and misclassified a noisy dark scene as black; the repaired detector uses per-cell pixel luma std/max so the control is not black.
- Follow-up work: test-worker coverage under `tests/**` is PENDING; night-time false-positive rate must be observed in the field before enabling remotely.
