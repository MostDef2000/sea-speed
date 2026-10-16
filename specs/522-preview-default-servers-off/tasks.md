# Tasks: #522 — preview relay: explicitly disable unused mediamtx default servers

- Specification: specs/522-preview-default-servers-off/spec.md

## Delivery tasks

- [x] T-1: renderer — add `api: false / metrics: false / pprof: false / playback: false / moq: false` to the `ubuntu-preview-relay` render skeleton (R-1, R-2); nothing else changes
- [x] T-2: tests — synchronize golden byte-config, legacy-parity oracle, re-render byte-identity and the api-less negative pin; add positive per-toggle pin (R-3, R-4, R-5)
- [x] T-3: docs — CAMERA_PREVIEW_RELAY.md render contract + :8892 disposition note
- [ ] T-4: PR Change Contract (exact file match, CONTROL_PLANE, risk REQUIRED), CI green on exact head, merge
- [ ] T-5: lane-A worker deploy of the exact merged head (DEPLOY-TRIGGER + owner gate)
- [ ] T-6: lane-B sysadmin tx (step 0 version/digest evidence → prepare → activate → ss verification → backup cleanup) + evidence on #522

## Completion gate

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [ ] Deferred work recorded
- [ ] Risks resolved or explicitly accepted
- [ ] Waivers resolved or current

## Requirements traceability

- AC-001 | Task: T-1, T-2, T-3 | Evidence: focused suite green; renderer diff reviewed | Coverage: COVERED
- AC-002 | Task: T-2, T-4 | Evidence: full battery + validate_sdd + validate_repo tails in PR | Coverage: COVERED
- AC-003 | Task: T-4 | Evidence: Change Contract validation + CI run on exact head | Coverage: COVERED
- AC-004 | Task: T-5, T-6 | Evidence: lane-B tx ss/service/digest evidence on #522 | Coverage: RUNTIME-MANUAL | Reason: on-box state is reachable only through the sysadmin session (lane B)

## Definition of Done

- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current
