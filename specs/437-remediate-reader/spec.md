# Spec: Canonical drift-remediation path for drifted LIVE reader rules

- Issue: #437
- Specification: specs/437-remediate-reader/spec.md

## Product outcome

During the #372 operator verification (2026-10-09) the canonical tool
correctly REFUSED a prepare-only 2-IP re-render of cam1 (fail-closed against
widening the live 1-IP rule — the `ensure_internal_reader_rule` byte-exact
guard at the heart of the bounded renderer). The refusal is right; the gap is
process: there is no repo-owned path to converge a DRIFTED live reader rule
back to canonical while preserving the live rule's current scopes. A drifted
block (hand-edited form: missing `pass:` field, block-style or reordered ips,
unquoted values, or a hand-added legitimate VPS reader IP) passes
`verify-reader-auth` but is forever refused by every re-render.

This change adds a bounded remediate path to the canonical tool:

1. A renderer core function (`remediate_internal_reader_rule`) locates the
   marker-anchored reader rule for the path, reuses `_parse_rule_block` to
   extract the live ips/actions, re-authorizes EVERY scope element through
   the existing validators (`validate_peer_reader_ip` then
   `validate_reader_ip` — the relay profile renders reader IPs as literal
   RFC1918 IPv4, so non-IPv4, loopback, link-local, multicast, reserved,
   public and duplicate ips fail closed), requires actions ⊆ {read, publish}
   with `publish` failing closed on the read-only cam1 relay profile
   (publisher roles cannot be recovered from a flat live ips list), and
   re-emits the canonical block via `_reader_rule_lines` preserving the live
   scopes. The remediation NEVER canonizes an unauthorized scope; a merged
   span (foreign unmarked entry between the drifted block and the next
   reader marker) also fails closed — run the #436 sanitize first.
2. A new CLI mode `ubuntu-remediate-reader` and a `camera-relay.sh
   remediate` subcommand wire the transaction: verify-before (marked loopback
   API rule on LIVE via the renderer mode; reader rule on LIVE via
   `verify-reader-auth`), converge, verify-after (reader rule + marked API
   rule on the candidate plus byte-exact `ensure_internal_reader_rule`
   idempotency), digest-bound 0600 candidate emission. Installation reuses
   the existing digest-bound `activate` runbook unchanged (expected-sha256
   binding, root-only timestamped backup, atomic install, systemctl restart,
   private-listener probe, "automatic rollback is not authorized").
3. Every existing renderer output stays byte-identical (7 modes + the
   preview-relay context untouched); single-IP historical output byte-pins
   preserved.

## User scenarios

- US-1: The operator runs one bounded on-box transaction
  (`camera-relay.sh remediate` → `activate --expected-sha256`): the drifted
  marked reader rule converges to the canonical block with the live scopes
  preserved, the relay restarts and the private listener proves green.
- US-2: The drifted rule carries an unauthorized scope (public/loopback/
  non-IPv4/duplicate ip, action outside {read, publish}, publish on the
  read-only cam1 relay profile, or a foreign entry merged into the span):
  remediate refuses with a scope report, replaces nothing, writes no
  candidate — the operator handles such rules explicitly.
- US-3: The live reader rule is conforming (non-drifted): remediate is an
  idempotent no-op (`REMEDIATION_NEEDED=NO`) whose candidate is
  byte-identical to the live config.
- US-4: A re-render after remediate: `prepare`/`activate` outputs are
  unchanged from before this change (byte-identical 7-mode surface; the
  converged block is exactly what `ensure_internal_reader_rule` accepts).

## Scope

- `scripts/operations/mediamtx_path_config.py`: `READER_RULE_ALLOWED_ACTIONS`
  constant, `_reader_rule_ips_in_order`, `remediate_internal_reader_rule`,
  the `render_ubuntu_remediate_reader` handler and the
  `ubuntu-remediate-reader` subparser. Purely additive; all existing modes
  untouched.
- `deploy/worker/ubuntu/camera-relay.sh`: usage text (command line + prose
  paragraph), `remediate` dispatch in the subcommand case, and one
  `remediate` transaction block (verify-before → remediate render → digest +
  0600 sha file → verify-after → evidence lines). The `prepare`/`activate`/
  `sanitize` flows are unchanged.
