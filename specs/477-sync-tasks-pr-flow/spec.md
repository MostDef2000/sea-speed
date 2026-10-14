# Spec: #477 sync-merged-tasks PR flow

- Issue: #477
- Specification: specs/477-sync-tasks-pr-flow/spec.md

## Product outcome

`.github/workflows/sync-merged-tasks.yml` flips `specs/*/tasks.md` completion markers after each squash merge to main, but the current revision commits and pushes DIRECTLY to main with `github.token`. Repository rulesets require PR checks, so a direct push can never satisfy them — the sync job always fails at push and markers stay unchecked. This task converts the sync to a self-contained PR-based flow: the workflow syncs markers on the exact merged head (guarded against stale triggers), pushes the delta to the deterministic branch `chore/tasks-md-auto-sync`, creates (or reuses) an auto-sync PR whose body passes the full Change Contract validator, waits for the PR's own required checks, and squash-merges it. Loop safety is structural: `sync_tasks_md.py`'s COMPLETION_RE matches only unchecked `- [ ]` markers, so the sync PR's own merge re-triggers the workflow, which then finds no delta and exits green (proven by a round-trip test).

## User scenarios

- US-1: a squash merge lands on main → the Quality integration gate push run completes → this workflow syncs the merged specs' markers, opens the auto-sync PR with a Change-Contract-compliant body, waits for its required checks, squash-merges → main's tasks.md is current with NO direct-to-main push.
- US-2: the sync finds nothing to flip (markers already current, or only unrecognized/orchestrator-owned markers remain) → the run exits green with no PR and no commit.
- US-3: a stale trigger (main advanced past `workflow_run.head_sha`, e.g. two merges race) → the run logs the staleness and exits green; the newer merge's own quality run re-triggers the sync.
- US-4: the auto-sync PR's required checks fail or exceed the watch window → the sync job fails LOUDLY naming the PR (head `chore/tasks-md-auto-sync`) so a human/orchestrator can finish the sync manually; the merge step is never retried blind.
- US-5: the generated PR body drifts from the change-control policy → the NEW `tests/test_sync_tasks_md_flow.py` contract test fails in CI (it validates the template against the REAL `validate_contract`), turning template drift into a red fix-PR instead of a red auto-sync PR after merge.
- US-6: a second sync run races the first → the concurrency group (`sync-merged-tasks`, `cancel-in-progress: false`) serializes runs; a reuse path force-pushes the existing open PR instead of creating duplicates.

## Scope

- `scripts/ci/sync_tasks_md.py`: NO logic change (its idempotency is the loop-safety core; the sha-suffix guard quirk — markers whose static text already contains "auto-synced on merge" get no sha annotation — is cosmetic and recorded, not fixed).
- `.github/workflows/sync-merged-tasks.yml`: rewritten in place. KEPT: workflow name (unreferenced by other workflows), `workflow_run` trigger on "Quality integration gate" completed, the event filter (`workflow_run.event == 'push' && head_branch == 'main' && conclusion == 'success'`), the pinned `actions/checkout@11d5960a326750d5838078e36cf38b85af677262` (ref main, fetch-depth 2), and the sync+freshness command pair. CHANGED: `permissions` gains `pull-requests: write`; `concurrency: { group: sync-merged-tasks, cancel-in-progress: false }` added; the direct `git push` replaced by: stale-trigger guard (compare fetched main tip vs `workflow_run.head_sha`, exit green on mismatch) → sync+freshness → delta detection (both `git status --porcelain` and the merge's `specs/*/tasks.md` diff non-empty) → deterministic PR body via the NEW generator into `$RUNNER_TEMP` → `git fetch`+`checkout -B chore/tasks-md-auto-sync` → bot-identity commit (only `':(glob)specs/*/tasks.md'`) → `git push --force-with-lease` → PR reuse-or-create (`gh pr list --head … --state open`, else `gh pr create --body-file`) → bounded required-checks wait (≤5 reads 30 s apart for exit codes 4/8, then `timeout 1800 gh pr checks N --watch --fail-fast`) → `gh pr merge N --squash --delete-branch --subject "chore(sdd): auto-sync tasks.md completion (<source-sha8>)"` → loud `::error::` failure notice naming the PR head.
- NEW `scripts/ci/build_sync_pr_body.py`: deterministic Change-Contract-compliant PR body generator (`--source-sha`, repeated `--changed-file`, `--out`); emits all six required sections and the full required-field surface for the auto-sync delta (specs/*/tasks.md only → impact NONE, all deployment fields NOT REQUIRED, capabilities NOT APPLICABLE, operator actions 0, `Risk profile: NOT REQUIRED`, verdict PASS, waivers NONE). Extracted as a script so the body template is unit-testable.
- NEW `tests/test_sync_tasks_md_flow.py` (7 tests): marker round-trip (second/third sync runs are no-ops on the real wave-4 tasks.md fixture); marker discipline (only recognized markers flip, nothing ever unchecks, suffix never stacks); synced file is freshness-clean; generated body passes the REAL `validate_contract` with derived impact NONE; body carries sha/files/six sections/branch name and no placeholder text; generator refuses an empty delta; CLI subprocess round-trip.
- SDD trio `specs/477-sync-tasks-pr-flow/`.
- OUT of scope: repository rulesets and branch protection; `sync_tasks_md.py` logic; deploy-*.yml and the quality/pr-validation workflows; validate_sdd; any runtime contour (VPS, Ubuntu worker/relay); the merged specs' marker CONTENT (the flow only flips what COMPLETION_RE recognizes — orchestrator-owned markers stay).

