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

| # | Risk | Severity | Likelihood | Mitigation |
|---|------|----------|------------|------------|
| RISK-001 | Canonicalization diverges between write and verify (a second normalization sneaks in) | HIGH | LOW | Structural pin: exactly one definition, exactly two injections feeding both blocks; no `.lower()` in the verify block |
| RISK-002 | Injection pattern lets a caller's env value win (tampered canonicalization) | HIGH | VERY LOW | Unconditional assignment+export in the script; reviewer-verified; fail-closed KeyError if absent |
| RISK-003 | Verify becomes too tolerant (missing packages pass) | HIGH | VERY LOW | Negative control test (empty installed map still fails+rebuilds); version compare unchanged |
| RISK-004 | Duplicate canonical keys in `installed_canonical` change semantics | MEDIUM | VERY LOW | Pip-managed venvs cannot hold two dists with one canonical name; pre-fix manifests only carry one spelling; last-wins is deterministic and fails safe on version conflict |
| RISK-005 | Lock input with non-canonical spelling diverges from requirements | MEDIUM | LOW | `validate_runtime_lock` unchanged → fails closed (exit 3) before any mutation; committed inputs verified canonical |
| RISK-006 | Manifest key spelling change breaks an unseen consumer | MEDIUM | VERY LOW | Repo-wide grep: only prepare-runtime.sh and the test read installed_packages; read-time tolerance covers old keys |
| RISK-007 | Test environment lacks a non-canonical metadata-Name dist | LOW | LOW | Prefers typing_extensions (near-universal); clear RuntimeError otherwise, not a silent skip |
| RISK-008 | On-box behavior differs from harness (0444 reuse across real deploys) | LOW | LOW | Harness executes the real script; runtime acceptance rides the next two deploy observations (issue #514 closure bar: two clean deploys) |

Test design: TEST-001 structural pin (RED on base); TEST-002 executed verify-with-manifest on a metadata-Name-keyed manifest (RED on base, exact incident signature); TEST-003 negative control (independent of fix); TEST-004 re-bake + re-verify recurrence closure (RED on base).

## Correct-course check

- C-1: If a pre-fix manifest key canonicalizes to a name absent from the lock → still fails (tolerance is spelling-only). Verified by TEST-003.
- C-2: If the deploy still logs VERIFY_FAILED after merge → read-time tolerance failed on-box; rollback target is the previous worker release; issue #514 stays open with the run logs.
- C-3: The 3/3 recurrence is closed only by evidence: two consecutive deploys with NO RUNTIME_VERIFY_FAILED+RUNTIME_REBUILT pair — the issue stays open until then (orchestrator-owned).

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
