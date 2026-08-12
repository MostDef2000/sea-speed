# Tasks: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Plan: specs/002-camera-preview-gallery/plan.md
- Issue: #103
- Status: Implementing

## Delivery tasks

- [ ] T001 Preserve the current operator frontend behavior while adding `Камеры` navigation.
- [ ] T002 Add the responsive `/sea-speed/cameras/` runtime-catalog gallery with one active HLS player.
- [ ] T003 Add additive camera catalog and on-demand preview API endpoints.
- [ ] T004 Enforce catalog-only source selection, private credential-free relay validation, one active preview and hard TTL.
- [ ] T005 Add a dedicated Ubuntu source-on-demand preview relay helper without touching Camera 1 service/config.
- [ ] T006 Add Cameras page install/rollback/smoke handling to VPS deployment.
- [ ] T007 Add focused deterministic tests for UI, API, relay safety and deployment integration.
- [ ] T008 Keep exact changed-file scope synchronized with Issue #103 and the PR Change Contract.

### Release tasks

- [ ] T009 Required PR Validation and Quality integration gate succeed for the exact PR head.
- [ ] T010 Obtain separate merge approval and merge the exact approved head.
- [ ] T011 Obtain separate production rollout authorization before Ubuntu/VPS runtime mutation.
- [ ] T012 Prepare and activate the dedicated Ubuntu preview relay from protected runtime inventory.
- [ ] T013 Install the sanitized catalog on the VPS and deploy exact merged source.
- [ ] T014 Perform runtime acceptance: catalog, start, switch, stop/TTL, failure isolation and Camera 1 regression check.

## Completion gate

- [ ] Gallery is idle with zero preview processes/source pulls.
- [ ] Selected camera preview visibly advances in the browser.
- [ ] Switching replaces the previous preview and Stop releases resources.
- [ ] Abandoned preview expires at the bounded TTL.
- [ ] Credentials do not leave protected Ubuntu runtime configuration.
- [ ] Camera 1 accepted public live path remains unchanged and healthy.
- [ ] VPS rollback includes the Cameras page.
- [ ] Runtime evidence verdict is recorded before `COMPLETE`.
