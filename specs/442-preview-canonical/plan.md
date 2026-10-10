# Plan: Fold the preview contour's inline config+catalog rendering into the canonical renderer

- Issue: #442
- Specification: specs/442-preview-canonical/spec.md

## Implementation approach

1. RECON-established facts (at c2bd3b9): the renderer already exposes 9
   verbs with 7 output modes (the harness population); the marker grammar is
   `reader_marker()` with the `# Sea Speed least-privilege reader for
   canonical` prefix that span-terminates rule blocks (`_parse_rule_block`)
   and the bounded sanitize scanner auto-owns any `# Sea Speed ` marker
   (`AUTH_MARKER_PREFIX`); `_reader_ip_list` + repeatable `--reader-ip` and
   `reader_scope_token` exist since #372; `write_candidate` writes 0600
   atomic candidates; the preview shell's heredoc (185-290) held the
   inventory validation, the unmarked reader rule, the standalone config,
   and the catalog with a non-deterministic `generated_at`; consumers
   (`api/app/main.py`, `configure-analytics-profiles.py`) do NOT read
   `generated_at`; the preview shell lacked the repo-root/renderer
   resolution block and multi-IP parsing.
2. Renderer (additive only): preview constants + `preview_reader_scope_token`;
   `_preview_inventory` (fail-closed validation equivalent to the heredoc);
   `_preview_reader_rule_lines` (marker + user any/pass/ips/read on the
   path pattern, canonical ips join); `_preview_render_texts` (legacy byte
   shape + marker line; catalog without the timestamp);
   `render_ubuntu_preview_relay` (two 0600 candidates via `write_candidate`,
   one RENDERED evidence line with both digests);
   `verify_preview_reader_auth_config` (exactly-one marker, subset
   semantics, read action, byte-exact comparison when the requested scope
   equals the full rule scope); `run_check_address` (reader-ip silent /
   private-rtsp host+port); three subparsers.
3. Preview shell: multi-IP arg parsing and forwarding mirror
   `camera-relay.sh`; renderer resolution + renderer-exists gate (exit 4);
   the heredoc becomes the `ubuntu-preview-relay` call; validators become
   `check-address` wrappers (same function names, same call sites, same
   exit-code discipline); unit heredoc and all existing evidence lines stay
   byte-untouched; ONE additive `READER_AUTH_SCOPE` evidence line.
4. cam1 shell: only the two validator bodies become `check-address`
   wrappers (`ubuntu-relay` render untouched → rendered config
   byte-identical).
5. Tests: new 34-test battery (golden bytes, parity minus drifts,
   idempotency, drift rejection, multi-IP, api-less, inventory fail-closed,
   check-address, shell forwarding pins); re-pin the gallery battery.

## Architecture

- The preview mode is a fresh full-file render (the preview config is fully
  renderer-owned), unlike the bounded read-edit-write cam1 modes; this is
  exactly the legacy heredoc's semantics, now inside the canonical module
  with the protected-inventory gate preserved in the shell (root-owned
  0600 regular non-symlink checks stay in the shell; the renderer
  re-checks regular-non-symlink and validates the payload).
- The preview marker reuses the canonical prefix grammar: (a) it
  span-terminates the PRECEDING rule in `_parse_rule_block` (no new parser
  semantics); (b) `AUTH_MARKER_PREFIX` marks the rule renderer-owned (never
  deletable by bounded sanitize); (c) exact-string lookup keeps cam1
  markers unaffected. Pattern rules are looked up by their exact marker
  string; the preview contour has its own verify verb (the cam1
  `verify-reader-auth` stays path-literal).
- `check-address` is a pure validation verb (no stdout for reader-ip; host
  + port lines for private-rtsp) so the shells keep their existing parse
  shapes and exit-code contracts; errors flow through the existing
  `ERROR: <msg>` stderr path with exit 1.
- Byte-identity proof obligations are split: the 7 legacy modes are proven
  by the fixed-input harness (empty diff base↔head); the preview mode by
  golden bytes + idempotency; the legacy parity by the minus-marker /
  minus-generated_at comparisons in the battery.

## Decisions

- D-1: Fresh full-file render (not a bounded edit) for the preview contour:
  that is the legacy heredoc's semantics (the candidates directory is
  renderer-owned end to end); parity-minus-marker is therefore exact.
- D-2: The marker text is
  `# Sea Speed least-privilege reader for canonical preview-contour (path-pattern ~^preview_[a-z0-9._-]+$)`
  — the pattern is IN the marker so a single rule documents its own scope;
  the prefix keeps sanitize auto-ownership and span-terminator semantics.
