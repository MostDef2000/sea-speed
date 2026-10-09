# Tasks: Canonical drift-remediation path for drifted LIVE reader rules

- Specification: specs/437-remediate-reader/spec.md

## Delivery tasks

- T-437-001: RECON the reader-rule machinery: renderer markers/parse/verify/
  ensure functions, the `_parse_rule_block` set/loss-of-order semantics, the
  #436 per-entry scanner machinery, camera-relay.sh prepare/activate/sanitize
  transaction shape, existing renderer test batteries and the #372/#436 shell
  pins, change-control classification for the changed-file set; record
  findings in the durable progress file
- T-437-002: Add the bounded remediate core to the canonical renderer
  (`_reader_rule_ips_in_order` ordered parser, `READER_RULE_ALLOWED_ACTIONS`,
  `remediate_internal_reader_rule` with fail-closed scope classification and
  tight-span discipline, byte-exact ensure idempotency post-condition) and
  the `ubuntu-remediate-reader` CLI mode (verify-before → converge → 0600
  candidate); purely additive, all existing modes byte-identical
- T-437-003: Add the `camera-relay.sh remediate` subcommand (usage, dispatch,
  transaction block: verify-reader-auth on LIVE → remediate render → digest +
  root-only sha file → verify-reader-auth on CANDIDATE → evidence lines);
  keep the activate runbook unchanged
- T-437-004: Write the RED-first battery `tests/test_mediamtx_remediate_reader.py`
  (convergence, two-IP live-order byte-identity pin, idempotent no-op,
  fail-closed table, CLI transaction, shell pins); update the documented
  count pins in `tests/test_mediamtx_multi_reader_ip.py` (4→6) and
  `tests/test_mediamtx_sanitize_auth.py` (dispatch string, verify-reader-auth
  3→5, digest/MUTATIONS 2→3) with their reasons
- T-437-005: Append the remediate runbook after the #436 sanitize runbook in
  docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md (scope, fail-closed
  table, verify-before/after, transaction shape, no-auto-rollback contract)
- T-437-006: Run the verification battery (RED on base 4db356f recorded,
  full pytest, focused batteries, seven-mode byte-identity harness diff,
  `bash -n`, ruff on changed Python files, `validate_sdd.py --event`) and
  commit locally with the approved author identity; leave the branch unpushed
  for orchestrator admission

## Completion gate

- [x] T-437-001
- [x] T-437-002
- [x] T-437-003
- [x] T-437-004
- [x] T-437-005
- [x] T-437-006
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 18/18 on base 4db356f + full suite green on branch; worker-recorded; PR peer review and exact-head CI are orchestrator-owned)
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (renderer rides merge; shell change deploys with the repo source on the worker)
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box transaction (remediate → digest → activate --expected-sha256, output recorded per issue #437)
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-003 mitigated in plan.md Risk profile
- [x] Waivers resolved or current — none

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 18/18 on base 4db356f + full suite green on branch; PR peer review APPROVE is merge-phase, orchestrator-owned)
- [ ] Required CI green — exact-head PR CI — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box remediate transaction with recorded output
- [x] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-003 in plan.md Risk profile (all MITIGATED)
- [x] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-437-002,T-437-003,T-437-004 | Evidence: test_remediate_converges_drifted_single_ip_rule (reuses _parse_rule_block extraction, classifies through validate_peer_reader_ip + validate_reader_ip) + test_remediate_fails_closed_on_publish_action / _on_action_outside_read_publish / _on_public_ip / _on_loopback_ip / _on_non_ipv4_entry / _on_duplicate_ips (fail closed, text untouched) + test_cli_remediate_fail_closed_leaves_candidate_untouched (nonzero exit, ERROR report, no candidate) | Coverage: COVERED
- AC-2 | Task: T-437-002,T-437-003,T-437-004 | Evidence: test_remediate_converges_drifted_single_ip_rule (canonical _reader_rule_lines re-emission replaces the drifted block in place; other marked rules byte-identical; verify_internal_reader_rule + verify_internal_api_rule + byte-exact ensure idempotency post-conditions) + test_remediate_preserves_live_two_ip_scope_in_live_order (live scopes and order preserved; block byte-identical to the canonical render) + test_cli_remediate_converges_and_writes_0600_candidate (0600 temp+rename candidate; installation rides the unchanged digest-bound activate per test_shell_contracts_remediate_subcommand --expected-sha256 pin) | Coverage: COVERED
- AC-3 | Task: T-437-003,T-437-004,T-437-005 | Evidence: test_shell_contracts_remediate_subcommand (subcommand dispatch, verify-reader-auth on LIVE+CANDIDATE, CANDIDATE_SHA256 digest emission, REMEDIATED_READER/REMEDIATION_NEEDED/MUTATIONS evidence, no systemctl worker strings, automatic-rollback contract, activate flow untouched) + seven-mode byte-identity harness diff (base 4db356f vs branch, empty) + documented pin updates (multi_reader 4→6; sanitize 3→5 / 2→3) + runbook operator transaction (require_root/auth-override gating; worker-stopped gate lives in the unchanged activate) | Coverage: COVERED
- AC-4 | Task: T-437-004,T-437-006 | Evidence: RED on base 4db356f — tests/test_mediamtx_remediate_reader.py fails 18/18 (exact names recorded in the durable progress file and the delivery transcript) — and the same byte-identical battery passes 18/18 on the branch (drift → refused prepare stays pinned by the #372/#436 batteries; remediate → converges; unauthorized scope → fail closed); full pytest suite green; this SDD trio with the plan.md deployment transaction audit | Coverage: COVERED
