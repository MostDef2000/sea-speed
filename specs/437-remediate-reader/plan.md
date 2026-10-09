# Plan: Canonical drift-remediation path for drifted LIVE reader rules

- Issue: #437
- Specification: specs/437-remediate-reader/spec.md

## Implementation approach

1. RECON-established facts: `_parse_rule_block` (L319–360) is marker-anchored
   and returns ips as a SET (loses live order, collapses duplicates) while
   merging across its span to the next reader marker (the #436 blind spot);
   `validate_reader_ip` (L223–229) requires literal RFC1918 IPv4;
   `validate_peer_reader_ip` (L232–241) accepts public IPv4 peers but rejects
   loopback/link-local/multicast/reserved — RFC1918 ⊆ peer-valid; the relay
   profile (`render_ubuntu_relay` L810–812) validates `--reader-ip` inputs
   with `validate_reader_ip`, so a canonical cam1 relay block can never
   contain public/loopback ips; `camera-relay.sh` gates prepare/sanitize on
   require_root + auth-environment overrides and installs only via the
   digest-bound activate (worker-stopped gate L309–312); the #372/#436 shell
   pins count `"${reader_ip_args[@]}"` and `verify-reader-auth` occurrences.
2. Renderer: add `_reader_rule_ips_in_order` (ordered ips companion to
   `_parse_rule_block` — duplicate detection + live-order preservation),
   `READER_RULE_ALLOWED_ACTIONS = {read, publish}`, and
   `remediate_internal_reader_rule`: locate exactly one marker for the path
   within `authInternalUsers`; bound the span at the next reader marker or
   block end; `_scan_auth_entries` must yield EXACTLY one entry whose start
   is the first non-blank line after the marker (else fail closed — no
   merged-scope canonization, no silent junk dropping); extract
   ips/actions via `_parse_rule_block` (tight span) + ordered ips; classify:
   duplicates → ConfigError, parse divergence → ConfigError, actions ⊆
   {read, publish} else ConfigError, publish → ConfigError (read-only relay
   profile; publisher roles unrecoverable from a flat live ips list), every
   ip must pass `validate_peer_reader_ip` AND `validate_reader_ip`
   (RFC1918-only); re-emit via `_reader_rule_lines(path, live_ips, None)` and
   replace the drifted block in place; post-conditions: byte-exact
   `ensure_internal_reader_rule` idempotency + `verify_internal_reader_rule` +
   `verify_internal_api_rule`; return (text, ips, needed). New CLI mode
   `ubuntu-remediate-reader` (`--config/--path/--output`): verify-before API
   rule → remediate → 0600 candidate + REMEDIATED evidence. All existing
   modes untouched (purely additive diff).
3. Shell: `remediate` subcommand = same arg gating as prepare/sanitize;
   transaction = verify-reader-auth on LIVE → renderer remediate render →
   digest + root-only sha file → verify-reader-auth on CANDIDATE → evidence
   block (`REMEDIATED_READER=YES`, `REMEDIATION_NEEDED=YES|NO` derived from
   the renderer output, `CANDIDATE_SHA256`, `MUTATIONS=PROTECTED_CANDIDATE_ONLY`,
   `SERVICE_RESTARTED=NO`, `SECRETS_DISPLAYED=NO`). The `activate` flow is
   byte-unchanged: the operator installs the converged candidate with
   `--expected-sha256`.
4. Tests: new RED-first battery `tests/test_mediamtx_remediate_reader.py`
   (convergence, live-order two-IP byte-identity pin, idempotent no-op,
   fail-closed table, CLI transaction, shell pins); documented pin updates in
   `tests/test_mediamtx_multi_reader_ip.py` (forwarding count 4→6) and
   `tests/test_mediamtx_sanitize_auth.py` (verify-reader-auth 3→5,
   digest/MUTATIONS 2→3) for the two new remediate verify-reader-auth calls
   and the third digest-emitting block.
5. Docs: remediate runbook appended after the #436 sanitize runbook in
   docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md.

## Architecture

- The remediator is a pure text transform over the same `_split_lines`/
  `_auth_internal_users_bounds` machinery the renderer already uses; it
  REUSES `_parse_rule_block` for scope extraction (per AC-1) but with a
  tightly-bounded `end` (the remediated entry's own end from
  `_scan_auth_entries`), so the #436 span-merge blind spot cannot smuggle a
  foreign rule's scope into the canonized block.
- Scope preservation is verbatim: the live ips ORDER is preserved (ordered
  parser companion), the live scope SET must equal the `_parse_rule_block`
  set (parse divergence fails closed), and the re-emitted block is exactly
  what `_reader_rule_lines` — the renderer `ubuntu-relay` itself uses —
  produces for those scopes, proven by the byte-exact
  `ensure_internal_reader_rule` post-condition.
- Fail-closed ordering: every authorization check runs BEFORE the block
  replacement; on any violation the input text is never returned modified
  and no candidate is written (the CLI handler writes only after the core
  returns successfully).
- The shell transaction keeps the established mutation boundary: every
  renderer invocation only writes the root-only candidate; live state changes
  exclusively inside the existing activate flow.

## Decisions

- D-1: Remediation targets the marked reader rule of the READ-ONLY relay
  profile: `publish` in the live actions fails closed even though the AC's
  subset phrasing ({read, publish}) would admit it. Rationale: publisher
  roles cannot be recovered from a flat live ips list, and the canonical
  relay profile renders reader-only blocks (`render_ubuntu_relay` →
  `ensure_internal_reader_rule(..., publisher_ips=None)`); mirroring the
  profile logic means publish-bearing blocks are out of remediation scope —
  the conservative reading that also satisfies the AC.
- D-2: IP classification = `validate_peer_reader_ip` THEN
  `validate_reader_ip`, both must pass ⇒ RFC1918-only. This is the
  conservative reading of the AC's "public/loopback/non-IPv4 fail closed"
  clause: a public ip passes only the peer validator, and the canonical cam1
  relay block can never contain one (the relay profile validates
  `--reader-ip` inputs with `validate_reader_ip`). The OR-formulation from
  the design note is subsumed: every ip passing `validate_reader_ip`
  automatically passes `validate_peer_reader_ip`.
- D-3: Duplicate ips are detected on the ORDERED ips sequence
  (`len(set) != len(list)` → ConfigError) because `_parse_rule_block`'s set
  result collapses duplicates; the ordered set is cross-checked against the
  `_parse_rule_block` set and any divergence fails closed (unmodeled parse).
- D-4: Span discipline: exactly one marked entry per span, entry start equal
  to the first non-blank line after the marker; anything else (foreign entry
  merged into the span, junk between marker and entry, missing/multiple
  markers) fails closed BEFORE any replacement — remediation never silently
  deletes or canonizes content it does not model.
- D-5: The renderer remediate mode takes NO `--reader-ip` (the scopes come
  from the live rule); the reader-domain guards stay with the existing
  `verify-reader-auth` mode, which the shell calls before and after the
  render. Consequence: the #372 forwarding pin count updates 4→6 and the
  #436 shell pins 3→5 / 2→3 (documented in the tests).
- D-6: Reuse the digest-bound `activate` runbook unchanged (AC-3): no new
  install path, no new backup logic, no automatic rollback. A failed
  remediate leaves the previous candidate in place; the runbook notes it
  must not be activated.
- D-7: New test file `tests/test_mediamtx_remediate_reader.py` as the cleaner
  home (mirrors the #436 battery structure named by the work order) instead
  of extending the existing renderer batteries beyond the documented pins.
- D-8: Docs live in the existing runbook (docs/operations/
  MEDIAMTX_COMPATIBILITY_REMEDIATION.md) right after the #436 sanitize
  section — the remediate transaction is part of the same profile's
  operations, not a new document.

## Affected contours

- Ubuntu Worker/relay: `deploy/worker/ubuntu/camera-relay.sh` (UBUNTU_WORKER
  per the change-control policy), `scripts/operations/mediamtx_path_config.py`
  (CONTROL_PLANE; renders worker relay config), the focused test files, the
  docs runbook, this SDD trio (+ durable progress file outside the repo
  tree).
- No change to `api/**`, `frontend/**`, `worker/**`, `.github/**`,
  `deploy/vps/**`, `deploy/nginx**`, preview-relay behavior, systemd
  units/timers, `specs/407-**`, `specs/436-**`, `scripts/release/**`.

## Validation

- RED: the new battery fails on base 4db356f (18/18 tests) and passes on the
  branch (exact names in the delivery transcript and tasks.md AC-4).
- Full suite on head branch: green (exact counts in the verification
  transcript).
- Focused batteries verbose:
  tests/test_camera1_live_replacement.py +
  tests/test_mediamtx_multi_reader_ip.py + tests/test_mediamtx_sanitize_auth.py
  + tests/test_mediamtx_remediate_reader.py.
- Byte-identity: seven-mode fixed-input harness (all existing CLI modes) run
  on base 4db356f and on the branch; the output directories must diff empty.
- `bash -n deploy/worker/ubuntu/camera-relay.sh`: clean.
- ruff (`scripts/quality/ruff.toml`) on changed Python files: clean.
- `python3 scripts/ci/validate_sdd.py --event <pr-event.json>`: green.

## Runtime feedback

- RF-001: Operator actions expected: 1 bounded on-box remediate transaction
  (remediate → digest → activate --expected-sha256), root-gated; the
  orchestrator records the runtime acceptance.
- RF-002: Evidence: `REMEDIATED mode=ubuntu-remediate-reader path=cam1
  remediation_needed=YES|NO reader_scope=… reader_permission=read-only
  output_sha256=…`; shell `REMEDIATED_READER=YES` + `REMEDIATION_NEEDED=…` +
  `CANDIDATE_SHA256=…`; fail-closed line `ERROR: …` (stderr, exit 1,
  candidate untouched).

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from
  `scripts/ci/validate_change_contract.py` `classify_file`/`derive_impact`
  over the changed-file set — `deploy/worker/ubuntu/camera-relay.sh`
  classifies UBUNTU_WORKER, `scripts/operations/mediamtx_path_config.py`
  classifies CONTROL_PLANE; `derive_impact` returns UBUNTU_WORKER (runtime
  contours {UBUNTU_WORKER}) with a config mutation, matching the Outcome
  Contract posted on issue #437.
- RISK-001 | Category: SEC | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: every scope element of the drifted block is re-authorized BEFORE re-emission (both validators per ip ⇒ RFC1918-only; duplicates and parse divergence fail closed; actions ⊆ {read, publish} with publish failing closed on the read-only relay profile); the span discipline refuses merged/foreign content; the replacement is in-place over exactly the marked entry's span; the reader/API verifies plus the byte-exact ensure idempotency run on the result — an unauthorized scope can never be canonized | Validation: executed fail-closed table (publish action, api action, public ip, loopback ip, non-IPv4 entry, duplicate ips, missing marker, multiple markers, foreign entry inside span, authMethod != internal) each asserting ConfigError AND untouched text, plus the convergence and no-op tests | Residual risk: LOW — a future MediaMTX entry shape this tool does not model is rejected (fail closed), not remediated | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the on-box transaction is the same digest-bound activate runbook the operator already runs (root-only timestamped backup, atomic install, private-listener probe, "automatic rollback is not authorized" preserved); verify-before refuses a live config whose reader rule no longer authorizes the operator-stated reader IPs, and the renderer verify-before refuses a broken marked API rule, so remediate cannot silently drop scopes the operator depends on or paper over an unrelated API-rule breakage | Validation: shell contract pins (verify-reader-auth on LIVE and CANDIDATE, digest emission, REMEDIATION_NEEDED evidence, no worker control strings, bash -n) plus CLI verify-before rejection and fail-closed tests | Residual risk: LOW — a stale previously prepared candidate remains on disk after a failed remediate; the runbook forbids activating it and the digest binding prevents accidental digest-mismatch activation | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the new code is purely additive (zero deleted renderer lines; the single changed shell line is the dispatch alternation); every existing mode is pinned byte-identical by the seven-mode fixed-input harness diffed base vs head; the two existing pin changes (forwarding count 4→6, sanitize pins 3→5 and 2→3) are documented with their reason | Validation: byte-identity harness diff empty; focused batteries + full suite green; documented pin updates in place | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_remediate_fails_closed_on_publish_action + test_remediate_fails_closed_on_action_outside_read_publish + test_remediate_fails_closed_on_public_ip + test_remediate_fails_closed_on_loopback_ip + test_remediate_fails_closed_on_non_ipv4_entry + test_remediate_fails_closed_on_duplicate_ips (each asserts ConfigError AND untouched text)
- TEST-002 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_remediate_fails_closed_without_marked_rule + test_remediate_fails_closed_on_multiple_marked_rules + test_remediate_fails_closed_on_foreign_entry_inside_span + test_remediate_requires_internal_auth_method (span discipline + auth gating, text untouched)
- TEST-003 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_remediate_converges_drifted_single_ip_rule (converges to the exact canonical block, other marked rules byte-identical, ensure idempotency) + test_remediate_preserves_live_two_ip_scope_in_live_order (byte-identity pin vs _reader_rule_lines for the live scopes in live order) + test_remediate_is_idempotent_noop_on_conforming_rule
- TEST-004 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_cli_remediate_converges_and_writes_0600_candidate (0600 candidate, REMEDIATED evidence line, remediation_needed=YES) + test_cli_remediate_noop_is_byte_identical_with_clear_evidence (remediation_needed=NO) + test_cli_remediate_fail_closed_leaves_candidate_untouched + test_cli_remediate_verify_before_rejects_external_auth_method
- TEST-005 | Covers: RISK-002 + RISK-003 | Level: unit | Priority: P0 | Evidence: test_shell_contracts_remediate_subcommand (bash -n, subcommand dispatch, verify-reader-auth on LIVE+CANDIDATE, digest emission, REMEDIATED_READER/REMEDIATION_NEEDED/MUTATIONS evidence, no systemctl worker strings, automatic-rollback contract) + documented pin updates (multi_reader 4→6, sanitize 3→5 / 2→3)
- TEST-006 | Covers: RISK-003 | Level: integration | Priority: P0 | Evidence: seven-mode byte-identity harness (base 4db356f vs branch, empty diff) + full pytest suite green

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: canonical issue #437 Outcome Contract; allowed paths (renderer, camera-relay.sh, tests, docs runbook, SDD trio, progress file) enforced before first write; GH007 author identity set before any commit
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: remediate verify-before (verify-reader-auth on LIVE + renderer verify_internal_api_rule on LIVE) and activate's existing digest/mode/worker-stopped/auth-environment gates; nothing is mutated until the operator explicitly activates the reviewed digest
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: prior MediaMTX config preserved at the printed BACKUP path; candidate remains root-only 0600 | Retry: NO | Rollback: the existing activate flow preserves a root-only timestamped backup for an explicit rollback decision; automatic rollback is intentionally not authorized; the remediated candidate itself is a pure renderer output (re-renderable) | Evidence: camera-relay.sh activate backup/install/restart sequence unchanged; remediate block only writes the root-only candidate + sha file
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: verify-after pair (verify-reader-auth on CANDIDATE + renderer verify_internal_reader_rule/verify_internal_api_rule on the remediated text) plus the byte-exact ensure_internal_reader_rule post-condition; activate re-verifies reader auth before install and probes the private listener after restart
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: no new durable state beyond the existing candidate/sha-file/backup set; the renderer keeps no state; the remediator is a pure function
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond existing candidate/backup temporaries | Retry: NO | Rollback: NONE | Evidence: write_candidate temp-file cleanup and state-root handling unchanged; failed remediate leaves the previous candidate untouched (runbook: must not be activated)
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: REMEDIATED/REMEDIATED_READER/REMEDIATION_NEEDED/CANDIDATE_SHA256/MUTATIONS=PROTECTED_CANDIDATE_ONLY/SERVICE_RESTARTED=NO/SECRETS_DISPLAYED=NO lines; fail-closed ERROR line on stderr with exit 1
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: config rollback rides the unchanged camera-relay.sh root-only timestamped backup (explicit operator decision); the remediate path itself is restart-free before activation so it cannot compound a failure | Evidence: unchanged activate fault paths (exit 30/31/32 with BACKUP printed; "automatic rollback is not authorized")
