# Plan — Issue #576 Security scanners causally required by Quality

- Issue: #576
- Spec: specs/576-security-merge-gate/spec.md
- Base: 60c17502 (origin/main); the local checkout HEAD f7d485f is
  historical and intentional. BEFORE implementation the three target
  source files were verified byte-identical to main 60c17502 (empty
  `git diff 60c17502 -- <path>`, blob hashes equal to the parent's source
  baseline JSON); after the source wave they differ from 60c17502 by
  exactly the designed delta below. The 19 foreign dirty/untracked
  working-tree paths are preserved untouched; no reset/stash/clean.

## Architecture

Three source files, additive only:

- `.github/workflows/security.yml` — the `on:` block gains `workflow_call:`
  (no inputs) after the existing `pull_request`/`push: main`/
  `workflow_dispatch` events; a terminal job `security-result` is appended
  after `dependency-audit`: `needs: [secret-scan, dependency-audit]`,
  `if: always()` (bare), `runs-on: ubuntu-latest`, no secrets/permissions/
  continue-on-error, exactly one run step whose env binds
  `SECRET_SCAN_RESULT: ${{ needs.secret-scan.result }}` and
  `DEPENDENCY_AUDIT_RESULT: ${{ needs.dependency-audit.result }}` (direct
  full-match expressions) and whose script is `set -euo pipefail`, prints
  both results and requires each via `[[ "$…" == success ]]`. The terminal
  job is the reusable surface's single green/fail verdict: when it is
  scheduled, `if: always()` makes it evaluate the dependency results even
  after a scanner failure, so a cancelled/skipped scanner can never produce
  a green verdict; a whole-workflow cancellation or an unavailable runner
  may still yield a cancelled/missing check — never green. The contract is
  "no successful Quality without both scanners literally successful", not a
  guarantee of execution. Both scanner jobs, all pins (checkout
  `11d5960…`, gitleaks 8.30.0 + checksum `79a3ab57…`, upload-artifact
  `ea165f8…`, setup-python `a26af69…`), commands, targets, timeouts, the
  `security-` concurrency prefix and `permissions: contents: read` are
  byte-preserved.
- `.github/workflows/quality-integration.yml` — an unconditional job
  `security` (`uses: ./.github/workflows/security.yml`, display name only,
  no `secrets`/`permissions`/`if`/`continue-on-error`) is inserted before
  the aggregate; the `quality-integration` aggregate keeps
  `if: always()` and gains `- security` as a fifth need,
  `SECURITY_RESULT: ${{ needs.security.result }}` in the existing step env,
  a `printf 'security=%s\n'` line and a fifth
  `[[ "$SECURITY_RESULT" == success ]]` assert under the existing
  `set -euo pipefail`. The four existing domains and their bindings/asserts
  are untouched; events, name, top contents and the
  `quality-integration-` concurrency prefix are untouched. The callee
  inherits `github.workflow` from the caller, but the two concurrency
  groups carry different static prefixes (`security-` vs
  `quality-integration-`), so no collision arises.
- `scripts/quality/validate_workflow_policy.py` — reads `security.yml`
  next to the other workflows and extends the existing
  `_require_markers` style: four causal markers appended to the existing
  quality tuple (local reusable call, fifth need, direct binding, strict
  assert) and one new marker block for security.yml (reusable trigger,
  terminal job, both scanner needs, direct bindings, strict asserts).
  Every pre-existing check (autonomous router, sync, deploy lanes,
  action allowlist/pins, permissions, heredoc/if-expression hygiene) is
  unchanged; stdlib-only; no YAML parser.

## Decisions

- **Terminal aggregate job inside Security**: a reusable workflow's own
  result is the union of its jobs; without a terminal `if: always()` job
  needing both scanners, a skipped/cancelled scanner could leave the call
  green. The terminal job makes "both scanners succeeded" a single
  machine-checkable verdict, and the frozen battery executes its real run
  block rather than re-implementing the decision in Python.
- **Direct env bindings, not inline expressions**: each result is bound via
  a full-match `${{ needs.<id>.result }}` env expression and consumed as
  `$VAR` in the script. A masked expression such as
  `needs.x.result == 'success' && 'success' || 'success'` would always
  evaluate to success on GitHub; the battery's masked-binding mutant proves
  such a shape is rejected (the binding no longer full-matches, the variable
  goes unset under `set -u`, the shell fails).
- **Call job carries nothing**: no `secrets` (no inherit), no `permissions`,
  no `if`, no `continue-on-error` — the callee's own read-only permission
  applies and the call cannot widen or condition it.
- **Marker-style validator extension**: the existing validator is
  substring-marker based; the extension follows that style instead of
  introducing a YAML parser. Structured/behavioral semantics (bindings,
  shell acceptance matrices, mutants) are protected by the frozen real-YAML
  tests, so the validator only needs to pin the wiring's existence.
  Rejected alternative: a structured parser in the validator — rejected as
  scope expansion (new partial YAML framework for six lines of
  requirements).
