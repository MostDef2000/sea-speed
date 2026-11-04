# Spec: #595 — Auto-sync PR reuse lookup uses the owner-qualified head filter

- Issue: #595
- Spec: specs/595-sync-pr-reuse/spec.md
- Plan: specs/595-sync-pr-reuse/plan.md
- Tasks: specs/595-sync-pr-reuse/tasks.md
- Base: 53d61d41 (origin/main content baseline; local HEAD f7d485f is
  content-identical to it on the workflow path; the test module carries the
  test specialist's uncommitted RED additions on top of that baseline)
- Authorization: the #595 whole-issue scope — five paths — admitted by the
  delivery orchestrator (canonical receipt: issue #595 comment
  6619795584): (1) the one lookup-line fix in
  `.github/workflows/sync-merged-tasks.yml`, (2) the test module
  `tests/test_sync_tasks_md_flow.py`, and (3-5) this SDD trio. The test
  module's #595 material (419 lines added vs the git base: the
  SyncPrLookupReuseCreateTests class, the fake-gh harness and the
  corrected structural pin) was written in RED by the test specialist as
  uncommitted working-tree changes on the baseline — it is NOT pre-existing
  on the git base. The code/GREEN phase keeps the test module
  byte-identical (hash-preserved); it is test-protected in this phase.

## Product outcome

