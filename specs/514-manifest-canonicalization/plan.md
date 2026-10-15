# Plan: #514 runtime manifest canonicalization (write+verify)

- Issue: #514
- Specification: specs/514-manifest-canonicalization/spec.md

## Implementation approach

Single-commit fix, exactly two files. prepare-runtime.sh gains ONE shared PEP 503 canonicalization defined once as a shell-exported python snippet (`SEA_SPEED_PYPI_CANON_SRC`) and exec-injected into both embedded python blocks. Verify side: build `installed_canonical` from the manifest keys at READ time (tolerance — 0444 manifests are immutable on target boxes) and look up canonical lock-pin names. Write side: bake keys via `_pypi_canon(dist.metadata Name)`. Test side: harness-driven executed tests through the documented `SEA_SPEED_426_PREPARE_RUNTIME_PATH` override — RED on base with the exact incident signature, GREEN on the fix; negative control independent of the fix; recurrence loop closed by asserting the re-baked manifest re-verifies.

## Architecture

The canonicalization lives in exactly one place (the shell-level snippet) and is consumed by both python blocks through the environment. Rationale: the script composes two heredoc python programs; a shared shell-level source keeps the definition single-sourced and structurally pinnable. The injection is unconditional (script overrides caller env) and fails closed (KeyError → non-zero exit → quarantine path) if ever removed. No new files, no new processes, no changes to the pip install path, no schema change beyond manifest key spelling (the only readers are the script itself and the test).

## Decisions

- D-1: Shared `_pypi_canon` (PEP 503: lowercase, `[-_.]+` → `-`) as the ONE normalization for manifest keys on both write and verify paths. Alternative rejected: normalizing only at verify (would leave new manifests non-canonical and the write/verify asymmetry alive for the next consumer).
- D-2: Verifier-side read-time canonicalization is the load-bearing half — target-box manifests are chmod 0444 immutable and cannot be rewritten in place; without read tolerance every pre-fix box rebuilds forever.
- D-3: Injection via `exec(os.environ[...])` with an unconditional shell assignment+export — script-owned bytes; caller-supplied env values cannot win; missing var fails closed.
- D-4: Deliberate non-change in `validate_runtime_lock` (keeps `.lower()`) — the committed lock inputs are all PEP 503 canonical (57 names enumerated), so behavior is identical; a future non-canonical lock spelling fails closed at validation instead of being healed.
- D-5: Negative control uses an EMPTY installed map — fails identically with or without the fix, proving the change adds tolerance only for spelling, never for absence.
- D-6: The 4-test delta rides in the existing rebuild harness suite (13 pre-existing tests untouched); RED authenticity re-observed by the orchestrator against the base script copy, not taken from worker prose.
- D-7: Byte-identity of the write path's non-key fields preserved (version source, sha256 hashes, sorted JSON formatting) — the manifest stays otherwise byte-identical to pre-fix output for canonical-key inputs.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: ONE canonicalization definition structurally pinned (exactly one `def _pypi_canon(`, exactly two exec-injections feeding both blocks, no `.lower()` in the verify block) — a divergent second normalization fails the pin in CI | Validation: test_manifest_names_share_one_pypi_canonicalization (RED on base) | Residual risk: a future edit could rewrite the pin — mitigated by the structural test failing loudly | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: SEC | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: the injected canonicalization source is script-owned — unconditional shell assignment+export overwrites any caller-supplied value; shell-single-quoted (no expansion hazards); missing var fails closed (KeyError → non-zero exit → quarantine path) | Validation: reviewer analysis of the injection pattern; negative-control test keeps absence detectable | Residual risk: none identified beyond the fail-closed path | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: verify tolerance is spelling-only — the negative control (empty installed map) fails identically with or without the fix; version compare unchanged | Validation: test_issue_514_genuinely_missing_manifest_package_still_fails | Residual risk: none — absence still yields graph drift + rebuild | Owner: delivery orchestrator | Status: MITIGATED
- RISK-004 | Category: DATA | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: duplicate canonical keys cannot occur in a pip-managed venv (one dist per canonical name) and pre-fix manifests carry one spelling per name; the last-wins map is deterministic and fails safe on version conflict (verify fails → rebuild) | Validation: reviewer analysis; write path already used the same last-wins pattern pre-fix | Residual risk: pathological hand-crafted duplicate distinfo — fails closed | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-005 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: validate_runtime_lock keeps `.lower()` deliberately — committed lock inputs are all PEP 503 canonical (57 names enumerated); a future non-canonical lock spelling fails closed at validation (exit 3) before any mutation | Validation: reviewer enumeration of lock/requirements/runtime-lock.json names | Residual risk: future lock regeneration with non-canonical names is rejected, not healed — acceptable fail-closed behavior | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-006 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: repo-wide grep shows prepare-runtime.sh and the test are the ONLY readers of installed_packages; read-time tolerance covers old underscore keys, so no consumer breaks | Validation: reviewer grep; gate/validators green | Residual risk: an out-of-repo consumer would be unknown — none is deployed | Owner: delivery orchestrator | Status: MITIGATED
- RISK-007 | Category: OPS | Probability: 2 | Impact: 1 | Score: 2 | Mitigation: the executed tests prefer typing_extensions (near-universal) and fall back to any non-canonical metadata Name; a truly bare interpreter raises a clear RuntimeError instead of silently skipping | Validation: focused rebuild module 17 passed in the CI-like sandbox env | Residual risk: exotic CI envs without typing_extensions error visibly — remediable by fixture generation if ever observed | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-008 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: on-box behavior (0444 manifest reuse across real deploys) is covered by harness inference executing the real script; the issue closure bar demands TWO consecutive clean deploy observations before #514 closes | Validation: deploy run logs (RUNTIME_* lines) on the merge SHA + the next deploy, recorded on #514 | Residual risk: a box-specific deviation would reopen #514 with run logs as evidence; rollback target is the previous worker release | Owner: delivery orchestrator | Status: OPEN

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P1 | Evidence: test_manifest_names_share_one_pypi_canonicalization — structural pin (one definition, two injections, exact write-side key expression, exact read-time map, no .lower() in the verify block); RED on base (3 failed / 14 passed, orchestrator re-observed)
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: test_issue_514_metadata_name_manifest_key_verifies_without_rebuild — executes the REAL script through the harness (PATH-stubbed venv python); metadata-Name-keyed manifest verifies WITHOUT rebuild; RED on base with the exact incident signature (RUNTIME_VERIFY_FAILED check=manifest_python, actual=None, RUNTIME_QUARANTINED)
- TEST-003 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: test_issue_514_genuinely_missing_manifest_package_still_fails — empty installed map fails identically with or without the fix (graph drift actual=None → quarantine → rebuild); negative control independent of the fix
- TEST-004 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: test_issue_514_rebaked_manifest_keys_are_canonical_and_reverify — first run RUNTIME_CREATED with canonical keys; second run RUNTIME_REUSED with no verify failure (closes the 3/3 recurrence loop); RED on base
- TEST-005 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: full battery 1035 passed / 4 skipped; focused rebuild module 17 passed, 4 subtests; sibling prepare-runtime suites 32 passed; bash -n OK; validate_repo (736 files) green; validate_sdd green; gate compatible=True; ruff zero new findings

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: the deploy observations on #514 are the recorded runtime acceptance path; no course correction is active at merge time

