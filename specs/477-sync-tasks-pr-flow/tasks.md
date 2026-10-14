# Tasks: #477 sync-merged-tasks PR flow

- Issue: #477
- Specification: specs/477-sync-tasks-pr-flow/spec.md

## Delivery tasks

- T-477-001: RECON the defect and the PR-side CI surface (per work order; progress notes are a guide, not authority): read the old sync-merged-tasks.yml (direct-to-main push defect), sync_tasks_md.py (COMPLETION_RE idempotency), pr-validation.yml + quality-integration.yml (D-2 PR-side CI surface), validate_change_contract.py + change-control-policy-v1.json (required sections/fields/impact classes), validate_sdd.py event mode (significance prefixes, validate_pr_link, requires_deployment_transaction_audit — sync workflow NOT covered)
- T-477-002: Prove the loop-safety premise empirically: scratch round-trip of sync_tasks_md.py (sync #1 flips 4 markers → "1 tasks.md file(s) synced"; syncs #2/#3 → "all changed tasks.md already current", no-op)
- T-477-003: Write NEW scripts/ci/build_sync_pr_body.py — deterministic Change-Contract-compliant auto-sync PR body generator (--source-sha, repeated --changed-file, --out; six sections + full required-field surface for the NONE-impact specs/*/tasks.md delta; SystemExit on empty delta or short sha)
- T-477-004: Write NEW tests/test_sync_tasks_md_flow.py (7 tests: round-trip no-op incl. suffix-once semantics, marker discipline — recognized-only flips / never unchecks / freshness-clean, generated body passes the REAL validate_contract with impact NONE, sha/files/six-sections/branch/no-placeholder assertions, empty-delta refusal, CLI subprocess round-trip)
- T-477-005: Rewrite .github/workflows/sync-merged-tasks.yml in place — KEEP trigger/name/event-filter/pinned checkout (ref main, fetch-depth 2) and the sync+freshness commands; ADD stale-trigger guard (tip vs workflow_run.head_sha → HAS_DELTA=false exit green), delta detection (porcelain AND merge diff non-empty), body generation into $RUNNER_TEMP, permissions pull-requests: write, concurrency sync-merged-tasks (cancel-in-progress: false), force-with-lease branch push to chore/tasks-md-auto-sync, PR reuse-or-create (gh pr list/create), bounded required-checks wait (≤5×30 s for exit 4/8, then timeout 1800 gh pr checks --watch --fail-fast), squash self-merge (--delete-branch, deterministic subject), loud ::error:: failure notice
- T-477-005b: Record the workflow verification approach — the workflow cannot execute locally; local verification is yaml.safe_load + structural assertions + the 7-test suite; LIVE acceptance is the fix PR's own PR-side CI and the first post-merge sync run (dogfooding: it flips this trio's remaining DoD markers via the first auto-sync PR), recorded by the orchestrator on issue #477
- T-477-006: Write the SDD trio specs/477-sync-tasks-pr-flow/ per the validated house format (spec: outcome/scenarios/scope/R-1..R-6/AC-001..006/RF/NFR-001..004; plan: REQUIRED risk profile + RISK-001..005 nine-field rows, D-1..D-9 incl. D-2 PR-side CI surface and D-6 no-TX-audit decision with the validator-rule rationale; tasks: T-477-001..006, traceability, 10-marker DoD); run the verification battery and record observed output
- T-477-007: Verification sweep: yaml.safe_load + structural assertions on the rewritten workflow; full unittest discover (expected 951 = 944 + 7 new); focused #477 suite; ruff (CI config); validate_repo; validate_sdd (plain, trio on disk); git diff --stat review; durable progress notes under /tmp/opencode/477/ (outside the git tree); NO commit, NO push (orchestrator-owned)

## Completion gate

- [x] T-477-001
- [x] T-477-002
- [x] T-477-003
- [x] T-477-004
- [x] T-477-005
- [x] T-477-005b
- [x] T-477-006
- [x] T-477-007
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (.github/workflows/sync-merged-tasks.yml, NEW scripts/ci/build_sync_pr_body.py, NEW tests/test_sync_tasks_md_flow.py, SDD trio; durable progress notes OUTSIDE the git tree)
- [x] Required tests and evidence complete (transcripts under /tmp/opencode/477/; worker-recorded; commit/PR/merge orchestrator-owned)

## Requirements traceability

- AC-001 | Task: T-477-005 | Evidence: TEST-001 (yaml assertions), TEST-006 | Coverage: COVERED
- AC-002 | Task: T-477-003, T-477-004 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-477-002, T-477-004 | Evidence: TEST-001, TEST-003 | Coverage: COVERED
- AC-004 | Task: T-477-005 | Evidence: TEST-004 | Coverage: COVERED
- AC-005 | Task: T-477-005 | Evidence: TEST-004 | Coverage: COVERED
- AC-006 | Task: T-477-004, T-477-007 | Evidence: TEST-005, TEST-006 | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [x] Deployment state resolved — control-plane-only change (one housekeeping workflow + PR-body generator + tests); no runtime contour, no deploy workflow, no migration; nothing to deploy
- [x] Runtime acceptance resolved — no runtime contour; live acceptance is the fix PR's own PR-side CI plus the first post-merge sync run (first auto-sync PR flips the remaining DoD markers above), recorded by the orchestrator on issue #477
- [x] Deferred work recorded — workflow logic (gh flag drift, runner-image gh versions) is verified only live; rulesets/branch-protection and deploy-*.yml out of scope; sync_tasks_md.py sha-suffix quirk recorded, deliberately unfixed
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-005 mitigated in plan.md
- [x] Waivers resolved or current — none
