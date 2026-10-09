# Plan: Tree-aware deployment freshness (merge race with sync bot)

- Issue: #409
- Specification: specs/409-deploy-freshness-tree-aware/spec.md

## Implementation approach

1. RECON-established facts: the freshness logic is inline bash in
   deploy-runtime-autonomous.yml step `Require quality commit is current main
   tip` (id `freshness`) comparing DEPLOY_SHA (quality head_sha) against
   `git rev-parse refs/remotes/origin/main`; on mismatch it writes
   fresh=false and exits 0, so three downstream gates skip and the release
   parks. `scripts/quality/validate_workflow_policy.py` and
   tests/test_autonomous_execution_policy.py hard-require four exact strings
   (step name, refs/remotes/origin/main, Ignoring stale successful Quality
   run, steps.freshness.outputs.fresh == 'true'). The sync bot's only writable
   file set is scripts/ci/sync_tasks_md.py output: specs/<NNN-...>/tasks.md.
   The checkout step uses fetch-depth: 0, so the full history needed for
   merge-base and diff evaluation is already present.
2. Freshness step: keep the fetch + rev-parse + equality check; in the
   mismatch branch first attempt the tree-aware acceptance —
   `git merge-base --is-ancestor "$DEPLOY_SHA" "$CURRENT_MAIN"` (tip is a
   strict descendant because equality was already handled) AND an empty
   `git diff --name-only "$DEPLOY_SHA" "$CURRENT_MAIN" -- .
   ':(glob,exclude)specs/*/tasks.md'` (single-level glob, peer-review aligned
   with the bot staging pathspec). Both true: emit the distinct evidence line,
   fresh=true, fresh_basis=tree-modulo-tasks. Otherwise: fresh=false,
   fresh_basis=stale and the unchanged stale line. Equality path: fresh=true,
   fresh_basis=tip. All four policy-required strings preserved.
3. Summary step (if: always()): add FRESH_BASIS env from
   steps.freshness.outputs.fresh_basis and print
   `- Freshness basis:` next to the existing quality SHA / current main lines
   so all three outcomes (tip / tree-modulo-tasks / stale) are evidenced.
4. Sync workflow: replace `git add -A` with
   `git add -- ':(glob)specs/*/tasks.md'`; no-change guard, bot identity,
   commit message and push flow byte-identical.
5. Contract lockstep in one change: validate_workflow_policy.py gains the
   tree-aware autonomous markers and a sync-merged-tasks.yml marker block
   (staging pathspec required, git add -A banned); the policy test mirrors the
   same markers and pins the staging.
6. Behavioral tests in tests/test_deploy_freshness.py extract the freshness
   run block between stable YAML anchors, execute it with bash and
   GITHUB_OUTPUT redirected to a temp file inside a git fixture
   (R -> A{specs/001-x/tasks.md, api-file} -> B bot tick -> C non-bot), and
   exercise the actual staging command extracted from the sync workflow.

## Architecture

- The freshness gate remains a pure evaluator over local git state: no new
  credentials, tokens, network calls beyond the existing origin fetch, and no
  change to the trigger or concurrency model.
- Acceptance is a conjunction: ancestry (tip built on the quality commit) and
  tree equality modulo the bot pathspec (only tasks.md ticks differ). Either
  condition failing lands on the existing fail-closed stale path.
- The contour jobs keep receiving `commit_sha` =
  steps.release.outputs.sha (the exact quality-approved commit); the
  tree-modulo-tasks acceptance only unblocks evaluation, it never changes what
  is deployed.
- Defense-in-depth is layered: the orchestrator accepts only bot-shaped
  deltas, and the bot itself can only produce them (restricted staging).

## Decisions