## Affected contours

- Ubuntu Worker/relay: `deploy/worker/ubuntu/prepare-runtime.sh` (verify+write paths) — the runtime manifest gate spelling contract; ships via the exact artifacts; runtime verification lands with the next two routine worker deploys (issue #514 acceptance bar).
- Tests: `tests/test_ubuntu_worker_runtime_rebuild.py` (+4 tests; 13 pre-existing untouched).

## Validation

- V-1: RED-vs-base contrast — the 4-test delta run against base `prepare-runtime.sh` via `SEA_SPEED_426_PREPARE_RUNTIME_PATH`: 3 failed / 14 passed with the exact production incident signature; negative control and all pre-existing tests pass on base. Re-observed by the orchestrator.
- V-2: GREEN — full battery `1035 passed, 4 skipped`; focused rebuild module `17 passed, 4 subtests`; sibling prepare-runtime suites `32 passed`; `bash -n` OK; validate_repo (736 files) green; validate_sdd green; gate `compatible=True`; ruff zero new findings (3 pre-existing on base).

## Runtime feedback

- RF-001: Operator actions expected: 0; the fix rides the autonomous Ubuntu-worker deploy on the merge SHA (DEPLOY-TRIGGER, полоса A); #514 closes only after two consecutive deploy observations show no RUNTIME_VERIFY_FAILED+RUNTIME_REBUILT pair — evidence recorded on the issue.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: work order for #514 (manifest canonicalization, verifier-side tolerance rationale); branch sdd/514-manifest-canonicalization from origin/main b337549; the DEPLOYABLE deploy script changes (runtime manifest write/verify path)
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: the install-time lock validation is unchanged and still fails closed (exit 3) on non-canonical lock inputs before any mutation; production safety envelope REQUIRED and covered: no secrets introduced, no public exposure change, the verify strictness for missing/mismatched packages is preserved (negative control)
- TX-003 | Stage: MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: staged release discarded; currently-running worker services unchanged | Retry: NO | Rollback: installer staging-then-restart pattern unchanged; the fix changes only which manifest keys are baked/accepted, not the mutation flow | Evidence: prepare-runtime.sh diff is canonicalization-only (reviewer hunk-by-hunk)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: the deploy health gate (verify-runtime-progression/check-worker-health) applies unchanged; expected post-fix signature: NO RUNTIME_VERIFY_FAILED+RUNTIME_REBUILT pair, or a pre-fix manifest verifying via read-time tolerance (RUNTIME_REUSED)
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: the worker's output/state contour is untouched; the manifest key spelling change is read-tolerated by the same fix
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: installer staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: deploy run logs (RUNTIME_* lines) for the merge SHA and the following deploy recorded on #514 at closure; repo-level evidence is the battery + RED/GREEN contrast + validator transcripts
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour UNCHANGED: it targets PREVIOUS complete releases which are self-consistent by construction (a rolled-back tree carries its own pre-fix script and manifests match its own writer) | Evidence: deploy/worker/ubuntu/rollback-exact.sh untouched in this diff
