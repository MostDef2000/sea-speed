# Tasks: Bounded prune of foreign unmarked loopback-API auth rules

- Specification: specs/436-sanitize-auth/spec.md

## Delivery tasks

- T-436-001: RECON the auth-rule machinery: renderer markers/parse/verify/ensure
  functions, the `_parse_rule_block` span-merge blind spot, camera-relay.sh
  prepare/activate transaction shape, existing renderer test batteries and
  the #372 forwarding pin, change-control classification for the changed-file
  set; record findings in the durable progress file
- T-436-002: Add the bounded scan/prune core to the canonical renderer
  (entry-segmenting scanner, indent-aware fail-closed field parser,
  `scan_foreign_auth_rules`/`count_foreign_auth_rules`/
  `sanitize_foreign_auth_rules` with exact-scope whitelist, byte-identity and
  foreign==0 post-conditions) and the `ubuntu-sanitize-auth` CLI mode
  (verify-before → prune → explicit foreign==0 → verify-after → 0600
  candidate); purely additive, all existing modes byte-identical
- T-436-003: Add the `camera-relay.sh sanitize` subcommand (usage, dispatch,
  transaction block: verify-reader-auth on LIVE → sanitize render → digest +
  root-only sha file → verify-reader-auth on CANDIDATE → evidence lines);
  keep the activate runbook unchanged
- T-436-004: Write the RED-first battery `tests/test_mediamtx_sanitize_auth.py`
  (scan counts, prune + marked-rule byte identity, fail-closed table, CLI
  transaction, shell pins); update the documented forwarding-count pin in
  `tests/test_mediamtx_multi_reader_ip.py` (2→4) with its reason
- T-436-005: Append the sanitize runbook to the "Ubuntu Worker relay API
  profile" section of docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md
  (scope, verify-before/after, transaction shape, no-auto-rollback contract)
- T-436-006: Run the verification battery (RED on base 095e4c9 recorded,
  full pytest, focused batteries, seven-mode byte-identity harness diff,
  `bash -n`, ruff on changed Python files, `validate_sdd.py --event`) and
  commit locally with the approved author identity; leave the branch unpushed
  for orchestrator admission

## Completion gate

- [x] T-436-001
- [x] T-436-002
- [x] T-436-003
- [x] T-436-004
- [x] T-436-005
- [x] T-436-006
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 16/16 on base 095e4c9 + full suite green on branch; worker-recorded; PR peer review and exact-head CI are orchestrator-owned)
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (renderer rides merge; shell change deploys with the repo source on the worker)
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box transaction (sanitize → digest → activate --expected-sha256, output recorded per issue #436)
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-003 mitigated in plan.md Risk profile
- [x] Waivers resolved or current — none

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 16/16 on base 095e4c9 + full suite green on branch; PR peer review APPROVE is merge-phase, orchestrator-owned)
- [ ] Required CI green — exact-head PR CI — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box sanitize transaction with recorded output
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-003 in plan.md Risk profile (all MITIGATED)
- [x] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-436-002,T-436-003,T-436-004 | Evidence: test_sanitize_removes_only_the_canonical_scope_duplicate + test_sanitize_fails_closed_on_wider_foreign_ips / _wider_foreign_actions / _non_api_foreign_rule / _ip_less_api_rule / _unmodeled_fields (fail closed, text untouched) + test_cli_sanitize_fail_closed_leaves_candidate_untouched (nonzero exit, ERROR scope report, no candidate) | Coverage: COVERED
- AC-2 | Task: T-436-002,T-436-003,T-436-004 | Evidence: test_cli_sanitize_verify_before_rejects_missing_marked_api_rule (verify-before) + test_cli_sanitize_removes_duplicate_and_reverifies_clean and test_sanitize_removes_only_the_canonical_scope_duplicate (marked API rule + both reader rules intact and verified after; sanitize_foreign_auth_rules post-conditions: marked spans byte-identical, count_foreign_auth_rules(pruned) == 0 via the dedicated scanner, not the span-merge verify) | Coverage: COVERED
- AC-3 | Task: T-436-003,T-436-004,T-436-005 | Evidence: test_shell_contracts_sanitize_subcommand (verify-reader-auth on LIVE+CANDIDATE, CANDIDATE_SHA256 digest emission, MUTATIONS=PROTECTED_CANDIDATE_ONLY, no systemctl worker strings, automatic-rollback contract, activate flow untouched) + seven-mode byte-identity harness diff (base 095e4c9 vs branch, empty) + test_shell_contracts_forward_all_reader_ip_occurrences (documented 2→4) | Coverage: COVERED
- AC-4 | Task: T-436-004,T-436-006 | Evidence: RED on base 095e4c9 — tests/test_mediamtx_sanitize_auth.py fails 16/16 (exact names recorded in the durable progress file and the delivery transcript) — and the same battery passes 16/16 on the branch; full pytest suite green; this SDD trio with the plan.md deployment transaction audit | Coverage: COVERED