## Requirements

- R-1 (AC-001): the sync never pushes directly to main; every marker update travels through the deterministic `chore/tasks-md-auto-sync` PR, which the workflow itself waits for and squash-merges only after its required checks are green.
- R-2 (AC-002): the auto-sync PR body passes the REAL Change Contract validator for the exact delta the sync commit carries, deterministically (same inputs → byte-identical body), including `- Source authorization: OUTCOME APPROVED` standing for the #477-established housekeeping authorization.
- R-3 (AC-003): the flow is idempotent and loop-safe — flipping is one-shot (COMPLETION_RE matches only unchecked markers), the suffix is appended at most once, the follow-up sync run after the auto-sync merge reports no delta and exits green.
- R-4 (AC-004): the run is safe under races — a stale trigger exits green without syncing, the concurrency group serializes overlapping runs, and an existing open auto-sync PR is force-pushed (reuse) rather than duplicated.
- R-5 (AC-005): failures are loud and bounded — checks failures and the 1800 s watch timeout exit non-zero with `::error::` naming the PR URL; the merge is never retried after a failed read window.
- R-6 (AC-006): the full unittest battery passes with no pin edits (expected 944 + 7 new = 951, skipped=4); ruff, validate_repo and validate_sdd stay green.

## Acceptance criteria

- AC-001: workflow inspection + yaml parse confirm no `git push` to main and the presence of the branch-push → PR → checks → squash-merge chain; the direct-to-main defect is gone.
- AC-002: `tests/test_sync_tasks_md_flow.py` SyncPrBodyContractTests pass — the generated body satisfies `validate_contract(body, changed_files)` with derived impact NONE, and carries source sha, changed-file list, six sections, the sync branch name and no placeholder text.
- AC-003: SyncMarkerRoundTripTests pass — round-trip no-op on re-run, only recognized markers flip, no unchecks, suffix at most once per marker, `check_tasks_freshness` clean after sync; CLI round-trip ("1 tasks.md file(s) synced" then "all changed tasks.md already current").
- AC-004: stale-trigger guard present (tip vs `head_sha` comparison, `HAS_DELTA=false` exit-0 path); concurrency group pins `sync-merged-tasks` with `cancel-in-progress: false`; reuse path force-pushes the open PR.
- AC-005: the checks-wait step implements the bounded retry (5 attempts, 30 s apart, exit codes 4/8 tolerated) and the hard watch timeout (1800 s, `--fail-fast`), and every failure path exits non-zero with an `::error::` naming the PR.
- AC-006: full battery observed `Ran 951 tests ... OK (skipped=4)`; `ruff check . --config scripts/quality/ruff.toml` clean; `validate_repo.py` and `validate_sdd.py` green at final head.

## Runtime feedback

- RF-001: Operator actions expected: 0. Control-plane-only change (one GitHub Actions workflow + a CI body-generator + tests); no VPS or Ubuntu-worker/relay contour is touched and no deploy workflow changes.
- RF-002: Evidence: the workflow cannot execute locally; its live acceptance is the fix PR's own PR-side CI (full Change Contract + significant-PR SDD link + battery), and its first real execution — the sync run triggered by THIS fix PR's merge, which must flip the remaining DoD markers via the first auto-sync PR (dogfooding). The orchestrator records that run's outcome on issue #477.

## NFR assessment

- NFR-001 | Area: reliability/operations | Target: deterministic, self-healing sync — same merge → same PR content; already-current runs are no-ops; stale triggers self-skip | Validation: round-trip + CLI tests OK; guard step present | Evidence: tests/test_sync_tasks_md_flow.py OK | Status: PASS
- NFR-002 | Area: security | Target: no direct-to-main write path; github.token limited to contents:write + pull-requests:write; the only merges are of the repo's own marker-flip commits; no secrets in the body | Validation: yaml parse of permissions + workflow diff review | Evidence: diff inspection; validator policies green | Status: PASS
- NFR-003 | Area: compatibility | Target: trigger surface unchanged (Quality integration gate → workflow_run); PR Validation and Quality gate run on every auto-sync PR unchanged; no other workflow touched | Validation: git diff scope review; validate_sdd event-mode rules re-checked | Evidence: D-2 in plan.md | Status: PASS
- NFR-004 | Area: maintainability | Target: the PR-side contract surface is a tested unit, not inline YAML heredoc | Validation: NEW build_sync_pr_body.py + 7-test suite | Evidence: battery green | Status: PASS
