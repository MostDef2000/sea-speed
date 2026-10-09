# Spec: Tree-aware deployment freshness (merge race with sync bot)

- Issue: #409
- Specification: specs/409-deploy-freshness-tree-aware/spec.md

## Product outcome

On merge, `Sync merged tasks.md` (GITHUB_TOKEN bot commit) and
`Autonomous runtime deployment` (workflow_run on Quality success) race for the
main tip. When the bot wins, the orchestrator's freshness gate sees quality
SHA != current tip, marks `fresh=false`, and skips both deploy contours; the
bot commit does not retrigger push workflows and has no Quality run of its
own, so the merged release silently stalls until a manual unblock (observed on
#408 / issue #393: quality `58bb96b` vs bot tip `02d231a`, run 37626106989).

This change makes the freshness gate tree-aware while staying fail-closed:

1. When the current main tip is a strict descendant of the quality-approved
   commit AND the SHA delta is confined to the sync bot's file set
   (`specs/*/tasks.md`), the freshness step marks `fresh=true` with
   `fresh_basis=tree-modulo-tasks` and the run proceeds to contour evaluation,
   still deploying the exact quality-approved commit (the tick commit is
   documentation-only and is not deployed).
2. In every other mismatch case (delta outside the bot file set, or a tip that
   is not a descendant of the quality SHA) the gate stays fail-closed:
   `fresh=false` with the existing stale-evidence line, now plus a
   `fresh_basis=stale` output.
3. The sync bot stages only its tasks.md pathspec (no `git add -A`), so bot
   commit content is provably limited to its file set.
4. The run summary shows freshness basis, quality SHA and current tip SHA for
   all outcomes (tip / tree-modulo-tasks / stale).

## User scenarios

- US-1: A merge lands and the sync bot commits a tasks.md tick before the
  orchestrator reads the tip: the orchestrator accepts the tip as fresh
  (`fresh_basis=tree-modulo-tasks`), evaluates policy, and deploys the exact
  quality-approved commit — no silent stall, no manual unblock commit.
- US-2: A merge lands and the delta between the quality SHA and the tip
  touches anything outside `specs/*/tasks.md`: the orchestrator skips with the
  existing stale-evidence line — fail-closed behavior is unchanged.
- US-3: The current main tip is not a descendant of the quality-approved SHA
  (force-push, unrelated history): the orchestrator skips with the existing
  stale-evidence line.
- US-4: Any observer reads the run summary after any outcome (tip /
  tree-modulo-tasks / stale): it shows the freshness basis, the quality SHA
  and the current tip SHA.

## Scope

- `.github/workflows/deploy-runtime-autonomous.yml`: freshness step gains the
  tree-aware acceptance branch (strict descendant + bot-pathspec-confined
  delta), `fresh_basis` output in all paths, and a distinct evidence line for
  the tree-modulo-tasks path; the four policy-required strings, the three
  downstream binary `fresh == 'true'` gates and the stale-evidence line are
  preserved; summary step gains the freshness-basis evidence line.
- `.github/workflows/sync-merged-tasks.yml`: staging restricted from
  `git add -A` to `git add -- ':(glob)specs/*/tasks.md'`; bot identity,
  no-change guard, commit message and push flow unchanged.
- `scripts/quality/validate_workflow_policy.py`: autonomous router marker
  contract extended (tree-aware essentials) and a new sync-bot staging marker
  contract added; no existing marker weakened.
- `tests/test_autonomous_execution_policy.py`: router markers extended in the
  same change plus a new sync-staging pin; no existing test weakened.
- `tests/test_deploy_freshness.py` (new): behavioral tests that extract and
  execute the actual workflow shell block and the actual sync staging pathspec
  in temporary git fixtures; default source is the working-tree workflow.
- `specs/409-deploy-freshness-tree-aware/spec.md`, `plan.md`, `tasks.md` and
  the durable progress file.
- Out of scope: quality-integration.yml, deploy-vps.yml,
  deploy-ubuntu-worker.yml, scripts/ci/sync_tasks_md.py (its output file set
  is unchanged), delegation/policy evaluators, and any runtime source.

## Requirements

- R-1: The freshness step accepts the current tip only when the tip is a
  strict descendant of the quality-approved SHA (verified with
  `git merge-base --is-ancestor`) AND `git diff --name-only` between them,
  excluding `specs/*/tasks.md` via the single-level glob pathspec
  `':(glob,exclude)specs/*/tasks.md'`, is empty; in that case it emits
  `fresh=true` and `fresh_basis=tree-modulo-tasks` plus a distinct evidence
  line naming the tip, the quality SHA and the confined delta.
- R-2: On exact SHA equality the step emits `fresh=true` with
  `fresh_basis=tip`; in every other mismatch case it emits `fresh=false` with
  `fresh_basis=stale` and the existing `Ignoring stale successful Quality run`
  line; the four policy-required strings and the three binary downstream
  `fresh == 'true'` gates are preserved.
- R-3: The sync job stages only its tasks.md pathspec (no `git add -A`); its
  no-change guard, bot identity, commit message and push flow are unchanged.
- R-4: `validate_workflow_policy.py` and `tests/test_autonomous_execution_policy.py`
  require the tree-aware essentials (`merge-base --is-ancestor`, the
  `':(glob,exclude)specs/*/tasks.md'` pathspec, `fresh_basis=tree-modulo-tasks`,
  `fresh_basis=tip`, summary basis evidence, and the sync staging pathspec)
  in the same change.
- R-5: Behavioral tests execute the extracted freshness shell block and the
  extracted staging pathspec in temporary git fixtures covering: tasks.md-only
  delta (fresh), non-bot delta (stale), non-descendant tip (stale), exact tip
  (fresh), and index confinement of the staging pathspec to feature
  `tasks.md` files.

## Acceptance criteria

- AC-1: Race resolved deterministically -- when current main tip is a strict descendant of the quality-approved commit AND the SHA delta is confined to `specs/*/tasks.md` paths, the orchestrator marks `fresh=true` with `fresh_basis=tree-modulo-tasks` and proceeds to contour evaluation.
- AC-2: Fail-closed unchanged -- any delta outside `specs/*/tasks.md`, or a tip that is not a descendant of the quality SHA, keeps `fresh=false` with the existing stale-evidence line.
- AC-3: Sync-bot defense-in-depth -- the sync job stages only its synced tasks.md paths (no `git add -A`), so bot commit content is provably limited to its file set.
- AC-4: Contract lockstep -- `scripts/quality/validate_workflow_policy.py` and `tests/test_autonomous_execution_policy.py` updated in the same change; full unittest suite green.
- AC-5: Run-summary evidence shows freshness basis, quality SHA and current tip SHA for all paths (tip / tree-modulo-tasks / stale).

## Runtime feedback

- RF-001: Operator actions expected: 0 — the fix is pure delivery-infrastructure
  evaluator logic; the next main-chain merge exercises the tree-aware path
  automatically and no operator action is required to unblock the race class.
- RF-002: Evidence lines: `Freshness: tip <sha> descends from quality SHA
  <sha> with delta confined to specs/*/tasks.md` on the race path;
  `Ignoring stale successful Quality run for <sha>; current main is <sha>`
  on the fail-closed path; run summary `- Freshness basis:` / `- Quality
  commit:` / `- Current main:` lines for all outcomes.

## NFR assessment

- NFR-001 | Area: reliability/operations | Target: the #409 merged-but-not-deployed race class is closed deterministically — a tasks.md-only bot tick between the quality SHA and the main tip no longer parks the release, and no manual empty-commit unblock is needed | Validation: executed behavioral fixture tests where the extracted workflow block runs against commits R->A->B(bot tick)->C: B-tip yields fresh=true with fresh_basis=tree-modulo-tasks (fails against the base workflow, RED proven) | Evidence: tests/test_deploy_freshness.py — test_tasks_md_only_delta_after_quality_is_fresh_tree_modulo_tasks | Status: PASS
- NFR-002 | Area: security | Target: no widening of deployment authority — the tree-aware branch requires BOTH strict descendant proof AND a delta confined to the bot pathspec; non-descendant tips and out-of-scope deltas keep fail-closed skipping with the unchanged stale-evidence line, and the deployed commit remains the exact quality-approved SHA | Validation: executed fixture scenarios for non-bot delta and non-descendant tip (fresh=false + stale line) and exact-tip (fresh=true); deployed commit_sha remains steps.release.outputs.sha | Evidence: tests/test_deploy_freshness.py — test_non_bot_delta_keeps_fresh_false_with_stale_evidence, test_non_descendant_tip_keeps_fresh_false, test_exact_tip_is_fresh | Status: PASS
- NFR-003 | Area: least-privilege | Target: the sync bot can only ever commit its file set — staging is restricted to the tasks.md glob pathspec so bot commit content is provably limited; the freshness exclude `':(glob,exclude)specs/*/tasks.md'` and the staging pathspec `':(glob)specs/*/tasks.md'` are exact aligned literals with identical single-level semantics (`*` does not cross `/`), executed through git rather than a drifting Python copy | Validation: executed index-confinement fixture (staged set is exactly the feature tasks.md files; plan.md, api-file and nested paths stay unstaged), executed nested-delta freshness fixture (a tip whose only delta vs the quality SHA is specs/001-x/sub/tasks.md stays fresh=false — peer-review LOW finding regression test) plus marker contracts in validate_workflow_policy.py and the policy test | Evidence: tests/test_deploy_freshness.py — test_staging_command_confines_index_to_feature_tasks_md, test_nested_tasks_md_delta_is_not_bot_shaped; scripts/quality/validate_workflow_policy.py sync-merged-tasks block | Status: PASS
