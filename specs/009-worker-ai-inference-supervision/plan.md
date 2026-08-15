# Implementation Plan: Worker AI inference supervision

- Specification: specs/009-worker-ai-inference-supervision/spec.md
- Issue: #159
- Status: Accepted supporting runtime remediation

## Architecture

```text
media/state parent
 -> persistent AI child process
    -> bounded request write + response read
    -> model.track(... persist=True ...)
 -> timeout/failure: terminate child, bounded backoff, empty detections for frame
 -> media/state loop continues

startup
 -> two blank-frame calls on same child
 -> retain that child for production
 -> exact activation gate waits for AI ready + frame/state progress
```

## Decisions

### D-001 - Isolate inference failure
AI child failure must not freeze media/state.

### D-002 - Absolute deadline includes pipe write
Backpressure is part of inference boundedness.

### D-003 - Retain the self-tested child
Readiness must refer to the process used for production frames.

### D-004 - Runtime dependency closure before service
Pin lazy ByteTrack dependency and disable Ultralytics auto-install.

### D-005 - Restore clears systemd failure budget
Candidate start-limit exhaustion must not prevent previous-release restore.

## Affected contours

- Repository: Ubuntu Worker entrypoint/updater/runtime requirements/tests/SDD.
- VPS: NONE for remediation source.
- Ubuntu Worker/relay: YES.
- Windows AI Worker: no production rollout for the Ubuntu-specific supervision entrypoint.
- Public interfaces: NONE.

## Validation

Supervisor protocol/deadline/startup/dependency/updater tests plus exact-head CI/package and production progression gates.

## Rollout and rollback

Every candidate remained exact-SHA production-authorized; failed candidates restored previous release. Final accepted candidate proceeded to Issue #159 completion.

## Runtime feedback

Accepted production architecture includes supervised AI child and exact progression gating. Failed candidate details remain durable Issue history rather than being removed from the record.
