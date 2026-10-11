# Spec: Preview verify hardening — full-scope drift pin, standalone status, verification-semantics records

- Issue: #452
- Specification: specs/452-preview-verify-hardening/spec.md

## Product outcome

PR #451's peer review of the #442 preview canonicalization left four
non-gating findings (LOW/INFO) collected in issue #452. None is a production
defect: the D2 closure already rejects the finding-1 drift class (probed on
base 463ae37 — a drifted `path:` pattern line with intact ips/action/marker
is rejected by the full-scope byte-exact comparison), but that detector had
NO red test; and the #442 shell change accidentally withdrew `status`'s
pre-#442 standalone property by placing the renderer-exists gate before the
status branch. Findings 3 and 4 are institutional-knowledge records.

This change delivers, in one test/docs-hardening unit:

1. F1 (test): ONE regression-pin test where the full-scope byte-exact
   comparison is the SOLE drift detector — `verify-preview-auth` with a
   full-scope request must REJECT a rule whose `path: "~^preview_[a-z0-9._-]+$"`
   pattern line is drifted while ips/action/marker stay intact. The pin is
   proven non-vacuous with the repo's RED-harness shape: on base 463ae37 the
   test passes against the intact verifier and FAILS
   (`AssertionError: 0 != 1`) when the byte-exact branch is disabled.
2. F2 (behavioral): `camera-preview-relay.sh status` works standalone again
   (pre-#442 behavior): the renderer-exists gate moves after the status
   branch; inside status it applies only when `--private-rtsp-address`
   requests the TCP probe (which resolves through the renderer's
   `check-address` verb). Healthy-box status output stays byte-identical.
3. F3 (INFO): the runbook records that `verify-preview-auth` is
   intentionally NOT wired into prepare/activate (D2 verification is a repo
   verb run on-box manually; the contract requires verifiability, not
   in-transaction gating) plus the criterion for a future transaction to add
   an in-transaction drift gate.
4. F4 (INFO, inherited): the runbook records that verify uses the
   span-merge `_parse_rule_block` parsing — the same #436-class blind spot
   as cam1 `verify-reader-auth` (a foreign entry appended after the
   canonical block with a subset of the same IPs passes) — unchanged,
   cam1-identical, noted for the future unified-parser wave.

Operator actions: 0. Risk profile: NOT REQUIRED.

## User scenarios

- US-1: A contributor (or future refactor) weakens the preview verify's
  byte-exact branch or otherwise lets a drifted `path:` pattern through:
  the battery fails on `test_verify_rejects_drifted_path_pattern_fail_closed`
  instead of silently losing the detector.
- US-2: An operator runs `camera-preview-relay.sh status` on a worker box
  (with or without `--private-rtsp-address`): status reports the systemd
  evidence lines without requiring the renderer; with the address probe
  requested and the renderer present, the TCP line behaves exactly as
  before.
- US-3: An operator planning a future preview transaction reads the runbook
  and knows why verify-preview-auth is manual today and when an
  in-transaction drift gate becomes mandatory (in-place rule edits).
- US-4: The future unified-parser wave finds the recorded #436-class
  span-merge blind spot (preview AND cam1) in the runbook instead of
  rediscovering it.

## Scope

- `tests/test_mediamtx_preview_relay.py`: ADDITIVE — one
  `PreviewAuthVerificationTests` drift-path pin; one
  `PreviewShellContractTests` structural pin for the gate move. No existing
  test changes.
- `deploy/worker/ubuntu/camera-preview-relay.sh`: ONLY the renderer-exists
  gate moves (after the status branch; conditional inside status) with
  comments; every other byte unchanged (status output lines, prepare,
  activate, evidence streams).
- `docs/operations/CAMERA_PREVIEW_RELAY.md`: one new "Verification semantics
  (issue #452)" section (F3 + F4). No existing doc line changes.
- This SDD trio and the durable progress file (untracked).
- OUT of scope: any renderer change (F1's verifier already conforms — probed,
  not assumed); the unified-parser wave (F4 is recorded, not fixed);
  in-transaction verify wiring (F3 records the boundary, does not move it);
  PR body/contract derivation (orchestrator-owned); push/PR/CI (commit on
  branch only).

## Requirements

- R-1: A full-scope drifted-`path:` rejection pin exists in the preview
  battery; it is green on the branch and proven red when the byte-exact
  branch is disabled (RED-harness evidence on base 463ae37).
- R-2: `camera-preview-relay.sh status` runs without the renderer; healthy
  -box status stdout is byte-identical to base 463ae37; the status+address
  renderer gate (clean exit 4) is preserved.
- R-3: The runbook records the verify-not-wired-into-prepare/activate
  convention (D2 verifiability, manual on-box verb) and the future
  in-transaction drift-gate criterion.
- R-4: The runbook records the span-merge #436-class blind spot for preview
  verify, marked inherited/unchanged and cam1-identical, with the
  unified-parser wave pointer.

## Acceptance criteria

- AC-1: `test_verify_rejects_drifted_path_pattern_fail_closed` green on the
  branch; red-harness proof recorded (base 463ae37: green intact / FAILED
  with byte-exact branch disabled).
- AC-2: `status` standalone restored; byte-compare of healthy-box status
  output base vs fixed is IDENTICAL; `bash -n` green on both relay shells.
- AC-3: F3 recorded verbatim-in-substance in
  `docs/operations/CAMERA_PREVIEW_RELAY.md`.
- AC-4: F4 recorded in the same section.
- AC-5: full unittest suite green (baseline 907 + 2 new tests), ruff clean,
  validate_sdd event green (base 463ae37, head = commit).

## Runtime feedback

- RF-001: Operator actions expected: 0 (issue #452). The F2 shell change
  ships to the box through the standard worker-update flow; no on-box
  transaction is required or authorized by this slice.
- RF-002: Evidence: red-harness transcript (intact=OK, disabled=FAILED
  `0 != 1`), byte-compare transcript (status stdout IDENTICAL), suite/ruff/
  bash -n/validate_sdd outputs recorded in the delivery report and
  PROGRESS-452.md.

## NFR assessment

- NFR-001 | Area: security | Target: the preview contour's #362-class drift detection for a mutated `path:` pattern line stays fail-closed and is regression-pinned by repo tooling (full-scope byte-exact comparison as the SOLE detector, marker/ips/action checks deliberately left intact by the fixture) | Validation: drifted-path pin green on head + RED-harness proof on base 463ae37 (green with intact verifier; FAILED 0 != 1 with the branch disabled) + pre-existing drift table still green | Evidence: tests/test_mediamtx_preview_relay.py — PreviewAuthVerificationTests; probe transcript | Status: PASS
- NFR-002 | Area: reliability/operations | Target: `status` is standalone again (pre-#442 behavior) with byte-identical healthy output; the status+address renderer gate stays clean (exit 4, no stderr noise / no misleading TCP=FAIL) | Validation: byte-compare harness (cmp IDENTICAL, 6 evidence lines) + missing-renderer scenario table + bash -n | Evidence: F2 harness transcript; PreviewShellContractTests | Status: PASS
- NFR-003 | Area: maintainability | Target: the verify-semantics boundary (manual D2 verb, not in-transaction) and the inherited span-merge blind spot are durable repo knowledge, not session memory; the unit touches no renderer code (probe-first discipline) | Validation: runbook section present; SDD trio complete; full suite green | Evidence: docs/operations/CAMERA_PREVIEW_RELAY.md "Verification semantics (issue #452)"; tasks.md traceability | Status: PASS