- D-3: The catalog drops `generated_at` (non-deterministic; no consumer
  reads it — verified in `api/app/main.py` and
  `configure-analytics-profiles.py`): the catalog digest becomes stable,
  which the digest-bound activation contract requires. Documented one-time
  drift.
- D-4: Multi-IP by day one (repeatable + comma-separated, mirroring
  camera-relay.sh): closes the #372 gap class for the preview contour;
  single-IP renders stay byte-identical to the legacy single-IP shape.
- D-5: `check-address` bounded to the two relay shells: it removes the two
  inline heredocs in THIS slice's scripts; the other ~15 copies stay
  (explicitly out of slice; nothing filed) to keep the change reviewable.
- D-6: Preview activate does NOT gain the #447 identity derivation in this
  slice (R8): the activate block stays byte-untouched; a negative pin
  asserts the absence.
- D-7: The preview scope token is preview-prefixed
  (`preview-single-rfc1918-peer`) rather than reusing the cam1 token: contour
  attribution in evidence, single-IP literal preserved.
- D-8: Inventory root-ownership/mode checks stay in the shell (the
  renderer checks regular-non-symlink + payload validity): the shell gate is
  the protected-input boundary, the renderer is the schema authority.

## Affected contours

- UBUNTU_WORKER (renderer CONTROL_PLANE + worker scripts):
  `scripts/operations/mediamtx_path_config.py`,
  `deploy/worker/ubuntu/camera-relay.sh` (validators only),
  `deploy/worker/ubuntu/camera-preview-relay.sh`, the new test battery, the
  re-pinned gallery battery, the docs runbook, this SDD trio (+ durable
  progress file outside the repo tree).
- No change to the 9 legacy renderer verbs, the renderer module's existing
  functions, prepare/sanitize/remediate flows, `deploy/vps/**`,
  `.github/**`, systemd units, api/, frontend/.

## Validation

- RED: the new battery fails 30/34 on base c2bd3b9 (exact names in the
  delivery transcript and tasks.md AC traceability) and passes 34/34 on the
  branch.
- Full suite on the head branch: green (exact counts in the verification
  transcript).
- Byte-identity: seven-mode fixed-input harness on base c2bd3b9
  (byte-id-base-442) and on the branch (byte-id-head-442); the 7 legacy
  modes must diff EMPTY; the 8th fixed-input preview case must match the
  committed golden bytes; preview idempotency and legacy-parity-minus-
  marker/generated_at recorded in the transcript.
- `bash -n` on both relay shells; ruff on the touched Python files;
  `python3 scripts/ci/validate_sdd.py --event <pr-event.json>` green
  (base c2bd3b9, head = branch tip).

## Runtime feedback

- RF-001: Operator actions expected: 1 bounded on-box preview-relay
  re-render transaction (byte-identical render for a conforming box modulo
  the documented drifts; digest-bound activate; road probe window);
  orchestrator records the runtime acceptance.
- RF-002: Evidence: prepare/activate evidence lines as listed in the spec;
  renderer RENDERED/VERIFIED lines; harness transcript.

## Risk profile

