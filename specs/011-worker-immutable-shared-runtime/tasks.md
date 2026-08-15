# Tasks: Immutable shared Ubuntu Worker runtime

Status: Active
Issue: #170
Specification: `specs/011-worker-immutable-shared-runtime/spec.md`

## Delivery tasks

- [x] Record the approved 15-path Implementation Scope Check in Issue #170.
- [x] Receive `OUTCOME APPROVED` after the recorded scope.
- [x] Revalidate exact `main` and create a fresh implementation branch.
- [x] Add canonical `runtime-lock.json` and deterministic runtime fingerprinting.
- [x] Add `prepare-runtime.sh` with ready reuse, legacy local adoption, persistent cache and atomic publication.
- [x] Change manual source preparation to record `runtime-id` instead of creating a per-SHA heavy venv.
- [x] Bind systemd to exact source SHA plus exact runtime ID.
- [x] Update exact activation to verify and report source/runtime binding while retaining the runtime progression gate and automatic restoration.
- [x] Make explicit rollback runtime-aware while retaining legacy per-release rollback safety.
- [x] Add focused shared-runtime, installer, updater, systemd and rollback contract tests.
- [x] Add SDD specification, plan and task tracking.
- [x] Confirm the exact branch diff is limited to the approved 15 paths.
- [x] Open PR #171 with valid Change Contract and `Specification: specs/011-worker-immutable-shared-runtime/spec.md`.
- [ ] Obtain PR Validation and Quality integration success on the exact PR head.
- [ ] Resolve any CI/review findings without expanding scope.
- [ ] Revalidate main/head/scope/reviews and merge with expected-head protection.
- [ ] Verify fresh post-merge exact-SHA quality gates.
- [ ] Request separate exact-SHA production authorization for the Ubuntu Worker contour.
- [ ] First production migration: adopt/reuse the local compatible runtime with no heavyweight network reinstall, prove exact source/runtime unit binding and pass sustained runtime gate.
- [ ] Record production evidence on Issue #170.
- [ ] On a subsequent source-only Worker rollout with the same runtime definition, prove `RUNTIME_REUSED` and zero heavyweight dependency installation/download before closing the steady-state acceptance item.

## Completion gate

Source delivery is complete only when the approved 15-path diff passes required exact-head CI, merges with expected-head protection and fresh post-merge gates pass. Production migration remains incomplete until a separately authorized exact merged SHA is activated with local runtime adoption/reuse and sustained Worker acceptance. The architecture's steady-state performance acceptance additionally requires evidence from a later source-only rollout that the same ready runtime is reused without package installation or heavyweight dependency download.
