# Implementation Plan: Worker RTSP Runtime Resilience

- Specification: specs/008-worker-rtsp-runtime-resilience/spec.md
- Issue: #159
- Status: Accepted supporting runtime remediation

## Architecture

```text
RTSP source
 -> FFmpeg subprocess, RTSP/TCP
 -> bounded frame-byte reads
 -> recreate on timeout/EOF/failure
 -> existing Worker processing

exact updater
 -> candidate unit
 -> exact source heartbeat
 -> frame + state-post progression
 -> commit active marker only on PASS
 -> restore prior exact unit on failure
```

## Decisions

### D-001 - FFmpeg/TCP for production RTSP
Production evidence showed the in-process reader could stall after initial frames while direct FFmpeg/TCP continued.

### D-002 - Bounded reader recreation
No media read may block Worker progress indefinitely.

### D-003 - Runtime progression is activation evidence
`active/running` process state alone is insufficient.

## Affected contours

- Repository: Worker/updater/tests/SDD.
- VPS: NONE for this remediation.
- Ubuntu Worker/relay: YES.
- Windows AI Worker: no production rollout for this Ubuntu-specific entrypoint.
- Public interfaces: NONE.

## Validation

Reader/updater/runtime dependency tests, exact-head quality, production progression gates.

## Rollout and rollback

Candidate activation is fail-closed and restores the previous exact unit/source when its progression gate fails.

## Runtime feedback

Accepted Issue #159 runtime incorporates this architecture. Later AI-supervision remediation was required before sustained production acceptance; both are represented as separate supporting SDD features.
