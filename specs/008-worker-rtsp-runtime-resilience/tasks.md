# Tasks: Worker RTSP Runtime Resilience

- Specification: specs/008-worker-rtsp-runtime-resilience/spec.md
- Plan: specs/008-worker-rtsp-runtime-resilience/plan.md
- Issue: #159

## Delivery tasks

- [x] T001 Add an Ubuntu-only FFmpeg RTSP entrypoint with TCP transport, bounded frame reads, redacted logging, and bounded subprocess recreation while delegating non-RTSP input to the existing worker.
- [x] T002 Point the Ubuntu Worker systemd unit at the resilient entrypoint without changing detection/tracking/calibration logic.
- [x] T003 Pin critical top-level Worker runtime dependencies and require the exact CUDA 13.0 torch/torchvision pair before release preparation completes.
- [x] T004 Add an exact-SHA heartbeat progression verifier for frame and state-post counters.
- [x] T005 Strengthen `update-exact.sh --activate` so the active marker moves only after progression and the previous unit/service is restored automatically on candidate failure.
- [x] T006 Update focused Worker RTSP, manual-install, and exact-updater contract tests for the new runtime architecture and preserve calibration ownership assertions.
- [ ] T007 Obtain green PR validation, quality integration, and Worker package gates for the exact branch head.
- [ ] T008 Merge with expected-head protection and obtain green post-merge gates on the exact release SHA.
- [ ] T009 After fresh exact-SHA production authorization, roll out Worker first and record sustained frame/state progression plus clean AI-frame acceptance.
- [ ] T010 Roll out VPS frontend on the same exact SHA and record browser acceptance for persistent single-owner ROI/A/B geometry.

## Completion gate

- [x] Requirements are covered by tasks.
- [x] Spec, plan and tasks match the implemented behavior.
- [ ] Required CI is green.
- [ ] Separate merge approval is present.
- [ ] Applicable deployment/runtime acceptance is complete, or explicitly NOT REQUIRED.
- [ ] Runtime learning and deferred work are written back to the feature artifacts.
