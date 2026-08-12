# Tasks: Camera Preview Gallery

- Specification: specs/002-camera-preview-gallery/spec.md
- Plan: specs/002-camera-preview-gallery/plan.md
- Original Issue: #103
- Extension Issue: #109
- Status: Snapshot-stability remediation in progress under existing Outcome Authorization

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

#### Initial source implementation

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

#### Initial delivery and production gates

- [x] T109-12 Verify exact six-file branch diff against source main.
- [x] T109-13 Required PR Validation succeeds for exact head.
- [x] T109-14 Required Quality integration gate succeeds for exact head.
- [x] T109-15 Confirm no unresolved review threads and fresh head/base relationship.
- [x] T109-16 Merge exact green head under still-valid Outcome Authorization; no separate MERGE APPROVED token.
- [x] T109-17 Obtain production safety-envelope authorization for exact merged main `11306b23f3dd2fb21917a593c0e055911eefc6ff` before VPS mutation.
- [x] T109-18 Deploy exact merged VPS release `11306b23f3dd2fb21917a593c0e055911eefc6ff`; Ubuntu preview relay remained untouched.
- [x] T109-19 Verify Camera 1 baseline before and after rollout.
- [x] T109-20 Verify idle gallery/API baseline and one-active server policy.

#### Visual acceptance finding and remediation

- [x] T109-21 Run Preview All visual acceptance and capture runtime finding: some canvases were retained before camera images fully formed.
- [x] T109-22 Identify root cause in browser orchestration: first-frame readiness followed by fixed 1.2-second dwell is too early for some streams.
- [x] T109-23 Replace fixed post-ready dwell with bounded `video.currentTime` progression gate: at least 3 seconds of media advancement before automatic batch `drawImage()`.
- [x] T109-24 Keep a 12-second stabilization timeout and continue to the next camera if playback does not advance enough.
- [x] T109-25 Add focused regression assertions for progression gating and removal of the 1.2-second dwell.
- [x] T109-26 Update spec/plan/tasks/quickstart with the runtime finding and remediation behavior.
- [ ] T109-27 Verify remediation branch diff remains inside the exact six-file Outcome Authorization scope.
- [ ] T109-28 Required PR Validation succeeds for the remediation exact head.
- [ ] T109-29 Required Quality integration gate succeeds for the remediation exact head.
- [ ] T109-30 Confirm no unresolved review threads and fresh head/base relationship.
- [ ] T109-31 Merge exact green remediation head under the still-valid Outcome Authorization; no separate MERGE APPROVED token.

#### Remediation production and final acceptance

- [ ] T109-32 Obtain a fresh production safety-envelope authorization for the new exact merged main SHA; prior production authorization was bound to `11306b23f3dd2fb21917a593c0e055911eefc6ff`.
- [ ] T109-33 Deploy the new exact VPS release; Ubuntu preview relay remains untouched.
- [ ] T109-34 Verify Camera 1 baseline before and after remediation rollout.
- [ ] T109-35 Verify Preview All waits for real playback progression and representative retained frames are visually formed rather than gray/partial startup frames.
- [ ] T109-36 Verify Stop All prevents further batch starts and leaves no active server preview while already retained frames remain visible.
- [ ] T109-37 Verify manual switch/stop retains prior successful frame.
- [ ] T109-38 Verify page reload clears all retained frames and no persistence is created.
- [ ] T109-39 Record final runtime/visual acceptance evidence in Issue #109 and mark COMPLETE.

## Completion gate for Issue #109

- [ ] Exact six-file source scope only across the feature and remediation work.
- [ ] Required CI green on exact remediation merged source.
- [ ] Remediation production rollout separately authorized and exact-SHA bound.
- [ ] Sequential Preview All visually identifies representative cameras with stable retained last frames after real playback progression.
- [ ] Stop All returns backend preview state to idle and prevents further traversal.
- [ ] Manual preview preserves the last successful frame after switch/stop.
- [ ] Retained frames disappear on reload and are not persisted.
- [ ] Camera failures remain isolated.
- [ ] Camera 1 accepted public live path remains unchanged and healthy.
- [ ] Runtime evidence verdict recorded before `COMPLETE`.
