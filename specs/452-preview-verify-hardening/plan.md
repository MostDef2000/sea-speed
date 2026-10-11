# Plan: Preview verify hardening — full-scope drift pin, standalone status, verification-semantics records

- Issue: #452
- Specification: specs/452-preview-verify-hardening/spec.md

## Implementation approach

1. RECON-established facts (at 463ae37): `verify_preview_reader_auth_config`
   (renderer :1234) already rejects a drifted `path:` pattern line via the
   full-scope byte-exact branch (:1259–1264) — probed, not assumed; the
   marker line embeds `PREVIEW_PATH_PATTERN`, so a fixture must drift ONLY
   the permissions `path:` line for byte-exact to be the SOLE detector
   (marker drift trips the marker-count check instead); the preview battery
   had drifted-ips/marker/action pins but no drifted-path pin; the shell's
   renderer-exists gate (:160) sat before the status branch (:162) — base
   f487dfb had status standalone; status output literals are pinned nowhere,
   so the F2 byte-check must be an observed base-vs-head run.
2. F1: add `test_verify_rejects_drifted_path_pattern_fail_closed` to
   `PreviewAuthVerificationTests` (render → replace ONLY the permissions
   `path:` line with a realistic loosening `~^preview_.*$` → full-scope
   verify → assert exit 1 + the byte-exact branch's message). Prove the pin
   with the repo RED-harness shape in a 463ae37 worktree: green intact,
   FAILED with the byte-exact branch disabled.
3. F2: move the renderer gate after the status branch; add the conditional
   in-status gate (renderer required only for the address probe); keep the
   prepare/activate gate before `require_root`; byte-compare status output
   base vs fixed with a shimmed `systemctl`; `bash -n`.
4. F3+F4: one runbook section; no code.
5. SDD trio + validate_sdd event; single local commit; NO push.

## Architecture

- F1 is a detector-gap pin, NOT a production fix: the probe on base
  (ConfigError "existing ... rule does not match the requested rule")
  establishes the verifier already conforms, so the deliverable is the pin
  plus the RED-harness non-vacuity proof — the standard shape when a
  detector exists but no test fires on it.
- F2 restores gate ORDER, not gate PRESENCE: the gate is unconditional for
  prepare/activate (before `require_root`, preserving relative gate order)
  and conditional inside status (renderer needed only when the TCP probe
  must resolve the address). A pure move would degrade status+address with
  a missing renderer into `TCP=FAIL` plus python3 stderr noise — a worse,
  misleading failure mode than today's clean exit 4.
- F3/F4 land as one runbook section ("Verification semantics (issue #452)")
  so the boundary and the blind spot are recorded next to the existing
  verify-preview-auth contract lines.
- The unit is test/docs + a 2-position gate move: no renderer byte changes,
  so F1's green-on-head result is identical on base and head by construction
  (the verifier is untouched).

## Decisions

- D-1: Regression-pin over "fix": the probe proved the verifier already
  rejects the F1 drift (D2 closure sound); the RED-first obligation is
  discharged by the RED-harness proof (test fails when the detector is
  disabled) instead of a red-on-base production fix, per the work order's
  decision tree. A real rejection gap would have BLOCKED the unit instead.
- D-2: The in-status renderer gate is conditional on `--private-rtsp-address`
  (not dropped): standalone status is restored AND status+address keeps the
  unambiguous renderer-missing error rather than a degraded TCP=FAIL.
- D-3: F3/F4 are documentation records in the existing preview runbook (the
  #442-added file), not new docs and not code comments only: they must
  survive as operator-facing knowledge.
- D-4: Risk profile NOT REQUIRED per issue #452 (all findings LOW/INFO,
  non-gating): F1 adds a test only; F2 moves one shell gate back behind the
  status branch (byte-checked); F3/F4 are doc records. No RISK rows
  (validate_sdd forbids them under NOT REQUIRED).
- D-5: The fixture drifts ONLY the `path:` line (marker untouched): drifting
  the marker instead would trip the marker-count check first and the pin
  would no longer prove the byte-exact branch is the sole detector.

## Affected contours

- UBUNTU_WORKER: `deploy/worker/ubuntu/camera-preview-relay.sh` (gate
  position only) — the PR contract will derive UBUNTU_WORKER + envelope
  REQUIRED regardless of the small change; orchestrator-owned.
- CONTROL_PLANE/test/docs: `tests/test_mediamtx_preview_relay.py`,
  `docs/operations/CAMERA_PREVIEW_RELAY.md`, this trio, the untracked
  progress file.
- No change: the renderer module (probe-only), the 9 legacy verbs, prepare/
  activate flows and evidence lines, cam1 shell, api/, frontend/, CI.

## Validation

- F1 probe (base verifier, pre-test): drifted `path:` (marker/ips/action
  intact, full-scope request) → exit 1, `ERROR: existing Sea Speed preview
  reader authorization rule does not match the requested rule`.
- RED-harness (worktree at 463ae37, outside the repo tree): intact verifier
  → Ran 1 OK; byte-exact branch disabled → FAILED `AssertionError: 0 != 1`.
- Full battery on the branch: `python3 -m unittest discover -s tests`
  (baseline 907 OK / 4 skipped + 2 new tests), ruff, `bash -n` on both relay
  shells, validate_sdd event (base 463ae37, head = commit).
- F2 byte-check: shimmed `systemctl`, base 463ae37 shell vs fixed shell —
  status stdout cmp IDENTICAL; standalone-status restoration table
  (missing renderer: fixed exit 0 vs base exit 4).

## Runtime feedback

- RF-001: Operator actions expected: 0 (issue #452). No on-box transaction;
  the F2 change rides the standard worker-update flow.
- RF-002: Evidence: the transcripts listed under Validation, recorded in
  PROGRESS-452.md and the delivery report.

## Risk profile

- Risk profile: NOT REQUIRED
- Rationale: per issue #452 — all four findings LOW/INFO and non-gating;
  F1 is a test-only pin (probe first proved the verifier already conforms),
  F2 restores pre-#442 status behavior with byte-identical healthy output,
  F3/F4 are runbook records. No production-code behavior change beyond the
  one shell gate position; no auth topology, no renderer change, no secrets,
  operator actions 0.

## Test design

- TEST-001 | Covers: R-1 | Level: unit | Priority: P0 | Evidence: test_verify_rejects_drifted_path_pattern_fail_closed (sole-detector fixture: drifted `path:` line only) + RED-harness proof on base 463ae37 — intact verifier: Ran 1 OK; byte-exact branch disabled: FAILED `AssertionError: 0 != 1` (worktree ss-452-red, transcript in the delivery report)
- TEST-002 | Covers: R-2 | Level: unit | Priority: P0 | Evidence: test_shell_status_is_standalone_and_renderer_gate_follows_it (gate count/position pins) + bash -n both shells + byte-compare harness cmp IDENTICAL + missing-renderer scenario table (fixed 0 / base 4)
- TEST-003 | Covers: R-1,R-2 | Level: integration | Priority: P0 | Evidence: python3 -m unittest discover -s tests — 909 tests (baseline 907 + 2 new), 4 skipped, OK
- TEST-004 | Covers: R-3,R-4 | Level: unit | Priority: P2 | Evidence: runbook section present with both records (F3 boundary + criterion; F4 blind spot + cam1 parity + unified-parser pointer); no code to test by design

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: issue #452 findings list and bounded scope (test battery, preview shell, runbook, SDD trio, progress file) enforced before first write; GH007 author identity configured before commit
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: F1 probe on the base verifier (drifted path rejected, exit 1) BEFORE writing the test; RED-harness worktree at 463ae37 placed outside the repo tree
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: prior file contents restorable from git | Retry: NO | Rollback: git checkout -- of the touched tracked files (single-commit unit, branch-local) | Evidence: edits confined to tests/test_mediamtx_preview_relay.py, deploy/worker/ubuntu/camera-preview-relay.sh, docs/operations/CAMERA_PREVIEW_RELAY.md, specs/452-preview-verify-hardening/*
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: RED-harness transcript (OK intact / FAILED 0 != 1 disabled), byte-compare IDENTICAL, full suite 909/4skipped, ruff clean, bash -n green, validate_sdd event base 463ae37 head = commit
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: working tree keeps the edits; branch unchanged | Retry: YES | Rollback: NONE (branch is local-only; orchestrator may reset it) | Evidence: ONE local commit `test(preview): full-scope drift pin + standalone status gate (#452)` on sdd/452-preview-verify-hardening; NO push
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: scratch remains outside the repo tree | Retry: NO | Rollback: NONE | Evidence: git worktree remove ss-452-red + scratch dir deletion after the battery
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: observed outputs recorded in PROGRESS-452.md (red-harness, byte-compare, suite counts, ruff, validate_sdd) and the delivery report
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: branch is local-only and unpushed — rollback is branch deletion; no shared/on-box state exists to roll back | Evidence: commit on branch only, NO push, no PR, operator actions 0
