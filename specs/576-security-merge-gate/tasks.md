# Tasks — Issue #576 security merge gate (source-only wave)

- Issue: #576
- Spec: specs/576-security-merge-gate/spec.md
- Plan: specs/576-security-merge-gate/plan.md
- Base: 60c17502 (origin/main); local checkout HEAD f7d485f historical and
  intentional. BEFORE implementation the three production target files were
  verified byte-identical to main 60c17502 (blob hashes equal the parent's
  source baseline JSON; empty git diff); after the source wave they differ
  from 60c17502 by exactly the designed delta. The 19 foreign working-tree
  paths are preserved untouched.

## Delivery tasks

- [x] T-1 `.github/workflows/security.yml` — add `workflow_call:` to the
  existing events; append the terminal job `security-result` (needs
  `secret-scan` + `dependency-audit`, `if: always()`, ubuntu-latest, one
  run step, direct `${{ needs.*.result }}` env bindings, `set -euo
  pipefail`, print both results, strict `[[ == success ]]` per scanner).
  Both scanner jobs byte-preserved (ids, names, commands, gitleaks
  checksum + action pins, upload `if: always()`, targets, timeouts); top
  contents and `security-` concurrency prefix unchanged; no secrets
  inherit, no new permissions, no job overrides/conditions/COE/masking.
- [x] T-2 `.github/workflows/quality-integration.yml` — add the
  unconditional job `security` (`uses:
  ./.github/workflows/security.yml`, no secrets/permissions/if/COE);
  extend the `quality-integration` aggregate with `security` as a fifth
  need, the direct `SECURITY_RESULT` binding, the `printf` line and the
  strict success assert under the existing `set -euo pipefail`. Events,
  name, top contents, `quality-integration-` concurrency prefix and all
  four existing domain jobs unchanged except the adjacent additions.
- [x] T-3 `scripts/quality/validate_workflow_policy.py` — narrow
  `_require_markers`-style extension: Security reusable trigger, terminal
  job, both scanner needs, direct bindings and strict asserts; Quality
  causal binding (local reusable call, fifth need, direct binding, strict
  assert). All existing policy checks retained; stdlib-only; no new
  module/dependency/parser.
