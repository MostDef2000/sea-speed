# Tasks: Activate service-identity derivation must fail closed

- Specification: specs/447-activate-identity/spec.md

## Delivery tasks

- T-447-001: RECON the activate block (silent-fallback derivation at
  420-434, exit-code map, mutation ordering), the established
  extractable-function + stubbed-systemctl test pattern, and docs coverage;
  read issue #447 and record the incident in the durable progress file
- T-447-002: Write the RED-first battery tests/test_mediamtx_activate_identity.py
  (8 derivation execution cases with stubbed systemctl/id + 3 structural
  contract pins); record RED on base 80bcb0e (10 failed / 1 passed, exact
  names in the delivery transcript) with the counts guard passing by
  construction
- T-447-003: Implement camera-relay.sh: extractable
  `derive_relay_service_identity` function (systemctl show definitive →
  unit file via systemctl cat with last-assignment parsing → explicit
  refusal), fail-closed caller (`|| exit 9`) replacing the silent fallback,
  and INSTALL_OWNER/MODE evidence before the install; derivation stays
  before the backup (zero mutation before identity is known)
- T-447-004: Append the "Relay service identity derivation" runbook
  subsection (incident one-liner, derivation order, chroot note, fail-closed
  contract, evidence lines) to docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md
- T-447-005: Write the SDD trio specs/447-activate-identity/ (spec, plan
  with REQUIRED risk profile + 8-stage TX audit, tasks with traceability and
  DoD)
- T-447-006: Run the verification battery (RED re-confirmed with the final
  test file cmp-verified on red-base-447, full pytest, ruff, bash -n,
  seven-mode byte-identity harness diff empty, `validate_sdd.py --event`)
  and commit locally with the approved author identity; leave the branch
  unpushed for orchestrator admission

## Completion gate

- [x] T-447-001
- [x] T-447-002
- [x] T-447-003
- [x] T-447-004
- [x] T-447-005
- [x] T-447-006
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 10 failed / 1 passed on base 80bcb0e with the final test file byte-identical via cmp + full suite green on branch; worker-recorded; PR peer review and exact-head CI are orchestrator-owned)
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (shell change deploys with the repo source on the worker)
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box verification transaction (dry activate or equivalent derived-owner check confirming root:mediamtx 0640; output recorded per issue #447)
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-003 mitigated in plan.md Risk profile
- [x] Waivers resolved or current — none

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 10 failed / 1 passed on base 80bcb0e, final file cmp-verified + full suite green on branch; PR peer review APPROVE is merge-phase, orchestrator-owned)
- [ ] Required CI green — exact-head PR CI — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box verification transaction with recorded output
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-003 in plan.md Risk profile (all MITIGATED)
- [x] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-447-003,T-447-002 | Evidence: test_both_derivations_fail_closed (rc 1, explicit "refusing to install with guessed ownership" ERROR, no IDENTITY output) + test_unit_file_group_unresolvable_fails_closed (non-root group unresolvable → refuse) + test_chroot_show_unavailable_falls_back_to_unit_file (empty systemctl show answer is never trusted as root — the unit file is derived instead) + test_shell_is_valid_and_contracts_fail_closed_derivation (old silent-fallback markers pinned absent; `identity="$(derive_relay_service_identity)" || exit 9` present) + test_identity_derivation_precedes_any_mutation (refusal point precedes backup AND install) | Coverage: COVERED
- AC-2 | Task: T-447-003,T-447-002 | Evidence: test_shell_is_valid_and_contracts_fail_closed_derivation (INSTALL_OWNER=%s:%s and MODE=%s evidence lines pinned) + test_show_user_mediamtx_derives_group_from_show / test_chroot_show_unavailable_falls_back_to_unit_file (IDENTITY=root mediamtx 0640 → the caller prints INSTALL_OWNER=root:mediamtx + MODE=0640 before the install) | Coverage: COVERED
- AC-3 | Task: T-447-003,T-447-002 | Evidence: test_activate_flow_unchanged_pins_hold (verify-reader-auth == 5, CANDIDATE_SHA256 == 3, MUTATIONS == 3, --expected-sha256, systemctl restart, "automatic rollback is not authorized" — no pin count changes, no new renderer invocations) + test_show_explicit_root_keeps_root_root_0600 + test_chroot_unit_without_user_means_root (definitive-answer semantics preserved) + seven-mode byte-identity harness diff empty (renderer untouched) | Coverage: COVERED
- AC-4 | Task: T-447-002,T-447-006 | Evidence: RED on base 80bcb0e — tests/test_mediamtx_activate_identity.py fails 10 / passes 1 (all 8 derivation execution cases + 2 structural pins; exact names recorded in the durable progress file and the delivery transcript) — and the battery passes 11/11 on the branch; full pytest suite green; this SDD trio with the plan.md deployment transaction audit | Coverage: COVERED
