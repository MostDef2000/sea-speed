# Plan: Bounded prune of foreign unmarked loopback-API auth rules

- Issue: #436
- Specification: specs/436-sanitize-auth/spec.md

## Implementation approach

1. RECON-established facts: `_parse_rule_block` is marker-anchored and merges
   ips/actions from the marker to the next reader marker or block end (the
   #436 blind spot); `ensure_internal_api_rule` is byte-exact idempotent over
   its own 5-line block; `camera-relay.sh` prepare/activate already gate on
   digest, mode, worker-stopped and auth-environment overrides; the existing
   BASE_CONFIG test fixtures already contain the exact unmarked duplicate
   shape; the #372 forwarding pin counts `"${reader_ip_args[@]}"`.
2. Renderer: add an entry-segmenting scanner (`_scan_auth_entries`: entry =
   `  - ` line to next `  - `/`  #`/block end; marked = preceding non-blank
   line is a `# Sea Speed ` marker comment), an indent-aware field parser
   (`_parse_auth_entry_fields`: unmodeled content → fail closed), the
   descriptive scan (`scan_foreign_auth_rules`), the explicit counter
   (`count_foreign_auth_rules`), and the bounded pruner
   (`sanitize_foreign_auth_rules`: delete ONLY foreign entries with
   ips == {127.0.0.1} ∧ actions == {"api"} ∧ well-formed; anything else →
   ConfigError BEFORE any deletion; post-conditions: marked spans
   byte-identical, foreign count == 0). New CLI mode `ubuntu-sanitize-auth`
   (`--config/--output`): verify-before API rule → prune → explicit
   foreign==0 → verify-after API rule → 0600 candidate + SANITIZED evidence.
   All existing modes untouched (purely additive diff).
3. Shell: `sanitize` subcommand = same arg gating as prepare; transaction =
   verify-reader-auth on LIVE → renderer sanitize render → digest +
   root-only sha file → verify-reader-auth on CANDIDATE → evidence block
   (`SANITIZED_FOREIGN_AUTH=YES`, `CANDIDATE_SHA256`,
   `MUTATIONS=PROTECTED_CANDIDATE_ONLY`, `SERVICE_RESTARTED=NO`,
   `SECRETS_DISPLAYED=NO`). The `activate` flow is byte-unchanged: the
   operator installs the pruned candidate with `--expected-sha256`.
4. Tests: new RED-first battery `tests/test_mediamtx_sanitize_auth.py` (scan
   counts, prune + byte-identity of marked rules, fail-closed table, CLI
   transaction, shell pins); one documented pin update in
   `tests/test_mediamtx_multi_reader_ip.py` (forwarding count 2→4 for the two
   new sanitize verify-reader-auth calls).
5. Docs: sanitize runbook appended to the "Ubuntu Worker relay API profile"
   section of docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md.

## Architecture

- The pruner is a pure text transform over the same `_split_lines`/
  `_auth_internal_users_bounds` machinery the renderer already uses; it does
  not reuse `_parse_rule_block` (span-merge is the bug class being closed)
  and does not widen any verify: the existing
  `verify_internal_api_rule`/`verify_internal_reader_rule` remain the
  canonical post-install checks on the activated config.
- Foreign/marked classification is line-structural: an entry is marked only
  when the immediately preceding non-blank line is a two-space-indented
  `# Sea Speed ` marker comment (the renderer's marker namespace). Forged
  markers are out of threat scope (local operator edits); a forged-marker
  rule would still fail every byte-exact `ensure_*` re-render check.
- Deletion eligibility is exact-scope equality plus full modelability — a
  whitelist, not a blacklist: unknown fields, deeper nesting (e.g.
  permission-level ips), non-`user:` entry headers, and blank-line-adjacent
  oddities make an entry undeletable (fail closed) even when its parsed
  scope looks canonical.
- The shell transaction keeps the established mutation boundary: every
  renderer invocation only writes the root-only candidate; live state changes
  exclusively inside the existing activate flow.

## Decisions

- D-1: Exact-scope equality (ips == {127.0.0.1} ∧ actions == {"api"}) rather
  than subset semantics: an ip-less `action: api` entry is WIDER than the
  canonical scope (any source) and must fail closed, so subset parsing of an
  empty ips set would be unsafe. The AC's "subset" phrasing is implemented as
  exact equality with the canonical singleton scope — the conservative
  reading that also satisfies it.
- D-2: Fail closed on ANY other foreign rule, transaction-wide, BEFORE any
  deletion (no partial prunes): partial deletion would leave the operator
  unable to reason about the live auth state from the renderer output alone.
- D-3: The renderer sanitize mode takes NO reader/path input (sanitize is
  reader-agnostic); the reader domain stays with the existing
  `verify-reader-auth` mode, which the shell calls before and after the
  render. Consequence: the #372 forwarding pin count updates 2→4 (two new
  verify-reader-auth calls), documented in the test.
- D-4: Reuse the digest-bound `activate` runbook unchanged (AC-3): no new
  install path, no new backup logic, no automatic rollback. A failed sanitize
  leaves the previous candidate in place; the runbook notes it must not be
  activated.
- D-5: New test file `tests/test_mediamtx_sanitize_auth.py` as the cleaner
  home (named by the work order's verification command) instead of extending
  the two existing renderer batteries.
- D-6: Docs live in the existing "Ubuntu Worker relay API profile" section —
  the sanitize transaction is part of that profile's operations, not a new
  document.

## Affected contours

- Ubuntu Worker/relay: `deploy/worker/ubuntu/camera-relay.sh` (UBUNTU_WORKER
  per the change-control policy), `scripts/operations/mediamtx_path_config.py`
  (CONTROL_PLANE; renders worker relay config), the focused test files, the
  docs runbook, this SDD trio (+ durable progress file outside the repo
  tree).
- No change to `api/**`, `frontend/**`, `worker/**`, `.github/**`,
  `deploy/vps/**`, `deploy/nginx**`, preview-relay behavior, systemd
  units/timers, `specs/407-**`, `scripts/release/**`.

## Validation

- RED: the new battery fails on base 095e4c9 (16/16 tests) and passes on the
  branch (exact names in the delivery transcript and tasks.md AC-4).
- Full suite on head branch: green (exact counts in the verification
  transcript).
- Focused batteries verbose:
  tests/test_camera1_live_replacement.py +
  tests/test_mediamtx_multi_reader_ip.py + tests/test_mediamtx_sanitize_auth.py.
- Byte-identity: seven-mode fixed-input harness (all existing CLI modes) run
  on base 095e4c9 and on the branch; the output directories must diff empty.
- `bash -n deploy/worker/ubuntu/camera-relay.sh`: clean.
- ruff (`scripts/quality/ruff.toml`) on changed Python files: clean.
- `python3 scripts/ci/validate_sdd.py --event <pr-event.json>`: green.

## Runtime feedback

- RF-001: Operator actions expected: 1 bounded on-box sanitize transaction
  (sanitize → digest → activate --expected-sha256), root-gated; orchestrator
  records the runtime acceptance.
- RF-002: Evidence: `SANITIZED mode=ubuntu-sanitize-auth
  foreign_rules_removed=N foreign_rules_remaining=0
  api_rule=loopback-watchdog-intact output_sha256=…`; shell
  `SANITIZED_FOREIGN_AUTH=YES` + `CANDIDATE_SHA256=…`; fail-closed line
  `ERROR: foreign unmarked authInternalUsers rule is outside the canonical
  loopback-api scope …` (stderr, exit 1, candidate untouched).

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from
  `scripts/ci/validate_change_contract.py` `classify_file`/`derive_impact`
  over the changed-file set — `deploy/worker/ubuntu/camera-relay.sh`
  classifies UBUNTU_WORKER, `scripts/operations/mediamtx_path_config.py`
  classifies CONTROL_PLANE; `derive_impact` returns UBUNTU_WORKER (runtime
  contours {UBUNTU_WORKER}) with a config mutation, matching the Outcome
  Contract posted on issue #436.
- RISK-001 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: deletion eligibility is an exact-scope whitelist (ips == {127.0.0.1} ∧ actions == {"api"} ∧ fully modeled) with transaction-wide fail-closed BEFORE any deletion; marked rules carry a byte-identity post-condition; the reader/API verifies run before and after; no partial prune can silently narrow or widen auth | Validation: executed fail-closed table (wider ips/actions, non-api action, ip-less grant, unmodeled fields, authMethod, missing block) and marked-span byte-identity + idempotent no-op tests | Residual risk: LOW — a future MediaMTX entry shape that parses as canonical-scope but carries unmodeled semantics would be rejected (fail closed), not deleted | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the on-box transaction is the same digest-bound activate runbook the operator already runs (root-only timestamped backup, atomic install, private-listener probe, "automatic rollback is not authorized" preserved); verify-before refuses a live config whose marked API rule is missing so sanitize cannot be the first thing to break an already-broken box unnoticed | Validation: shell contract pins (verify-reader-auth on LIVE and CANDIDATE, digest emission, no worker control strings, bash -n) plus CLI verify-before rejection test | Residual risk: LOW — a stale previously prepared candidate remains on disk after a failed sanitize; the runbook forbids activating it and the digest binding prevents accidental digest mismatch activation | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the new scanner is purely additive (zero deleted renderer lines); every existing mode is pinned byte-identical by the seven-mode fixed-input harness diffed base vs head; the one existing pin change (forwarding count 2→4) is documented with its reason | Validation: byte-identity harness diff empty; focused batteries + full suite green; test_shell_contracts_forward_all_reader_ip_occurrences updated in place | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_sanitize_fails_closed_on_wider_foreign_ips + test_sanitize_fails_closed_on_wider_foreign_actions + test_sanitize_fails_closed_on_non_api_foreign_rule + test_sanitize_fails_closed_on_ip_less_api_rule + test_sanitize_fails_closed_on_unmodeled_fields (each asserts ConfigError AND untouched text)
- TEST-002 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_sanitize_removes_only_the_canonical_scope_duplicate (marked rules byte-identical, both reader rules verify) + test_sanitize_removes_multiple_exact_duplicates + test_sanitize_is_idempotent_noop_without_foreign_rules
- TEST-003 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_cli_sanitize_removes_duplicate_and_reverifies_clean (0600 candidate, SANITIZED evidence line, foreign_rules_removed=1 remaining=0) + test_cli_sanitize_verify_before_rejects_missing_marked_api_rule + test_cli_sanitize_fail_closed_leaves_candidate_untouched
- TEST-004 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_shell_contracts_sanitize_subcommand (bash -n, subcommand dispatch, verify-reader-auth on LIVE+CANDIDATE, digest emission, MUTATIONS=PROTECTED_CANDIDATE_ONLY, no systemctl worker strings, automatic-rollback contract)
- TEST-005 | Covers: RISK-003 | Level: integration | Priority: P0 | Evidence: seven-mode byte-identity harness (base 095e4c9 vs branch, empty diff) + test_scan_counts_only_unmarked_entries + test_shell_contracts_forward_all_reader_ip_occurrences (documented 2→4) + full pytest suite green

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: canonical issue #436 Outcome Contract; allowed paths (renderer, camera-relay.sh, tests, docs runbook, SDD trio, progress file) enforced before first write; GH007 author identity set before any commit
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: sanitize verify-before (verify-reader-auth on LIVE + renderer verify_internal_api_rule on LIVE) and activate's existing digest/mode/worker-stopped/auth-environment gates; nothing is mutated until the operator explicitly activates the reviewed digest
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: prior MediaMTX config preserved at the printed BACKUP path; candidate remains root-only 0600 | Retry: NO | Rollback: the existing activate flow preserves a root-only timestamped backup for an explicit rollback decision; automatic rollback is intentionally not authorized; the pruned candidate itself is a pure renderer output (re-renderable) | Evidence: camera-relay.sh activate backup/install/restart sequence unchanged; sanitize block only writes the root-only candidate + sha file
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: verify-after pair (verify-reader-auth on CANDIDATE + renderer verify_internal_api_rule on pruned) plus explicit count_foreign_auth_rules(pruned) == 0 post-condition from the dedicated scanner; activate re-verifies reader auth before install and probes the private listener after restart
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: no new durable state beyond the existing candidate/sha-file/backup set; the renderer keeps no state; the scanner is a pure function
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond existing candidate/backup temporaries | Retry: NO | Rollback: NONE | Evidence: write_candidate temp-file cleanup and state-root handling unchanged; failed sanitize leaves the previous candidate untouched (runbook: must not be activated)
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: SANITIZED/SANITIZED_FOREIGN_AUTH/CANDIDATE_SHA256/MUTATIONS=PROTECTED_CANDIDATE_ONLY/SERVICE_RESTARTED=NO/SECRETS_DISPLAYED=NO lines; fail-closed ERROR line on stderr with exit 1
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: config rollback rides the unchanged camera-relay.sh root-only timestamped backup (explicit operator decision); the sanitize path itself is restart-free before activation so it cannot compound a failure | Evidence: unchanged activate fault paths (exit 30/31/32 with BACKUP printed; "automatic rollback is not authorized")