- [x] T-4 SDD trio (this directory) conforming to scripts/ci/validate_sdd.py.
- [x] T-5 Evidence battery — focused frozen-module run and policy/lint/SDD
  gates observed and recorded in the completion gate below. Admitted
  SOURCE-WAVE scope accounting (SEVEN paths): the two workflows + the
  validator (code worker); tests/quality/test_security_merge_gate.py
  authored in RED by the test worker and preserved byte-identical by the
  code worker (frozen git blob e8f0504ee515296e75036651193aee8718b77fd0
  before/after); this SDD trio. The code worker's writable set is the SIX
  paths source + trio; the full source wave is SEVEN paths; tests/** is
  frozen. All OTHER tests, scripts, workflows and specs untouched.
- [ ] T-6 Post-merge SOURCE-wave acceptance — orchestrator-owned, PENDING
  (unchecked by design): on real GitHub CI, a Quality PR/push run must
  show the nested reusable call actually executing both scanners inside
  the Quality run, with the inner `security-result` and outer aggregate
  gates evaluating true actual results and the existing check names
  preserved (AC-008). Not producible at code-worker time; never faked.
- [ ] T-7 DEFERRED full-issue acceptance — orchestrator-owned, explicitly
  OUTSIDE this source wave, UNCHECKED and NOT executed: the live synthetic
  canary, branch-protection/rulesets read acceptance and close/delete
  cleanup on issue #576 (the 47-Connector capability inventory has no
  delete_branch and no protection/rulesets read — pending external
  capability; requires its own explicit scope). The full #576 issue
  remains OPEN until that later acceptance; source-wave acceptance
  (T-6/AC-008) is not full-issue closure.
- [x] T-8 diagnostic implementation (DONE, parent-verified at blob
  413506fa): the four-path test-only diagnostic per AC-009 (bounded D576
  sidecar, CHILD producer, overflow characterization unit, old-#514
  first-call wrap with real-stderr re-emit on failure, bounded 512-byte
  reads); whole module 21 tests 0 failures; 10 frozen method ASTs + 76
  original asserts + published7/foreign19 baselines intact.
- [ ] T-9 diagnostic publication + CI observation (PENDING,
  orchestrator-owned): one guarded diagnostic commit onto PR #607;
  observe the natural new-head CI; capture the #514 outcome and (on
  failure) the published D576 block as RF-CI001 evidence; stage ends at
  observation (no merge/deploy/old-head retry/speculative fix).

## Completion gate

- Baseline truth: BEFORE implementation the three production target files
  were byte-identical to main 60c17502 (parent source-baseline JSON; empty
  git diff); after the source wave they differ by exactly the designed
  delta. Parent-observed 2026-11-07 preflight: the inherited repository
  suite was 1362 tests OK with 17 environment skips; the inherited
  `TemporaryDirectory` `ResourceWarning` is known and unsuppressed (do not
  credit it as a failure).
- Parent-observed full gates (2026-11-07, /tmp/opencode/576/final-gates.log):
  the full suite on the wave head ran 1368 tests OK with 17 environment
  skips (the six new Security methods all ran — no PyYAML skips; the 17
  skips are the unchanged old-suite environment skips), Ruff base/strict
  PASS, mypy strict-tier (7 files) PASS, two exact-artifact builds
  deterministic + validate PASS, all nine gates green — parent
  observations, not expectations. Required CI on the exact PR head,
  exact-green-head merge and the post-merge actual Actions observation
  (T-6/AC-008) remain PENDING and unchecked; no publish/merge claim.
- RF-CI001 (UNRESOLVED, root cause UNKNOWN): the mandatory Repository
  Validation check failed twice on the old PR #607 head on
  test_issue_514_rebaked_manifest_keys_are_canonical_and_reverify
  (AssertionError: 1 != 0 : cp: cannot stat '': No such file or
  directory); the single old-head rerun is CONSUMED; no flake or
  pre-existing claim is made (local pass is not CI equivalence); the T-8
  diagnostic exists to capture bounded D576 evidence on the next natural
  CI run (T-9/AC-010).
- RED (parent-executed before the code fix, against base 60c17502): the
  frozen module ran authentic RED — 6 test methods, 10 sub-failures: 6
  security non-success cases accepted by the old Quality aggregate (rc 0)
  + 4 new wiring gaps (workflow_call / terminal job / call job / fifth
  need); no harness unbound-variable artifacts credited.
- Peer truth (roles attributed; no model IDs): the earlier test review
  role produced two STATIC review passes (finding secrets/fixture issues)
  and then hit a quota error with no final verdict; the fresh same-role
  test peer (session ses_e4bd93801ffezn58NiHZiHGCH0) DID EXECUTE the
  frozen module in its own sandbox — 6 methods, 10 authentic RED
  sub-failures on the base, and PASS on the whole contract plus all 14
  mutants after the fix. The independent code peer (session
  ses_e4bcdba57ffeLARsUOCNdaAJ80) DID EXECUTE the GREEN 6-method run (and
  separately reproduced the base RED 6/10) and returned SOURCE PASS with
  REQUEST_CHANGES on the docs — addressed by this a2 doc-only pass. The
  canonical cross-family validator security peer (session
  ses_e4e37d612ffeC6Ljfd0EMcNVB6) performed a STATIC review only (not
  executed) with the same six documentation truth findings, SOURCE PASS,
  no logic blocker. The parent executes the full battery (now observed
  above) and verified the test hash, storing the frozen copy
  (/tmp/opencode/576/test/frozen-tests.py).
- Focused frozen module `python3 -W error::ResourceWarning -m unittest
  tests.quality.test_security_merge_gate -v`: OBSERVED (code worker, after
  the source edits) "Ran 6 tests … OK" — 6/6 green, zero PyYAML skips, all
  14 mutants caught; frozen blob e8f0504e… unchanged before/after (cmp
  against the parent's frozen copy OK); no test edits by the code worker.
- `python3 scripts/quality/validate_workflow_policy.py`: OBSERVED "Workflow
  policy valid: protected public main -> exact quality -> standing policy
  -> restricted VPS/Ubuntu zero-touch execution" (exit 0).
- `ruff check --config scripts/quality/ruff.toml .`: OBSERVED "All checks
  passed!" (exit 0).
- `python3 scripts/ci/validate_sdd.py`: OBSERVED "Sea Speed SDD validation
  passed" (exit 0); the native PR seam (validate_change_contract.py +
  validate_sdd.py --event over the exact seven-path diff with a prepared
  template body) OBSERVED passing in scratch — the parent owns the final
  PR body verification/publication.
- `git diff --check`: clean; both new run blocks pass `bash -n`; YAML
  parses (the frozen battery loads both workflows with real PyYAML).
- Preservation: the 19 foreign paths compare equal to
  /tmp/opencode/576/preserve-baseline.json; the three source files started
  byte-identical to main 60c17502 (baseline JSON hashes) and only the
  designed additions are present in the diff.
- Pending by design (orchestrator-owned, NOT prechecked): required CI green
  on the exact PR head; exact-green-head merge; the post-merge actual
  nested reusable-workflow propagation on GitHub (T-6/AC-008, SOURCE
  scope). T-7 (full-issue live synthetic canary / protection acceptance
  and close/delete cleanup) is DEFERRED outside this source wave, pending
  external capability, explicitly unchecked and not executed. The
  recognized completion markers below stay unchecked for the normal
  marker-sync flip; issue #576 is not closed from here (no code-worker
  closure authority), and #604/#595 keep their own natural no-op
  acceptance PENDING.

## Requirements traceability

- AC-001 | Task: T-1 | Evidence: test_security_workflow_shape observed ok | Coverage: COVERED
- AC-002 | Task: T-1 | Evidence: test_security_terminal_shell_behavior observed ok (12 subtests) | Coverage: COVERED
- AC-003 | Task: T-2 | Evidence: test_quality_wiring_shape observed ok | Coverage: COVERED
- AC-004 | Task: T-2 | Evidence: test_quality_aggregate_shell_behavior observed ok (10 subtests) | Coverage: COVERED
- AC-005 | Task: T-1, T-2 | Evidence: test_baseline_protections observed ok | Coverage: COVERED
- AC-006 | Task: T-1, T-2 | Evidence: test_mutations_detected observed ok (14 subtests) | Coverage: COVERED
- AC-007 | Task: T-3 | Evidence: `python3 scripts/quality/validate_workflow_policy.py` exit 0 observed | Coverage: COVERED
- AC-008 | Task: T-6 | Evidence: post-merge actual nested reusable-workflow propagation on GitHub CI — both scanners executing inside a Quality run, inner `security-result` and outer aggregate gates on true actual results, existing check names preserved — automatic, orchestrator-owned; PENDING — to be observed and recorded on issue #576 after merge, not observed at code-worker time; the full-issue canary/protection/cleanup acceptance is deferred T-7, outside this SOURCE-wave AC set | Coverage: RUNTIME-MANUAL | Reason: live GitHub nested-Actions evidence cannot be produced locally; post-merge CI supplies it
- AC-009 | Task: T-8 | Evidence: parent-verified at blob 413506fa — whole module 21 tests 0 failures, 10 frozen method ASTs + 76 original asserts + published7/foreign19 baselines intact; review loop closed (same-role test peer PASS with adversarial oracles; cross-family security validator FAIL → bounded-read + real-stderr-re-emit fixes → CONDITION_MET) | Coverage: COVERED
- AC-010 | Task: T-9 | Evidence: one guarded diagnostic commit onto PR #607, then the natural new-head CI run observed; on a #514 failure the published bounded D576 block in the job log is the RF-CI001 evidence — automatic, orchestrator-owned; PENDING — never produced locally; stage ends at observation (no merge/deploy/old-head retry/speculative fix) | Coverage: RUNTIME-MANUAL | Reason: CI evidence cannot be produced locally; the natural new-head CI run supplies it

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified — admitted SOURCE-WAVE SEVEN-path
  accounting:
  .github/workflows/security.yml, .github/workflows/quality-integration.yml,
  scripts/quality/validate_workflow_policy.py (code worker),
  tests/quality/test_security_merge_gate.py (test worker RED phase; frozen
  at e8f0504ee515296e75036651193aee8718b77fd0 and byte-identical through
  the code phase), and specs/576-security-merge-gate/{spec,plan,tasks}.md;
  the code worker's writable set is the SIX paths source + trio; all OTHER
  tests, scripts, workflows and specs untouched; the 19 foreign
  dirty/untracked files preserved untouched
- [x] Required tests and evidence complete (code-worker-observed: frozen
  module 6/6 OK, zero skips, 14/14 mutants; workflow-policy validator,
  ruff, SDD and the native PR-contract seam observed; parent-OBSERVED full
  battery: 1368 tests OK / 17 environment skips, all nine gates, Ruff
  base/strict PASS, mypy strict-tier PASS, deterministic exact-artifact
  builds + validate PASS — /tmp/opencode/576/final-gates.log)
- [ ] Required CI green — orchestrator-owned (exact PR head)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [x] Deployment state resolved — NOT REQUIRED (CONTROL_PLANE only; no VPS/Ubuntu deploy contour in this change)
- [ ] Runtime acceptance resolved — SOURCE-wave scope only: post-merge actual nested reusable-workflow propagation observed on GitHub CI (T-6/AC-008: both scanners inside a Quality run, inner + outer gates on true actual results, check names preserved); the full-issue live synthetic canary / branch-protection acceptance and close/delete cleanup are DEFERRED (T-7, outside this source wave, pending external capability) and the full #576 issue remains OPEN until then (evidence on issue #576)
- [x] Deferred work recorded (T-7: full-issue live synthetic canary, branch-protection/rulesets read acceptance and close/delete cleanup — deferred outside this source wave, pending external capability, unchecked and not executed; no canary publication, no protection/rulesets reads or changes, no admin/permission/settings/creds/cleanup-workflow/fallback actions in this source-only wave — the 47-Connector capability inventory has no delete_branch and no protection/rulesets read; #604/#595 natural no-op acceptance stays PENDING and is not substituted by this wave; the code-CI binding is not claimed immune to an admin later removing branch protection)
- [x] Risks resolved or explicitly accepted (plan.md Risk profile: REQUIRED, RISK-001..003; RISK-001/RISK-002 ACCEPTED — real nested Actions propagation (T-6/AC-008) is pending parent observation and the full-issue canary/protection acceptance is deferred T-7; RISK-003 MITIGATED by the frozen real-YAML battery)
- [x] Waivers resolved or current (no waivers)
