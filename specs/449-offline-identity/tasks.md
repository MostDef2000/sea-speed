# Tasks: Productive offline service-identity derivation + #448-review hardening pins

- Specification: specs/449-offline-identity/spec.md

## Delivery tasks

- T-449-001: RECON the derivation function (systemctl cat bus dependency),
  the caller field order, the #448 review findings (F1/F2/F3a residual
  semantics), the existing battery harness, and the runbook subsection;
  read issue #449 + scope-update comment 6098207117; record in the durable
  progress file
- T-449-002: Extend tests/test_mediamtx_activate_identity.py to the on-disk
  harness (path-root substitution with literal assertions, longest-first;
  bus-fail-for-everything systemctl stub) and add the #449 cases (offline
  parse, precedence, drop-in dir, whitespace, symlink refusal, structural
  pins); record RED on base 1ede018 with the final file cmp-verified
  (15 failed / 4 passed, exact names in the delivery transcript)
- T-449-003: Implement camera-relay.sh derive_relay_service_identity: direct
  on-disk unit read (three standard paths, first readable regular
  non-symlink wins), drop-in merge (lexical, newline-separated), whitespace-
  tolerant seds; refusal path byte-unchanged
- T-449-004: Update the runbook identity-derivation subsection (on-disk
  parse, грабля №27, bounded limitations)
- T-449-005: Write the SDD trio specs/449-offline-identity/ (REQUIRED risk
  profile; RISK-001..004; TEST-001..005; TX-001..008; AC traceability; DoD
  with the 1 operator on-box verification)
- T-449-006: Run the verification battery (full pytest, ruff, bash -n,
  seven-mode harness empty diff, validate_sdd event) and commit locally
  with the approved author identity; leave the branch unpushed for
  orchestrator admission

## Completion gate

- [x] T-449-001
- [x] T-449-002
- [x] T-449-003
- [x] T-449-004
- [x] T-449-005
- [x] T-449-006
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 15 failed / 4 passed on base 1ede018 with the final test file byte-identical via cmp + full suite green on branch; worker-recorded; PR peer review and exact-head CI are orchestrator-owned)
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (worker script deploys with the repo source)
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box verification of the productive offline path under chroot (no config mutation expected; derived INSTALL_OWNER=root:mediamtx MODE=0640 with the bus unavailable recorded per issue #449)
- [x] Deferred work recorded — specs/447-activate-identity/plan.md D-3 wording reconciliation (issue #449 F1, "may ride") is outside this unit's allowed paths; recorded here for a future doc-slice
- [x] Risks resolved or explicitly accepted — RISK-001..004 mitigated in plan.md Risk profile
- [x] Waivers resolved or current — none

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 15 failed / 4 passed on base 1ede018, final file cmp-verified + full suite green on branch; PR peer review APPROVE is merge-phase, orchestrator-owned)
- [ ] Required CI green — exact-head PR CI — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box verification with recorded output
- [x] Deferred work recorded — F1 plan.md wording reconciliation deferred (outside allowed paths)
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-004 in plan.md Risk profile (all MITIGATED)
- [x] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-449-003,T-449-002 | Evidence: test_chroot_show_and_cat_fail_parses_on_disk_unit_file (show AND cat fail, readable on-disk unit → root:mediamtx 0640 — the exact RF-001 chroot shape) + test_offline_unit_path_precedence_etc_wins + test_offline_unit_path_precedence_falls_through_to_lib + test_offline_drop_in_directory_last_assignment_wins + test_offline_branch_does_not_call_systemctl_cat (the bus-dependent call is gone from the executable body) + test_offline_branch_reads_standard_unit_paths_in_order | Coverage: COVERED
- AC-2 | Task: T-449-003,T-449-002 | Evidence: test_both_derivations_fail_closed (explicit refusal ERROR + rc 1, no IDENTITY output) + test_offline_symlinked_unit_is_refused + test_identity_derivation_precedes_any_mutation (refusal point precedes backup AND install — unchanged ordering) | Coverage: COVERED
- AC-3 | Task: T-449-002,T-449-003 | Evidence: test_caller_read_field_order_is_pinned (exact `read -r install_owner install_group install_mode <<< "$identity"` line, #448 F2) + test_offline_whitespace_after_equals_is_tolerated + test_whitespace_tolerant_captures_are_pinned (both captures tolerate optional whitespace after `=`, #448 F3a, RED-first behavioral case) | Coverage: COVERED
- AC-4 | Task: T-449-002,T-449-004,T-449-006 | Evidence: RED on base 1ede018 — the extended battery fails 15 / passes 4 with the final file cmp-verified (exact names in the durable progress file and the delivery transcript) — and passes 19/19 on the branch; full pytest suite green; runbook subsection updated (on-disk parse + грабля №27 + bounded limitations); this SDD trio | Coverage: COVERED
