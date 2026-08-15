# Tasks: Worker RTSP Runtime Resilience

- Specification: specs/008-worker-rtsp-runtime-resilience/spec.md
- Plan: specs/008-worker-rtsp-runtime-resilience/plan.md
- Issue: #159

## Delivery tasks

- [x] Localize production frame stall to the RTSP reader path.
- [x] Move Ubuntu production RTSP ingestion to bounded FFmpeg/TCP.
- [x] Add bounded timeout/recreation and redacted diagnostics.
- [x] Require exact candidate frame/state progression before activation commit.
- [x] Preserve automatic previous-release restoration.
- [x] Pin/verify critical Ubuntu runtime package contract.
- [x] Pass focused source/quality checks.
- [x] Feed runtime evidence into subsequent AI-supervision remediation.
- [x] Final Issue #159 Worker acceptance reached sustained progression.

## Completion gate

- [x] RTSP reads are bounded.
- [x] Activation is progression-gated.
- [x] Rollback/restore remains exact.
- [x] Supporting runtime remediation is accepted as part of closed Issue #159.
