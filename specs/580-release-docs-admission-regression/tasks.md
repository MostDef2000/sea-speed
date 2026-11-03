# Tasks — Issue #580: release-process docs drift + admission regression

- Issue: #580
- Spec: specs/580-release-docs-admission-regression/spec.md
- Plan: specs/580-release-docs-admission-regression/plan.md
- Base: 8531f3e (branch fix/580-release-docs-admission-regression)

## Delivery tasks

- [x] T-1 RECON: drift inventory + admission surface + coverage gap
      (explore + architect passes; facts cited in plan.md).
- [x] T-2 `tests/test_release_admission_regression.py` — 6 admission
      regression tests through the real `evaluate()`/`main()` with a real
      temp git repo fixture and mocked transport (AC-001).
- [x] T-3 `docs/quality/testing-policy.md` :50 — standing-delegation
      description; intro + four bullets preserved verbatim (AC-002).
- [x] T-4 `docs/quality/quality-gate-architecture.md` :17/:56/:58 — router
      reality, `workflow_dispatch` as manual/recovery, protected
      `production` environment retained (AC-003).
- [x] T-5 `deploy/vps/README.md` :227/:240 — policy-gated deployment
      sentence with the verbatim merge clause; path-based contour
      classification (AC-004).
- [x] T-6 validation runs (see Battery identity).
- [x] T-7 this SDD trio.
- [x] T-8 independent peer review of the full stage diff (different model
      family; read-only).
- [ ] T-9 commit, PR, exact-head CI, merge per the admitted scope.

## Battery identity

- Baseline 8531f3e (stage admission base): Ran 1255, skipped 50 in CI
  (no fastapi); local with fastapi skipped 17.
- Stage tree: `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p 'test_*.py'` → Ran 1261 / OK (skipped=17) / EXIT=0
  (orchestrator-observed, 72.4 s) — delta exactly the new module (+6
  tests), no new skips, zero ResourceWarnings attributable to the new
  file (grep for the module's tempdir prefix `sea-speed-admission-580-`
  in the battery log: 0 hits). CI (no fastapi) expects the same delta
  with skipped=50.
- Focused: `python3 -m unittest tests.test_release_admission_regression
  -v` → 6/6 OK (orchestrator-observed).
- RED-authenticity of the pins: demonstrated by the test worker via
  fixture flips in both directions (Outcome Contract heading
  present/absent flips the verdict; the metadata-mismatch case fails on
  the runtime-metadata check, not on changed-file equality).

## Completion gate

- [x] AC-001 — new module 6/6 green (focused + full battery evidence
      above).
- [x] AC-002 — testing-policy.md hunk applied; intro + 4 bullets
      preserved (grep-verified: heading line 43, bullet count 4).
- [x] AC-003 — quality-gate-architecture.md hunks applied; no other
      sentence changed meaning (full-diff inspection).
- [x] AC-004 — vps README hunks applied; "Merge does not itself authorize
      a deployment." preserved verbatim at line 227 (grep-verified).
- [x] AC-005 — full battery green with the delta exactly the new module;
      preserved-verbatim strings grep-verified.
- [x] Peer review verdict recorded (T-8).
- [ ] PR merged with exact-head green CI (T-9).

## Requirements traceability

- AC-001 | Task: T-2 | Evidence: tests/test_release_admission_regression.py — 6 tests green through real evaluate()/main() (orchestrator-observed: Ran 6, OK); exact-message pins for the Outcome Contract deny, the metadata-override deny and the typed delegation deny; decision-payload integrity asserted via decisionId + validate_decision(require_allow=True) | Coverage: COVERED
- AC-002 | Task: T-3 | Evidence: git diff hunk on testing-policy.md:50; intro + four bullets preserved verbatim (grep: heading at :43, 4 bullets) | Coverage: COVERED
- AC-003 | Task: T-4 | Evidence: git diff hunks at quality-gate-architecture.md:17/:56/:58; router/standing-delegation wording with workflow_dispatch as manual/recovery and the protected production environment retained | Coverage: COVERED
- AC-004 | Task: T-5 | Evidence: git diff hunks at deploy/vps/README.md:227/:240; verbatim merge sentence grep-verified at :227; "## Manual run" section untouched | Coverage: COVERED
- AC-005 | Task: T-6 | Evidence: full CI-pinned battery Ran 1261 / OK (skipped=17) / EXIT=0 on the stage tree with the delta exactly the new module and zero admission-prefix ResourceWarnings (orchestrator-observed); CI Quality gate re-checks on the PR head | Coverage: COVERED

Requirement-to-AC mapping: R-1 → AC-002; R-2 → AC-003; R-3 → AC-004;
R-4 → AC-001; R-5 → AC-002/AC-003/AC-004 (preserve-verbatim greps) and
AC-005 (battery + diff inspection).

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (3 docs files + 1 new test module + this trio)
- [x] Required tests and evidence complete (Battery identity above)
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (rides the autonomous post-merge VPS contour; runtime bits identical to the deployed baseline; observed, not dispatched, by this stage)
- [ ] Runtime acceptance resolved (none required — no runtime contour mutated by this stage; autonomous pipeline evidence observed post-merge)
- [x] Deferred work recorded (test_line_crossing.py:272 ResourceWarning cleanup is a follow-up candidate outside this scope)
- [x] Risks resolved or explicitly accepted (plan.md Risk profile: NOT REQUIRED with rationale)
- [x] Waivers resolved or current (no waivers)

Evidence notes:

- Full battery green on the stage tree with the delta accounted (+6 tests,
  no new skips, no new ResourceWarnings from the new module).
- No assertion weakened, skipped or mocked to obtain green; only the
  `github_json` transport is mocked, with exact-URL and token assertions.
- No secrets, no local runtime state, no generated output committed; the
  fixture token is a gitleaks-safe low-entropy throwaway value per repo
  precedent.
- Peer review completed and findings addressed or explicitly
  dispositioned (T-8).
- PR merged with exact-head required CI; issue #580 checkpoint updated
  with the stage evidence cursor.
