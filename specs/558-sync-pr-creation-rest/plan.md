# Plan — 558 Sync workflow: PR creation on REST

- Specification: `specs/558-sync-pr-creation-rest/spec.md`
- Issue: #558
- Status: DELIVERED

## Architecture

Single-step control-plane fix in one workflow file plus its structural test. The sync flow's PR lifecycle has two code paths — reuse (PATCH an open auto-sync PR) and create (open a new one). RF-014 (2026-10-14) already moved the reuse path to REST because the `SYNC_PR_TOKEN` classic PAT (`public_repo`) cannot serve GraphQL `read:org`-demanding calls; the create path kept the GraphQL-backed CLI form and failed live (run 40281552508, `HTTP 401: Bad credentials (https://api.github.com/graphql)`). The fix makes both paths REST, matching the established RF-014 pattern: same `gh api` client, same token env, `-F body=@file` for the generated Change Contract body, `--jq '.number'` for the PR number.

## Decisions

- DEC-001: REST `gh api -X POST repos/.../pulls` instead of switching the token to a GraphQL-capable PAT. Rationale: least privilege (no new scopes; the PAT stays `public_repo`), and REST already proven for PATCH/issue operations in this repository's live runs.
- DEC-002: Pin the fix structurally in `tests/test_sync_tasks_md_flow.py` (assertIn REST create, assertNotIn CLI create). Rationale: the flow's existing test style pins workflow text for policy invariants (RF-014/RF-015/RF-018/RF-019 pins live there); the invariant here is genuinely textual (which API the workflow calls). Runtime confirmation rides the next natural sync run with a delta and is recorded on #558.
- DEC-003: No `permissions:` change in the workflow. Rationale: `pull-requests: write` and `contents: write` are already declared and sufficient for REST PR creation; widening would violate least privilege.

## Affected contours

- CONTROL_PLANE only: `.github/workflows/sync-merged-tasks.yml`, `tests/test_sync_tasks_md_flow.py`, `specs/558-sync-pr-creation-rest/`. No api/, worker/, deploy/, schemas/, contracts/ paths; no VPS, no Ubuntu worker, no Windows (retired).

## Validation

- Local: `python3 -m unittest tests.test_sync_tasks_md_flow -v` (flow pins green), full suite, `python3 scripts/quality/validate_workflow_policy.py` (valid), dogfooded `validate_change_contract` and `validate_sdd` against the PR body and diff.
- PR: Repository validation (SDD + Change Contract), quality-integration, static security, Gitleaks.
- Live: the next merge with a tasks.md delta exercises the REST create end-to-end; result recorded on #558.

## Runtime feedback

- Not applicable beyond the workflow itself; see spec Runtime feedback for the live-confirmation path.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: `tests/test_sync_tasks_md_flow.py` asserts `gh api -X POST "repos/${GH_REPO}/pulls"` present and the CLI create path absent from the create-or-reuse step
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: existing RF-014 pins (`gh api -X PATCH ...`, assertNotIn CLI edit) unchanged and green in the same test module
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: full suite green; `validate_workflow_policy.py` valid on the modified workflow

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE
