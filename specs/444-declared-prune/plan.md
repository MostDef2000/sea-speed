# Plan: Explicit opt-in prune of declared legacy foreign rules

- Issue: #444
- Specification: specs/444-declared-prune/spec.md

## Implementation approach

1. RECON-established facts: the #436 sanitizer (in main since 4db356f)
   segments `authInternalUsers` per entry via `_scan_auth_entries` and prunes
   only the canonical loopback-api scope; `_parse_auth_entry_fields` SKIPPED
   permission-level `path:` values (the #444 gap — the cam1-test rules carry
   `path: cam1-test` under permissions items); the fail-closed-before-deletion
   discipline and the marked-span byte-identity + foreign-count==0
   post-conditions are the conventions to preserve; the operator's reader-ip
   (10.123.239.101) equals the second legacy rule's IP, so declarations must
   match the full path+ips+actions triple to keep the canonical reader rule
   safe.
2. Renderer: extend `_parse_auth_entry_fields` to collect permission-level
   `path:` scalars (quote-stripped, comma-split) into a `paths` set (return
   shape `(ips, actions, paths, well_formed)`; empty `path:` value stays
   unmodeled); add `DeclaredAuthPrune` (NamedTuple) and
   `parse_declared_auth_prune` (grammar `path=NAME,ips=IP[,IP...],
   actions=ACTION[,ACTION...]`, bare tokens continue the previous key; ips
   validated as IP addresses, actions restricted to {read, publish, api});
   add `sanitize_foreign_auth_rules_declared(text, declared_prunes)` — the
   #436 core with declared triples as additional removable entries (exact
   equality, first-matching declaration consumed, per-declaration counts) —
   and keep `sanitize_foreign_auth_rules` as a stable 2-tuple wrapper with
   empty declarations; add the repeatable `--prune-declared` CLI flag and
   per-declaration `DECLARED_PRUNED ... removed=N` evidence lines (printed
   only when declarations are present).
3. Shell: `declared_prune_specs=()` collection with a `--prune-declared`
   case (non-empty validation; grammar delegated to the renderer); the
   sanitize block builds `declared_args`, forwards them to the renderer,
   captures its stdout, and prints
   `DECLARED_PRUNED=path=...:removed=N,...` only when declarations were
   given (a missing renderer line fails closed via grep under pipefail).
   Usage documents the option and the declared-prune semantics. The
   activate runbook is byte-unchanged.
4. Tests: extend `tests/test_mediamtx_sanitize_auth.py` (+22 tests, 4 new
   classes — declaration grammar, declared-prune core, CLI transaction,
   shell passthrough pins) RED-first on base cf2a462.
5. Docs: declared-prune runbook appended to the #436 sanitize section of
   docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md, including the
   operator retry window from the issue relay context.

## Architecture

