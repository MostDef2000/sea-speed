# Tasks — #546 wave 2 follow-up: honest post_state coalescing

- Issue: #546
- Specification: specs/546-coalesce-followup/spec.md
- Plan: specs/546-coalesce-followup/plan.md
- Date: 2026-10-22

## Delivery tasks

- T-546-101 [DONE]: remove the dead `"event"` kept-block from `post_state` coalescing; drain stale items with paired `task_done()`; update the seam comment to the actual drop-stale semantics.
- T-546-102 [DONE]: add the behavioral coalescing test (full queue, stale items dropped, fresh state enqueued, `unfinished_tasks` balanced) with publish-thread and HTTP disabled via mocks.
- T-546-103 [DONE]: verify RED authenticity on base main @ 18b7c47 (test fails without the fix) and GREEN on the fix head (focused run 14 passed; ruff clean under scripts/quality/ruff.toml).
- T-546-104 [DONE]: SDD trio (this directory) synchronized with the exact changed-file scope.

## Completion gate

- [x] CI gate: full battery green on the exact PR head — orchestrator-owned. Evidence: required CI green on the exact PR head b70b336 (Repository validation incl. Change Contract validation, quality-integration; merge commit CI on 0139f3e8 6/6 success, run 39883264504 workflow)
- [x] merge gate: exact-green-head merge complete — orchestrator-owned. Evidence: PR #547 merged 2026-10-22 15:57 UTC as merge commit 0139f3e8ae52285f264b4a2e77875bc5ad2d8838 (exact-green-head)
- [x] deploy gate: exact-SHA Ubuntu worker deploy success (standing delegation; owner approved 2026-10-22) — orchestrator-owned. Evidence: deploy-ubuntu-worker.yaml run 39883264504 success 2026-10-23 01:19:26 UTC, deliveryId ubuntu-0139f3e8ae52-20261023T011926Z, manifest 6/6, on-box shared/config/active-source-commit=0139f3e8 (verified on GPU box)
- [x] runtime gate: acceptance probes (outbox drain, restart drain, 409 retain) recorded on #537 — orchestrator-owned. Evidence: probes P1 (drain of stale pending rows), P2 (restart drain), P3 (409 terminal retain), P4 (metrics unchanged), P5 (healthy publish byte-identity) recorded on issue #537 (2026-10-23)

## Requirements traceability

- AC-001 | Task: T-546-101,T-546-102 | Evidence: BoundedQueueAndPublishingTests.test_publish_queue_coalescing_drops_stale_and_balances — queue qsize == 1 and fresh marker present after a full-queue post_state | Coverage: COVERED
- AC-002 | Task: T-546-101,T-546-102 | Evidence: same test — unfinished_tasks == 0 after the fresh item is consumed and acknowledged (RED on base 18b7c47: unfinished_tasks accumulated because drained items never received task_done) | Coverage: COVERED
- AC-003 | Task: T-546-103 | Evidence: orchestrator diff inspection of the PR (exact changed-file scope: worker/ubuntu_worker_entrypoint.py, tests/test_detection_runtime_optimization.py, specs/546-coalesce-followup/**); protected suites stay green | Coverage: RUNTIME-MANUAL | Reason: zero-diff property is verified by review, not by an executable test

## Definition of Done

- [x] Issue/spec/plan/tasks current (issue #546 closed with verification record 2026-10-24; this sync reconciles tasks.md to the delivered state)
- [x] Exact changed-file scope verified (worker/ubuntu_worker_entrypoint.py, tests/test_detection_runtime_optimization.py, specs/546-coalesce-followup/**). Evidence: PR #547 diff matches exactly (worker/ubuntu_worker_entrypoint.py, tests/test_detection_runtime_optimization.py, specs/546-coalesce-followup/**); protected surfaces zero-diff (orchestrator-verified)
- [x] Required tests and evidence complete (RED authenticity on base 18b7c47 + GREEN focused run + ruff canon). Evidence: RED authenticity on base 18b7c47 verified (T-546-103); GREEN focused run 14 passed; ruff clean under scripts/quality/ruff.toml
- [x] CI gate: Required CI green on the exact PR head — orchestrator-owned. Evidence: required CI green on the exact PR head b70b336 (Repository validation incl. Change Contract validation, quality-integration; merge commit CI on 0139f3e8 6/6 success, run 39883264504 workflow)
- [x] merge gate: Exact-green-head merge complete — orchestrator-owned. Evidence: PR #547 merged 2026-10-22 15:57 UTC as merge commit 0139f3e8ae52285f264b4a2e77875bc5ad2d8838 (exact-green-head)
- [x] state gate: Deployment state resolved — exact-SHA Ubuntu worker deploy per the standing delegation — orchestrator-owned. Evidence: deploy-ubuntu-worker.yaml run 39883264504 success 2026-10-23 01:19:26 UTC, deliveryId ubuntu-0139f3e8ae52-20261023T011926Z, manifest 6/6, on-box shared/config/active-source-commit=0139f3e8 (verified on GPU box)
- [x] runtime gate: Runtime acceptance resolved — post-deploy probes recorded on #537 — orchestrator-owned. Evidence: probes P1 (drain of stale pending rows), P2 (restart drain), P3 (409 terminal retain), P4 (metrics unchanged), P5 (healthy publish byte-identity) recorded on issue #537 (2026-10-23)
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — Risk profile NOT REQUIRED (plan.md)
- [x] Waivers resolved or current — none
