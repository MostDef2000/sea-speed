# 396 — D-6: exact-artifact convergence is bidirectional

- Issue: #396
- Specification: specs/396-d6-artifact-convergence/spec.md

## Product outcome

#396 waves 1-6 each had to hand-sync two mirrors of the same api/app module
set: the vps required list in `scripts/quality/build_exact_artifacts.py` and
the deploy mirror sites in `deploy/vps/deploy.sh` (seven sites per module, see
the wave-6 plan D-3). The exact-artifact validator
(`scripts/quality/validate_exact_artifacts.py`) checked only the
artifact-inventory side (build list ⊆ manifest files): single-sided drift in
either direction passed validation and surfaced at deploy time (`release_complete`
failure) or not at all. Outcome: the exact-artifact validator now fails closed
when EITHER side drifts — a build-list module without a deploy.sh TARGET mirror,
or a deploy.sh TARGET module missing from the build required list — so the
asymmetry the #396 waves repeatedly hit is closed at CI time, before any deploy.

## User scenarios

- Scenario 1: a contributor adds a new api/app module to the build vps required
  list but forgets the deploy.sh TARGET mirror — `python
  scripts/quality/validate_exact_artifacts.py` exits non-zero naming the
  unmirrored module, in every workflow that validates exact artifacts
  (quality-integration, deploy-vps, deploy-ubuntu-worker).
- Scenario 2: a contributor adds a `<NAME>_TARGET` module mirror to deploy.sh
  but forgets the build vps required list — the same validator exits non-zero
  naming the module missing from the required list.
- Scenario 3: the converged repository (today's state, 10 modules) validates
  exactly as before — identical artifacts, identical digests, zero byte drift.

## Requirements

- R1: `deploy_app_module_targets(deploy_sh_text)` parses deploy.sh
  `<NAME>_TARGET` variable definitions in both established idioms — the
  env-default idiom (`"...app/<m>.py"`, as `API_TARGET`) and the dirname idiom
  (`$(dirname "$API_TARGET")/<m>.py`) — and returns the mirrored api/app module
  set; non-python targets (frontend html/js) carry no `.py` path and are ignored.
- R2: `validate_vps_module_convergence(required_modules, deploy_sh_text)` fails
  closed (SystemExit naming the offending paths) when a build-list api/app
  module has no TARGET mirror (direction A).
- R3: the same function fails closed when a deploy.sh TARGET api/app module is
  missing from the build vps required list (direction B).
- R4: the check is wired into `validate_exact_artifacts.py main()` immediately
  after the manifest schema check, so every existing CI invocation of the
  validator enforces the invariant; the required-module side is read from
  `COMPONENT_FILES["vps"]["required"]` (single source of truth, no duplication).
- R5: invariant scope is the api/app module set only — deploy plumbing
  (deploy.sh, cutover, helper, nginx scripts) is intentionally not TARGET-mirrored;
  no deploy.sh change, no api/** change, route table untouched.

## Acceptance criteria

- AC-001: on the converged repository the parser returns exactly the 10
  api/app modules (main, store, config, identity, objects_registry,
  passage_mirrors, water_passages, camera_preview, analytics, live_feeds) and
  no frontend targets.
- AC-002: direction A fixture — a ghost module added to the required set
  against real deploy.sh text — raises SystemExit "not mirrored" naming the
  module.
- AC-003: direction B fixture — a `GHOST_TARGET` dirname-idiom line added to a
  copy of real deploy.sh text — raises SystemExit "missing from vps required
  list" naming the module.
- AC-004: RED-first evidence recorded — both drift scenarios observed exiting 0
  against the base validator (b9309dc), and exiting 1 with fail-closed messages
  after the fix (end-to-end, in a disposable sandbox copy).
- AC-005: battery delta is exactly the new tests (915 OK, skipped=4; baseline
  910/4), validate_repo, validate_sdd, ruff (0.16.10, CI config) and
  `bash -n deploy/vps/deploy.sh` all green.

## Runtime feedback

CI-tooling only: the change alters what CI validates, not what runs on any
contour. No runtime acceptance probes are required; the PR Change Contract
declares VPS deployment NOT REQUIRED.

## NFR assessment

- NFR-001 | Area: Reliability | Target: single-sided build-list/deploy.sh mirror drift fails the exact-artifact validator in CI before any deploy | Validation: direction A/B fail-closed unit tests plus sandbox end-to-end drift scenarios (exit 1 both directions) | Evidence: tests/quality/test_exact_artifact_convergence.py 5/5 OK; sandbox scenarios A and B exit 1 | Status: PASS
- NFR-002 | Area: Compatibility | Target: converged repository validates with zero artifact-byte change and zero new required inventory | Validation: end-to-end build+validate on the real repo; full battery delta exactly +5 | Evidence: Ran 915 OK (skipped=4); deterministic artifacts unchanged | Status: PASS
- NFR-003 | Area: Maintainability | Target: future #396-family module waves no longer need a manual two-sided sync audit; the validator pins the equality | Validation: real-repo equality test pins exactly 10 modules on both sides | Evidence: test_real_repo_converges_in_both_directions OK | Status: PASS
