# Plan — 685 shared operator CSS extraction

- Specification: specs/685-shared-operator-css/spec.md
- Issue: #685
- Base SHA (ordered): `eba2604dbbc5bf22546d948d118b5e6abb0141ff`
- Actual worktree HEAD: `e4c5bf2a1b6ec2c66975f76e572c41a9ca75a634` on `agent/wave7-688-685`
- Risk profile: REQUIRED

> Base-SHA note: the ordered `base_sha` `eba2604dbbc5bf22546d948d118b5e6abb0141ff`
> does not exist in the local clone (`git rev-parse` reports "no such commit").
> The checked-out branch `agent/wave7-688-685` sits at `e4c5bf2a1b6ec2c66975f76e572c41a9ca75a634`
> ("fix(#688): pin hls.js 1.7.4 with byte-verified SRI"), whose file:line content
> matches the architect's spot-checks for `index.html:10-17` and
> `road/index.html:10-13`. Implementation proceeded against that tree; the SHA
> mismatch is recorded for the orchestrator rather than silently ignored.

## Architecture

Two operator HTML pages share a byte-identical ordered prefix of base CSS. The
prefix is hoisted into one static asset served from the operator web root; both
pages link it with the absolute `/sea-speed/operator-common.css` (required
because Water is aliased at `/sea-speed/water/` and Road lives under
`/sea-speed/road/`). Domain-specific rules remain inline in each page.

Prefix boundary (inclusive of the base `.objects-link` rule):

- Shared (moved to `operator-common.css`): `:root` tokens, `*`/`html`/`body`
  reset, button/input/summary base + focus, `h1,h2,h3,p`, the shared
  `.operator-header/.operator-shell/.operator-footer` width rule, `.operator-header`,
  `.project-home`, `.brand-inline`, `.header-links`, and base `.objects-link`.
  Serialized as 22 ordered rules (2366 bytes).
- Not shared (left inline): `.objects-link:hover,…` (Road adds `.objects-link.active`),
  `.status-strip` and the rest of the shell, camera/canvas stacking,
  `#waterMainVideo`/`#roadMainVideo`, the 700px (Water) vs 760px (Road)
  breakpoints, fullscreen controls, and every domain rule.

Asset delivery: `operator-common.css` ships in the exact VPS artifact (both
quality inventories) and is installed by `deploy/vps/deploy.sh` alongside the
HTML pages.

## Decisions

- D1 — Extract by rule, not by line. Road packs several rules onto one source
  line, with base `.objects-link` immediately followed by
  `.objects-link:hover,…,.objects-link.active`. The cut is made at the
  `.objects-link:hover` token so `.objects-link.active` stays inline.
- D2 — Use the Water serialization as the canonical asset text; the two prefixes
  are equal after whitespace normalization (identical SHA-256 of the
  whitespace-stripped rule text), so either serialization proves equivalence.
- D3 — Absolute stylesheet URL. Relative links would break the `/sea-speed/water/`
  alias and the nested Road path.
- D4 — Deploy the asset as a first-class release member rather than deriving it
  at runtime: inventories, release completeness, bootstrap capture and
  `verify_frontends` all understand it.
- D5 — Activation ordering is transactional: upgrade installs CSS before the
  HTML that links it; downgrade restores the HTML before removing CSS. This
  makes a live page never reference an absent asset at any instant.
- D6 — Tolerate the pre-feature rollback release. The #688 release predates this
  asset and carries neither the file nor an `.absent` marker. Instead of a
  mandatory marker check (which would break the first rollback), the script
  derives `css_state=prefeature` and accepts it only when the release HTML does
  not reference `operator-common.css`; a referencing-but-missing candidate fails
  closed.

## Affected contours

- `frontend/sea-speed/operator-common.css` (new) — the shared prefix.
- `frontend/sea-speed/index.html` — link + prefix removal (Water).
- `frontend/sea-speed/road/index.html` — link + prefix removal (Road), keeping
  `.objects-link.active` inline.
- `scripts/quality/build_exact_artifacts.py` — VPS required inventory.
- `scripts/quality/validate_exact_artifacts.py` — VPS required inventory.
- `deploy/vps/deploy.sh` — target/URL vars, release completeness, download loop,
  install-to-release, bootstrap capture, `ensure_current_release_has_operator_css`,
  `css_state` guard + ordering, `verify_frontends` check.
- Out of scope: `tests/**` (owned by the test worker), `api/**`, `worker/**`,
  `.github/**`, Cameras/Objects pages, lockfiles.