The tasks.md auto-sync flow's create-or-reuse step looks up an open
auto-sync PR with `gh api "repos/${GH_REPO}/pulls?head=...&base=main&state=open"`.
GitHub's `head` filter is `owner:branch`, but the workflow passed
`${GH_REPO}:${BRANCH}` — literally `owner/repo:branch` — which matches
nothing. The open auto-sync PR was therefore never detected, the flow fell
through to PR creation, and GitHub rejected the duplicate create with HTTP
422, killing the sync run after the flip commit had already been pushed.
After this change the lookup filters on `${GH_REPO%%/*}:${BRANCH}`
(owner-qualified head), so the existing open auto-sync PR (currently bot PR
#566) is found and refreshed via REST PATCH, and a genuinely absent PR is
created exactly once. Everything else in the step — PAT-push /
workflow-token-REST split, strict shell options, permissions, bounded push
retry, parked-run approval, check polling, squash merge — is unchanged.

## User scenarios

- SC-1: a merge flips a DoD marker while the auto-sync PR is already open —
  the owner-qualified lookup finds it and the flow PATCHes title/body; no
  second PR is attempted, no 422.
- SC-2: no auto-sync PR is open — the empty lookup falls through to exactly
  one REST POST create and the returned number is exported for the
  check-polling and merge steps.
- SC-3: the lookup fails (401 or network error) — the step aborts nonzero
  before any POST/PATCH and before the PR_NUMBER export; the already-pushed
  branch is not rolled back (unchanged, deliberate property).
- SC-4: the sync flow runs twice against the same open PR (the normal
  merge-loop rhythm) — the PR is created exactly once across the runs; every
  later run reuses and refreshes it.

## Requirements

- R-1: the reuse lookup in the step "Push sync branch and create or reuse
  the auto-sync PR" reads
  `gh api "repos/${GH_REPO}/pulls?head=${GH_REPO%%/*}:${BRANCH}&base=main&state=open" --jq '.[0].number // empty'`
  — only the head-filter owner component changes; the `repos/${GH_REPO}`
  API endpoint, `base=main`, `state=open` and the jq extraction stay
  byte-identical.
- R-2: the lookup stays a bare command substitution under the step's
  `set -euo pipefail`: a 401 or network failure exits nonzero before any
  POST/PATCH and before `PR_NUMBER` is exported. No retry, no 422 fallback,
  no race fixes — explicitly out of scope.
- R-3: all other workflow behavior is preserved verbatim: token split
  (SYNC_PUSH_TOKEN PAT for the git push only, workflow token for every REST
  call), strict shell options, permissions block, push retry with backoff,
  parked-run approval, required-check polling, squash merge.
- R-4: the test-protected #595 regression material in
  tests/test_sync_tasks_md_flow.py (class
  `SyncPrLookupReuseCreateTests`, which extracts and executes the REAL
  shell suffix against a deterministic fake gh reproducing GitHub's
  owner:branch head-filter semantics and the duplicate-create 422, with
  zero network — authored in RED by the test specialist on the baseline,
  not on the git base) passes unmodified during the code/GREEN phase,
  together with the structural pin the test specialist corrected to the
  owner-qualified lookup string and the whole module.

## Acceptance criteria

- AC-001: with open auto-sync PR #566 in the fake state, the extracted real
  suffix issues lookup + REST PATCH only (no POST) and exports
  `PR_NUMBER=566`; the evaluated lookup URL carries the owner-qualified
  head filter (test_existing_open_pr_is_reused_via_patch_never_post).
- AC-002: with an empty lookup result, the suffix issues lookup + exactly
  one REST POST (head branch, base main, title, body file) and exports the
  returned number (test_no_open_pr_creates_exactly_once_and_exports_number).
- AC-003: a 401 lookup and a network-failure lookup each abort the suffix
  nonzero with only the lookup call logged — no POST/PATCH, no PR_NUMBER
  export (test_lookup_401_fails_closed_without_create_or_export,
  test_lookup_network_failure_fails_closed_without_create_or_export).
- AC-004: across two consecutive suffix runs the PR is created exactly once
  (one POST total); the second run discovers the created PR through the
  owner-qualified filter and PATCHes it (test_repeated_invocation_reuses_
  created_pr_never_second_post).
- AC-005: safety preservation — the committed workflow keeps its pinned
  safety shape (token split, strict shell options, push retry, tasks.md-only
  pathspec, REST-only PR lifecycle, squash merge, no direct main push) and
  `scripts/quality/validate_workflow_policy.py` accepts it
  (WorkflowStructuralPinTests + policy validator).
- AC-006: required CI is green on the exact PR head, the merge is
  exact-green-head, and the next real sync run on main demonstrates the live
  reuse path — with bot PR #566 open, the owner-qualified lookup finds and
  updates it instead of dying on the duplicate-create 422 (automatic,
  orchestrator-owned; live evidence PENDING — to be observed and recorded
  on issue #595 after merge, not asserted at code-worker time).

## Runtime feedback

- CONTROL_PLANE only: api/**, worker/**, deploy/**, frontend/** untouched;
  VPS and Ubuntu runtime contours unaffected; no deployment transaction
  audit (the SDD validator derives that requirement only for deploy/**
  paths, deployment workflows, or a PRODUCTION_LEARNING trigger — none
  apply). The workflow itself is the runtime surface: after merge, the next
  merge carrying a tasks.md delta exercises the fixed lookup live against
  real GitHub, reusing/updating/merging the open bot PR #566 without
  operator action. Failure modes are unchanged and fail-closed: a lookup
  401/network failure still fails the run after the push (no rollback of the
  pushed branch is attempted or promised). Rollback of the change itself is
  `git revert` of the one-line diff.

## NFR assessment

- NFR-001 | Area: reuse correctness | Target: the lookup URL evaluates to GitHub's owner:branch head-filter semantics, so an open auto-sync PR is found and reused instead of triggering a duplicate-create 422 | Validation: the five #595 tests execute the real extracted shell suffix against a deterministic fake gh (owner:branch semantics + 422), zero network | Evidence: RED before fix observed "Ran 5 tests ... FAILED (failures=3)" (class) with the module-level structural pin also red (orchestrator-observed "Ran 15 ... FAILED (failures=4)"); after the fix OBSERVED "Ran 15 tests in 0.452s / OK" | Status: PASS
- NFR-002 | Area: safety preservation | Target: zero behavioral change outside the head-filter owner component; token split, strict shell, push retry, permissions, polling and merge byte-identical | Validation: WorkflowStructuralPinTests green + validate_workflow_policy.py exit 0 + exact-diff inspection | Evidence: observed gate outputs recorded in the completion gate | Status: PASS
- NFR-003 | Area: fail-closed errors | Target: lookup 401/network failure keeps the step nonzero before any POST/PATCH/export (push already happened; no rollback promised) | Validation: #595 cases 3-4 assert lookup-only call history and no export | Evidence: both cases observed ok in the focused run | Status: PASS
- NFR-004 | Area: minimality | Target: one-line query fix plus one explanatory comment; no new helpers, config, runbook, dependencies, retry or fallback logic | Validation: exact git diff of the workflow shows only the owner component and the #595 comment | Evidence: diff recorded in the completion gate | Status: PASS
