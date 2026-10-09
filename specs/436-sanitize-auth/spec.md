# Spec: Bounded prune of foreign unmarked loopback-API auth rules

- Issue: #436
- Specification: specs/436-sanitize-auth/spec.md

## Product outcome

During the #407 on-box activation (2026-10-09) the canonical re-render
installed the canonical MARKED loopback API rule for cam1, but the
pre-existing UNMARKED API rule from the 2026-10-07 manual edit remained in the
live `mediamtx.yml` as an inert duplicate (same loopback scope; probes green;
no auth widening). The root cause is structural: `ensure_internal_api_rule`
manages only its own marker block and is byte-exact idempotent, while
`verify_internal_api_rule` parses from the marker to the next reader marker or
block end and merges `ips`/`actions` across that span — a foreign unmarked
`127.0.0.1`/`api` entry is invisible to it, so every re-render reinstalls the
duplicate. No subcommand today removes foreign/unmarked auth rules.

This change adds a bounded sanitize path to the canonical tool:

1. A renderer scanner/pruner (`scripts/operations/mediamtx_path_config.py`)
   segments `authInternalUsers` per entry (not per marker span), identifies
   FOREIGN entries (not preceded by a canonical `# Sea Speed ` marker
   comment), and removes ONLY those whose scope EXACTLY equals the canonical
   loopback API rule (`ips == ["127.0.0.1"]`, `permissions == [- action: api]`,
   fully modeled fields). ANY other foreign rule fails the whole sanitize
   closed (reported scope, no deletion, nonzero exit, candidate untouched).
2. A new CLI mode `ubuntu-sanitize-auth` and a `camera-relay.sh sanitize`
   subcommand wire the transaction: verify-before (marked API rule on LIVE,
   reader rule on LIVE), prune, explicit foreign-rule count == 0 assertion
   (dedicated scanner, not the span-merge verify), verify-after (marked API
   rule + reader rule on CANDIDATE), digest-bound candidate emission.
   Installation reuses the existing digest-bound `activate` runbook unchanged
   (expected-sha256 binding, root-only timestamped backup, atomic install,
   systemctl restart, private-listener probe, "automatic rollback is not
   authorized").
3. Every existing renderer output stays byte-identical (7 modes + the
   preview-relay context untouched).

## User scenarios

- US-1: The operator runs one bounded on-box transaction
  (`camera-relay.sh sanitize` → `activate --expected-sha256`): the foreign
  unmarked duplicate is removed, the canonical marked rules survive
  byte-identically, the relay restarts and the private listener proves green.
- US-2: A foreign rule exists whose scope is NOT the canonical loopback-api
  scope (extra reader IP, extra action, missing ips restriction, or unmodeled
  fields): sanitize refuses with a scope report, deletes nothing, writes no
  candidate — the operator must handle such rules explicitly.
- US-3: The live config has no foreign rules: sanitize is an idempotent no-op
  (candidate byte-identical to the live config, `foreign_rules_removed=0`).
- US-4: A re-render after sanitize: `prepare`/`activate` outputs are unchanged
  from before this change (byte-identical 7-mode surface; the duplicate can no
  longer be re-installed because it is gone from the live config).

## Scope

- `scripts/operations/mediamtx_path_config.py`: `AUTH_ENTRY_RE`/
  `AUTH_ENTRY_COMMENT_RE`/`AUTH_MARKER_PREFIX`/`CANONICAL_API_SCOPE_*`
  constants, `_scan_auth_entries`, `_parse_auth_entry_fields`,
  `scan_foreign_auth_rules`, `count_foreign_auth_rules`,
  `sanitize_foreign_auth_rules`, the `render_ubuntu_sanitize_auth` handler and
  the `ubuntu-sanitize-auth` subparser. Purely additive; all existing modes
  untouched.
- `deploy/worker/ubuntu/camera-relay.sh`: usage text, `sanitize` dispatch in
  the subcommand case, and one `sanitize` transaction block (verify-before →
  sanitize render → verify-after → digest evidence). The `prepare`/`activate`
  flows are unchanged.
- `tests/test_mediamtx_sanitize_auth.py`: new RED-first battery (scan/prune
  core, CLI mode, shell contract pins).
- `tests/test_mediamtx_multi_reader_ip.py`: one documented pin update — the
  `"${reader_ip_args[@]}"` forwarding count 2→4, because the #436 sanitize
  block adds two `verify-reader-auth` forwardings (verify-before on LIVE,
  verify-after on CANDIDATE); the pin's intent (every reader-IP-consuming
  renderer call forwards all accumulated occurrences) is preserved.
- `docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md`: sanitize runbook
  appended to the "Ubuntu Worker relay API profile" section.
- This SDD trio and the durable progress file.
- Out of scope: `deploy/vps/**`, `deploy/nginx**`, preview-relay behavior,
  `.github/**`, `scripts/release/**`, specs/407-**; deleting ANY foreign rule
  outside the exact canonical loopback-api scope; automatic rollback.

## Requirements

- R-1: The sanitize path (renderer mode + `camera-relay.sh sanitize`
  subcommand) removes ONLY foreign unmarked `authInternalUsers` rules whose
  scope exactly equals the canonical loopback-api scope (`ips == ["127.0.0.1"]`,
  `permissions == [- action: api]`); ANY other foreign rule fails closed
  (report, no deletion, nonzero exit, candidate untouched).
