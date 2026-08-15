# Tasks: Calibration Overlay Ownership

- Specification: specs/007-calibration-overlay-ownership/spec.md
- Plan: specs/007-calibration-overlay-ownership/plan.md
- Issue: #159

## Delivery tasks

- [x] T001 Record failed production acceptance of the first Issue #159 frontend-only implementation and the revised mixed Outcome Contract.
- [x] T002 Receive fresh `OUTCOME APPROVED` for the revised seven-file scope and create a fresh branch from exact current `main`.
- [x] T003 Make frontend ROI/speed-line canvases persistently visible while limiting editing handles and pointer interaction to edit mode.
- [x] T004 Remove worker main-path ROI/speed-line drawing from the JPEG overlay used for latest state and event snapshots without changing computation paths.
- [x] T005 Add focused frontend/worker contract coverage for the single visual-owner behavior and preserved ROI/speed computation paths.
- [x] T006 Add this feature specification and implementation plan including mixed-contour compatibility, rollout and rollback order.
- [ ] T007 Verify complete branch files, syntax/structure, exact seven-file diff, `behind_by=0`, and absence of secrets/runtime artifacts.
- [ ] T008 Open one bounded PR linked to Issue #159 and `specs/007-calibration-overlay-ownership/spec.md` with production impact `MIXED`.
- [ ] T009 Require PR Validation and Quality integration success on the exact final PR head; remediate only within the approved seven-file scope if necessary.
- [ ] T010 Re-check current `main`, exact scope, reviews/threads and exact green head, then merge under the active Outcome Authorization.
- [ ] T011 Record the new merged exact `main` SHA and source evidence in Issue #159; do not mutate production until a fresh exact-SHA `PRODUCTION APPROVED` is supplied.
- [ ] T012 After separate production authorization, roll out worker first then VPS, collect exact runtime evidence, perform browser acceptance, write back runtime feedback, and close Issue #159 only on accepted evidence.

## Completion gate

- [x] Requirements are covered by tasks.
- [x] Spec, plan and tasks match the revised implemented behavior.
- [ ] Exact branch scope is the approved seven files and remains based on current `main`.
- [ ] Required PR Validation and Quality integration are green on the exact final head.
- [ ] Exact green head is merged with zero unresolved review threads.
- [ ] Separate exact-SHA production authorization is recorded before worker/VPS mutation.
- [ ] Worker and VPS deployment identities, rollback targets and runtime acceptance are complete.
- [ ] Runtime learning is written back and final product evidence verdict is `accepted` before Issue #159 is closed.
