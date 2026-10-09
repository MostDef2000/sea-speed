# Spec: Explicit opt-in prune of declared legacy foreign rules

- Issue: #444
- Specification: specs/444-declared-prune/spec.md

## Product outcome

The 2026-10-10 operator sanitize retry (#436 transaction) failed closed as
designed: besides the target unmarked loopback-API duplicate, the live worker
config carries two UNMARKED legacy `authInternalUsers` rules for the dead
`cam1-test` path — ips `["10.123.239.102"]` with actions `publish, read`, and
ips `["10.123.239.101"]` with action `read`. Repository evidence shows
`cam1-test` is dead legacy (its only repository reference is a source-URL
comment in a test fixture). The #436 sanitizer correctly refuses any foreign
rule outside the canonical loopback-api scope, so these rules are stuck: no
canonical path retires them, and manual config edits are forbidden.

This change extends the bounded sanitize path with repeatable explicit
opt-in prune declarations:

1. The renderer gains `--prune-declared SPEC` (repeatable) on
   `ubuntu-sanitize-auth`: a declaration pins one exact (path, ips, actions)
   triple. A foreign unmarked rule becomes deletable when its parsed
   permission-path set equals the declared path, its ips set equals the
   declared ips and its actions set equals the declared actions — EXACT
   equality, no subset semantics. Declarations are validated fail-closed
   (ips must parse as IP addresses; actions restricted to the renderer
   vocabulary {read, publish, api}). WITHOUT declarations the behavior is
   byte-for-byte the #436 fail-closed default.
2. The #436 discipline is unchanged: fail closed BEFORE any deletion on any
   foreign rule that is neither the canonical loopback-api scope nor a
   declared triple (partial matches refuse); marked `# Sea Speed ` rules are
   never removed even on an exact triple match and carry the byte-identity
   post-condition; the foreign-count == 0 post-condition is asserted by the
   dedicated scanner. Installation still rides the unchanged digest-bound
   `activate` runbook; no automatic rollback.
3. `camera-relay.sh sanitize` forwards repeatable `--prune-declared` specs to
   the renderer and reports per-declaration removals
   (`DECLARED_PRUNED=path=...:removed=N,...`); every existing renderer output
   stays byte-identical (7 modes + the preview-relay context untouched).

## User scenarios

- US-1: The operator retry window (issue #444 relay context: live config
  `/etc/mediamtx/mediamtx.yml`, private-rtsp-address `10.123.239.102:8554`,
  reader-ip `10.123.239.101`): stop the AI worker → `camera-relay.sh
  sanitize` with the two cam1-test declarations → `activate
  --expected-sha256` → start the worker → remediate verify. Both legacy rules
  are removed in one transaction, the canonical marked rules survive
  byte-identically, and `DECLARED_PRUNED=path=cam1-test:removed=1,...`
  documents the per-declaration removals.
- US-2: A third foreign rule exists that is neither the canonical loopback-api
  scope nor declared (e.g. another cam1-test-shaped rule with an undeclared
  IP): sanitize refuses with a scope report, deletes nothing, writes no
  candidate.
- US-3: A rule partially matches a declaration (same path, different ip; or
  extra ip; or extra action): the transaction fails closed — exact triple
  equality is the removal gate.
- US-4: The operator runs sanitize WITHOUT declarations on the same live
  config: byte-for-byte today's #436 behavior (refusal, no candidate, no
  `DECLARED_PRUNED` evidence lines).
- US-5: Re-running the same transaction on the sanitized config: idempotent
  no-op (`foreign_rules_removed=0`, per-declaration `removed=0`, candidate
  byte-identical to the live config).

## Scope