- R-2: Verify-before/verify-after: the canonical marked API rule and the
  reader rules are intact before and after; the foreign-rule count is
  asserted == 0 explicitly after sanitize via a dedicated per-entry scanner
  (the existing verify's span-merge logic is not relied upon).
- R-3: Sanitize reuses the digest-bound activate runbook unchanged
  (expected-sha256, root-only timestamped backup, atomic install, systemctl
  restart, private-listener probe, "automatic rollback is not authorized"
  preserved); all existing renderer outputs stay byte-identical (7 modes +
  preview untouched).
- R-4: The sanitize candidate is written mode 0600 by the existing
  `write_candidate` machinery and the shell emits the digest evidence
  (`CANDIDATE_SHA256`) for the operator.
- R-5: The sanitize transaction never starts, stops, restarts or enables the
  AI worker and never displays secrets.

## Acceptance criteria

- AC-1: New sanitize path (renderer mode + `camera-relay.sh` subcommand)
  removes ONLY foreign unmarked auth rules whose scope exactly equals the
  canonical loopback-api scope (ips subset of {127.0.0.1}, actions subset of
  {api}); ANY other foreign rule fails closed (report, no deletion).
- AC-2: Verify-before/verify-after: canonical marked API rule and both reader
  rules intact; foreign-rule count asserted == 0 explicitly after sanitize
  (do NOT rely on existing verify's span-merge logic).
- AC-3: Sanitize reuses the digest-bound activate runbook (expected-sha256,
  root-only timestamped backup, atomic install, systemctl restart,
  private-listener probe, "automatic rollback is not authorized" preserved);
  all existing renderer outputs byte-identical (7 modes + preview untouched).
- AC-4: RED behavioral tests (the existing BASE_CONFIG fixtures already
  contain the unmarked duplicate shape); full suite green; SDD trio with
  deployment transaction audit.

## Runtime feedback

- RF-001: Operator actions expected: 1 bounded on-box sanitize transaction
  (`camera-relay.sh sanitize` → digest → `camera-relay.sh activate
  --expected-sha256`), run as root per the script gating; recorded in the
  #436 runtime acceptance by the orchestrator.
- RF-002: Evidence lines: renderer
  `SANITIZED mode=ubuntu-sanitize-auth foreign_rules_removed=N
  foreign_rules_remaining=0 api_rule=loopback-watchdog-intact
  output_sha256=…`; shell `SANITIZED_FOREIGN_AUTH=YES` +
  `CANDIDATE_SHA256=…` + `MUTATIONS=PROTECTED_CANDIDATE_ONLY` +
  `SERVICE_RESTARTED=NO` + `SECRETS_DISPLAYED=NO`; fail-closed evidence is
  `ERROR: foreign unmarked authInternalUsers rule is outside the canonical
  loopback-api scope …` on stderr with exit 1.

## NFR assessment

- NFR-001 | Area: security | Target: the bounded prune deletes ONLY foreign unmarked auth rules whose scope exactly equals the canonical loopback-api rule; any wider, narrower-unmodeled, or unparseable foreign rule fails the whole transaction closed before any deletion, and canonical marked rules are preserved byte-identically (post-condition asserted) | Validation: executed fail-closed table (wider ips, wider actions, non-api action, ip-less api grant, permission-level unmodeled ips, authMethod != internal, missing block) plus byte-identical marked-span post-condition and idempotent no-op | Evidence: tests/test_mediamtx_sanitize_auth.py — test_sanitize_fails_closed_on_wider_foreign_ips, test_sanitize_fails_closed_on_wider_foreign_actions, test_sanitize_fails_closed_on_non_api_foreign_rule, test_sanitize_fails_closed_on_ip_less_api_rule, test_sanitize_fails_closed_on_unmodeled_fields, test_sanitize_requires_internal_auth_method, test_sanitize_removes_only_the_canonical_scope_duplicate | Status: PASS
- NFR-002 | Area: operations/reliability | Target: the operator transaction is digest-bound and mutation-bounded — verify-before rejects a live config without the intact marked API rule, the candidate is 0600 with an explicit foreign-count==0 assertion from a dedicated scanner, and installation rides the unchanged activate runbook with root-only backup and no automatic rollback | Validation: executed CLI transaction tests (duplicate removed and re-verified, noop byte-identical, fail-closed leaves no candidate) plus shell contract pins (verify-reader-auth on LIVE and CANDIDATE, digest emission, no worker control strings) | Evidence: tests/test_mediamtx_sanitize_auth.py — test_cli_sanitize_removes_duplicate_and_reverifies_clean, test_cli_sanitize_noop_is_byte_identical_and_reverifies_clean, test_cli_sanitize_fail_closed_leaves_candidate_untouched, test_cli_sanitize_verify_before_rejects_missing_marked_api_rule, test_shell_contracts_sanitize_subcommand | Status: PASS
- NFR-003 | Area: compatibility | Target: every pre-existing renderer mode and the preview-relay context keep byte-identical output; the #372 reader-forwarding pin semantics are preserved (all occurrences forwarded; count 2→4 documented) | Validation: seven-mode fixed-input byte-identity harness diffed base vs head (empty diff) plus the documented pin update | Evidence: byte-identity harness transcript (byte-id-base vs branch, diff empty) and tests/test_mediamtx_multi_reader_ip.py — test_shell_contracts_forward_all_reader_ip_occurrences | Status: PASS
