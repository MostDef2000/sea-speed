# Tasks: ROI-bounded motion and AI inference

- Specification: specs/010-roi-bounded-motion-inference/spec.md
- Plan: specs/010-roi-bounded-motion-inference/plan.md
- Issue: #168

## Delivery tasks

- [x] Capture one effective ROI snapshot per frame.
- [x] Create same-size black-outside ROI processing frame.
- [x] Run motion and AI on the masked frame.
- [x] Use the same ROI snapshot for final guard.
- [x] Reset motion baseline/active window on ROI signature change.
- [x] Remove yellow technical motion rectangles while preserving real AI boxes.
- [x] Preserve ByteTrack/speed/event/API/frontend/auth/media semantics.
- [x] Pass exact source/quality gates and merge.
- [x] Obtain exact-SHA production authorization and deploy Ubuntu Worker only.
- [x] Pass sustained runtime/operator acceptance and close Issue #168.

## Completion gate

- [x] Source and CI accepted.
- [x] Exact Ubuntu runtime accepted.
- [x] No VPS deployment required.
- [x] Issue #168 closed completed.
