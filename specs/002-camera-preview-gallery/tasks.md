# Tasks: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Plan: specs/002-camera-preview-gallery/plan.md
- Issue: #103
- Status: Release recovery before production rollout

## Delivery tasks

- [x] T001 Preserve the current operator frontend behavior while adding `Камеры` navigation.
- [x] T002 Add the responsive `/sea-speed/cameras/` runtime-catalog gallery with one active HLS player.
- [x] T003 Add additive camera catalog and on-demand preview API endpoints.
- [x] T004 Enforce catalog-only source selection, private credential-free relay validation, one active preview and hard TTL.
- [x] T005 Add a dedicated Ubuntu source-on-demand preview relay helper without touching Camera 1 service/config.
- [x] T006 Add Cameras page install/rollback/smoke handling to VPS deployment.
- [x] T007 Add focused deterministic tests for UI, API, relay safety and deployment integration.
- [x] T008 Keep exact changed-file scope synchronized with Issue #103 and the PR Change Contract.

### Release tasks

- [x] T009 Required PR Validation and Quality integration gate succeed for the original implementation PR exact head.
- [x] T010 Obtain separate merge approval and merge the original implementation exact approved head.
- [x] T011 Obtain separate production rollout authorization before Ubuntu/VPS runtime mutation.
- [ ] T012 Prepare and activate the dedicated Ubuntu preview relay from protected runtime inventory.
- [ ] T013 Install the sanitized catalog on the VPS and deploy an exact merged source whose release artifact includes the Cameras page.
- [ ] T014 Perform runtime acceptance: catalog, start, switch, stop/TTL, failure isolation and Camera 1 regression check.

### Pre-release recovery tasks

- [x] T015 Stop production rollout after detecting that the VPS exact artifact omitted `frontend/sea-speed/cameras/index.html`; no runtime mutation occurred.
- [x] T016 Remove the accidental empty `__NOOP__` file in the approved recovery branch.
- [x] T017 Make the Cameras page a required member of both VPS exact-artifact build and validation.
- [x] T018 Add regression coverage asserting that a newly built VPS artifact inventory contains the Cameras page.
- [ ] T019 Required PR Validation and Quality integration gate succeed for the exact recovery head.
- [ ] T020 Obtain separate merge approval for the exact green recovery head and merge it.
- [ ] T021 Verify post-merge exact-artifact/quality evidence for the new merge commit before resuming production rollout.

## Completion gate

- [ ] Gallery is idle with zero preview processes/source pulls.
- [ ] Selected camera preview visibly advances in the browser.
- [ ] Switching replaces the previous preview and Stop releases resources.
- [ ] Abandoned preview expires at the bounded TTL.
- [ ] Credentials do not leave protected Ubuntu runtime configuration.
- [ ] Camera 1 accepted public live path remains unchanged and healthy.
- [ ] VPS rollback includes the Cameras page.
- [ ] Exact VPS release artifact contains `frontend/sea-speed/cameras/index.html` for the deployed merge commit.
- [ ] Runtime evidence verdict is recorded before `COMPLETE`.