- `scripts/operations/mediamtx_path_config.py`: `_parse_auth_entry_fields`
  now also collects permission-level `path:` values (return shape
  `(ips, actions, paths, well_formed)`; empty `path:` value stays unmodeled);
  new `DeclaredAuthPrune` NamedTuple, `parse_declared_auth_prune` grammar
  parser, `sanitize_foreign_auth_rules_declared` core (declared triples
  extend the removable set; everything else of the #436 algorithm
  unchanged), `sanitize_foreign_auth_rules` kept as a stable 2-tuple
  wrapper, and the `--prune-declared` CLI flag with per-declaration
  `DECLARED_PRUNED` evidence lines.
- `deploy/worker/ubuntu/camera-relay.sh`: usage text (option + sanitize
  prose), `--prune-declared` argument case collecting `declared_prune_specs`,
  and the sanitize transaction block forwarding the declarations and
  emitting the aggregated `DECLARED_PRUNED=` evidence only when declarations
  were given. The `prepare`/`activate`/`remediate` flows are unchanged.
- `tests/test_mediamtx_sanitize_auth.py`: RED-first extension (+24 tests in
  4 new classes: declaration grammar, declared-prune core, CLI transaction,
  shell passthrough pins).
- `docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md`: declared-prune
  runbook appended to the sanitize section (grammar, exact-triple scope,
  operator retry window).
- This SDD trio and the durable progress file.
- Out of scope: any change to the activate runbook, automatic rollback,
  subset-scope matching, removing MARKED rules via declarations,
  `deploy/vps/**`, `.github/**`, preview-relay behavior, the #372/#437
  forwarding pins (verify-reader-auth count stays 5; no reader-ip forwarding
  change).

## Requirements

- R-1: `ubuntu-sanitize-auth` accepts repeatable `--prune-declared
  path=NAME,ips=IP[,IP...],actions=ACTION[,ACTION...]` declarations; without
  them the transaction is byte-for-byte the #436 fail-closed default (any
  foreign rule refuses).
- R-2: A declared prune removes ONLY unmarked rules whose parsed
  (paths, ips, actions) equals the declared triple exactly (path set ==
  {path}, ips set == declared ips set, actions set == declared actions,
  fully modeled fields); any other foreign rule fails closed before any
  deletion; marked rules are byte-identical (post-condition); the
  foreign-count == 0 post-condition is unchanged.
- R-3: Declaration grammar is validated fail-closed: exactly one `path=`,
  at least one syntactically valid ip, at least one action in
  {read, publish, api}; unknown keys, bare tokens before any key, duplicate
  path keys, empty values and whitespace-bearing paths refuse the
  transaction.
- R-4: The shell passes repeatable `--prune-declared` specs through to the
  renderer and reports per-declaration removals; the digest-bound activate
  runbook is unchanged; no auto-rollback; worker control and secrets
  discipline unchanged.
- R-5: Every pre-existing renderer mode and shell evidence surface stays
  byte-identical when no declarations are given (evidence lines appear only
  when declarations are present).

## Acceptance criteria

- AC-1: `ubuntu-sanitize-auth` gains repeatable explicit opt-in prune
  declarations (declared path + ips + actions); WITHOUT them the behavior is
  byte-for-byte today's fail-closed default (any foreign rule refuses the
  transaction).
- AC-2: A declared prune removes ONLY unmarked rules matching the declared
  (path, ips, actions) triple exactly; any other foreign rule still fails
  closed; marked rules remain byte-identical; foreign-count == 0 and
  marked-span byte-identity post-conditions unchanged.
- AC-3: The shell sanitize subcommand passes declarations through; evidence
  reports per-declaration removals; the digest-bound activate runbook is
  unchanged; no auto-rollback.
- AC-4: RED-first battery (declared prune converges; undeclared foreign rule
  still refuses; no-op idempotency), full suite green; SDD trio with
  deployment transaction audit.

## Runtime feedback

- RF-001: Operator actions expected: 1 bounded on-box transaction — the
  already-planned retry window (stop worker → sanitize with the two
  cam1-test declarations → activate digest → start worker → remediate
  verify), run as root per the script gating; recorded in the #444/#436
  runtime acceptance by the orchestrator.
