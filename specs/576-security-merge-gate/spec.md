# Spec: #576 — Security scanners causally required by the Quality gate

- Issue: #576
- Spec: specs/576-security-merge-gate/spec.md
- Plan: specs/576-security-merge-gate/plan.md
- Tasks: specs/576-security-merge-gate/tasks.md
- Base: 60c17502 (origin/main content baseline; the local checkout HEAD
  f7d485f is historical and intentional). BEFORE implementation the three
  production target files were verified byte-identical to main 60c17502
  (empty `git diff 60c17502 -- <path>`, blob hashes equal to the parent's
  source-baseline JSON); after the source wave they differ from 60c17502 by
  exactly the designed delta recorded in plan.md Architecture.
- Authorization: the admitted #576 SOURCE-WAVE scope — seven paths —
  admitted by the delivery orchestrator (canonical receipt: issue #576
  comment 6700510324; gen-2 confirmation: comment 6701988555): (1)
  `.github/workflows/security.yml`, (2)
  `.github/workflows/quality-integration.yml`, (3)
  `scripts/quality/validate_workflow_policy.py` (code worker), (4) the test
  module `tests/quality/test_security_merge_gate.py` (test specialist, RED
  phase; frozen at git blob e8f0504ee515296e75036651193aee8718b77fd0 and
  preserved byte-identical by the code worker), and (5-7) this SDD trio.
  The code worker's writable set is the SIX paths source + trio; the full
  source wave is SEVEN paths; tests/** is frozen. This admits the source
  wave only, not the whole #576 issue: the live synthetic canary /
  branch-protection acceptance and close/delete cleanup stay outside this
  wave (deferred, T-7 in tasks.md) and the issue remains OPEN for them.
  Source-only outcome: no deploy, no settings, no canary publication, no
  issue closure in this wave.
  Scope expansion (owner approval: `commit approved`, 2026-11-08): the
  declared set grows to NINE changed paths — the previous eight (the seven
  SOURCE-WAVE paths plus the #576 diagnostic's
  tests/test_ubuntu_worker_runtime_rebuild.py) plus
  deploy/worker/ubuntu/prepare-runtime.sh — for the #514 fix delta
  (variant a; AC-011/T-10): both `"${candidates[@]:-}"` occurrences in the
  script become `"${candidates[@]}"` (new blob 59f75f5e…, previously
  87c7e060…), pinned by ONE new deterministic regression test in
  tests/test_ubuntu_worker_runtime_rebuild.py; every other admitted file
  keeps its frozen bytes.

## Product outcome

Today the Quality integration gate aggregates its four own domains
(static-contract-security, property-fuzz-reliability, exact-artifact-e2e,
release-deployment-evidence) but has no causal relationship to the Security
gates workflow: `security.yml` runs `pull_request`/`push: main` as an
independent workflow, so a green Quality aggregate can be presented while a
gitleaks or pip-audit failure is red in a separate check — or while Security
never ran at all (e.g. on callers that invoke only Quality). Merge protection
that requires only the Quality aggregate check is therefore not causally
backed by both scanners.

After this change `security.yml` is a reusable workflow (`workflow_call`)
that keeps all of its existing triggers, scanner jobs, pins, commands and
read-only permission, and gains a terminal `security-result` job that needs
BOTH scanners, runs `if: always()`, binds each scanner result through a
direct `needs.<id>.result` env expression, and fails unless both are
literally `success`. `quality-integration.yml` gains an unconditional
`security` job calling `./.github/workflows/security.yml`, and the
`quality-integration` aggregate gains `security` as a fifth mandatory need
with the same strict-success treatment as the four existing domains. A green
Quality aggregate now logically requires both scanners to have succeeded in
the same run. Everything else — scanner commands, gitleaks checksum pin,
upload-on-failure, timeouts, concurrency prefixes, permissions, the four
existing domains — is unchanged.

## User scenarios

- SC-1: a developer opens a PR — Quality runs, calls Security as a nested
  reusable workflow: the INNER `security-result` job prints and requires
  `secret-scan=success` AND `dependency-audit=success`, and the OUTER
  Quality aggregate prints and requires `security=success` alongside the
  four domain results; any scanner failure fails the Quality aggregate.
- SC-2: gitleaks detects a secret in the PR diff — `secret-scan` fails, the
  terminal `security-result` job fails even though the other scanner
  succeeded (`if: always()`), and the Quality aggregate fails on its fifth
  need; the PR cannot present a green Quality.
- SC-3: pip-audit finds a vulnerable pinned requirement — `dependency-audit`
  fails and the same causal chain fails `security-result` and the Quality
  aggregate.
- SC-4: one scanner job is cancelled or skipped — when the terminal job is
  scheduled, `if: always()` makes it evaluate the non-success dependency
  result and fail; an empty/unknown result value also fails the strict
  comparison. A whole-workflow cancellation or an unavailable runner may
  instead yield a cancelled or missing check — never a green one; the
  contract is "no successful Quality without both scanners literally
  successful", not a guarantee that the terminal job always executes.
- SC-5: an attempted weakening — masking a scanner binding with an always-
  true expression, removing a binding, replacing an assert with `exit 0`,
  adding `continue-on-error`/`if` bypasses, inheriting secrets into the
  call, raising permissions, or tampering with the gitleaks checksum pin —
  is caught by the frozen structured/behavioral regression battery (real
  YAML parses, real shells, 14 mutants). The workflow-policy validator is
  a complementary textual gate: its markers pin the wiring's presence and
  do not by themselves reject every semantic mutant.
- SC-6: a maintainer reads the checks list — the Security workflow keeps its
  own name, events and concurrency prefix, so direct PR/push/main Security
  runs behave exactly as before; only the callable surface and the Quality
  causal link are added.

## Requirements

- R-1: `.github/workflows/security.yml` keeps its existing events
  (`pull_request`, `push: main`, `workflow_dispatch`), top-of-file contents
  (name, `permissions: contents: read`, `security-`-prefixed concurrency)
  and BOTH scanner jobs byte-for-byte (job ids, names, timeouts, checkout
  pin `actions/checkout@11d5960…`, gitleaks 8.30.0 with checksum
  `79a3ab57…`, upload-artifact pin and `if: always()` upload, pip-audit
  command lines and targets). The only event-level addition is
  `workflow_call:` with no inputs.
- R-2: `security.yml` gains a terminal job `security-result` that (a) needs
  exactly `secret-scan` and `dependency-audit`, (b) runs `if: always()`
  (bare form), (c) has no `secrets`, no `permissions` override and no
  `continue-on-error`, (d) contains exactly one run step on ubuntu-latest
  with no step-level `if`/`continue-on-error`, (e) binds
  `${{ needs.secret-scan.result }}` and `${{ needs.dependency-audit.result }}`
  as direct full-match env expressions, (f) runs `set -euo pipefail`, prints
  both results, and requires each to be literally `success` via
  `[[ "$…" == success ]]`.
- R-3: `.github/workflows/quality-integration.yml` keeps its events, name,
  top-of-file contents, `quality-integration-`-prefixed concurrency, all
  four existing domain jobs and the aggregate's `if: always()`; it gains an
  unconditional job `security` with `uses:
  ./.github/workflows/security.yml` and no `secrets` (no inherit), no
  `permissions`, no `if`, no `continue-on-error`.
- R-4: the `quality-integration` aggregate job needs the four existing
  domains PLUS `security` (fifth), binds
  `${{ needs.security.result }}` as a direct env expression next to the four
  existing bindings, prints the security result, and asserts
  `[[ "$SECURITY_RESULT" == success ]]` under the existing
  `set -euo pipefail` alongside the four existing strict asserts.
- R-5: `scripts/quality/validate_workflow_policy.py` keeps every existing
  policy check and narrowly extends its `_require_markers` style to require:
  the Security reusable trigger, terminal job, both scanner needs, direct
  result bindings and strict success asserts; and the Quality causal
  binding (local reusable call, fifth need, direct binding, strict assert).
  stdlib-only; no new dependency, no YAML parser, no new module.
- R-6: the frozen test module `tests/quality/test_security_merge_gate.py`
  (git blob e8f0504ee515296e75036651193aee8718b77fd0) passes unmodified
  during the code/GREEN phase: all 6 methods green with PyYAML present
  (zero skips), including all 14 mutation-sensitivity cases.
- R-7: no other workflow, source, test, config, secret or settings path
  changes; the 19 foreign working-tree paths are preserved untouched; no
  reset/stash/clean; no commit/push/PR/merge by the code worker.

## Acceptance criteria

- AC-001: security.yml keeps its existing events, scanner jobs, pins,
  commands, timeouts, read-only workflow permission (exactly
  `contents: read`, no job overrides) and `security-` concurrency prefix,
  and gains `workflow_call` plus the terminal `security-result` job that
  needs both scanners, runs `if: always()`, carries direct
  `needs.<id>.result` env bindings referenced by its run block, and has no
  secrets/permissions/continue-on-error bypasses
  (test_security_workflow_shape).
- AC-002: the terminal `security-result` run block, executed verbatim
  through bash with env built from the actual parsed bindings, accepts both
  scanners `success` and rejects every non-success result of either scanner
  (failure, failed, skipped, cancelled, empty, unknown)
  (test_security_terminal_shell_behavior).
- AC-003: quality-integration.yml keeps its events and four domain jobs and
  gains the unconditional `security` call job (local reusable workflow, no
  secrets/permissions/if/continue-on-error) and the aggregate's fifth need
  `security` with a direct binding referenced by the aggregate run block
  (test_quality_wiring_shape).
- AC-004: the aggregate run block, executed verbatim through bash, accepts
  all five needs `success` and rejects both a non-success security result
  (all six non-success values) and a failure of each of the four existing
  domains (test_quality_aggregate_shell_behavior).
- AC-005: baseline protections hold — scanner pins/commands/timeouts,
  read-only permissions, both concurrency prefixes, aggregate shape and the
  four domain bindings survive the change (test_baseline_protections).
- AC-006: mutation sensitivity — all 14 mutants (checksum tampering,
  continue-on-error, scanner condition, permission weakening/scoping,
  concurrency prefix change, binding removal, assert removal, masked
  binding expression, secrets inherit, step-level bypasses) are caught by
  the battery (test_mutations_detected).
- AC-007: `python3 scripts/quality/validate_workflow_policy.py` exits 0
  with the new Security/Quality causal markers required and every
  pre-existing policy check intact.
- AC-008: post-merge SOURCE-wave acceptance — orchestrator-owned, PENDING
  (never produced locally): on real GitHub CI a Quality PR/push run
  actually propagates the nested reusable call — both scanners execute
  inside the Quality run, the inner `security-result` and the outer
  aggregate gate evaluate true actual results, and the existing check
  names are preserved. Real nested Actions propagation is NOT claimed from
  local evidence. The full-issue synthetic canary / branch-protection
  acceptance and close/delete cleanup are EXCLUDED from this source wave
  (deferred, T-7); the full #576 issue remains OPEN for them.
- AC-009: the #576 diagnostic expansion (test-only, four admitted paths:
  tests/test_ubuntu_worker_runtime_rebuild.py + this SDD trio) — opt-in,
  failure-only, bounded D576 sidecar diagnostic instrumenting a GENERATED
  COPY of the production script deploy/worker/ubuntu/prepare-runtime.sh
  (the production script byte-identical, blob 59f75f5e… after the #514
  fix delta, previously 87c7e060… at the diagnostic freeze; the frozen
  Security test module e8f0504e… untouched; the 76 original assertions of
  the instrumented module byte-identical, 10 frozen method ASTs intact);
  whole module 21 tests 0 failures; review loop closed (same-role test
  peer PASS with adversarial oracles; cross-family security validator
  FAIL → bounded-read + real-stderr-re-emit fixes → CONDITION_MET).
- AC-010: diagnostic publication + natural new-head CI observation —
  orchestrator-owned, PENDING (never produced locally): one guarded
  diagnostic commit onto PR #607, then the natural CI run on the new head
  is observed; if the #514 test fails again, the published bounded D576
  block in the job log is the RF-CI001 evidence. Stage ends at
  observation: NO merge, NO deploy, NO old-head retry (the single
  old-head rerun is consumed), NO speculative fix.
- AC-011: the #514 fix delta (variant a; owner approval `commit approved`,
  2026-11-08) — deploy/worker/ubuntu/prepare-runtime.sh replaces BOTH
  `"${candidates[@]:-}"` occurrences with `"${candidates[@]}"` (inner
  dedup loop, behavior-neutral; outer legacy-adopt loop — the actual fix:
  with an empty candidates array the `[@]:-` form expands to ONE empty
  element under bash 5.x, the legacy-adopt guard could then pass system
  python, and `cp -a --reflink=auto ""` died under `set -euo pipefail` —
  the deterministic PR Validation #514 failure; on boxes where
  /usr/bin/python matches the lock's python section the script would
  ADOPT system python instead of building the hash-locked venv); new
  script blob 59f75f5e919eaa30be6214d13c26a473409e9765 (previously
  87c7e060…); pinned by exactly ONE new deterministic structural test
  (test_no_quoted_empty_default_array_expansion_in_repo_script) asserting
  the trap core `[@]:-` absent from the script text — RED-verified
  (restoring `:-` at the outer loop fails the pin) and GREEN-verified;
  all pre-existing assertions byte-identical; whole module 22 tests
  0 failures 0 skips; `bash -n` exit 0.

## Runtime feedback

- CONTROL_PLANE only: api/**, worker/**, deploy/**, frontend/** untouched;
  VPS and Ubuntu runtime contours unaffected; no deployment transaction
  audit (the validator derives that requirement only for deploy/** paths,
  deployment workflows, or a PRODUCTION_LEARNING trigger — none apply).
  CI is the first runtime: after merge, the next Quality run on a PR/push
  exercises the nested call live. All failure paths fail closed and loud
  (when the terminal job is scheduled, non-success scanner results fail it
  and the aggregate; a whole-workflow cancellation or unavailable runner
  yields a cancelled/missing check, never green).
  Rollback of the change itself goes through the normal PR/CI gates (a
  revert PR); no manual revert/push directly on main. Out of scope here
  (deferred T-7; the full #576 issue remains OPEN): canary publication,
  protection/rulesets reads or changes, issue closure, close/delete
  cleanup (the 47-Connector capability inventory has no delete_branch and
  no protection/rulesets read), any admin/permission/settings change.
  Source-wave acceptance (AC-008) is not full-issue closure.

## NFR assessment

- NFR-001 | Area: causal gating | Target: a green Quality aggregate logically requires both Security scanners to be literally `success` in the same run — when the terminal job is scheduled, any non-success scanner result (including cancelled/skipped/empty/unknown) fails it and the aggregate; a whole-workflow cancellation or unavailable runner yields a cancelled/missing check, never green (a no-success-without-scanners contract, not an execution guarantee) | Validation: frozen battery executes the ACTUAL run blocks through bash with env from the ACTUAL parsed bindings (accept/reject matrices for both the terminal and the aggregate) | Evidence: code-worker-observed `python3 -W error::ResourceWarning -m unittest tests.quality.test_security_merge_gate -v` — "Ran 6 tests … OK" (6/6, zero skips) after the edit; RED truth (6 methods, 10 sub-failures) recorded in plan.md Validation | Status: PASS
- NFR-002 | Area: preservation | Target: existing Security scanner jobs, Quality domains, events, pins, commands, timeouts, permissions and concurrency prefixes are byte-preserved; only the specified additions land | Validation: test_baseline_protections plus exact git diff inspection against base 60c17502 | Evidence: test_baseline_protections observed ok; diff limited to the designed additions (workflow_call line, terminal job, call job, aggregate need/env/print/assert, validator markers) | Status: PASS
- NFR-003 | Area: fail-closed integrity | Target: the merge decision is never re-implemented or masked — bindings are direct `needs.<id>.result` full-match expressions, asserts are literal `[[ == success ]]`, no COE, no step/job conditions on gate steps, no secrets inherit, no permission raise | Validation: test_mutations_detected (14 mutants incl. masked-binding and secrets-inherit) + test_security_workflow_shape/test_quality_wiring_shape clean-job assertions | Evidence: test_mutations_detected observed ok (14 subtests) | Status: PASS
- NFR-004 | Area: minimality | Target: six changed paths total for the code worker (3 source + 3 SDD); no new module, helper framework, dependency or parser; validator extension stays stdlib-only `_require_markers` style | Validation: exact git diff inspection; ruff check; validator run | Evidence: diff inspected; `ruff check --config scripts/quality/ruff.toml .` "All checks passed!"; validator exit 0 | Status: PASS
- NFR-005 | Area: least privilege | Target: workflow permissions stay exactly `contents: read` in both workflows with no job-level overrides; the reusable call requests no secrets | Validation: test_baseline_protections `_assert_read_only` on both workflows + call-job clean assertions | Evidence: observed ok in the GREEN run | Status: PASS