- D-1: Tree-aware freshness (issue #409 recommended option 1) rather than bot
  re-runs Quality (new credential surface), bounded retry (slower, still
  racy) or pre-merge sync (changes merge semantics).
- D-2: Strict descendant via `git merge-base --is-ancestor` evaluated only
  after the equality check — the accepted tip is always strictly ahead of the
  quality SHA, so an equal-or-behind tip can never pass the tree-aware branch.
- D-3: The freshness exclusion uses the exact literal
  `':(glob,exclude)specs/*/tasks.md'`, aligned with the bot's staging pathspec
  `':(glob)specs/*/tasks.md'` — both single-level (glob semantics: `*` does
  not cross `/`). In git's default fnmatch `*` crosses `/`, so a bare
  `:(exclude)specs/*/tasks.md` would silently accept nested
  `specs/NNN/sub/tasks.md` deltas as bot-shaped (peer-review LOW finding,
  resolved in this change); both literals are pinned by markers and executed
  by git in tests so the semantics cannot drift into a copied Python regex.
- D-4: `fresh_basis` is a new output with exactly three values (tip /
  tree-modulo-tasks / stale); downstream gates stay binary on
  `steps.freshness.outputs.fresh == 'true'` so no gate logic widens.
- D-5: Restricted staging (`git add -- ':(glob)specs/*/tasks.md'`) instead of
  auditing `git status`: if the bot ever produced a non-tasks.md change, the
  commit step fails loudly instead of shipping an out-of-scope bot commit.
- D-6: Behavioral tests execute the extracted shell block and pathspec rather
  than re-implementing the logic, keeping the test honest against both the
  base (RED) and fixed (green) workflow.

## Affected contours

- Delivery infrastructure only: `.github/workflows/deploy-runtime-autonomous.yml`
  (autonomous production router), `.github/workflows/sync-merged-tasks.yml`
  (bot staging), `scripts/quality/validate_workflow_policy.py`, the policy
  test, the new behavioral test file and this SDD trio.
- No change to api/, frontend/, worker/, deploy/, contracts/, quality
  workflow, deploy-vps.yml or deploy-ubuntu-worker.yml; production impact NONE
  per the #409 Outcome Contract.

## Validation

- Full suite on head branch: `python3 -m unittest discover -s tests -p
  'test_*.py'` green (exact counts in the verification transcript and
  tasks.md AC-4).
- RED proof: tests/test_deploy_freshness.py executed with
  SEA_SPEED_DEPLOY_FRESHNESS_WORKFLOW pointing at the base workflow
  (git show c6da144:...) — the race scenario fails exactly as the issue
  describes; green against the new working-tree workflow.
- `python3 scripts/quality/validate_workflow_policy.py`: green.
- `python3 scripts/ci/validate_sdd.py`: green (repository form; the script
  takes no positional feature argument).
- ruff (`scripts/quality/ruff.toml`) on changed Python files: clean.

## Runtime feedback

- RF-001: Operator actions expected: 0 — the next merge whose sync bot wins
  the race resolves fresh via the tree-aware branch and deploys without
  operator involvement; no config, secret or environment change is involved.
- RF-002: Evidence: orchestrator run summary `- Freshness basis:
  tree-modulo-tasks` (race resolved) / `tip` (no bot tick) / `stale`
  (fail-closed), plus the step-level evidence lines in RF-002 of spec.md.

## Risk profile

- Risk profile: NOT REQUIRED
- Risk-profile rationale: the Change Contract formula derives NOT REQUIRED for
  impact CONTROL_PLANE with NONE-like security/schema/destructive/high-risk
  fields; the risk content below is retained in full as informational prose
  because the change set contains
  `.github/workflows/deploy-runtime-autonomous.yml`, a deployment-workflow
  change, which still carries the full deployment transaction audit — the
  audit and the risk-profile boolean are independent gates. The #409 Outcome
  Contract records the same derived impact CONTROL_PLANE (no api/, worker/ or
  VPS-runtime source paths change).
- Risk analysis (informational, contract formula derives NOT REQUIRED; four
  risks, all mitigated):

  1. Fail-closed conjunction (Category OPS, probability 2, impact 4). The
     tree-aware branch is a strict conjunction — strict descendant AND
     bot-pathspec-confined delta — so out-of-scope deltas and non-descendant
     tips keep the existing fail-closed skip with the unchanged
     stale-evidence line, and the deployed commit stays the exact
     quality-approved SHA (contours receive steps.release.outputs.sha).
     Validation: executed fixture scenarios
     test_non_bot_delta_keeps_fresh_false_with_stale_evidence,
     test_non_descendant_tip_keeps_fresh_false, test_exact_tip_is_fresh.
     Residual risk: LOW — a future bot writing outside specs/*/tasks.md would
     be skipped (stale) and fail closed. Owner: Delivery Orchestrator.
     Status: MITIGATED.
  2. Pathspec lockstep (Category TECH, probability 2, impact 3). Freshness
     acceptance and bot staging anchor on the same single-level
     specs/*/tasks.md pathspec literals, pinned by validate_workflow_policy.py
     markers and exercised through git itself in tests; behavioral tests
     extract and run the real workflow shell block instead of re-implementing
     the logic. Validation: test_staging_command_confines_index_to_feature_tasks_md
     plus the freshness fixture scenarios; validate_workflow_policy.py green.
     Residual risk: LOW — a sync script change to a different file set would
     need this contract updated in lockstep (AC-4 guard). Owner: Delivery
     Orchestrator. Status: MITIGATED.
  3. No new credentials (Category SEC, probability 1, impact 4). No new
     credentials, permissions or triggers; the workflow keeps contents: read,
     actions: read, checks: read, issues: read, pull-requests: read and
     pinned actions; the bot keeps contents: write with a now-narrower staging
     surface. Validation: validate_workflow_source loop over all workflows
     (permissions, pinned SHA actions) green; no new uses: entries
     introduced. Residual risk: NONE. Owner: Delivery Orchestrator. Status:
     MITIGATED.
  4. Bot file-set drift (Category OPS, probability 1, impact 3). If the bot
     ever produced a change outside its pathspec, restricted staging stages
     nothing and the commit fails visibly in the sync job instead of shipping
     an out-of-scope bot commit or widening the freshness exclude.
     Validation: staging pathspec confinement fixture (non-tasks.md changes
     stay unstaged); binary gates unchanged. Residual risk: LOW — the sync
     job would fail loudly and require an orchestrator decision; acceptable
     over silent widening. Owner: Delivery Orchestrator. Status: MITIGATED.

## Test design

- TEST-001 | Covers: tree-aware race resolution (OPS) | Level: unit | Priority: P0 | Evidence: tests/test_deploy_freshness.py — test_tasks_md_only_delta_after_quality_is_fresh_tree_modulo_tasks (bot tick tip yields fresh=true + fresh_basis=tree-modulo-tasks + descendant evidence line; RED-verified against the base workflow where it fails with fresh=false)
- TEST-002 | Covers: fail-closed conjunction (OPS) | Level: unit | Priority: P0 | Evidence: tests/test_deploy_freshness.py — test_non_bot_delta_keeps_fresh_false_with_stale_evidence (api-file delta keeps fresh=false + unchanged stale line) + test_nested_tasks_md_delta_is_not_bot_shaped (tip whose only delta vs the quality SHA is the nested specs/001-x/sub/tasks.md keeps fresh=false; RED-proven against the pre-fix non-glob exclude where it wrongly yielded fresh=true)
- TEST-003 | Covers: fail-closed conjunction (OPS) | Level: unit | Priority: P0 | Evidence: tests/test_deploy_freshness.py — test_non_descendant_tip_keeps_fresh_false (tip behind the quality SHA keeps fresh=false + stale line) + test_exact_tip_is_fresh (equality path fresh=true, basis tip when emitted)
- TEST-004 | Covers: pathspec lockstep (TECH) | Level: unit | Priority: P0 | Evidence: tests/test_deploy_freshness.py — test_staging_command_confines_index_to_feature_tasks_md (extracted staging command stages exactly the feature tasks.md set; plan.md, api-file, nested paths unstaged)
- TEST-005 | Covers: pathspec lockstep (TECH) | Level: unit | Priority: P0 | Evidence: tests/test_autonomous_execution_policy.py — extended router markers (merge-base --is-ancestor, ':(glob,exclude)specs/*/tasks.md', fresh_basis values, Freshness basis:) + test_sync_merged_tasks_bot_stages_only_its_tasks_md_pathspec
- TEST-006 | Covers: no-new-credentials (SEC) | Level: integration | Priority: P0 | Evidence: scripts/quality/validate_workflow_policy.py green (workflow source policies + new sync markers, git add -A ban) and full unittest suite green

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE
- Peer-review finding PR-409-1 (LOW): the freshness exclusion
  `':(exclude)specs/*/tasks.md'` did not exactly mirror the bot's single-level
  staging pathspec — git's default fnmatch lets `*` cross `/`, so a nested
  `specs/NNN/sub/tasks.md` delta would have been silently treated as
  bot-shaped and accepted as fresh.
- Peer-review resolution: exclusion changed to the exact literal
  `':(glob,exclude)specs/*/tasks.md'` (== `':(glob)specs/*/tasks.md'`
  single-level semantics); marker contracts updated in lockstep in
  validate_workflow_policy.py and tests/test_autonomous_execution_policy.py;
  new regression scenario test_nested_tasks_md_delta_is_not_bot_shaped added
  to tests/test_deploy_freshness.py (RED-proven against the pre-fix workflow,
  green after the fix). Scope unchanged; operator actions remain 0.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: canonical Issue #409 Outcome Contract scope; allowed paths (two workflows, policy validator, policy test, new behavioral test, SDD trio) enforced before first write
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged production state | Retry: NO | Rollback: NONE | Evidence: no new deployment machinery — the orchestrator only gains a wider deterministic acceptance predicate before its existing policy evaluation; validate_workflow_policy.py gate runs on the change itself
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: previous workflow bytes remain authoritative on main | Retry: NO | Rollback: revert of the workflow commit restores the exact pre-change freshness gate | Evidence: bounded git commit on the task branch; no runtime host is touched by this change
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: unverified change is not merged | Retry: NO | Rollback: NONE | Evidence: RED-then-green behavioral tests, full unittest suite, validate_workflow_policy.py and validate_sdd.py executed on the head branch
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: no persistent state is written by the freshness step beyond its step outputs and run summary
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond ordinary workflow logs | Retry: NO | Rollback: NONE | Evidence: temporary fixtures live in test-scoped temp directories removed by the test framework; no artifact retention added
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: freshness basis + quality SHA + current tip SHA in the run summary for all outcomes; step-level Freshness / Ignoring stale evidence lines
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: a reverted freshness gate returns to exact-tip-only semantics (fail-closed, never deploys wrong SHA); no runtime rollback path is affected because no deployment transport changed | Evidence: git revert of the single task commit; deploy contours keep requiring policy allow on the exact quality SHA
