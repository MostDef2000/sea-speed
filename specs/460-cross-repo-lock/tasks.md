# Tasks: Cross-repo GPU-box deploy lock for Ubuntu worker deploys (T8b)

- Specification: specs/460-cross-repo-lock/spec.md

## Delivery tasks

- T-460-001: RECON the deploy path (deploy-authorized.sh as the on-box mutation path; internal lock on fd 8 conflicting with the shared contract; first host mutation install -d; the content PR #14 lock contract; issue #460); record in the durable progress file
- T-460-002: Author the static contract battery UbuntuWorkerGpuBoxDeployLockTests (5 methods: path constant, byte-exact contention message, acquisition command order, lock-before-first-mutation, fd layout) from the content PR #14 contract — RED against base 7de5a29 (all five markers structurally absent from the base script); RED authenticity on the final state proven by mutation (contention-string mutation → byte-exact test fails; flock moved after the first install -d → ordering test fails, "6110 not less than 6075")
- T-460-003: Implement the cross-repo lock block in deploy/worker/ubuntu/deploy-authorized.sh (touch umask 000 → chmod 0666 belt-and-suspenders → exec 8< fail-closed → flock -n 8 fail-closed exit 6, byte-exact contention message) BEFORE the first host mutation; renumber the internal updater lock to fd 9; add the AGENTS.md "Cross-repo GPU-box deploy lock" subsection
- T-460-004: Adversarial peer review (independent model family): fd renumber completeness, bypass-path audit of the deploy transaction, contract byte-identity to content PR #14 — APPROVE; two low-severity observations resolved by folding R1 (static CI assertions) into this PR
- T-460-005: Run the verification battery: bash -n; behavioral harness (docker alpine) 5 scenarios incl. foreign-owner mtime refresh; contract byte-identity of the 4 contract command lines; focus suites tests/test_ubuntu_worker_deploy_authorized.py 14+5=19 OK and update-exact 37 OK; validate_repo (646 files); validate_sdd; unicode-scan
- T-460-006: Write the SDD trio specs/460-cross-repo-lock/ (REQUIRED risk profile; RISK-001..004; TEST-001..006; TX-001..008; AC traceability; DoD with the 1 operator on-box transaction) and keep the PR Change Contract synchronized with the exact diff

## Completion gate

- [x] T-460-001
- [x] T-460-002
- [x] T-460-003
- [x] T-460-004
- [x] T-460-005
- [x] T-460-006
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED proofs + behavioral harness 5 scenarios + suites 19 and 37 green + validate_repo/validate_sdd; worker-recorded; PR peer review APPROVE recorded; exact-head CI is orchestrator-owned)
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (on-box install of the updated deploy-authorized.sh per the Rollout order)
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box transaction (install copy + chmod; live two-sided proof with the next real sea-speed deploy; optional drill on issue #460)
- [x] Deferred work recorded — none: the content-side wrapper is already merged (content PR #14); the on-box install and live two-sided proof are post-merge rollout steps in the Rollout order, not deferred code work
- [x] Risks resolved or explicitly accepted — RISK-001..004 mitigated in plan.md Risk profile
- [x] Waivers resolved or current — none

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED authenticity by mutation on the final state + behavioral harness 5 scenarios via docker alpine + suites 14+5=19 and 37 green + validate_repo 646 files + validate_sdd; PR peer review APPROVE; exact-head PR CI is merge-phase, orchestrator-owned)
- [ ] Required CI green — exact-head PR CI — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (operator installs the updated deploy-authorized.sh on the GPU box)
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box transaction with recorded output (live two-sided proof at the next real sea-speed deploy; optional parallel-deploy drill on issue #460)
- [x] Deferred work recorded — none (out-of-scope items recorded in the spec Scope section)
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-004 in plan.md Risk profile (all MITIGATED)
- [x] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-460-002,T-460-003 | Evidence: test_cross_repo_gpu_box_lock_contention_message_is_byte_exact (byte-exact shared contention message) + test_cross_repo_gpu_box_lock_precedes_first_host_mutation (flock -n 8 precedes the first install -d) + harness b1/b2 (foreign holder → rc 6 + byte-identical diagnostic before any host mutation) | Coverage: COVERED
- AC-2 | Task: T-460-003,T-460-005 | Evidence: harness a0/a1/a2 (absent → created mode 666 owner 1000, acquired, no warning) + d1 (fresh root:root 0644 → non-fatal WARNING, open+flock acquired) + d2 (foreign-owner touch refreshes mtime on the 0666 file; docker alpine) + test_cross_repo_gpu_box_lock_uses_pinned_path_constant + test_cross_repo_gpu_box_lock_acquisition_commands_present_in_order (touch umask 000 → chmod 0666 → exec 8< → flock -n 8) | Coverage: COVERED
- AC-3 | Task: T-460-003,T-460-002 | Evidence: test_repo_internal_transaction_lock_uses_fd_9 (exec 9> on the unchanged internal path, flock -n 9 with the unchanged internal message, cross-repo open before internal open before internal flock) + child-script suites (update-exact 37 OK — fd renumber is local to deploy-authorized.sh, per-process fds) + test_shell_syntax | Coverage: COVERED
- AC-4 | Task: T-460-002,T-460-005 | Evidence: the 5-method static battery green in the full file run (19/19) + RED authenticity by mutation (t8b-red-a: contention-string mutation → byte-exact test fails; t8b-red-b: flock moved after the first install -d → ordering test fails, "6110 not less than 6075") + contract byte-identity normalization (CONTRACT_CMD_LINES_IDENTICAL) | Coverage: COVERED
