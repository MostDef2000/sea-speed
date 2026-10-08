# Tasks: Multi-reader-IP support in the canonical MediaMTX config tooling

- Specification: specs/372-multi-reader-ip/spec.md

## Delivery tasks

- T-372-001: RECON the reader-IP chain: renderer CLI parsing,
  `_reader_rule_lines` / `ensure_internal_reader_rule` /
  `verify_internal_reader_rule` list capability, `publisher_ips` list
  precedent, camera-relay.sh flag parsing/forwarding/READER_AUTH_SCOPE
  evidence, existing camera1 test pins, change-control classification for
  the changed-file set; record findings in the durable progress file
- T-372-002: Renderer: add `_reader_ip_list` (repeatable/comma-separated
  normalization, input-order preserving, duplicate/empty fail-closed) and
  `reader_scope_token`; switch `--reader-ip` to `action="append"` on
  `ubuntu-relay` and `verify-reader-auth`; per-IP RFC1918 validation and
  list pass-through in both render modes with deterministic evidence
  tokens; keep `verify_internal_reader_rule` SUBSET semantics, the
  fail-closed exact-block mismatch, every other renderer mode, and
  single-IP byte-identical output unchanged
- T-372-003: camera-relay.sh: repeatable/comma-separated `--reader-ip`
  parsing into `reader_ips` (trim + empty-entry rejection), per-IP
  validation loop before any renderer call, `reader_ip_args` forwarding
  into both the prepare render and the activate verify-reader-auth
  invocations, generalized deterministic `READER_AUTH_SCOPE` evidence
  (single-reader literal preserved), usage text update
- T-372-004: Add `tests/test_mediamtx_multi_reader_ip.py` (two-IP render
  incl. both IPs, order stability, single-IP byte-identity pins, mismatch
  fail-closed matrix, subset verify on a 2-IP rule, duplicate rejection,
  CLI repeatable/comma/fail-closed paths, camera-relay.sh forwarding
  structural pins) and apply the documented anchor re-pin in
  `tests/test_camera1_live_replacement.py` (READER_AUTH_SCOPE literal moved
  into reader_auth_scope(); strength preserved)
- T-372-005: Run the verification battery (full pytest, new battery verbose,
  `bash -n` on camera-relay.sh, ruff on changed Python files,
  `scripts/ci/validate_sdd.py`) and commit locally with the approved author
  identity; leave the branch unpushed for orchestrator admission

## Completion gate

- [ ] T-372-001
- [ ] T-372-002
- [ ] T-372-003
- [ ] T-372-004
- [ ] T-372-005
- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned (a future operator-scheduled 2-IP re-render through the canonical tool; no runtime change in this task)
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-004 mitigated or disclosed in plan.md
- [ ] Waivers resolved or current — none

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (tool-only change; activation of a 2-IP candidate remains a separate operator-gated transaction)
- [ ] Runtime acceptance resolved — orchestrator-owned (2-IP prepare renders ips: [...] with both reader IPs when first exercised on the worker)
- [ ] Deferred work recorded — none (preview-relay single-IP regex rule stays deferred to #373 by design)
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-004 in plan.md Risk profile
- [ ] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-372-002,T-372-004 | Evidence: test_two_ip_render_includes_both_ips_in_input_order + test_cli_repeatable_flags_render_both_ips + test_cli_comma_separated_value_renders_both_ips (candidate ips: ["10.123.239.101", "10.123.239.102"]; verify_internal_reader_rule green with both IPs) | Coverage: COVERED
- AC-2 | Task: T-372-002,T-372-004 | Evidence: test_verify_subset_semantics_on_two_ip_live_rule (single/str/list subset passes, non-member rejected) + test_cli_verify_reader_auth_accepts_repeatable_and_comma_ips (verify mode repeatable/comma on 2-IP rule; non-member exit 1) | Coverage: COVERED
- AC-3 | Task: T-372-002,T-372-004 | Evidence: test_single_ip_is_byte_identical_to_historical_str_behavior (str vs list vs comma equivalence, exact historical block bytes) + test_cli_single_flag_matches_historical_output (reader_scope=single-rfc1918-ip, idempotent str-API re-apply) | Coverage: COVERED
- AC-4 | Task: T-372-002,T-372-003,T-372-004 | Evidence: test_mismatch_reader_ip_list_is_rejected_fail_closed + test_cli_mismatch_list_is_rejected_and_candidate_untouched (exit 1, no candidate written) + test_duplicate_reader_ips_fail_closed | Coverage: COVERED
- AC-5 | Task: T-372-002,T-372-004 | Evidence: test_render_order_follows_input_order_stably (byte-identical same-order re-render; reversed input renders reversed ips line) | Coverage: COVERED
- AC-6 | Task: T-372-005 | Evidence: full pytest suite green; new battery verbose green; bash -n clean on camera-relay.sh; ruff clean on changed Python files; validate_sdd.py green | Coverage: COVERED
