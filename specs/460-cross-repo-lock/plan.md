# Plan: Cross-repo GPU-box deploy lock for Ubuntu worker deploys (T8b)

- Issue: #460
- Specification: specs/460-cross-repo-lock/spec.md

## Implementation approach

1. RECON-established facts: `deploy/worker/ubuntu/deploy-authorized.sh` IS the on-box mutation path (root, EUID check; invocation chain .github/workflows/deploy-ubuntu-worker.yml → VPS ProxyJump → forced command `sea-speed-ubuntu-zero-touch-gate` → deploy-authorized.sh); the repo-internal transaction lock sat on fd 8 — conflicting with the shared contract's fd 8 = cross-repo; the first host mutation is `install -d "$updater_root"`; the VPS privileged helper is Auth-v1-only and performs no GPU-box worker mutations, so deploy-authorized.sh is the single cross-repo acquisition point; the content contract (content PR #14, 9d96373) is the 4-line lock block with the byte-exact contention message.
2. Tests-first static battery: add `UbuntuWorkerGpuBoxDeployLockTests` (5 methods) to `tests/test_ubuntu_worker_deploy_authorized.py` pinning the path constant, byte-exact contention message, acquisition command order, lock-before-first-mutation and the fd 8/9 layout — RED against base 7de5a29 (all five markers structurally absent from the base script); RED authenticity on the final state proven by mutation (contention-string mutation and flock-after-first-mutation each fail the named test).
3. Implementation: insert the lock block (BEGIN/END markers) after the required-commands check and BEFORE the first `install -d` (touch umask 000 → chmod 0666 belt-and-suspenders → exec 8< fail-closed → flock -n 8 fail-closed exit 6); renumber the internal updater lock fd 8 → 9; add the `AGENTS.md` "Cross-repo GPU-box deploy lock" subsection.
4. Verification battery: bash -n; behavioral harness (docker alpine for the foreign-owner case); contract byte-identity normalization vs content; focus suites 19 (14+5) and 37; validate_repo; validate_sdd; unicode-scan.

## Architecture

- Single cross-repo acquisition point: deploy-authorized.sh performs the worker mutations itself as root on the box, so the lock lives exactly where the mutations live; the sudo-privileged helper is VPS-side Auth v1 only.
- Fail-closed ordering: touch (umask 000 subshell) → chmod 0666 (belt-and-suspenders, failure non-fatal ONLY because open+flock below fails closed) → exec 8< (open failure exits 6 with the self-heal diagnostic) → flock -n 8 (contention exits 6) — all BEFORE the first `install -d`; the static ordering pin turns any regression into a named CI failure.
- Self-heal without bootstrap: /var/tmp persists across reboot and is mode 1777 on a standard Ubuntu, so the deploy user creates/owns the lock file itself; the umask-000 subshell makes 0666 umask-independent; flock works through a read-only fd even on 0644, so a stale root-owned 0644 file still works.
- No explicit unlock/cleanup: the kernel releases the flock when fd 8 closes, and fd 8 closes on every exit path (normal exit, error exits, signals); extra cleanup could be skipped by an early exit/trap and adds no guarantee.
- fd layout 8 = cross-repo, 9 = repo-internal — the content deploy-wrapper's layout; the fixed acquisition order (cross-repo first, then internal) excludes lock-order inversion/deadlock; the internal lock keeps path, 0600 mode, message and exit 6.
- Static pins extend the existing battery in its own style (module-level SCRIPT constant, setUp read, assertIn markers + index/assertLess ordering, no docstrings): 5 methods guard path, message, order, lock-before-mutation and fd layout.

## Decisions