- `tests/test_mediamtx_remediate_reader.py`: new RED-first battery (core
  convergence/no-op/fail-closed table, CLI mode, shell contract pins).
- `tests/test_mediamtx_multi_reader_ip.py`: one documented pin update — the
  `"${reader_ip_args[@]}"` forwarding count 4→6, because the #437 remediate
  block adds two `verify-reader-auth` forwardings (verify-before on LIVE,
  verify-after on CANDIDATE); the pin's intent (every reader-IP-consuming
  renderer call forwards all accumulated occurrences) is preserved.
- `tests/test_mediamtx_sanitize_auth.py`: documented structural pin updates
  for the same reason (dispatch string gains `remediate`; verify-reader-auth
  count 3→5; CANDIDATE_SHA256/MUTATIONS=PROTECTED_CANDIDATE_ONLY counts 2→3).
- `docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md`: remediate runbook
  appended after the #436 sanitize runbook.
- This SDD trio and the durable progress file.
- Out of scope: `deploy/vps/**`, `deploy/nginx**`, preview-relay behavior,
  `.github/**`, `scripts/release/**`, specs/407-**, specs/436-**; widening or
  narrowing any live scope (remediation preserves the live scopes verbatim);
  automatic rollback.

## Requirements

- R-1: The remediate path (renderer mode + `camera-relay.sh remediate`
  subcommand) reads the live config, locates the drifted marker-anchored
  reader rule, reuses `_parse_rule_block` for the live ips/actions, and
  classifies every ip through the existing validators; actions must be a
  subset of {read, publish}; publish on the cam1 relay profile fails closed;
  non-IPv4/public/loopback/duplicate ips fail closed — the remediation NEVER
  canonizes an unauthorized scope.
- R-2: Re-emit the canonical block via `_reader_rule_lines` preserving the
  live scopes, replace the drifted block, re-verify both reader and API
  rules, write the candidate via the existing 0600 temp+rename path; the
  existing digest-bound `activate` runbook is used unchanged.
- R-3: The new `camera-relay.sh` subcommand carries the existing guards
  (require_root, auth-override check, worker-stopped gate via the unchanged
  activate, expected-sha256 binding); preview relay untouched; all other
  render modes byte-identical; single-IP historical output byte-pins
  preserved.
- R-4: A conforming (non-drifted) live rule is an idempotent no-op with clear
  evidence (`REMEDIATION_NEEDED=NO`); the candidate is still emitted
  byte-identical to the live marked span.
- R-5: The remediate transaction never starts, stops, restarts or enables the
  AI worker and never displays secrets.

## Acceptance criteria

- AC-1: Remediate path reads the live config, locates the drifted
  marker-anchored reader rule, reuses `_parse_rule_block` to extract live
  ips/actions, classifies every ip through the existing validators
  (`validate_peer_reader_ip`/`validate_reader_ip`); actions must be a subset
  of {read, publish}; publish on cam1 relay profile fails closed;
  non-IPv4/public/loopback/duplicate ips fail closed — NEVER canonize an
  unauthorized scope.
- AC-2: Re-emit the canonical block via `_reader_rule_lines` preserving the
  live scopes, replace the drifted block, re-verify both reader and API
  rules, write candidate via existing 0600 temp+rename; existing digest-bound
  activate used unchanged.
- AC-3: New `camera-relay.sh` subcommand carries existing guards (require_root,
  auth-override check, worker-stopped gate, digest binding); preview relay
  untouched; all other render modes byte-identical; single-IP historical
  output byte-pins preserved.
- AC-4: RED behavioral tests (drift → refused prepare stays; remediate →
  converges; unauthorized scope → fail closed); full suite green; SDD trio.

## Runtime feedback

- RF-001: Operator actions expected: 1 bounded on-box remediate transaction
  (`camera-relay.sh remediate` → digest → `camera-relay.sh activate
  --expected-sha256`), run as root per the script gating; recorded in the
  #437 runtime acceptance by the orchestrator.
