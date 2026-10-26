# 558 — Sync workflow: PR creation on REST (no GraphQL)

- Issue: #558
- Status: DELIVERED
- Linked plan: `specs/558-sync-pr-creation-rest/plan.md`
- Linked tasks: `specs/558-sync-pr-creation-rest/tasks.md`

## Product outcome

After this fix, the tasks.md auto-sync flow creates its auto-sync PR through the REST endpoint (`POST /repos/{owner}/{repo}/pulls`) instead of the GraphQL-backed CLI create path. The live failure (run 40281552508: the flip commit landed on `chore/tasks-md-auto-sync`, then PR creation died with `HTTP 401: Bad credentials (https://api.github.com/graphql)`) can no longer recur: the `SYNC_PR_TOKEN` classic PAT (`public_repo` only) cannot serve the GraphQL lookup the CLI create path performs, while REST needs no extra scopes. The flow completes unattended again on any merge with a tasks.md delta.

## User scenarios

- A merge to main flips a DoD marker in a specs tasks.md — the sync workflow pushes the flip branch and creates the auto-sync PR via REST with the generated Change Contract body; no manual PR is needed.
- The auto-sync PR already exists (open from a previous sync) — the flow reuses it and refreshes title/body via REST PATCH (RF-014, unchanged).
- An operator reads the run log — PR creation reports the created PR number; a GraphQL failure path no longer exists in the workflow text.

## Requirements

- FR-001: the create-or-reuse step creates a missing auto-sync PR with `gh api -X POST "repos/${GH_REPO}/pulls"` (REST), extracting the PR number via `--jq '.number'`; the workflow must not contain the GraphQL-backed CLI create path.
- FR-002: the reused-PR refresh path remains REST PATCH (`gh api -X PATCH "repos/${GH_REPO}/pulls/${number}"`, RF-014) and must not contain the GraphQL-backed CLI edit path.
- FR-003: the structural flow test (`tests/test_sync_tasks_md_flow.py`) pins the REST create form and forbids both GraphQL-backed CLI paths in the workflow run blocks.

## Acceptance criteria

- AC-001: `.github/workflows/sync-merged-tasks.yml` creates the auto-sync PR via `gh api -X POST "repos/${GH_REPO}/pulls"` with `head`/`base`/`title`/`body` fields and no GraphQL-backed CLI create occurrence anywhere in the workflow.
- AC-002: `tests/test_sync_tasks_md_flow.py` asserts the REST create pin and the absence of the CLI create path; the existing REST-PATCH reuse pins (RF-014) are preserved.
- AC-003: full test suite green; `scripts/quality/validate_workflow_policy.py` valid.

## Runtime feedback

- The workflow itself is the runtime surface; verification happens on the next natural merge with a tasks.md delta (the sync run then exercises the REST create live). CI on this PR validates the workflow policy and the structural pins; the live-create confirmation is recorded on issue #558 after the first real sync run with a delta.
- Live follow-up (first REST-create exercise, sync run on merge `88e54f2`): the create path's GraphQL dependency was removed, but the REUSE check still used the GraphQL-backed CLI list form and died with the same `HTTP 401: Bad credentials (graphql)` immediately after the branch push. The reuse check was therefore converted to REST as well (`GET /repos/{owner}/{repo}/pulls?head=...&base=main&state=open`); same token-class invariant, recorded here so the spec reflects the live finding.
- Live follow-up 3 (PR #563, manual merge after run 40325903845): RF-006's premise is obsolete — pull_request workflow runs DO fire for a bot-authored auto-sync PR, but they are PARKED as `action_required` (untrusted author), and the ruleset's required context evaluates on those parked runs, blocking both `gh pr checks --required` and the merge regardless of the dispatched runs' conclusions. The flow now approves every parked run on the sync branch via the REST actions-approve endpoint (`actions/runs/{id}/approve`, actions: write already in scope) before polling; the manual approval of the three parked runs in #563 unblocked the merge, proving the mechanism.
- Live follow-up 2 (sync run on merge `cc25cbd`, after the reuse-check REST conversion): the REST list call now gets past GraphQL, but `gh api` with the `SYNC_PR_TOKEN` PAT still fails with `gh: Bad credentials (HTTP 401)` — the same value authenticates the git push (objects uploaded, force-push succeeded) yet is rejected by the REST API. The PAT is therefore pinned to the git push only (`SYNC_PUSH_TOKEN`, preserving the RF-015 human push actor), and every REST call in the create-or-reuse step uses the workflow token; bot authorship of the auto-sync PR is safe because the flow dispatches the required-check workflows itself (RF-006), so no `pull_request` events exist to park.

## NFR assessment

- NFR-001 | Area: Reliability | Target: zero GraphQL dependency in the sync flow's PR lifecycle (create + refresh) | Validation: structural pins (assertNotIn) plus workflow text review | Evidence: `tests/test_sync_tasks_md_flow.py` updated assertions; PR CI | Status: PASS
- NFR-002 | Area: Token least privilege | Target: no new scopes requested — REST create works with existing `pull-requests: write` + contents tokens | Validation: diff shows no `permissions:` change in the workflow | Evidence: PR diff | Status: PASS
- NFR-003 | Area: Loop safety | Target: the change does not alter the sync/flip/merge loop argument (COMPLETION_RE matches only unchecked markers) | Validation: existing loop-safety tests in `tests/test_sync_tasks_md_flow.py` remain green untouched | Evidence: full suite run | Status: PASS