- D-1: Adopt the content PR #14 contract byte-identically where it is observable on the box (lock path, 0666 mode, contention message, fd layout): the two repos must agree on diagnostics for unambiguous on-box triage, and a diverging contract would make contention handling repo-specific.
- D-2: /var/tmp over /run: /run is tmpfs (the original lock died at every reboot) while /var/tmp persists and is 1777 on a standard Ubuntu — the deploy user self-heals the file, no root bootstrap (content's own T8 follow-up migration, adopted here from the start).
- D-3: Non-blocking flock (`flock -n`): a deploy that would interleave fails fast (exit 6) instead of blocking a GitHub Actions job against an unknown-duration holder; serialization intent is preserved because the active deploy completes and the rejected side can retry.
- D-4: touch failure is a non-fatal WARNING: the open+flock below is the single fail-closed decider (e.g. a stale root-owned 0644 file still opens read-only and flocks); adding root bootstrap for that edge would widen the failure surface for no gain.
- D-5: Internal lock renumber fd 8 → 9 with everything else unchanged (path, chmod 0600, message, exit 6): file descriptors are per-process, so child scripts (update-exact.sh/rollback-exact.sh) are unaffected by construction.
- D-6: No explicit unlock or trap-based cleanup: kernel-managed flock release at fd close covers every exit path; a cleanup trap could itself be skipped and cannot improve the guarantee.
- D-7: The battery EXTENDS tests/test_ubuntu_worker_deploy_authorized.py rather than adding a new file: one deploy-contract battery keeps the existing 14 methods and file conventions untouched and the whole change reviewable as a single diff.
- D-8: RED authenticity is proven by MUTATION on the final state (string + ordering mutations) rather than by a base-revert run: the five pins assert markers that are structurally absent from base 7de5a29, and the mutation proofs demonstrate each guard fires on its exact regression direction.

## Affected contours

- UBUNTU_WORKER: `deploy/worker/ubuntu/deploy-authorized.sh` (cross-repo lock block + fd 8→9 renumber), `AGENTS.md` (contract subsection), `tests/test_ubuntu_worker_deploy_authorized.py` (5-method battery), this SDD trio (+ durable progress file outside the repo tree).
- No change to: child scripts update-exact.sh/rollback-exact.sh, rollback-code.sh, the content wrapper, deploy/vps/**, .github/workflows/**, worker/**.

## Validation

- bash -n on the full script (rc 0) and on the harness-extracted lock block (EXTRACTED_BLOCK_SYNTAX_OK, 35 lines); unittest test_shell_syntax ok.
- Behavioral harness (real lock block extracted via the BEGIN/END markers; docker alpine for the foreign-owner case; docker /var/tmp shared 1:1 verified by probe; fixtures rm-before-create so root-owned fixtures materialize): (a0) absent confirmed → (a1) acquired, no warning → (a2) created mode 666 owner 1000; (c1)(c2) two sequential acquisitions OK; (b1) holder = real lock block (fd 8 held) → second attempt rc 6 + byte-identical diagnostic; (b2) holder = flock CLI → same; (d1) fresh root:root 0644 → WARNING emitted, open+flock acquired; (d2) root:root 0666 → non-owner touch (uid 1000) refreshes mtime, mode/owner intact.
- Contract byte-identity: the 4 contract command lines normalized (variable renamed, declaration line excluded, handler style abstracted) → CONTRACT_CMD_LINES_IDENTICAL; the contention string grep-verified byte-identical and exactly once per file.
- RED authenticity: t8b-red-a (contention string → "sea-speed/content") fails test_cross_repo_gpu_box_lock_contention_message_is_byte_exact; t8b-red-b (flock -n 8 moved after the first install -d) fails test_cross_repo_gpu_box_lock_precedes_first_host_mutation ("6110 not less than 6075"); against base 7de5a29 all five contract markers are structurally absent (RED by construction).
- Suites: python3 -m unittest tests.test_ubuntu_worker_deploy_authorized → 19/19 OK (14 existing + 5 new); adjacent AGENTS.md-referencing suites (delivery_contract_convergence, delivery_resume_contract, delivery_terminal_states) → 37/37 OK.
- scripts/ci/validate_repo.py → "Sea Speed repository validation passed" (646 files); scripts/ci/validate_sdd.py → passed; unicode-scan on the changed files → 0 findings.

## Runtime feedback

- RF-001: Operator actions expected: 1 (on-box install copy + chmod over the forced-command path); live two-sided proof arrives with the next real sea-speed deploy; optional parallel-deploy drill documented on issue #460; orchestrator records the runtime acceptance.
- RF-002: Evidence: deploy logs carry the lock acquire/contention diagnostics; the contention diagnostic is byte-identical to content's; acceptance recorded on issue #460 + session log.

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from scripts/ci/validate_change_contract.py classify_file/derive_impact — the change gates the root Ubuntu worker deploy path (deploy/** → UBUNTU_WORKER) and renumbers an internal lock fd; Security impact declared LOW in the PR body (fail-closed concurrency gate; no new capability, no secret handling change, no sudo/exec widening).
- RISK-001 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: non-blocking fail-closed acquisition BEFORE the first host mutation with the byte-exact shared contention diagnostic; fixed acquisition order (cross-repo fd 8 → internal fd 9, identical to content) excludes deadlock; a rejected deploy exits 6 fast instead of queueing | Validation: harness b1/b2 (foreign holder → rc 6, byte-identical message, zero host mutations) + static ordering pin test_cross_repo_gpu_box_lock_precedes_first_host_mutation | Residual risk: LOW — the other repo's deploy is blocked for the duration of an active deploy; that is the intended serialization, and the non-blocking rejection keeps the failed side short | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: self-heal contract — persistent 1777 /var/tmp lets the deploy user create the file itself (no root bootstrap); umask-000 subshell makes 0666 umask-independent; a stale root-owned 0644 file degrades to a non-fatal WARNING with open+flock as the fail-closed decider; >30-day idle is self-healed by recreation on the next deploy | Validation: harness a0/a1/a2 (absent → 0666 + acquired), d1 (0644 fixture → WARNING + acquire), d2 (foreign-owner touch refreshes mtime) | Residual risk: LOW — a non-standard unwritable /var/tmp fails closed at open with an explicit self-heal diagnostic (remove the stale root-owned file; the next deploy recreates it) | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the fd renumber is local to deploy-authorized.sh (file descriptors are per-process); child scripts keep their own descriptors; the internal lock keeps path, 0600 mode, contention message and exit 6 | Validation: test_repo_internal_transaction_lock_uses_fd_9 (cross-open before internal-open before internal-flock) + update-exact suite 37 OK + test_shell_syntax | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: SEC | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the gate only rejects concurrency — no new capability, no sudo/exec widening, no secret handling change; the lock file is empty and world-readable by design (its only cross-user affordances are touch for mtime and flock through a read-only fd) | Validation: static contract battery (path constant + byte-exact message) + harness foreign-holder/foreign-owner scenarios | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_cross_repo_gpu_box_lock_precedes_first_host_mutation (flock -n 8 precedes the first install -d) + test_cross_repo_gpu_box_lock_acquisition_commands_present_in_order (touch → chmod 0666 → exec 8< → flock -n 8) + test_cross_repo_gpu_box_lock_contention_message_is_byte_exact + harness b1/b2
- TEST-002 | Covers: RISK-002 | Level: integration | Priority: P0 | Evidence: behavioral harness scenarios a0/a1/a2 (absent → created mode 666 owner 1000, acquired, no warning), d1 (stale root:root 0644 → non-fatal WARNING, open+flock acquired), d2 (foreign-owner touch refreshes mtime on 0666; docker alpine)
- TEST-003 | Covers: RISK-003 | Level: unit | Priority: P0 | Evidence: test_repo_internal_transaction_lock_uses_fd_9 (exec 9>, flock -n 9, unchanged internal message; cross-open before internal-open before internal-flock) + test_cross_repo_gpu_box_lock_uses_pinned_path_constant + update-exact suite 37 OK
- TEST-004 | Covers: RISK-004,NFR-001 | Level: unit | Priority: P0 | Evidence: test_cross_repo_gpu_box_lock_contention_message_is_byte_exact + RED authenticity by mutation (t8b-red-a contention-string mutation fails the byte-exact test; t8b-red-b flock-after-first-mutation fails the ordering test)
- TEST-005 | Covers: NFR-002,NFR-003 | Level: integration | Priority: P1 | Evidence: contract byte-identity normalization (CONTRACT_CMD_LINES_IDENTICAL) + full-script bash -n + unittest 19/19 + validate_repo (646 files) + validate_sdd
- TEST-006 | Covers: NFR-002 | Level: runtime-manual | Priority: P1 | Evidence: on-box install of the updated deploy-authorized.sh + live two-sided proof at the next real sea-speed deploy; optional parallel-deploy drill on issue #460 | Reason: requires the production GPU box; pre-merge proof is the behavioral harness

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: issue #460 + owner scope approval recorded in the delivery session (2026-10-12, T2+T8b+T7 batch, standing directive to proceed unless blocked); the changed-file scope (deploy-authorized.sh, AGENTS.md, test battery, SDD trio) enforced before the first write
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: adversarial peer review APPROVE (independent model family) before the commit; R1 static assertions folded into this PR; on the box the adopted gate acquires the cross-repo lock BEFORE the first host mutation (static pin test_cross_repo_gpu_box_lock_precedes_first_host_mutation)
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: prior repository state — the change is one bounded commit that lands whole or not at all; on the box the adopted gate rejects contention before any host mutation | Retry: NO | Rollback: git revert of 37ed77d restores the pre-T8b behavior (no cross-repo gate); the on-box lock file is plain persistent state needing no cleanup | Evidence: repository commit 37ed77d; diff --stat exactly 3 files (AGENTS.md +10, deploy-authorized.sh +43 −2, tests +37)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: behavioral harness 5 scenarios via docker alpine incl. foreign-owner mtime refresh; contract byte-identity of the 4 contract command lines vs content PR #14; focus suites 19 (14+5) and 37 green; RED proofs for string and ordering mutations; downstream verify-before/post-install probes unchanged
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: exact-green-head merge after required CI on the exact head (orchestrator-owned); release identity bound by the PR Change Contract (issue #460, PR #459)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond existing temporaries | Retry: NO | Rollback: NONE | Evidence: the lock block creates no temporaries and performs no cleanup (kernel releases the flock at fd 8 close on every exit path — no trap needed); the verification scratch tree lives outside the repository (tool-output), leaving the repo tree clean
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: PR #459 + issue #460 + durable delivery progress files (t8b, t8b-r1); deploy logs carry the lock acquire/contention diagnostics; no new evidence format on the box
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: revert of 37ed77d restores the pre-T8b path (no cross-repo gate); the on-box lock file needs no cleanup and self-heals; the internal fd renumber reverts with the same revert | Evidence: Rollback target in the PR Change Contract; automatic rollback is not authorized for the box transaction beyond the unchanged downstream fault paths
