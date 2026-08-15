# Implementation Plan: ROI-bounded motion and AI inference

- Specification: specs/010-roi-bounded-motion-inference/spec.md
- Issue: #168
- Status: Accepted / completed

## Architecture

```text
frame
 -> effective ROI snapshot
 -> same-size black-outside mask
 -> motion detection
 -> supervised AI inference
 -> final ROI/motion filtering using same snapshot
 -> existing track/speed/event pipeline
```

## Decisions

### D-001 - Mask, do not crop
Preserve original image dimensions and coordinates.

### D-002 - Same ROI snapshot per frame
Slow inference cannot cause a later ROI fetch to change final filtering semantics for the same frame.

### D-003 - Reset baseline on effective ROI change
Mask transitions are not motion.

### D-004 - Technical motion boxes are not operator output
Real AI detection boxes remain.

## Affected contours

- Repository: Worker source/tests/SDD.
- VPS: NONE.
- Ubuntu Worker/relay: YES.
- Windows AI Worker: not deployed for Issue #168.
- Public interfaces: NONE.

## Validation

Focused Worker tests, PR Validation, Quality integration, exact Worker updater runtime gate and operator-visible acceptance.

## Rollout and rollback

Exact Ubuntu Worker only under separate production authorization; rollback target was the previously accepted Worker release.

## Runtime feedback

Issue #168 acceptance is complete on exact `8cdf7d5...`: sustained frame/state/AI progression and expected operator-visible ROI/motion behavior; Issue closed completed.