- RF-002: Evidence lines: renderer
  `REMEDIATED mode=ubuntu-remediate-reader path=cam1 remediation_needed=YES|NO
  reader_scope=… reader_permission=read-only output_sha256=…`; shell
  `REMEDIATED_READER=YES` + `REMEDIATION_NEEDED=YES|NO` +
  `CANDIDATE_SHA256=…` + `MUTATIONS=PROTECTED_CANDIDATE_ONLY` +
  `SERVICE_RESTARTED=NO` + `SECRETS_DISPLAYED=NO`; fail-closed evidence is
  the offending-scope ERROR line on stderr with exit 1 and no candidate.

## NFR assessment

- NFR-001 | Area: security | Target: the bounded remediation re-authorizes EVERY scope element of the drifted marked reader block BEFORE re-emission — every ip must pass both validate_peer_reader_ip and validate_reader_ip (RFC1918-only relay profile), duplicates and parse divergence fail closed, actions must be a subset of {read, publish} with publish failing closed on the read-only cam1 relay profile, and the span discipline refuses merged/foreign content — so an unauthorized scope can never be canonized | Validation: executed fail-closed table (publish action, api action, public ip, loopback ip, non-IPv4 entry, duplicate ips, missing marker, multiple markers, foreign entry inside span, authMethod != internal) each asserting ConfigError AND untouched text | Evidence: tests/test_mediamtx_remediate_reader.py — test_remediate_fails_closed_on_publish_action, test_remediate_fails_closed_on_action_outside_read_publish, test_remediate_fails_closed_on_public_ip, test_remediate_fails_closed_on_loopback_ip, test_remediate_fails_closed_on_non_ipv4_entry, test_remediate_fails_closed_on_duplicate_ips, test_remediate_fails_closed_without_marked_rule, test_remediate_fails_closed_on_multiple_marked_rules, test_remediate_fails_closed_on_foreign_entry_inside_span, test_remediate_requires_internal_auth_method | Status: PASS
- NFR-002 | Area: operations/reliability | Target: the operator transaction is digest-bound and mutation-bounded — verify-before rejects a live config whose reader rule no longer authorizes the operator-stated reader IPs or whose marked API rule is broken, the candidate is 0600 via the existing write_candidate temp+rename path, and installation rides the unchanged digest-bound activate runbook with root-only backup and no automatic rollback; a conforming rule is an idempotent no-op with REMEDIATION_NEEDED=NO evidence and a byte-identical candidate | Validation: executed CLI transaction tests (convergence + 0600 candidate + evidence line, no-op byte-identical, fail-closed leaves no candidate, verify-before rejection) plus shell contract pins (verify-reader-auth on LIVE and CANDIDATE, digest emission, REMEDIATED_READER/REMEDIATION_NEEDED evidence, no worker control strings) | Evidence: tests/test_mediamtx_remediate_reader.py — test_cli_remediate_converges_and_writes_0600_candidate, test_cli_remediate_noop_is_byte_identical_with_clear_evidence, test_cli_remediate_fail_closed_leaves_candidate_untouched, test_cli_remediate_verify_before_rejects_external_auth_method, test_shell_contracts_remediate_subcommand | Status: PASS
- NFR-003 | Area: compatibility | Target: every pre-existing renderer mode and the preview-relay context keep byte-identical output; the remediated block is structurally byte-identical to what ubuntu-relay renders for the same live scopes (shared _reader_rule_lines), with the live ips order preserved; the #372/#436 shell pin semantics are preserved (all occurrences forwarded; counts 4→6 / 3→5 / 2→3 documented) | Validation: seven-mode fixed-input byte-identity harness diffed base vs head (empty diff) plus the documented pin updates and the two-IP live-order byte-identity test | Evidence: byte-identity harness transcript (byte-id-base-437 vs branch, diff empty) and tests/test_mediamtx_remediate_reader.py — test_remediate_preserves_live_two_ip_scope_in_live_order; tests/test_mediamtx_multi_reader_ip.py — test_shell_contracts_forward_all_reader_ip_occurrences (documented 4→6) | Status: PASS
