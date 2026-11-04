# Plan — Issue #595 owner-qualified auto-sync PR reuse lookup

- Issue: #595
- Spec: specs/595-sync-pr-reuse/spec.md
- Base: 53d61d41 (origin/main content baseline; local HEAD f7d485f is
  content-identical to it on the workflow path; the test module carries the
  test specialist's uncommitted RED additions on top of that baseline)

## Architecture

One line in the "Push sync branch and create or reuse the auto-sync PR"
step of `.github/workflows/sync-merged-tasks.yml`. The reuse lookup

    number="$(gh api "repos/${GH_REPO}/pulls?head=${GH_REPO}:${BRANCH}&base=main&state=open" --jq '.[0].number // empty')"

passes `owner/repo:branch` as GitHub's `head` filter, while the API filters
on `owner:branch` — the malformed filter matches nothing, so the open
auto-sync PR is never found and the flow dies on the duplicate-create 422.
The fix narrows only the filter's owner component to `${GH_REPO%%/*}`
(POSIX parameter expansion, the step's existing shell dialect), leaving the
`repos/${GH_REPO}` endpoint path, `base=main`, `state=open`, the jq
extraction and every downstream step untouched. The regression tests extract
the real suffix (lookup assignment through the PR_NUMBER export) from the
committed workflow and execute it verbatim by bash against a deterministic
fake gh — the conditional is never reimplemented in Python and no network
or credential is touched.

## Decisions

- **Fix the filter, not the flow**: GitHub's documented head filter is
  `owner:branch`; `owner/repo:branch` can never match. Owner-only
  extraction via `${GH_REPO%%/*}` needs no new variable, helper or config.
- **No retry / no 422 fallback / no race fixes**: explicitly out of scope.
  With the filter correct, a duplicate-create 422 remains a loud failure
  rather than something masked by fallback logic.
- **Lookup failure stays fatal after the push**: the flip commit is already
  on origin when the lookup runs; a 401/network failure must abort the step
  before any POST/PATCH/export. No rollback of the pushed branch is
  attempted — pre-existing property, preserved.
- **Test-protected reproduction**: the test specialist wrote the #595
  reproduction in RED as uncommitted working-tree changes on the 53d61d41
  baseline (419 lines added to tests/test_sync_tasks_md_flow.py vs the git
  base, including the corrected structural pin); the code/GREEN phase turns
  them GREEN with no test edits during the GREEN/code phase and no weakened
  assertion.

## Affected contours

- CONTROL_PLANE — `.github/workflows/sync-merged-tasks.yml` (one lookup
  line + one #595 comment) and this SDD trio; classified CONTROL_PLANE by
  data/contracts/change-control-policy-v1.json (`.github/workflows/`).
- VPS — NOT affected: api/**, frontend/**, deploy/vps/** untouched.
- Ubuntu worker/relay — NOT affected: worker/**, deploy/worker/** untouched.
- tests/test_sync_tasks_md_flow.py — part of the admitted whole-issue scope
  (five paths) but test-protected during the code/GREEN phase: the test
  specialist changed it in the RED phase (+419/-1 lines vs the git base —
  the #595 class, the fake-gh harness, the corrected structural pin); the
  code worker preserves it byte-identical (hash
  ee433890c437fab0a8fa01f810020e0cdc188d5a before/after the code phase).
  No other tests/** path is touched by the issue.
- Excluded automatic behavior preserved verbatim: PAT-push /
  workflow-token-REST split, `set -euo pipefail`, permissions block, push
  retry with backoff, parked-run approval, required-check polling, squash
  merge, concurrency serialization. The owner-known automatic follow-up is
  preserved: with bot PR #566 open, the next real sync run reuses/updates
  and merges it without operator action.

## Validation

- RED (observed before the fix): `python3 -W error::ResourceWarning -m
  unittest tests.test_sync_tasks_md_flow.SyncPrLookupReuseCreateTests -v` —
  "Ran 5 tests ... FAILED (failures=3)" (reuse URL mismatch, create URL
  mismatch, repeat 422); the module-level structural pin failed in the
  orchestrator's observed module run ("Ran 15 ... FAILED (failures=4)").
  The 401/network fail-closed cases already passed pre-fix and must
  stay green (property preservation).
- GREEN (observed after the fix): `python3 -W error::ResourceWarning -m
  unittest tests.test_sync_tasks_md_flow -v` — "Ran 15 tests in 0.452s /
  OK" (15/15, zero skips; no test edits during the GREEN/code phase — the
  RED state was authored by the test specialist).
- Gates: `python3 scripts/ci/validate_sdd.py`,
  `python3 scripts/quality/validate_workflow_policy.py`,
  `ruff check --config scripts/quality/ruff.toml .` — observed outputs in
  the completion gate.
- Pending by design (not prechecked): PR CI, exact-green-head merge, and
  the live reuse of open bot PR #566 by the next real sync run — the
  auto-sync flips the recognized completion markers after merge.

## Runtime feedback

- CI is the first runtime for this change (workflow policy + structural
  pins on the PR head). The real acceptance scenario is automatic and
  PENDING observation: the first post-merge sync run with a tasks.md delta
  performs the owner-qualified lookup against real GitHub and should
  reuse/update/merge the open bot PR #566 — the exact path that died on 422
  before the fix; the orchestrator must observe and record it on issue
  #595. A lookup 401/network failure still fails the run loudly after the
  push; no rollback of the pushed branch is attempted (unchanged, intended).

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the diff touches only the head-filter owner component (endpoint, base/state filters, jq and all downstream steps byte-identical); the five #595 tests execute the real extracted suffix against a fake gh reproducing GitHub's owner:branch semantics and the 422, and the structural pin plus the workflow policy validator hold the safety shape | Validation: focused module observed "Ran 15 tests ... OK" after the fix; RED baseline (3 class failures + structural pin) observed before | Residual risk: a future GitHub head-filter semantics change would resurface as the duplicate-create 422 — loud, not silent | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: the live reuse path is exercised automatically by the next post-merge sync run while bot PR #566 is open; until then the live claim is explicitly pending, not asserted | Validation: PENDING — live reuse/update/merge of PR #566 must be observed and recorded by the orchestrator on issue #595 after merge; NOT observed at code-worker time | Residual risk: until that run, owner-qualified reuse is proven only against the fake-gh semantics (accepted; the fake reproduces GitHub's documented head filter) | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the fix cannot widen authority — it only corrects a query filter; the lookup still runs under the workflow token after the PAT push, and failure paths stay fail-closed | Validation: structural pins (token split, strict shell) green; cases 3-4 green | Residual risk: none identified | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: reuse — open PR found via the owner-qualified filter, REST PATCH refresh, no POST, PR_NUMBER exported, evaluated lookup URL pinned | Level: integration | Priority: P0 | Evidence: tests/test_sync_tasks_md_flow.py::SyncPrLookupReuseCreateTests::test_existing_open_pr_is_reused_via_patch_never_post (real suffix executed by bash against fake gh)
- TEST-002 | Covers: absent-create — empty lookup leads to exactly one REST POST and the number export | Level: integration | Priority: P0 | Evidence: tests/test_sync_tasks_md_flow.py::SyncPrLookupReuseCreateTests::test_no_open_pr_creates_exactly_once_and_exports_number
- TEST-003 | Covers: fail-closed errors — 401 and network-failure lookups abort before POST/PATCH/export | Level: integration | Priority: P0 | Evidence: test_lookup_401_fails_closed_without_create_or_export + test_lookup_network_failure_fails_closed_without_create_or_export observed ok
- TEST-004 | Covers: repeat idempotency — two consecutive runs create exactly once, second run PATCHes the created PR | Level: integration | Priority: P0 | Evidence: tests/test_sync_tasks_md_flow.py::SyncPrLookupReuseCreateTests::test_repeated_invocation_reuses_created_pr_never_second_post observed ok
- TEST-005 | Covers: safety preservation — structural pins (token split, strict shell, push retry, REST-only PR lifecycle, squash merge, pathspec staging) and the generic workflow policy | Level: integration | Priority: P0 | Evidence: WorkflowStructuralPinTests observed ok + validate_workflow_policy.py exit 0

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: none required — the admitted one-line fix turned the RED suite
  GREEN with no test edits during the GREEN/code phase; no production
  learning, architecture pivot, material scope change or scope expansion
  surfaced during implementation (the whole-issue five-path scope was
  already admitted; the code phase stayed inside its narrower admitted
  file set).
