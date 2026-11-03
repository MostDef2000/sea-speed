# Spec: #580 — release-process docs drift + admission regression

- Issue: #580
- Specification: specs/580-release-docs-admission-regression/spec.md
- Authorization: the #580 scope (three release-process docs files +
  tests/test_release_admission_regression.py + this trio) admitted by the
  delivery orchestrator; base 8531f3e (branch
  fix/580-release-docs-admission-regression). The VPS REQUIRED PR
  classification (path-derived from the `deploy/vps/README.md` edit) was
  disclosed to the owner before the first repository write.

## Product outcome

The release-process documentation describes the deployment model that is
actually implemented: production deployment runs under the standing
production delegation — initiated autonomously when the aggregate quality
check succeeds for a push to `main`, gated by the deterministic production
policy — while `workflow_dispatch` on the VPS workflow remains a
manual/recovery entry. Today three docs files still describe the retired
manual-only/per-release-approval model (audit #534 P2-06), and the admission
decision that production enforces on every merged change (Outcome Contract
required; mutable PR runtime metadata can never override source-derived
contours) has no regression coverage. This stage corrects the three docs
files without weakening any mandatory gate statement and pins the admission
decision end to end in a new stdlib-only regression module
(`tests/test_release_admission_regression.py`, 6 tests through the real
`evaluate()` and real `main()` of `scripts/release/evaluate_production_policy.py`).

## User scenarios

- SC-1: an operator reads `docs/quality/testing-policy.md`,
  `docs/quality/quality-gate-architecture.md` or `deploy/vps/README.md` —
  the release/deployment sections now match the standing-delegation reality
  (autonomous router on a green main quality run, policy-gated contours,
  `workflow_dispatch` as manual/recovery), and every mandatory gate
  statement (exact SHA, quality check, evidence, rollback, "Merge does not
  itself authorize a deployment.") is preserved.
- SC-2: a future change weakens the admission evaluator (drops the Outcome
  Contract requirement, or lets mutable PR metadata override source-derived
  contours) — the new regression module reds with the exact production
  messages, blocking the regression at the quality gate.
- SC-3: CI (no fastapi, no network) runs the battery — the new module is
  stdlib-only, mocks only the `github_json` transport with exact-URL
  assertions, builds its exact diff from a real temporary git repository,
  and adds no skips to the CI skip set.

## Requirements

- R-1: `docs/quality/testing-policy.md` release section describes the
  standing production delegation; the section intro and the four separation
  bullets are preserved verbatim.
- R-2: `docs/quality/quality-gate-architecture.md` stage flow and Stage 4
  describe the autonomous router reality; `workflow_dispatch` remains
  described as a manual/recovery entry; the protected `production`
  environment mention is kept.
- R-3: `deploy/vps/README.md` deployment paragraph is reworded to the
  policy-gated reality with "Merge does not itself authorize a deployment."
  preserved verbatim; the contour-classification note states that runtime
  impact is derived by file path, not content type.
- R-4: `tests/test_release_admission_regression.py` (new) pins the admission
  decision through the real `evaluate()` and real `main()` with zero
  production-code changes: missing Outcome Contract denies with the exact
  message; docs/tests-only change admits with NOT REQUIRED contours and a
  self-consistent decision payload; declared NOT REQUIRED metadata cannot
  override a runtime diff; `main()` deny/allow paths emit the real
  exit codes/stderr/outputs; missing delegation with `--require-allow`
  denies with the typed reason.
- R-5: no mandatory gate statement is weakened anywhere in the changed docs.

## Acceptance criteria

- AC-001: `tests/test_release_admission_regression.py` runs 6 tests, all
  green: (1) missing Outcome Contract → `PolicyError("canonical Issue is
  missing Outcome Contract")`; (2) docs/tests-only merged change with a
  valid Outcome Contract → decision allow, vps contour NOT REQUIRED,
  approvedFiles == exact declared list, sourceCommit == the fixture merge
  SHA, decision payload integrity (decisionId binds the canonical payload,
  `validate_decision(require_allow=True)` passes); (3) merge containing
  `api/app/main.py` with declared metadata NONE/NOT REQUIRED → PolicyError
  starting "mutable PR runtime metadata does not match exact source-derived
  contours" with the derived VPS/REQUIRED contours in the message; (4) real
  `main()` deny → exit 1, PolicyError text on stderr, no output files; (5)
  real `main()` allow → exit 0, `github-output.txt` emits
  allowed=true/vps_required=false and evidence.json records the allow; (6)
  missing delegation + `--require-allow` → exit 1 with
  `standing_delegation_missing`.
- AC-002: `docs/quality/testing-policy.md` — the manual/per-release-approval
  claim is replaced by the standing-delegation description; the intro
  "Merge, release, deployment and runtime acceptance are separate
  operations." and the four bullets (green PR ≠ deployment; merge ≠
  evidence; artifact ≠ installation; deployment ≠ acceptance) are preserved
  verbatim.
- AC-003: `docs/quality/quality-gate-architecture.md` — the stage flow line
  and Stage 4 describe the router/standing-delegation reality with
  `workflow_dispatch` as manual/recovery and the protected `production`
  environment retained; no other sentence in the file changes meaning.
- AC-004: `deploy/vps/README.md` — line ~227 reworded with "Merge does not
  itself authorize a deployment." preserved verbatim; line ~240 states the
  path-based classification (a docs edit under `deploy/vps/**` still
  classifies as a VPS-contour change; `docs/**`/`tests/**` classify as
  non-runtime); the "## Manual run" section is untouched.
- AC-005: the full CI-pinned battery (`python3 -W error::ResourceWarning -m
  unittest discover -s tests -p 'test_*.py'`) is green on the stage tree
  with the delta exactly the new module (no new skips, no new
  ResourceWarnings attributable to the new file), and the preserved-verbatim
  strings are grep-verified.

## Runtime feedback

- The autonomous deploy router will evaluate the merged main SHA; the diff
  classifies as a VPS-contour change by path (`deploy/vps/README.md`) while
  the runtime bits remain identical to the deployed baseline, so the deploy
  re-verifies policy and re-deploys byte-identical runtime content. The
  canonical issue #580 carries the Outcome Contract section the admission
  evaluator requires (the exact behavior pinned by AC-001 case 1).

## NFR assessment

- NFR-001 | Area: Test isolation | Target: zero production-code changes; no network, no credentials, no live GitHub calls in tests | Validation: diff inspection + focused battery run | Evidence: git diff touches only 3 docs files + 1 new test module + this trio; `github_json` mocked with exact-URL assertion and token equality check | Status: PASS
- NFR-002 | Area: Gate preservation | Target: every mandatory gate statement survives verbatim | Validation: grep checks on the final tree | Evidence: "Merge does not itself authorize a deployment." present at deploy/vps/README.md:227; testing-policy intro + 4 bullets intact (grep count 4 + heading line 43) | Status: PASS
- NFR-003 | Area: Battery integrity | Target: full CI-pinned battery green with the delta exactly the new module and no new skips | Validation: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'` locally and the exact-head CI Quality gate | Evidence: local battery green on the stage tree (orchestrator-observed, see tasks.md Battery identity); CI result recorded on the PR | Status: PASS
