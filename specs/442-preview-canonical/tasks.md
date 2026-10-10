# Tasks: Fold the preview contour's inline config+catalog rendering into the canonical renderer

- Specification: specs/442-preview-canonical/spec.md

## Delivery tasks

- T-442-001: RECON the renderer (marker grammar, span-terminated rule parser,
  sanitize scanner ownership, multi-IP grammar, write-candidate discipline),
  the preview shell heredoc, the consumer contracts (generated_at not read),
  and the test batteries to re-pin; record in the durable progress file
- T-442-002: Write the RED-first battery tests/test_mediamtx_preview_relay.py
  (34 tests: golden bytes, legacy parity minus documented drifts,
  idempotency, drift rejection, multi-IP, api-less negative pin, inventory
  fail-closed table, check-address table, shell forwarding/structural pins);
  record RED on base c2bd3b9 (30 failed / 4 passed with the final file
  cmp-verified)
- T-442-003: Implement the renderer additions (preview constants, scope
  token, inventory validation, rule lines, fresh render of config+catalog,
  verify-preview-auth, check-address, three subparsers) ADDITIVELY; replace
  the preview shell heredoc with the thin CLI (multi-IP parse/forward,
  renderer resolution, READER_AUTH_SCOPE evidence); move the cam1 shell's
  two inline validators to check-address wrappers
- T-442-004: Re-pin tests/test_camera_preview_gallery.py (renderer-owned
  literals re-pointed to the renderer; shell keeps structural pins); add
  docs/operations/CAMERA_PREVIEW_RELAY.md (prepare/activate/digest gates,
  one-time drifts, open on-box questions)
- T-442-005: Write the SDD trio specs/442-preview-canonical/ (REQUIRED risk
  profile with R1-R5, TX-001..008 audit, AC traceability, DoD with the four
  on-box open questions as open evidence items)
- T-442-006: Run the verification battery (RED re-confirmed on red-base-442
  with the final test file, full pytest, ruff, bash -n on both shells,
  seven-mode harness empty diff + 8th preview golden + idempotency +
  parity transcript, validate_sdd event) and commit locally with the
  approved author identity; leave the branch unpushed for orchestrator
  admission

## Completion gate

- [x] T-442-001
- [x] T-442-002
- [x] T-442-003
- [x] T-442-004
- [x] T-442-005
- [x] T-442-006
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 30 failed / 4 passed on base c2bd3b9 with the final test file byte-identical via cmp + full suite green on branch; worker-recorded; PR peer review and exact-head CI are orchestrator-owned)
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (worker scripts deploy with the repo source)
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box transaction (bounded preview-relay re-render; byte-identical render for a conforming box modulo the documented drifts; road probe window)
- [x] Deferred work recorded — remaining RFC1918 copies outside the two relay shells and the other #373 slices are explicitly out of scope (issue #442 do-not-merge list)
- [x] Risks resolved or explicitly accepted — RISK-001..005 (R1 marker drift, R2 generated_at, R3 dummy-credential fixtures, R4 frozen road-worker contracts, R5 api-less) mitigated in plan.md Risk profile
- [x] Waivers resolved or current — none

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED 30 failed / 4 passed on base c2bd3b9, final file cmp-verified + full suite green on branch; PR peer review APPROVE is merge-phase, orchestrator-owned)
- [ ] Required CI green — exact-head PR CI — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned + 1 operator on-box transaction with recorded output
- [x] Deferred work recorded — remaining RFC1918 sites and remaining #373 slices stay open in the issue, not merged here
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-005 in plan.md Risk profile (all MITIGATED)
- [x] Waivers resolved or current — none

## Open evidence items (on-box questions, from issue #442)

- OEV-001: live preview relay bind address/port not in the repo (fixtures
  10.0.0.8:8555 vs KB 8892) — confirm at the re-render transaction
- OEV-002: `sea_speed_camera_preview_inventory_v1` has no repo producer —
  confirm the live inventory location/producer
- OEV-003: top-level vs path-level transport pinning policy unresolved —
  renderer keeps the legacy shape (both levels) this slice
- OEV-004: road worker consumes `preview_road1` live — record the
  interruption window before/after the bounded transaction

## Requirements traceability

- AC-1 | Task: T-442-003,T-442-002 | Evidence: test_shell_is_valid_and_renders_through_the_canonical_module (thin CLI forwards inventory/outputs/address/IPs; no config literals left in the shell) + test_two_camera_render_matches_golden_bytes (canonical module renders config+catalog) + test_renderer_owns_the_preview_marker_and_validation (renderer owns the schemas and functions) | Coverage: COVERED
- AC-2 | Task: T-442-003,T-442-002 | Evidence: PreviewAuthVerificationTests (accepts canonical render; subset semantics on multi-IP rule; rejects drifted ips / missing marker / drifted action fail-closed) + test_preview_rule_verifies_through_the_shared_rule_parser (the marker works with the shared span-terminated rule parser and sanitize scanner ownership) | Coverage: COVERED
- AC-3 | Task: T-442-003,T-442-002 | Evidence: CheckAddressCliTests (reader-ip valid/invalid, private-rtsp valid prints host then port / invalid fails closed, stdout discipline) + test_both_relay_shells_single_source_validation_through_check_address + test_cam1_relay_shell_validators_move_to_check_address (both shells consume the verb; inline heredoc validators gone) | Coverage: COVERED
- AC-4 | Task: T-442-002,T-442-006 | Evidence: test_re_render_with_same_inputs_is_byte_identical (self-identity) + test_canonical_config_minus_marker_equals_legacy_heredoc_output + test_canonical_catalog_matches_legacy_contract_minus_generated_at (legacy parity minus documented drifts) + seven-mode harness empty diff (legacy modes untouched; harness transcript in the delivery report) | Coverage: COVERED
- AC-5 | Task: T-442-004,T-442-005,T-442-006 | Evidence: test_ubuntu_preview_relay_is_separate_source_on_demand_and_private + test_ubuntu_inventory_is_protected_and_catalog_is_sanitized (re-pinned: renderer-owned literals, shell structural pins) + full pytest suite green + docs/operations/CAMERA_PREVIEW_RELAY.md + this SDD trio | Coverage: COVERED