- The declaration extends the existing whitelist (canonical api-scope OR an
  exactly-declared triple); it does NOT loosen the fail-closed gate: every
  foreign rule still must be either api-scope (default #436) or an exact
  declared match, else the whole transaction refuses before any deletion.
- Matching uses parsed VALUES, not text: `_parse_auth_entry_fields` yields
  the entry's permission-path set, ips set and actions set; a declaration
  matches when `paths == {decl.path} ∧ ips == set(decl.ips) ∧ actions ==
  set(decl.actions)`. Exact set equality — no subset semantics — so a rule
  with an extra ip/action or a different path can never ride a declaration.
- Declarations never touch marked rules: the marked/unmarked classification
  happens in `_scan_auth_entries` before matching, and the marked-span
  byte-identity post-condition is asserted unchanged.
- The parser change is additive (one more set in the return tuple; the
  previous `path:` skip became a collect); without declarations the core
  takes the same code path as #436 (the declaration loop is empty), keeping
  the no-declaration behavior byte-identical.
- The shell keeps the established mutation boundary: renderer invocations
  only write the root-only candidate; live state changes exclusively inside
  the existing activate flow; the DECLARED_PRUNED aggregation is pure text
  shaping of renderer output (fail closed on missing evidence).

## Decisions

- D-1: Exact (path, ips, actions) triple equality, not subset semantics: the
  operator's reader-ip equals the second legacy rule's IP, so a path-only or
  ips-subset match could widen removal to live rules; the conservative
  reading of AC-2 is exact equality and that is what ships.
- D-2: Declarations validate fail-closed at parse time (unknown key, missing
  key, duplicate path, empty value, invalid ip, unknown action, whitespace
  in path → ConfigError before any config read), so a typo can never produce
  a silently narrower declaration that then refuses at prune time.
- D-3: The grammar uses comma-separated `key=value` sections with bare-token
  continuation (`path=cam1-test,ips=10.123.239.102,actions=publish,read`) —
  one flag per declaration, repeatable; values never contain commas so no
  escaping is needed.
- D-4: The actions vocabulary is the renderer's own {read, publish, api}; a
  legacy rule outside it cannot be declared and keeps failing closed (the
  bounded tool does not model other actions).
- D-5: Per-declaration evidence is a renderer concern (`DECLARED_PRUNED`
  lines) that the shell aggregates into `DECLARED_PRUNED=...`; the shell
  never parses auth rules itself — it only forwards specs verbatim.
- D-6: Tests extend the existing `tests/test_mediamtx_sanitize_auth.py`
  battery (same file as #436 — the domains share fixtures and helpers) in 4
  new classes; the two byte-for-byte-default guards intentionally pass on
  base (they pin today's behavior, not the new feature).
- D-7: Docs live in the existing sanitize runbook section as a #444
  subsection — the retry window is the same transaction as #436 with
  declarations added.

## Affected contours

- Ubuntu Worker/relay: `deploy/worker/ubuntu/camera-relay.sh` (UBUNTU_WORKER
  per the change-control policy), `scripts/operations/mediamtx_path_config.py`
  (CONTROL_PLANE; renders worker relay config), the focused test file, the
  docs runbook, this SDD trio (+ durable progress file outside the repo
  tree).
- No change to `api/**`, `frontend/**`, `worker/**`, `.github/**`,
  `deploy/vps/**`, `deploy/nginx**`, preview-relay behavior, systemd
  units/timers, `tests/test_mediamtx_multi_reader_ip.py` (forwarding pin
  counts unchanged), `specs/407-**`, `specs/436-**`, `scripts/release/**`.

## Validation

- RED: the extended battery fails 23/40 on base cf2a462 (all 22
  new-behavior tests + the empty-declarations core variant; exact names in
  the delivery transcript and tasks.md AC-4) and passes 40/40 on the branch.
- Full suite on head branch: green (exact counts in the verification
  transcript).
- Byte-identity: seven-mode fixed-input harness run on base cf2a462
  (byte-id-base-444) and on the branch (byte-id-head-444); the output
  directories must diff empty.
- `bash -n deploy/worker/ubuntu/camera-relay.sh`: clean.
- ruff (`scripts/quality/ruff.toml`) on changed Python files: clean.
- `python3 scripts/ci/validate_sdd.py --event <pr-event.json>`: green
  (base cf2a462, head = branch tip).

## Runtime feedback

- RF-001: Operator actions expected: 1 bounded on-box retry-window
  transaction (stop AI worker → sanitize with two cam1-test declarations →
  digest → activate --expected-sha256 → start worker → remediate verify),
  root-gated; orchestrator records the runtime acceptance (which also closes
  #436 per the issue).
- RF-002: Evidence: renderer `DECLARED_PRUNED path=... removed=N` per
  declaration + unchanged `SANITIZED mode=ubuntu-sanitize-auth
  foreign_rules_removed=N foreign_rules_remaining=0
  api_rule=loopback-watchdog-intact output_sha256=…`; shell
  `DECLARED_PRUNED=path=cam1-test:removed=1,path=cam1-test:removed=1` +
  `SANITIZED_FOREIGN_AUTH=YES` + `CANDIDATE_SHA256=…`; fail-closed lines
  `ERROR: foreign unmarked authInternalUsers rule is outside the canonical
  loopback-api scope and matches no declared prune …` /
  `ERROR: invalid --prune-declared declaration …` (stderr, exit 1, candidate
  untouched).

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from
  `scripts/ci/validate_change_contract.py` `classify_file`/`derive_impact`
  over the changed-file set — `deploy/worker/ubuntu/camera-relay.sh`
  classifies UBUNTU_WORKER, `scripts/operations/mediamtx_path_config.py`
  classifies CONTROL_PLANE; `derive_impact` returns UBUNTU_WORKER (runtime
  contours {UBUNTU_WORKER}) with a config mutation, matching the Outcome
  Contract posted on issue #444. Security impact is declared LOW in the PR
  body (matching RISK-001's LOW residual).
- RISK-001 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: a declaration can only extend the #436 whitelist with EXACT (path, ips, actions) set equality on UNMARKED, fully modeled entries; partial matches and undeclared rules fail the whole transaction closed before any deletion; marked rules are never declaration-removable and keep the byte-identity post-condition; the declaration vocabulary is validated at parse time (IP addresses, actions ∈ {read, publish, api}) | Validation: executed fail-closed table (undeclared third rule; partial matches extra-ip/different-path/extra-action; unmodeled fields under a declared shape; marked exact-match no-op) + grammar rejection tests | Residual risk: LOW — a legacy rule that parses exactly as declared but carries unmodeled semantics is rejected (fail closed), not deleted | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the retry window rides the unchanged digest-bound activate runbook (root-only timestamped backup, atomic install, private-listener probe, "automatic rollback is not authorized" preserved); verify-before/verify-after and the AI-worker-stopped gate are untouched; per-declaration removals are reported so the operator can compare declared vs removed counts before activating | Validation: CLI transaction tests (converge, per-declaration evidence, refusal variants leave no candidate) + shell contract pins (forwarding, evidence line, digest emission, no worker control strings, bash -n) | Residual risk: LOW — an operator could declare a still-needed rule by mistake; the exact-triple scope plus the printed DECLARED_PRUNED evidence and the digest review make the mistake visible before activation | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the parser change is additive (collect what was previously skipped) and the declaration code paths are inert without the flag; the seven-mode fixed-input harness pins every existing renderer output byte-identical; the #372/#436 shell pins keep their counts (verify-reader-auth == 5, CANDIDATE_SHA256 == 3) | Validation: byte-identity harness diff empty (byte-id-base-444 vs byte-id-head-444); no-declaration byte-for-byte guards; full pytest suite green | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: DeclaredAuthPruneSpecTests (grammar happy path, bare-token continuation, unknown key, missing path/ips/actions, invalid ip, invalid action, duplicate path, empty spec — all ConfigError)
- TEST-002 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_declared_prune_removes_exactly_the_declared_triples (both cam1-test rules + default api duplicate, per-declaration [1, 1], marked rules intact, verifies pass) + test_declared_prune_leaves_undeclared_foreign_rule_fail_closed + test_declared_prune_rejects_partial_match_extra_ip / _different_path / _extra_action + test_declared_prune_rejects_unmodeled_foreign_rule_even_if_scoped + test_declared_prune_never_touches_marked_rule_matching_the_triple + test_declared_prune_is_idempotent_noop_on_clean_config + test_no_declarations_is_byte_for_byte_todays_default
- TEST-003 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_cli_declared_prune_removes_legacy_rules_and_api_duplicate (two declarations, foreign_rules_removed=3, two DECLARED_PRUNED lines, 0600 candidate, canonical verifies) + test_cli_without_declarations_refuses_byte_for_byte + test_cli_one_declaration_with_two_legacy_rules_refuses + test_cli_invalid_declaration_spec_fails_closed
- TEST-004 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: test_shell_contracts_declared_prune_passthrough (bash -n, usage documents --prune-declared, declared_prune_specs collection, declared_args forwarding, DECLARED_PRUNED= evidence, verify-reader-auth == 5, CANDIDATE_SHA256 == 3, MUTATIONS discipline, no worker control strings)
- TEST-005 | Covers: RISK-003 | Level: integration | Priority: P0 | Evidence: seven-mode byte-identity harness (base cf2a462 vs branch, empty diff) + test_no_declarations_is_byte_for_byte_todays_default + test_cli_without_declarations_refuses_byte_for_byte + full pytest suite green

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: canonical issue #444 Outcome Contract; allowed paths (renderer, camera-relay.sh, tests, docs runbook, SDD trio, progress file) enforced before first write; GH007 author identity set before any commit
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: sanitize verify-before (verify-reader-auth on LIVE + renderer verify_internal_api_rule on LIVE) and activate's existing digest/mode/worker-stopped/auth-environment gates; declaration grammar validated before the config is read; nothing is mutated until the operator explicitly activates the reviewed digest
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: prior MediaMTX config preserved at the printed BACKUP path; candidate remains root-only 0600 | Retry: NO | Rollback: the existing activate flow preserves a root-only timestamped backup for an explicit rollback decision; automatic rollback is intentionally not authorized; the pruned candidate itself is a pure renderer output (re-renderable with the same declarations) | Evidence: camera-relay.sh activate backup/install/restart sequence unchanged; sanitize block only writes the root-only candidate + sha file
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: verify-after pair (verify-reader-auth on CANDIDATE + renderer verify_internal_api_rule on pruned) plus the unchanged count_foreign_auth_rules(pruned) == 0 post-condition covering declared AND default removals; activate re-verifies reader auth before install and probes the private listener after restart; DECLARED_PRUNED evidence lets the operator confirm declared == removed before activating
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: no new durable state beyond the existing candidate/sha-file/backup set; declarations live only in the operator command line and the transaction evidence
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond existing candidate/backup temporaries | Retry: NO | Rollback: NONE | Evidence: write_candidate temp-file cleanup and state-root handling unchanged; a failed declared sanitize leaves the previous candidate untouched (runbook: must not be activated)
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: per-declaration DECLARED_PRUNED lines plus SANITIZED/SANITIZED_FOREIGN_AUTH/CANDIDATE_SHA256/MUTATIONS=PROTECTED_CANDIDATE_ONLY/SERVICE_RESTARTED=NO/SECRETS_DISPLAYED=NO; fail-closed ERROR line on stderr with exit 1 (scope report or declaration grammar)
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: config rollback rides the unchanged camera-relay.sh root-only timestamped backup (explicit operator decision); the sanitize path itself is restart-free before activation so it cannot compound a failure; the AI worker stop/start steps in the retry window are operator-managed and independent of the relay tooling | Evidence: unchanged activate fault paths (exit 30/31/32 with BACKUP printed; "automatic rollback is not authorized")
