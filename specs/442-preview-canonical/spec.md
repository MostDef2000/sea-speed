# Spec: Fold the preview contour's inline config+catalog rendering into the canonical renderer

- Issue: #442
- Specification: specs/442-preview-canonical/spec.md

## Product outcome

The preview contour (dedicated `sea-speed-camera-preview-relay.service`)
rendered its standalone MediaMTX config and sanitized VPS catalog through a
~105-line inline Python heredoc inside `camera-preview-relay.sh` — a second,
divergent renderer. Its reader rule was UNMARKED, so repo tooling could not
verify it: a #362-class drift (wrong reader IPs, dropped path-pattern rule)
in the preview contour was undetectable (the D2 blind spot). RFC1918
validation was duplicated inline in both relay shells (D8, the first of
>=5 known sites). The reader IP was single-valued (the #372 gap class).

This change folds the preview rendering into the canonical module
(`scripts/operations/mediamtx_path_config.py`):

1. A new `ubuntu-preview-relay` mode renders the standalone preview config
   and the sanitized catalog from the protected inventory (fail-closed
   validation moved into the renderer). The shell becomes a thin CLI.
2. The preview reader rule carries a canonical marker
   (`READER_MARKER_PREVIEW`, keeping the `# Sea Speed least-privilege reader
   for canonical` prefix so the span-terminated rule parser and the bounded
   sanitize scanner treat it as renderer-owned) and is verifiable by repo
   tooling through the new `verify-preview-auth` verb — closing the D2
   blind spot.
3. A new `check-address` verb single-sources RFC1918 validation (reader-ip
   and private-rtsp kinds); both relay shells replace their duplicated
   inline validators with it (bounded slice: the other ~15 copies outside
   these two shells are out of scope and nothing is filed for them).
4. Multi-`--reader-ip` from day one on the preview contour (repeatable and
   comma-separated, order-preserving, fail-closed — mirroring
   `camera-relay.sh` since #372).
5. Byte discipline: re-renders with the same inputs are byte-identical;
   the canonical config render minus the ONE new marker line equals the
   legacy heredoc output for the same inputs; the catalog equals the legacy
   contract minus the dropped non-deterministic `generated_at` field (no
   consumer reads it); the 7 legacy renderer modes stay byte-identical
   (harness). The marker line and the dropped `generated_at` are DOCUMENTED
   one-time drifts (like the #437 drifted-rule remediation), not contract
   violations.
6. The preview profile stays API-LESS: the new mode never emits the
   `api`/`apiAddress` block (contrast: the cam1 contour's loopback watchdog
   API from #407).

## User scenarios

- US-1: An operator prepares the preview relay: the shell forwards the
  inventory and every `--reader-ip` occurrence to the renderer; the renderer
  validates the inventory fail-closed and writes the 0600 config + catalog
  candidates; the shell prints the historical evidence lines plus the new
  `READER_AUTH_SCOPE` token.
- US-2: The same inputs are prepared twice: both candidate digests are
  byte-identical (digest-bound activation depends on it; the legacy
  `generated_at` broke this for the catalog).
- US-3: Repo tooling verifies the live/candidate preview config:
  `verify-preview-auth` confirms exactly one marked preview rule with the
  requested reader scope and the read permission on the path pattern; a
  drifted rule (wrong IPs or action) is rejected fail-closed.
- US-4: A preview contour drift (`authInternalUsers` edited by hand) now
  trips the same detection class as the cam1 contour: the marker makes the
  rule owned and the byte-exact full-scope comparison detects mutations.
- US-5: Both relay shells validate addresses through the renderer
  `check-address` verb — a single RFC1918 implementation.
- US-6: A second VPS reader IP is added: `--reader-ip A --reader-ip B`
  renders one rule with both IPs in input order; the scope token reports
  `preview-multi-rfc1918-peer-count-2`.

## Scope

- `scripts/operations/mediamtx_path_config.py`: ADDITIVE ONLY — preview
  constants (`PREVIEW_PATH_PATTERN`, `READER_MARKER_PREVIEW`, inventory and
  catalog schemas), `preview_reader_scope_token`, `_preview_inventory`,
  `_preview_reader_rule_lines`, `_preview_render_texts`,
  `render_ubuntu_preview_relay`, `verify_preview_reader_auth_config`,
  `render_verify_preview_auth`, `run_check_address`, and three new
  subparsers. No existing function or mode changes (the 9 legacy verbs are
  untouched — harness-verified).
- `deploy/worker/ubuntu/camera-preview-relay.sh`: the inline heredoc
  (previously 185-290) becomes the renderer call; multi-IP parse/forward
  mirrors `camera-relay.sh`; renderer resolution block + renderer-exists
  gate; the two inline RFC1918 validators become `check-address` wrappers;
  the unit-file heredoc stays; the prepare/activate evidence lines stay
  byte-untouched with ONE new additive `READER_AUTH_SCOPE` line.
- `deploy/worker/ubuntu/camera-relay.sh`: ONLY the two validator function
  bodies (parse_address, validate_reader_ip) become renderer
  `check-address` wrappers — every other byte unchanged (the rendered cam1
  config is untouched because the `ubuntu-relay` mode is untouched).
- Tests: new `tests/test_mediamtx_preview_relay.py` (34 tests); re-pin
  `tests/test_camera_preview_gallery.py` (renderer-owned literals re-pointed
  to the renderer; shell keeps structural pins).
- Docs: `docs/operations/CAMERA_PREVIEW_RELAY.md` (short runbook).
- This SDD trio and the durable progress file.
- OUT of scope (per the issue's do-not-merge list): delivery knobs per
  contour; AI-worker-stopped guard (water only); config ownership split;
  auth topology shapes; watchdog `api` profile; unit hardening baselines;
  the sanitized catalog contract `sea_speed_camera_preview_catalog_v1`
  (schema string unchanged); historical water marker; no-auto-rollback
  policy; #447-style identity derivation for the preview activate; the
  other ~15 RFC1918 validation copies (vps/authentik/api/nginx/
  control-agent/tests — nothing filed).

## Requirements

- R-1: The preview config and catalog are rendered by the canonical module;
  the shell's inline heredoc is gone (thin CLI forwarding only).
- R-2: The preview reader rule carries the canonical marker with the
  `# Sea Speed ` prefix; `verify-preview-auth` detects #362-class drift
  fail-closed (exactly-one marker, subset semantics, read action, byte-exact
  full-scope comparison).
- R-3: RFC1918 validation is single-sourced through the `check-address`
  verb in both relay shells; exit codes and error discipline stay
  compatible with the existing shell pins.
- R-4: Multi-`--reader-ip` (repeatable + comma-separated, order-preserving,
  duplicates fail closed) on the preview contour, with the
  `preview-single-rfc1918-peer` / `preview-multi-rfc1918-peer-count-N`
  scope evidence.
- R-5: Byte-identity discipline: (a) self-identity; (b) legacy parity minus
  the marker line / `generated_at`; (c) the 7 legacy harness modes stay
  empty-diff; documented one-time drifts only.
- R-6: The preview profile emits no `api`/`apiAddress` block (API-less
  negative pin).
- R-7: The preview activate flow (digest gates, backups, restart, evidence
  lines) is byte-untouched; no #447 identity derivation in this slice.

## Acceptance criteria

- AC-1: preview config+catalog rendered by the canonical module
  (`scripts/operations/mediamtx_path_config.py`); the inline heredoc in
  `camera-preview-relay.sh` becomes a thin CLI.
- AC-2: the preview reader rule carries a canonical marker and is
  verifiable by repo tooling (closes the D2 blind spot: #362-class drift in
  the preview contour becomes detectable).
- AC-3: RFC1918 validation single-sourced (bounded: the `check-address`
  verb consumed by both relay shells).
- AC-4: byte-identical output discipline holds (self-identity; legacy
  parity minus the documented drifts; 7 legacy harness modes empty-diff).
- AC-5: contract tests green; SDD trio; digest-bound activation runbook
  unchanged.

## Runtime feedback

- RF-001: Operator actions expected: 1 bounded on-box preview-relay
  re-render transaction (prepare with the live inventory; confirm the
  rendered candidates are byte-identical to the live install modulo the
  documented marker/generated_at drifts; digest-bound activate; road worker
  probe window). Orchestrator records the runtime acceptance.
- RF-002: Evidence: prepare prints `PREPARED_PREVIEW_RELAY=YES`,
  `READER_AUTH_SCOPE`, the three candidate digests,
  `MUTATIONS=PROTECTED_CANDIDATES_ONLY`, `SERVICE_RESTARTED=NO`,
  `SECRETS_DISPLAYED=NO`; the renderer prints
  `RENDERED mode=ubuntu-preview-relay ... reader_scope=... api=none
  config_sha256=<digest> catalog_sha256=<digest>`; verify prints
  `VERIFIED mode=preview-auth reader_scope=... reader_permission=read-only`;
  activation keeps the historical `ACTIVATED_PREVIEW_RELAY=YES` evidence
  set.

## NFR assessment

- NFR-001 | Area: security | Target: the preview contour's reader authorization is renderer-owned and machine-verifiable: the marked rule keeps the "# Sea Speed " prefix (bounded sanitize auto-ownership), the rule parser's span-terminator treats it as a rule boundary, and verify-preview-auth fails closed on missing/duplicated markers, wrong scopes, wrong actions and (full-scope) any byte drift; inventory validation (schema, id grammar, duplicates, display bounds, private credential-bearing sources) is fail-closed in the renderer | Validation: executed drift table (missing marker, drifted ips, drifted action) + inventory fail-closed table (7 cases) + structural pins (renderer owns the literals, shell has no config literals left) | Evidence: tests/test_mediamtx_preview_relay.py — PreviewAuthVerificationTests, PreviewInventoryValidationTests, PreviewRendererStructuralTests | Status: PASS
- NFR-002 | Area: reliability/operations | Target: byte discipline — deterministic re-render (the legacy generated_at made the catalog digest unstable), legacy parity minus documented drifts, untouched legacy modes, digest-bound activation flow unchanged; the two shell evidence streams stay byte-compatible (one additive READER_AUTH_SCOPE line) | Validation: golden-bytes render, idempotency re-render, parity-minus-marker/generated_at comparison, 7-mode harness empty diff, bash -n | Evidence: tests/test_mediamtx_preview_relay.py — PreviewRendererGoldenTests, PreviewLegacyParityTests; harness transcript (byte-id-base-442 vs head) | Status: PASS
- NFR-003 | Area: maintainability | Target: one renderer, one RFC1918 validation (for the two relay shells), one multi-IP grammar: the preview contour shares the canonical marker grammar, the rule parser, the write-candidate discipline (0600 atomic) and the evidence conventions with the cam1 contour; the do-not-merge boundaries are preserved (no delivery knobs, no auth topology changes, catalog schema string unchanged) | Validation: structural pins (9 legacy verbs untouched, api-less negative pin, check-address single-sourcing in both shells) + full pytest suite | Evidence: tests/test_mediamtx_preview_relay.py — PreviewRendererStructuralTests, PreviewShellContractTests, CheckAddressCliTests | Status: PASS