- RF-002: Evidence lines: renderer per-declaration
  `DECLARED_PRUNED path=cam1-test ips=10.123.239.102 actions=publish,read
  removed=1` plus the unchanged `SANITIZED mode=ubuntu-sanitize-auth
  foreign_rules_removed=3 foreign_rules_remaining=0
  api_rule=loopback-watchdog-intact output_sha256=…`; shell
  `DECLARED_PRUNED=path=cam1-test:removed=1,path=cam1-test:removed=1` (only
  when declarations were given) + `SANITIZED_FOREIGN_AUTH=YES` +
  `CANDIDATE_SHA256=…` + `MUTATIONS=PROTECTED_CANDIDATE_ONLY` +
  `SERVICE_RESTARTED=NO` + `SECRETS_DISPLAYED=NO`; fail-closed evidence is
  `ERROR: foreign unmarked authInternalUsers rule is outside the canonical
  loopback-api scope and matches no declared prune …` on stderr with exit 1,
  or `ERROR: invalid --prune-declared declaration …` for grammar violations.

## NFR assessment

- NFR-001 | Area: security | Target: a declared prune removes ONLY unmarked rules matching the declared (path, ips, actions) triple exactly; partial matches, undeclared foreign rules and unmodeled entries fail the whole transaction closed before any deletion; marked rules are never removable via declarations and carry the byte-identity post-condition; the declaration vocabulary is bounded (ips must parse as IP addresses, actions ∈ {read, publish, api}) | Validation: executed fail-closed table (undeclared third rule, partial matches: extra ip / different path / extra action, unmodeled fields under a declared shape, marked-rule exact-match no-op) plus marked-span byte-identity and idempotent no-op tests | Evidence: tests/test_mediamtx_sanitize_auth.py — test_declared_prune_leaves_undeclared_foreign_rule_fail_closed, test_declared_prune_rejects_partial_match_extra_ip / _different_path / _extra_action, test_declared_prune_rejects_unmodeled_foreign_rule_even_if_scoped, test_declared_prune_never_touches_marked_rule_matching_the_triple, test_parse_declared_spec_rejects_* | Status: PASS
- NFR-002 | Area: operations/reliability | Target: the retry-window transaction is digest-bound and mutation-bounded exactly as #436 — verify-before/verify-after unchanged, candidate 0600, per-declaration removal evidence, installation rides the unchanged activate runbook with root-only backup and no automatic rollback | Validation: executed CLI transaction tests (declared prune converges with per-declaration evidence, no-declaration refusal byte-for-byte, one-of-two-declarations refuses, invalid spec refuses, no candidate on any failure) plus shell contract pins (declared_args forwarding, DECLARED_PRUNED evidence, digest/activate discipline unchanged) | Evidence: tests/test_mediamtx_sanitize_auth.py — test_cli_declared_prune_removes_legacy_rules_and_api_duplicate, test_cli_without_declarations_refuses_byte_for_byte, test_cli_one_declaration_with_two_legacy_rules_refuses, test_cli_invalid_declaration_spec_fails_closed, test_shell_contracts_declared_prune_passthrough | Status: PASS
- NFR-003 | Area: compatibility | Target: WITHOUT declarations the renderer and shell behavior is byte-for-byte the #436 default (no DECLARED_PRUNED lines, same SANITIZED line, same exit codes); every pre-existing renderer mode keeps byte-identical output; the #372/#436 forwarding pins keep their counts (verify-reader-auth == 5, CANDIDATE_SHA256 == 3) | Validation: seven-mode fixed-input byte-identity harness diffed base vs head (empty diff); no-declaration CLI guard asserting identical refusal; shell pin counts unchanged | Evidence: byte-identity harness transcript (byte-id-base-444 vs branch, diff empty), tests/test_mediamtx_sanitize_auth.py — test_no_declarations_is_byte_for_byte_todays_default, test_cli_without_declarations_refuses_byte_for_byte, test_shell_contracts_sanitize_subcommand | Status: PASS
