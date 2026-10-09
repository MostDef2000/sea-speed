# Tasks: Explicit opt-in prune of declared legacy foreign rules

- Specification: specs/444-declared-prune/spec.md

## Delivery tasks

- T-444-001: RECON the #436 sanitizer state on main (per-entry scanner,
  fail-closed parser, post-conditions), confirm the `path:`-skip gap in
  `_parse_auth_entry_fields`, the shell sanitize transaction shape and the
  forwarding-pin invariants; read issue #444 and record the relay context in
  the durable progress file
- T-444-002: Write the RED-first battery extension (+22 tests: declaration
  grammar, declared-prune core, CLI transaction, shell passthrough pins);
  record RED on base cf2a462 (23 failed / 17 passed, exact names in the
  delivery transcript) with the two byte-for-byte-default guards passing by
  construction
- T-444-003: Implement the renderer: collect permission-level `path:` values
  in `_parse_auth_entry_fields`, add `DeclaredAuthPrune` +
  `parse_declared_auth_prune` (fail-closed grammar), the
  `sanitize_foreign_auth_rules_declared` core (exact-triple whitelist
  extension, per-declaration counts, unchanged fail-closed and
  post-condition discipline), the stable `sanitize_foreign_auth_rules`
  wrapper, the repeatable `--prune-declared` CLI flag and per-declaration
  `DECLARED_PRUNED` evidence lines
- T-444-004: Extend `camera-relay.sh sanitize`: `--prune-declared` spec
  collection, `declared_args` forwarding to the renderer, captured renderer
  output with the aggregated `DECLARED_PRUNED=` evidence line only when
  declarations were given; keep the digest-bound activate runbook and all
  existing pins byte-unchanged
- T-444-005: Append the declared-prune runbook (grammar, exact-triple scope,
  operator retry window with the relay context from issue #444) to the
  sanitize section of docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md
- T-444-006: Write the SDD trio specs/444-declared-prune/ (spec, plan with
  REQUIRED risk profile + 8-stage TX audit, tasks with traceability and DoD)
- T-444-007: Run the verification battery (RED on base re-confirmed with the
  final test file, full pytest, ruff, `bash -n`, seven-mode byte-identity
  harness diff empty, `validate_sdd.py --event`) and commit locally with the
  approved author identity; leave the branch unpushed for orchestrator
  admission

## Completion gate

- [x] T-444-001
- [x] T-444-002
- [x] T-444-003
- [x] T-444-004
- [x] T-444-005
- [x] T-444-006
- [x] T-444-007
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 23 failed / 17 passed on base cf2a462 with the final test file byte-identical via cmp + full suite green on branch; worker-recorded; PR peer review and exact-head CI are orchestrator-owned)
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (renderer rides merge; shell change deploys with the repo source on the worker)
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box retry-window transaction (stop AI worker → sanitize with two cam1-test declarations → activate --expected-sha256 → start AI worker → remediate verify; output recorded per issue #444, closing #436)
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-003 mitigated in plan.md Risk profile
- [x] Waivers resolved or current — none

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 23 failed / 17 passed on base cf2a462, final file cmp-verified + full suite green on branch; PR peer review APPROVE is merge-phase, orchestrator-owned)
- [ ] Required CI green — exact-head PR CI — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box retry-window transaction with recorded output
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-003 in plan.md Risk profile (all MITIGATED)
- [x] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-444-003,T-444-004,T-444-002 | Evidence: test_parse_declared_spec_full_grammar + test_parse_declared_spec_bare_tokens_continue_previous_key (repeatable declarations, documented grammar) + test_no_declarations_is_byte_for_byte_todays_default and test_cli_without_declarations_refuses_byte_for_byte (WITHOUT declarations: byte-for-byte today's fail-closed default — same ConfigError scope text, same exit 1, no DECLARED_PRUNED lines, no candidate) | Coverage: COVERED
- AC-2 | Task: T-444-003,T-444-002 | Evidence: test_declared_prune_removes_exactly_the_declared_triples (both cam1-test rules + the default api duplicate, marked rules byte-identical, canonical verifies pass, foreign count == 0) + test_declared_prune_leaves_undeclared_foreign_rule_fail_closed + test_declared_prune_rejects_partial_match_extra_ip / _different_path / _extra_action (exact triple equality, fail closed, text untouched) + test_declared_prune_rejects_unmodeled_foreign_rule_even_if_scoped + test_declared_prune_never_touches_marked_rule_matching_the_triple + test_declared_prune_is_idempotent_noop_on_clean_config | Coverage: COVERED
- AC-3 | Task: T-444-004,T-444-002,T-444-005 | Evidence: test_shell_contracts_declared_prune_passthrough (declared_prune_specs collection, declared_args forwarding, DECLARED_PRUNED= per-declaration evidence, verify-reader-auth == 5 and CANDIDATE_SHA256 == 3 pins unchanged, no worker control strings, automatic-rollback contract) + test_cli_declared_prune_removes_legacy_rules_and_api_duplicate (per-declaration renderer evidence, digest, 0600) + docs runbook with the operator retry window | Coverage: COVERED
- AC-4 | Task: T-444-002,T-444-007 | Evidence: RED on base cf2a462 — tests/test_mediamtx_sanitize_auth.py fails 23 / passes 17 (all 22 new-behavior tests RED: 10 declaration-grammar, 9 declared-prune core, 3 CLI, 1 shell; exact names recorded in the durable progress file and the delivery transcript) — and the battery passes 40/40 on the branch; full pytest suite green; this SDD trio with the plan.md deployment transaction audit | Coverage: COVERED
