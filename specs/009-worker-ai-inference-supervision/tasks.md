# Tasks: Worker AI inference supervision

- Specification: specs/009-worker-ai-inference-supervision/spec.md
- Plan: specs/009-worker-ai-inference-supervision/plan.md
- Issue: #159

## Delivery tasks

- [x] Isolate YOLO tracking in a persistent child.
- [x] Bound request write/response read and child failure recovery.
- [x] Require two startup calls on the same retained child.
- [x] Add heartbeat AI readiness/success/failure/restart evidence.
- [x] Extend activation observation budget for bounded startup.
- [x] Pin lazy ByteTrack dependency and disable runtime auto-install.
- [x] Reset systemd failed/start-limit state before automatic restore.
- [x] Pass exact source/quality/package checks on final remediation heads.
- [x] Reach sustained accepted production Worker progression under Issue #159.

## Completion gate

- [x] AI inference is bounded and supervised.
- [x] Activation requires AI-ready + frame/state progression.
- [x] Dependency closure is deterministic before service.
- [x] Failed candidates restore exact prior runtime.
- [x] Supporting remediation accepted as part of closed Issue #159.