- **No new dependencies/modules**: bash builtins in the two run blocks;
  stdlib-only Python. No workflow inputs, no secrets plumbing, no
  concurrency changes.

## Affected contours

- CONTROL_PLANE — `.github/workflows/security.yml`,
  `.github/workflows/quality-integration.yml`,
  `scripts/quality/validate_workflow_policy.py` and this SDD trio;
  classified CONTROL_PLANE by data/contracts/change-control-policy-v1.json
  (`.github/workflows/**`, `scripts/quality/**`).
- VPS / Ubuntu worker — NOT affected: api/**, frontend/**, deploy/**
  untouched; no deployment transaction audit (the validator derives that
  requirement only for deploy paths, deployment workflows or a
  PRODUCTION_LEARNING trigger — none apply).
- tests/quality/test_security_merge_gate.py — admitted SOURCE-WAVE scope
  (seven paths) but test-protected in the code phase: authored in RED by
  the test
  specialist, frozen at git blob e8f0504ee515296e75036651193aee8718b77fd0,
  preserved byte-identical by the code worker; no other tests/** path is
  touched.
- All other workflows, scripts, specs, source and config untouched; the 19
  foreign dirty/untracked working-tree paths (583/595/604/530 artifacts and
  the frozen test module) are preserved as-is.

## Validation

- RED (parent-executed before the code fix, against base 60c17502): the
  frozen module (423 lines, 6 test methods) ran authentic RED — 10
  sub-failures total: 6 security non-success cases accepted by the old
  Quality aggregate (rc 0 with a non-success security result) + 4 new
  wiring gaps (missing workflow_call/terminal/call/fifth-need shape); no
  harness unbound-variable artifacts credited.
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
  no logic blocker. The parent executes the full battery (now observed —
  see below) and verified the test hash, storing the frozen copy
  (/tmp/opencode/576/test/frozen-tests.py).
- GREEN (code-worker-observed, after the three source edits):
  `python3 -W error::ResourceWarning -m unittest
  tests.quality.test_security_merge_gate -v` — "Ran 6 tests … OK" (6/6,
  zero PyYAML skips, all 14 mutants caught). The frozen module blob is
  unchanged before/after (e8f0504e…).
- Parent-observed full gates (2026-11-07, /tmp/opencode/576/final-gates.log):
  the full suite on the wave head ran 1368 tests OK with 17 environment
  skips (the six new Security methods all ran — no PyYAML skips; the 17
  skips are the unchanged old-suite environment skips; the inherited
  `TemporaryDirectory` `ResourceWarning` is known and unsuppressed), Ruff
  base/strict PASS, mypy strict-tier (7 files) PASS, two exact-artifact
  builds deterministic + validate PASS, all nine gates green — parent
  observations, not expectations.
- Gates: `python3 scripts/quality/validate_workflow_policy.py` exit 0
  ("Workflow policy valid: …"); `ruff check --config
  scripts/quality/ruff.toml .` "All checks passed!"; SDD repository
  validation and the native PR-contract seam observed (see tasks.md
  Completion gate); `git diff --check` clean; both new run blocks pass
  `bash -n`.
- Pending by design (not prechecked): PR CI on the exact PR head, exact-
  green-head merge, and the post-merge actual nested reusable-workflow
  propagation on GitHub (AC-008, SOURCE scope). The full-issue synthetic
  canary / protection acceptance and close/delete cleanup are DEFERRED
  (T-7, outside this source wave, pending external capability) — the full
  #576 issue remains OPEN for them; no CI success or merge claims are
  made.

## Runtime feedback

- CI is the first runtime for this change: after merge, the next Quality
  run on a PR or push/main exercises the nested reusable call against real
  GitHub — both scanners execute inside the Quality run, the terminal
  `security-result` job and the aggregate gate evaluate real results. Real
  nested Actions propagation is verified by the parent post-merge, never
  claimed from local evidence. Failure modes fail closed (when the
  terminal job is scheduled, any non-success scanner result fails it and
  the aggregate; a whole-workflow cancellation or unavailable runner
  yields a cancelled/missing check, never green); rollback of the
  change itself is a normal revert PR through the standard review/CI gates.
  The full-issue live acceptance (synthetic canary, protection read,
  close/delete cleanup) is explicitly OUT of this source-only wave and
  DEFERRED as unchecked T-7 (pending external capability): the
  47-Connector capability inventory has no delete_branch and no
  protection/rulesets read, no canary is published here, and no
  admin/permission/settings/creds/cleanup-workflow/fallback action is
  authorized. The code-CI binding is NOT claimed to be immune to an admin
  later removing branch protection. Source-wave acceptance (AC-008) does
  not close the full #576 issue.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the causal chain is enforced twice — inside Security (terminal `if: always()` job needing both scanners with direct bindings and literal strict asserts) and inside Quality (fifth aggregate need with the same strict treatment); the frozen battery executes the real run blocks against accept/reject matrices and 14 weakening mutants, and the policy validator pins the wiring | Validation: 6/6 frozen methods GREEN observed post-edit (zero skips); RED truth 6+4 recorded; validator exit 0 | Residual risk: real nested reusable-workflow propagation on GitHub is not observable locally — it is verified by the parent on actual post-merge CI (AC-008, PENDING); a masked/conditional bypass shape not in the mutant set would need new coverage | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: this wave is source-only — no canary publication, no protection/rulesets reads or changes, no issue closure, no cleanup (the 47-Connector capability inventory has no delete_branch and no protection/rulesets read); the full-issue live synthetic canary / protection acceptance and close/delete cleanup are DEFERRED as explicit unchecked T-7 (outside this source wave, pending external capability), the full #576 issue stays OPEN for them (source-wave acceptance is not full-issue closure), and #604/#595 keep their own natural no-op acceptance PENDING (not substituted by this wave) | Validation: scope accounting in tasks.md (T-6 SOURCE post-merge CI, T-7 deferred); no such action taken (verifiable from the session/diff) | Residual risk: until the post-merge CI observation lands, the merge-gate improvement is proven only by the frozen battery; the code-CI binding is not immune to an admin later removing branch protection | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-003 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the validator extension is substring-marker based (consistent with the existing style), so a structurally different but marker-satisfying file could theoretically pass the validator alone; the frozen real-YAML battery is the structured/behavioral oracle and must stay green in CI | Validation: validator exit 0 plus 6/6 battery GREEN observed together | Residual risk: marker/structure drift between the two layers is caught by CI running both gates on every PR | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: security.yml shape — events kept + workflow_call, terminal job needs/if/bindings/run-reference, no bypass keys, read-only permissions | Level: integration | Priority: P0 | Evidence: tests/quality/test_security_merge_gate.py::SecurityMergeGateTests::test_security_workflow_shape observed ok (frozen blob e8f0504e…)
- TEST-002 | Covers: terminal shell behavior — accepts both-success, rejects all six non-success values of either scanner, executing the ACTUAL run block via bash | Level: integration | Priority: P0 | Evidence: test_security_terminal_shell_behavior observed ok (12 subtests)
- TEST-003 | Covers: quality wiring — events/domains kept, clean call job, aggregate fifth need + binding + run reference | Level: integration | Priority: P0 | Evidence: test_quality_wiring_shape observed ok
- TEST-004 | Covers: aggregate shell behavior — accepts all-five-success, rejects security non-success (6 values) and each domain failure | Level: integration | Priority: P0 | Evidence: test_quality_aggregate_shell_behavior observed ok (10 subtests)
- TEST-005 | Covers: baseline protections — scanner pins/commands/timeouts, read-only permissions, concurrency prefixes, aggregate shape/bindings | Level: integration | Priority: P0 | Evidence: test_baseline_protections observed ok
- TEST-006 | Covers: mutation sensitivity — 14 weakening mutants all caught (checksum, COE, conditions, permissions, concurrency, binding removal, assert removal, masked binding, secrets inherit, step bypasses) | Level: integration | Priority: P0 | Evidence: test_mutations_detected observed ok (14 subtests)
- TEST-007 | Covers: policy validator — causal markers required, all pre-existing policy checks intact | Level: integration | Priority: P0 | Evidence: `python3 scripts/quality/validate_workflow_policy.py` exit 0 observed

## Correct-course check

- Trigger: NONE
  Classification rationale: this is a new planned wave inside the admitted
  #576 scope, not a production runtime or deployment failure, so
  PRODUCTION_LEARNING does not apply; the architecture is unchanged in kind
  (no ARCHITECTURE_PIVOT) and the admitted seven-path file scope is
  unchanged (no MATERIAL_SCOPE_CHANGE).
- Issue impact: NONE — the wave implements exactly the admitted #576
  outcome; the issue remains OPEN by design for the pending live
  acceptance items.
- Specification impact: NONE — spec authored fresh for this wave from the
  admitted scope; no correction needed.
- Plan impact: NONE — plan authored fresh for this wave; no correction
  needed.
- Tasks impact: NONE — tasks authored fresh for this wave; no correction
  needed.
- Authorization impact: UNCHANGED — same seven admitted paths; canonical
  receipt issue #576 comment 6700510324 + gen-2 comment 6701988555; no new
  paths, no scope expansion, no new approvals.
- Follow-up: post-merge, the orchestrator verifies real nested Actions
  propagation on actual CI (AC-008) and later owns the full-issue live
  canary/protection acceptance; no fictitious outcome values are recorded
  before observation.
