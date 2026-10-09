# Tasks: Tree-aware deployment freshness (merge race with sync bot)

- Specification: specs/409-deploy-freshness-tree-aware/spec.md

## Delivery tasks

- T-409-001: RECON the freshness chain: freshness step in
  deploy-runtime-autonomous.yml, downstream binary gates, sync bot staging,
  policy validator and policy test marker contracts, baseline suite state;
  record findings in the durable progress file
- T-409-002: Make the freshness step tree-aware: strict-descendant check via
  git merge-base --is-ancestor plus a delta confined to the
  ':(glob,exclude)specs/*/tasks.md' single-level pathspec; emit fresh_basis in
  all paths (tip / tree-modulo-tasks / stale) with the distinct Freshness
  evidence line while
  preserving the four policy-required strings, the three binary downstream
  gates and the unchanged stale-evidence line; add the Freshness basis line to
  the always() summary step
- T-409-003: Restrict the sync bot staging from git add -A to
  git add -- ':(glob)specs/*/tasks.md' keeping the no-change guard, bot
  identity, commit message and push flow unchanged
- T-409-004: Extend scripts/quality/validate_workflow_policy.py and
  tests/test_autonomous_execution_policy.py in the same change: new
  tree-aware markers, new sync-merged-tasks.yml marker contract with a git
  add -A ban, no existing marker weakened
- T-409-005: Add tests/test_deploy_freshness.py: behavioral tests that extract
  the freshness run block from the workflow YAML, execute it with bash in a
  temporary git fixture (tasks.md-only delta, non-bot delta, non-descendant
  tip, exact tip) and exercise the extracted sync staging pathspec for index
  confinement; prove RED against the base workflow from c6da144
- T-409-006: Run the verification battery (full unittest suite, new battery
  verbose, validate_workflow_policy.py, validate_sdd.py, ruff on changed
  Python files) and commit locally with the approved author identity; leave
  the branch unpushed for orchestrator admission

## Completion gate

- [ ] T-409-001
- [ ] T-409-002
- [ ] T-409-003
- [ ] T-409-004
- [ ] T-409-005
- [ ] T-409-006
- [x] Issue/spec/plan/tasks current — Outcome Contract on #409 (exact '## Outcome Contract' heading per evaluate_production_policy parser)
- [ ] Exact changed-file scope verified
- [x] Required tests and evidence complete — RED vs base (2 defect failures), green head 796/4, validate_workflow_policy + validate_sdd pass; peer review APPROVE with 2 LOW findings fixed in-change
- [x] Required CI green — orchestrator-owned (PR #433 exact-head CI 8/8 green: Repository validation, quality-integration 4/4 sub-jobs, Gitleaks, pip-audit)
- [x] Exact-green-head merge complete — squash merge #433; main @ 7940dc892e9f1a928382e356a966df44406813d3
- [x] Deployment state resolved — orchestrator-owned (this merge IS the main-chain deploy: Autonomous runtime deployment run 37884775053 completed success after rerun; contours derived CONTROL_PLANE -> no runtime transport; deployed commit identity = exact quality SHA)-aware path)
- [x] Runtime acceptance resolved — orchestrator-owned (production exercise: freshness gate passed and policy evaluation decision=allow issue=#409 pr=#433 commit=7940dc89 decision_id=dab7edc1c96099cb7ff1179e3b0f5325a7355e2231a20b7cef67c5c55c926; basis=tip on this run since the bot push was GH013-rejected by branch protection — the tree-modulo-tasks branch is RED-verified behaviorally and stays armed for the first bot-landing merge)s basis on the next raced merge)
- [ ] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — plan.md Risk profile analysis (4 risks, all MITIGATED; fail-closed regression covered by executed fixture scenarios)ATED)
- [ ] Waivers resolved or current — none

## Definition of Done

- [x] Issue/spec/plan/tasks current — Outcome Contract on #409 (exact '## Outcome Contract' heading per evaluate_production_policy parser)
- [ ] Exact changed-file scope verified
- [x] Required tests and evidence complete — RED vs base (2 defect failures), green head 796/4, validate_workflow_policy + validate_sdd pass; peer review APPROVE with 2 LOW findings fixed in-change
- [x] Required CI green — orchestrator-owned (PR #433 exact-head CI 8/8 green: Repository validation, quality-integration 4/4 sub-jobs, Gitleaks, pip-audit)
- [x] Exact-green-head merge complete — squash merge #433; main @ 7940dc892e9f1a928382e356a966df44406813d3
- [x] Deployment state resolved — orchestrator-owned (delivery-infrastructure change; production exercise = run 37884775053 success; no runtime transport by derived impact)n impact NONE)
- [x] Runtime acceptance resolved — orchestrator-owned (freshness step + policy evaluator exercised live in run 37884775053, decision=allow; tree-modulo-tasks basis recorded when a bot-confined tip first reaches the gate — currently guarded by behavioral RED tests since bot pushes are branch-protection-blocked)on the next raced merge)
- [ ] Deferred work recorded — none
- [x] Risks resolved or explicitly accepted — plan.md Risk profile analysis (4 risks, all MITIGATED; fail-closed regression covered by executed fixture scenarios)ATED)
- [ ] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-409-002,T-409-005 | Evidence: test_tasks_md_only_delta_after_quality_is_fresh_tree_modulo_tasks (extracted workflow block executed in a git fixture: tasks.md-only delta tip yields fresh=true + fresh_basis=tree-modulo-tasks + descendant evidence line; RED-proven against base c6da144 workflow where it fails with fresh=false) | Coverage: COVERED
- AC-2 | Task: T-409-002,T-409-005 | Evidence: test_non_bot_delta_keeps_fresh_false_with_stale_evidence + test_non_descendant_tip_keeps_fresh_false (fresh=false with the unchanged Ignoring stale successful Quality run line; fresh_basis=stale when emitted) + test_nested_tasks_md_delta_is_not_bot_shaped (nested specs/001-x/sub/tasks.md delta keeps fresh=false; RED-proven against the pre-fix non-glob exclude) + test_exact_tip_is_fresh | Coverage: COVERED
- AC-3 | Task: T-409-003,T-409-005 | Evidence: test_staging_command_confines_index_to_feature_tasks_md (extracted staging command stages exactly the feature tasks.md set; plan.md, api-file and nested paths stay unstaged) + validate_workflow_policy.py sync-merged-tasks marker contract with git add -A ban | Coverage: COVERED
- AC-4 | Task: T-409-004,T-409-006 | Evidence: validate_workflow_policy.py autonomous markers extended (merge-base --is-ancestor, ':(glob,exclude)specs/*/tasks.md', fresh_basis values) and test_autonomous_execution_policy.py extended in the same change; full unittest suite green | Coverage: COVERED
- AC-5 | Task: T-409-002,T-409-004 | Evidence: summary step prints Freshness basis + Quality commit + Current main for all outcomes; marker contracts pin fresh_basis=tree-modulo-tasks, fresh_basis=tip and the Freshness basis: summary line | Coverage: COVERED
