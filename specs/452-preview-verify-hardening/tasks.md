# Tasks: Preview verify hardening — full-scope drift pin, standalone status, verification-semantics records

- Specification: specs/452-preview-verify-hardening/spec.md

## Delivery tasks

- T-452-001: RECON the preview verify branch (byte-exact sole detector),
  the battery's existing drift pins, the F2 gate regression (base f487dfb
  standalone status vs #442 gate position), and the #442 runbook; record in
  PROGRESS-452.md
- T-452-002: F1 — probe the base verifier with a drifted `path:` fixture
  (marker/ips/action intact, full-scope request); on rejection observed,
  add the regression pin `test_verify_rejects_drifted_path_pattern_fail_closed`
  and prove it non-vacuous with the RED-harness worktree at 463ae37 (green
  intact / FAILED with the byte-exact branch disabled); a non-rejecting
  verifier would have BLOCKED the unit instead
- T-452-003: F2 — move the renderer-exists gate after the status branch
  (conditional inside status for the address probe); byte-compare healthy
  status output base vs fixed; add the structural gate-position pin;
  bash -n both shells
- T-452-004: F3+F4 — record the verification-semantics section in
  docs/operations/CAMERA_PREVIEW_RELAY.md (not-wired rationale + future
  in-transaction gate criterion; span-merge #436-class blind spot, cam1
  parity, unified-parser wave pointer)
- T-452-005: Write the SDD trio specs/452-preview-verify-hardening/
  (Risk profile NOT REQUIRED — no RISK rows; Test design rows for F1;
  correct-course; full 8-stage TX audit; AC traceability; DoD)
- T-452-006: Run the verification battery (full unittest discover, ruff,
  bash -n both shells, validate_sdd event base 463ae37 head = commit),
  clean up the scratch worktree/dir, and commit locally with the GH007
  identity; leave the branch unpushed for orchestrator admission

## Completion gate

- [x] T-452-001
- [x] T-452-002
- [x] T-452-003
- [x] T-452-004
- [x] T-452-005
- [x] T-452-006
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED-harness OK/FAILED transcript + byte-compare IDENTICAL + full suite green, worker-recorded; PR peer review and exact-head CI are orchestrator-owned)

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (red-harness + byte-compare + full suite green on branch; worker-recorded)
- [ ] Required CI green — orchestrator-owned (exact-head PR CI after push; not runnable in this unit)
- [ ] Exact-green-head merge complete — orchestrator-owned (post-PR)
- [x] Deployment state resolved — no on-box action in this slice (issue #452: operator actions 0); the F2 shell change ships via the standard worker-update flow
- [x] Runtime acceptance resolved — none required (operator actions: 0); F1 is repo-verifiable (probe + red-harness + green transcripts recorded)
- [x] Deferred work recorded — F4's unified-parser wave and any future in-transaction verify wiring stay recorded in the runbook, not implemented here
- [x] Risks resolved or explicitly accepted — Risk profile NOT REQUIRED (no RISK rows per validate_sdd)
- [x] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-452-002 | Evidence: test_verify_rejects_drifted_path_pattern_fail_closed green on head (PreviewAuthVerificationTests Ran 6 OK) + RED-harness transcript on base 463ae37 (intact: Ran 1 OK; byte-exact branch disabled: FAILED `AssertionError: 0 != 1`) + F1 probe transcript (base verifier rejects, exit 1) | Coverage: COVERED
- AC-2 | Task: T-452-003 | Evidence: byte-compare harness (status stdout cmp IDENTICAL, 6 lines) + missing-renderer scenario table (fixed exit 0 standalone vs base exit 4; status+address clean exit 4 preserved) + test_shell_status_is_standalone_and_renderer_gate_follows_it + bash -n both shells | Coverage: COVERED
- AC-3 | Task: T-452-004 | Evidence: docs/operations/CAMERA_PREVIEW_RELAY.md "Verification semantics (issue #452)" first bullet (manual D2 verb rationale + in-transaction gate criterion) | Coverage: COVERED
- AC-4 | Task: T-452-004 | Evidence: same section, second bullet (span-merge `_parse_rule_block` #436-class blind spot, cam1 verify identical, unified-parser wave pointer) | Coverage: COVERED
- AC-5 | Task: T-452-006 | Evidence: full unittest suite (baseline 907/4 + 2 new tests green), ruff clean, bash -n green, validate_sdd event (base 463ae37, head = commit), this SDD trio | Coverage: COVERED