- Risk profile: REQUIRED
- Risk-profile rationale: derived from scripts/ci/validate_change_contract.py classify_file/derive_impact over the changed-file set — the renderer (CONTROL_PLANE) plus the two worker relay scripts classify UBUNTU_WORKER with a rendering behavior change, matching the Outcome Contract on issue #442. Security impact is declared LOW in the PR body (fail-closed direction: marked verifiable rule, single-sourced validation; no auth topology change).
- RISK-001 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the marker keeps the canonical prefix (sanitize auto-ownership + span-terminator semantics) and verify-preview-auth fails closed on missing/duplicated markers, wrong scopes, wrong actions and byte drift; fresh renders eliminate the unmarked rule class | Validation: drift rejection tests (missing marker / drifted ips / drifted action) + shared-rule-parser compatibility test + structural pins | Residual risk: LOW — an out-of-repo tool pinning the exact old unmarked block would see the added marker line (documented one-time drift) | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: the catalog drops the non-deterministic generated_at field (no repo consumer reads it — verified in api/app/main.py and configure-analytics-profiles.py); the catalog digest becomes stable, which the digest-bound activation contract requires; the drift is documented in the runbook | Validation: parity-minus-generated_at test + consumer grep evidence | Residual risk: LOW — an unknown out-of-repo consumer of generated_at would lose that field | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: test fixtures build dummy camera credentials at runtime via string concatenation (no literal credential shapes committed); inventories are fabricated per-test in TemporaryDirectory; no real hostnames, addresses beyond RFC1918 fixtures, or credential material in the tree | Validation: ruff clean + fixture review + grep for committed credential shapes | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: frozen road-worker contracts pinned byte-exact: the dedicated service name, the active-catalog path /var/lib/sea-speed-camera-preview/active/camera-preview-catalog.json, the catalog schema string sea_speed_camera_preview_catalog_v1, the preview_{camera_id} path naming, the catalog camera payload shape, the standalone-config top-level key set, and the global+per-path tcp transport shape; the activate flow and its evidence lines stay byte-untouched | Validation: golden-bytes render + structural evidence pins + 7-mode legacy harness empty diff | Residual risk: LOW — the catalog key order changes as part of the documented drift; the road worker reads camera_id/display_name/source only | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: SEC | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: the preview profile stays API-LESS — the new render path has no api/apiAddress emission (negative pin); the cam1 loopback-watchdog API in its own mode is untouched | Validation: assertNotIn pins on the rendered config + renderer structural pin + legacy harness | Residual risk: NONE | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: RISK-004 | Level: unit | Priority: P0 | Evidence: test_two_camera_render_matches_golden_bytes + test_canonical_config_minus_marker_equals_legacy_heredoc_output + test_canonical_catalog_matches_legacy_contract_minus_generated_at + test_re_render_with_same_inputs_is_byte_identical (golden bytes, parity minus documented drifts, idempotency)
- TEST-002 | Covers: RISK-001 | Level: unit | Priority: P0 | Evidence: test_verify_accepts_the_canonical_render + test_verify_is_subset_semantics_on_multi_ip_rule + test_verify_rejects_drifted_ips_fail_closed + test_verify_rejects_missing_marker + test_verify_rejects_drifted_action + test_preview_rule_verifies_through_the_shared_rule_parser
- TEST-003 | Covers: RISK-002 | Level: unit | Priority: P0 | Evidence: PreviewInventoryValidationTests (unsupported schema, empty list, duplicate id, unsafe id, public source, missing userinfo, overlong display name, non-RFC1918 reader IP — all fail closed with outputs absent)
- TEST-004 | Covers: RISK-005 | Level: unit | Priority: P0 | Evidence: test_preview_profile_stays_api_less (api/apiAddress absent, marker prefix owned) + PreviewRendererStructuralTests (renderer owns the literals; 9 legacy verbs untouched)
- TEST-005 | Covers: RISK-003 | Level: unit | Priority: P0 | Evidence: CheckAddressCliTests (valid/invalid reader-ip and private-rtsp, stdout discipline, both shells single-source through check-address) + PreviewShellContractTests (thin CLI, renderer resolution, multi-IP parse/forwarding, inventory gates, scope evidence, no #447 derive, cam1 validators moved)
- TEST-006 | Covers: RISK-002 | Level: integration | Priority: P0 | Evidence: seven-mode byte-identity harness (base c2bd3b9 vs head, empty diff) + 8th fixed-input preview golden + idempotency + full pytest suite green

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: canonical issue #442 Outcome Contract; allowed paths (renderer, two worker shells, two test batteries, docs runbook, SDD trio, progress file) enforced before first write; GH007 author identity verified before commit
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: prepare writes only protected 0600 candidates under the state root; inventory validation is fail-closed before any candidate write; the digest/mode gates are unchanged
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: previous candidates/active files preserved; backups retained at the printed paths | Retry: NO | Rollback: the unchanged activate flow retains root-only backups for an explicit rollback decision; automatic rollback is not authorized | Evidence: unchanged preview activate backup/install/restart sequence (byte-untouched this slice)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: unchanged digest gates (config/unit/catalog), executable+user+group checks, restart + is-active + private-listener probe; NEW repo-tooling verification via verify-preview-auth on the live config (D2 closure)
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: no new durable state; the renderer writes only the two candidates it already wrote (now through the canonical module, 0600 atomic)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: none beyond existing temporaries | Retry: NO | Rollback: NONE | Evidence: renderer temp files are cleaned in write_candidate's finally block; failed renders leave no candidates (the legacy heredoc could leave partial files — the renderer is strictly cleaner)
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: prepare evidence lines byte-unchanged + new READER_AUTH_SCOPE; renderer RENDERED line carries both digests + scope + api=none; VERIFIED line for the D2 check
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: preview rollback rides the unchanged root-only timestamped backups (explicit operator decision); automatic rollback is not authorized (unchanged) | Evidence: unchanged activate fault paths (exit 30/31/32/33 with backup evidence)
