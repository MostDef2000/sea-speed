# Tasks: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Plan: specs/002-camera-preview-gallery/plan.md
- Original Issue: #103
- Extension Issue: #109
- Status: Approved extension implementation

## Delivery tasks

### Original gallery delivery

- [x] T001 Preserve the current operator frontend behavior while adding `Камеры` navigation.
- [x] T002 Add the responsive `/sea-speed/cameras/` runtime-catalog gallery with one active HLS player.
- [x] T003 Add additive camera catalog and on-demand preview API endpoints.
- [x] T004 Enforce catalog-only source selection, private credential-free relay validation, one active preview and hard TTL.
- [x] T005 Add a dedicated Ubuntu source-on-demand preview relay helper without touching Camera 1 service/config.
- [x] T006 Add Cameras page install/rollback/smoke handling to VPS deployment.
- [x] T007 Add focused deterministic tests for UI, API, relay safety and deployment integration.
- [x] T008 Keep exact changed-file scope synchronized with Issue #103 and the PR Change Contract.
- [x] T009 Merge original implementation and release-artifact recovery after required CI.
- [x] T010 Activate the dedicated Ubuntu preview relay from protected runtime inventory and install sanitized VPS catalog.
- [x] T011 Deploy accepted Camera Preview Gallery source to VPS.
- [x] T012 Remediate HLS public-serving permissions by creating preview session directories as mode `0755`.
- [x] T013 Complete technical runtime acceptance: catalog, representative start/switch/stop, public HLS and Camera 1 regression check.
- [x] T014 Complete visual acceptance of moving preview video and switching; close Issue #103.

### Issue #109 - Sequential Preview All + retained last frames

#### Source implementation

- [x] T109-01 Record exact six-file Outcome Contract and `OUTCOME APPROVED` authorization in canonical Issue #109.
- [x] T109-02 Keep existing backend/API/Ubuntu relay/Camera 1/AI contours outside source scope.
- [x] T109-03 Add global `Предпросмотр всех` and `Остановить все` controls with visible progress/current camera.
- [x] T109-04 Implement sequential catalog traversal through the existing one-active preview start/stop API.
- [x] T109-05 Add generation-token cancellation so Stop All prevents later batch traversal and cleans up late start responses.
- [x] T109-06 Keep camera-card DOM stable and capture the latest decodable live video frame into the card canvas before switch/stop.
- [x] T109-07 Make manual Play/Switch/Stop preserve last successfully decoded frames too.
- [x] T109-08 Keep retained frames volatile to the current page only; do not use localStorage, sessionStorage, IndexedDB, Cache API, server snapshot files or database persistence.
- [x] T109-09 Continue batch traversal after per-camera start/readiness failures and show the error only on the affected card.
- [x] T109-10 Add focused regression tests for sequential batch control, last-frame capture, cancellation, failure continuation and storage boundaries.
- [x] T109-11 Update spec/plan/tasks/quickstart for the accepted extension behavior and runtime acceptance plan.

#### Delivery gates

- [ ] T109-12 Verify exact six-file branch diff against source main.
- [ ] T109-13 Required PR Validation succeeds for exact head.
- [ ] T109-14 Required Quality integration gate succeeds for exact head.
- [ ] T109-15 Confirm no unresolved review threads and fresh head/base relationship.
- [ ] T109-16 Merge exact green head under still-valid Outcome Authorization; no separate MERGE APPROVED token.

#### Production and runtime acceptance

- [ ] T109-17 Obtain separate production safety-envelope authorization for exact merged main before VPS mutation.
- [ ] T109-18 Deploy exact merged VPS release; Ubuntu preview relay remains untouched.
- [ ] T109-19 Verify Camera 1 baseline before and after rollout.
- [ ] T109-20 Verify idle gallery starts no preview.
- [ ] T109-21 Verify Preview All progresses serially and successful cards retain last frames while at most one server preview is active.
- [ ] T109-22 Verify Stop All prevents further batch starts and leaves no active server preview while already retained frames remain visible.
- [ ] T109-23 Verify manual switch/stop retains prior successful frame.
- [ ] T109-24 Verify page reload clears all retained frames and no persistence is created.
- [ ] T109-25 Record runtime/visual acceptance evidence in Issue #109 and mark COMPLETE.

## Completion gate for Issue #109

- [ ] Exact six-file source diff only.
- [ ] Required CI green on exact merged source.
- [ ] Production rollout separately authorized and exact-SHA bound.
- [ ] Sequential Preview All visually identifies representative cameras with retained last frames.
- [ ] Stop All returns backend preview state to idle and prevents further traversal.
- [ ] Manual preview preserves the last successful frame after switch/stop.
- [ ] Retained frames disappear on reload and are not persisted.
- [ ] Camera failures remain isolated.
- [ ] Camera 1 accepted public live path remains unchanged and healthy.
- [ ] Runtime evidence verdict recorded before `COMPLETE`.
