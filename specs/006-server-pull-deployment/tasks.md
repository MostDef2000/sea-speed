# Tasks: Server-Pull Runtime Deployment Handoff

- Specification: specs/006-server-pull-deployment/spec.md
- Plan: specs/006-server-pull-deployment/plan.md
- Issue: #135

## Delivery tasks

- [x] T001 Supersede the earlier WSL-native-artifact Task Brief in Issue #135 with the approved server-pull outcome and exact five-file scope.
- [x] T002 Create a fresh branch from the current exact `main` SHA through the GitHub Connector.
- [x] T003 Advance `contracts/branches/project-manager.md` to 1.8.0 and define target-local server-pull/operator-handoff invariants.
- [x] T004 Advance `contracts/SEA_SPEED_DELIVERY_POLICY.md` to 1.8.0 and define exact-SHA server-pull as the default interactive VPS/Ubuntu-worker runtime transport.
- [x] T005 Add the `006-server-pull-deployment` specification, plan and task linkage.
- [ ] T006 Verify branch freshness and exact changed-file scope against current `main`.
- [ ] T007 Open one bounded PR with a valid Change Contract linked to Issue #135 and this specification.
- [ ] T008 Require PR Validation and Quality integration success on the exact final PR head.
- [ ] T009 Verify current `main`, exact diff and unresolved review threads, then merge the exact green head under `OUTCOME APPROVED` if scope/protected boundaries remain unchanged.
- [ ] T010 Record merge/CI evidence in Issue #135 and close it COMPLETE; no runtime deployment is required.

## Completion gate

- [x] Requirements are covered by tasks.
- [x] Spec, plan and tasks match the approved server-pull behavior.
- [x] Source authorization is `OUTCOME APPROVED` after the revised Implementation Scope Check; no separate legacy merge approval is required while scope and protected boundaries remain unchanged.
- [ ] Exact branch scope is the approved five files and is not behind current `main`.
- [ ] Required PR Validation and Quality integration are green on the exact final head.
- [ ] Exact green head is merged to current `main` with zero unresolved review threads.
- [x] Applicable deployment/runtime acceptance is explicitly NOT REQUIRED for this control-plane/contracts/SDD-only feature.
- [ ] Terminal Issue #135 evidence records the final merge SHA and control-plane completion state.