## Validation

- Ordered whole-rule equivalence reconstructed per page and compared to the
  pre-extraction page (brace-depth split; internal whitespace preserved):
  Water 129 = 22 + 107, Road 130 = 22 + 108, both True.
- `bash -n deploy/vps/deploy.sh` → OK.
- `python3 -m py_compile scripts/quality/build_exact_artifacts.py scripts/quality/validate_exact_artifacts.py` → OK.
- Inventories: CSS present in both VPS required sets; validate's VPS set remains
  a subset of build's (pre-existing shape preserved).
- `python3 scripts/ci/validate_sdd.py` → green (this SDD).
- Visual parity (AC-008) is PENDING the UI worker; no screenshots fabricated.

## Runtime feedback

- Static gates are green as listed under Validation.
- Rendered layout parity is deferred to the UI worker (V-1..V-3 matrix).
- Live VPS upgrade/rollback is deferred to the deploy stage; the pre-feature
  rollback path is statically guarded, not yet exercised on a live host.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: ordered whole-rule equivalence proof plus the UI worker visual matrix on both pages | Validation: equivalence script output (True for both pages) and UI-worker screenshots | Residual risk: browser-specific default differences not observable in source comparison | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: pre-feature rollback acceptance rule (neither file accepted only when HTML does not reference CSS) and CSS-before-HTML activation ordering | Validation: static review of deploy/vps/deploy.sh plus bash -n | Residual risk: first live rollback path not yet exercised against a real release | Owner: delivery-orchestrator | Status: ACCEPTED

## Test design

Tests live under `tests/**` and are owned by a separate test worker; this plan
records the design only.

- TEST-001 | Covers: AC-001,AC-003 | Level: integration | Priority: P0 | Evidence: ordered whole-rule reconstruction equals pre-extraction page for both pages
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: both pages link the absolute URL and residual inline begins at .objects-link:hover
- TEST-003 | Covers: AC-004 | Level: integration | Priority: P1 | Evidence: CSS present in both VPS inventories and validate set is a subset of build set
- TEST-004 | Covers: AC-005,AC-006 | Level: integration | Priority: P1 | Evidence: deploy.sh static assertions plus bash -n; pre-feature and referencing-missing branches covered by test worker
- TEST-005 | Covers: AC-008 | Level: runtime-manual | Priority: P1 | Evidence: UI worker baseline screenshot matrix V-1..V-3

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

`deploy/vps/deploy.sh` is in the diff, so the deployment is audited as a
transaction. Stages run in the order below; the rollback stage is entered from
any fatal stage during a real deployment.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no live change; inputs rejected before mutation | Retry: re-run after correcting the SHA or archive | Rollback: none required | Evidence: validate_sha/validate_auth_boundary_inputs/validate_runtime_access/ensure_layout/download_release logs and archive sha256
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: live source untouched; boundary probe verdict logged | Retry: re-run after boundary recovery | Rollback: none required | Evidence: verify_private_m2m_boundary degraded probe and recover_auth_boundary_before_source_mutation output
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: only staged .next files when failure precedes activation; a mid-activation failure hands control to the rollback stage | Retry: none automatic; operator re-runs after fix | Rollback: install_release of the previous release restores HTML before CSS removal | Evidence: bootstrap capture, ensure_current_release_has_operator_css, install_release staging/activation ordering
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: live source is the target release; service restarted | Retry: none automatic | Rollback: install_release of the previous release then restart_and_verify | Evidence: migrate_legacy_roi_to_normalized, restart_and_verify, run_auth_boundary, verify_frontends CSS check
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: release pointers not advanced past the failing write | Retry: re-run after correcting state | Rollback: install_release of the previous release | Evidence: PREVIOUS_FILE and CURRENT_FILE writes
- TX-006 | Stage: HOUSEKEEPING | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: stale release directories remain on disk; deployment still succeeds | Retry: next deployment prunes again | Rollback: none required | Evidence: prune_releases warning lines
- TX-007 | Stage: EVIDENCE | Mutation: YES | Failure disposition: FATAL | State after failure: deployment manifest may be absent for the attempt | Retry: re-run writes the manifest | Rollback: manifest with rolled_back state on failure path | Evidence: write_deployment_manifest JSON plus exact-artifact quality evidence
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if rollback verification fails the script exits non-zero with the old release live | Retry: operator re-runs after remediation | Rollback: this stage is the rollback; no further nested rollback | Evidence: install_release old_current, restart_and_verify, manifest state rolled_back
