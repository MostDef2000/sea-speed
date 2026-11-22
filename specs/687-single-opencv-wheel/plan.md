# Plan: Single OpenCV distribution in the Ubuntu worker runtime

- Spec: specs/687-single-opencv-wheel/spec.md
- Issue: #687

## Architecture
`deploy/worker/ubuntu/requirements-runtime.txt` is the direct manifest (7 pins before this change: ultralytics,
lap, two OpenCV distributions, numpy, requests, python-dotenv; torch/torchvision are installed separately from
the CUDA index). `deploy/worker/ubuntu/requirements-runtime.lock.txt` is the resolved hash-pinned graph the
Ubuntu worker installs, and `deploy/worker/ubuntu/runtime-lock.json` is its schema-2 companion.
`prepare-runtime.sh` validates the pair before any mutation: the lockfile must start with
`# sea-speed-runtime-lock-v1`, carry a sha256 hash on every requirement line and contain every manifest pin at
the exact declared version; `resolved_lock.sha256` must equal the SHA-256 of the lockfile bytes; each
`pytorch.artifact_sha256` digest must appear among that package's hash lines. The runtime then installs in two
phases — `pip download --require-hashes --only-binary=:all:` into a wheelhouse, then
`pip install --no-index --find-links` from the verified set — into `runtimes/<runtime-id>`, where the id is
`sha256(runtime-lock.json bytes + NUL + requirements-runtime.txt bytes + NUL + lockfile bytes)`.

The change deletes one distribution from the manifest and regenerates the lock around the deletion, then updates
the digest. The pair remains a matching pair, and the runtime id necessarily moves — the intended signal for the
deploy transaction to prepare a new immutable runtime. Because the retained wheel is the same version
(`5.0.0.93`) as the removed one, no code path changes; only the set of installed distributions changes.

Resolution mechanics used (mirroring `.github/workflows/resolve-runtime-lock.yml:39-85` and the #716 precedent):
an input file containing `-r deploy/worker/ubuntu/requirements-runtime.txt` plus the two sorted cu130 pins from
`runtime-lock.json`, compiled with `uv pip compile --generate-hashes --index-url
https://download.pytorch.org/whl/cu130 --extra-index-url https://pypi.org/simple --index-strategy
unsafe-best-match --python-version 3.14`, against a temporary constraints file pinning every surviving package to
its current version. A deletion needs no `--upgrade-package` target.

## Decisions
- Keep `opencv-python`, remove `opencv-python-headless`: the resolved lock attributes `opencv-python` to the direct
  manifest **and** to `ultralytics`, while `opencv-python-headless` is attributed to the direct manifest only.
  `ultralytics` requires a distribution literally named `opencv-python`; a headless-named distribution cannot
  satisfy that requirement, so keeping only headless would still leave the ultralytics requirement unsatisfied.
  Both pins are `5.0.0.93`, so the retained wheel carries the API the worker already uses.
- No HighGUI dependency is created: `worker/worker_render.py` uses only in-memory operations
  (`cv2.cvtColor`, `cv2.Laplacian`, `cv2.rectangle`, `cv2.getTextSize`, `cv2.addWeighted`, `cv2.putText`,
  `cv2.imwrite` with `IMWRITE_JPEG_QUALITY`), and a `grep` over `worker/` finds no `imshow`, `namedWindow`,
  `waitKey`, `startWindowThread` or `VideoCapture`. Video arrives as FFmpeg raw frames. The GUI-capable wheel's
  extra linkage is never loaded by this code.
- Regenerate, do not hand-edit: `--require-hashes` installs demand every wheel's real digest; a hand-removed block
  would either leave hashes whose provenance the resolver never produced or hide an unintended resolution move.
- Pin all survivors in a temporary constraints file: the resolver cannot move a package that is constrained to its
  current version, which makes the diff unambiguous — anything beyond the headless block would be a red flag.
- Strip the temporary `-c` annotations and restore the canonical header: the committed file must reference only
  files that exist in the repository and keep the exact shape the resolver workflow emits. Peer review finding
  F1 showed the header was missing the workflow's index flags: line 3 now carries `--index-url
  https://download.pytorch.org/whl/cu130 --extra-index-url https://pypi.org/simple` (the literal the
  workflow's `$PYTORCH_INDEX_URL` resolves to from `runtime-lock.json.pytorch.index_url`), matching
  `.github/workflows/resolve-runtime-lock.yml:68-75`.
- Land the three files together: the digest is defined over the exact lockfile bytes, so manifest, lockfile and
  `runtime-lock.json` must never be reviewed or merged separately.
- Use local `uv 0.9.26` although the workflow pins `uv==0.9.8`, and disclose it: CI audits the committed lockfile,
  it does not re-resolve. Two control resolutions (unchanged manifest, all 57 pins constrained, one run under each
  uv version) reproduced the committed graph's versions and every hash exactly. The only difference is comment
  formatting: the committed file's two single-line `# via` comments (`certifi` via `requests`, `six` via `torch`)
  are historical artifacts of the #392 lock — `git blame` dates both lines to commit `1f81c5e` — and neither uv
  version emits that form, so the regenerated file expands exactly those two. Cosmetic, disclosed, no waiver.
- Base-SHA note: the work order named base `e2ef5562667bedc50f1bd26da41116c32262c35d`, which does not exist in
  this repository (`git cat-file -t` fails). The branch head at admission was
  `39ff43644c54a1dd92558b0eefa37808c9cb5329` (merge of `origin/main` `6fa1a5b` into
  `agent/wave6-703-702-687`), and the working tree content matched the order's stated premise. The discrepancy is
  recorded here and in tasks.md rather than silently ignored.

## Affected contours
- Repository: `deploy/worker/ubuntu/requirements-runtime.txt` (one line removed),
  `deploy/worker/ubuntu/requirements-runtime.lock.txt` (headless block removed, nine hashes removed, one `# via`
  reference removed, two cosmetic `# via` expansions, canonical header with the workflow's index flags and the
  marker restored), `deploy/worker/ubuntu/runtime-lock.json` (`resolved_lock.sha256` only), plus this SDD trio.
- VPS: NONE — no VPS file, package or runtime participates.
- Ubuntu worker/relay: the worker installs the new graph on the next Ubuntu worker deploy; `prepare-runtime.sh`,
  `update-exact.sh`, `install-manual.sh`, `deploy-authorized.sh`, `rollback-exact.sh` and every unit template are
  unchanged, so the existing deploy and rollback transactions apply.
- Windows worker/AI: NONE.
- Public interfaces: NONE — no API, URL, form field or operator flow changes; the observable internal difference
  is the worker runtime id (a 64-hex value) and one fewer installed distribution inside it.
- Explicitly unchanged: torch/torchvision pins and their artifact digests, every other surviving pin's version and
  hash lines, `api/requirements-api.txt`, the API lockfile, all deploy scripts, all workflows, all unit files.
- PR Change Contract fields required by this diff: `Production impact: UBUNTU_WORKER`,
  `VPS deployment: NOT REQUIRED`, `Ubuntu worker/relay update: REQUIRED`, `Production safety envelope: REQUIRED`,
  `VPS execution capability: NOT APPLICABLE`, `Ubuntu worker execution capability: CONNECTOR`,
  `Operator actions expected: 0`, plus `Risk profile: REQUIRED` and
  `Specification: specs/687-single-opencv-wheel/spec.md`.

## Validation
- Graph delta: a package-by-package parse of the previous and new lockfile (name+version → sorted sha256 set)
  reported 57 → 56 packages, `only old: opencv-python-headless 5.0.0.93`, `only new: (none)`, and no surviving
  hash-set change; 1120 → 1111 hash pins = the nine headless wheel hashes; `torch` and `torchvision` hash sets
  identical.
- Textual delta: 19 changed lines from the regeneration — the headless pin, its nine hash lines and its `# via`
  block, the `#   opencv-python-headless` entry in numpy's `# via` list, and the two disclosed `# via` expansions
  — plus peer-review finding F1's single header line (workflow index flags added; no pin or hash touched).
- Digest: `hashlib.sha256(lockfile bytes).hexdigest()` equals `resolved_lock.sha256`
  (`41d28eaa35caff2add5ac166ae1dbbca4553b77adf70198d944b455ca32e0517`; 98 225 bytes) → True. The digest moved
  from `93b7dbe2…a9d7` (98 132 bytes) to `41d28eaa…0517` solely because of the F1 header line.
- Schema: `python3 -c "import json; json.load(open('deploy/worker/ubuntu/runtime-lock.json'))"` → JSON loads,
  digest printed; `pytorch` and `verification_imports` inspected unchanged.
- Hash-lock module: `python3 -m unittest tests.test_ubuntu_worker_runtime_hash_lock -v` → Ran 24 tests, OK.
- Test worker landed: `tests/test_ubuntu_worker_manual_install.py` asserts `opencv-python==5.0.0.93` only,
  `tests/test_687_single_opencv_wheel.py` and `tests/support/opencv_lock_baseline_687.json` carry the literal
  oracles. Observed: RED on the pre-change tree 6 failed / 7 passed; after the landing 1646 passed, 2 skipped,
  858 subtests; hash-lock module 24 OK.
- Post-F1 full suite: `python3 -m pytest tests/ -q` → `1 failed, 1645 passed, 2 skipped, 858 subtests passed`
  in 152.37s. The single failure is
  `tests/test_687_single_opencv_wheel.py::DigestBindingTests::test_resolved_lock_sha256_binds_the_lockfile_bytes`
  at `tests/test_687_single_opencv_wheel.py:241` — it compares the recomputed digest against its literal
  `LOCK_SHA256 = "93b7dbe2…a9d7"` from before F1. tests/** is outside this change's write scope; the failure is
  reported verbatim and requires a one-line re-pin by the test worker. No waiver.
- Not run here (orchestrator duty): repository quality gates beyond `validate_sdd.py`, ruff, exact-head CI,
  PR Change Contract, deploy.

## Runtime feedback
- The evidence that settled the wheel choice came from the lock's own `# via` attribution: ultralytics names
  `opencv-python`, and no headless wheel can satisfy that name. That is checkable from the repository, so the
  decision did not depend on external recall.
- The deletion-only regeneration was the cleanest possible controlled change: with every survivor constrained,
  the resolver had no legal move other than dropping the removed package, and the observed diff matched that
  exactly.
- Encountered mechanics worth remembering: `uv pip compile` resolves relative `-r` paths against the **input
  file's** directory, not the working directory, and the generated `# via` annotations embed the path spelling.
  Running from a scratch directory with a `deploy` symlink preserved the canonical
  `-r deploy/worker/ubuntu/requirements-runtime.txt` annotation without writing scratch files into the repo.
- The uv version difference is real but inert here; the two control runs are what make that claim evidence rather
  than assertion. The corollary is that any future resolution which changes a survivor's hash under 0.9.26 must
  be treated as drift and stopped, not normalized away.

- Peer-review finding F1 was a genuine parity defect: the workflow compiles with `--index-url "$PYTORCH_INDEX_URL"
  --extra-index-url "https://pypi.org/simple"`, and its `PYTORCH_INDEX_URL` is populated from
  `runtime-lock.json.pytorch.index_url` (`https://download.pytorch.org/whl/cu130`), so the canonical header must
  name both literal URLs. The header was corrected and the digest rebound; a re-resolve was not needed and no pin
  or hash moved.
- Consequence worth remembering: the digest is an exact-bytes binding, so a comment-only header fix is still a
  digest change. Any oracle that hard-codes the digest must be re-pinned after such a fix; here that is a
  one-line test constant owned by the test worker.

## Risk profile
- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: retaining the GUI-capable wheel keeps Qt/GTK linkage installed that the worker never loads, which is extra surface on a headless host — however the wheel is the same `5.0.0.93` release the worker already used, `worker/` contains no HighGUI call, and the deploy/rollback transactions are unchanged | Validation: `grep` over `worker/` for `imshow|namedWindow|waitKey|startWindowThread|VideoCapture` returns no call sites; the retained pin is version-identical; hash-lock module 24 tests OK | Residual risk: low — unused linkage is not executed, and the alternative (headless only) would leave the ultralytics requirement unsatisfied | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: the resolver used is uv 0.9.26 while the workflow pins 0.9.8, so a different resolution could in principle move survivors or hashes — both control runs (all 57 pinned, unchanged manifest, one per uv version) reproduced the committed versions and every hash exactly, and the real run moved only the removed package | Validation: parse comparison old vs new (57 → 56, no surviving hash-set change); control-run comparisons identical except `# via` formatting | Residual risk: low — any future re-resolution that moves a survivor must be treated as drift and stopped | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: a mismatched digest would block the deploy, and the landed test file hard-codes the pre-F1 digest, so one assertion is red until the test worker re-pins it — the digest is computed from the exact committed bytes, the three files land together, `prepare-runtime.sh` fails closed before any mutation, and the stale oracle is reported verbatim with its line | Validation: digest equality observed True (98 225 bytes); hash-lock module 24 tests OK; post-F1 full suite `1 failed, 1645 passed, 2 skipped, 858 subtests` with the single failure identified as `tests/test_687_single_opencv_wheel.py:241`'s literal digest constant | Residual risk: one red test assertion until the test-worker re-pin lands; recorded, never waived | Owner: delivery orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: the canonical header now mirrors the workflow command exactly, so a future resolver-workflow regeneration keeps a clean header diff; the change is comment-only and does not affect installation or resolution | Validation: line 3 compared with `.github/workflows/resolve-runtime-lock.yml:68-75`; no pin/hash line changed (graph parse unchanged: 56 packages, 1111 hash pins) | Residual risk: low — uv version formatting of the header could differ in a future run, but the flags and order now match the workflow | Owner: delivery orchestrator | Status: MITIGATED

## Test design
- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: `git diff` of `deploy/worker/ubuntu/requirements-runtime.txt` shows exactly the removed `opencv-python-headless==5.0.0.93` line with `opencv-python==5.0.0.93` retained; `tests/test_ubuntu_worker_runtime_hash_lock.py::StructuralPinsTests.test_committed_lock_carries_marker_and_full_hash_pinned_graph` iterates the manifest and asserts each pin is uniquely present, exact-version and hash-pinned (24 tests OK); `tests/test_687_single_opencv_wheel.py::ManifestOracleTests` asserts the single OpenCV pin (landed by the test worker)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: package-by-package parse comparison of the committed lock before/after: 57 → 56, only `opencv-python-headless 5.0.0.93` absent, no surviving hash-set change, 1120 → 1111 hash pins, torch/torchvision hash sets identical; the same module's `test_committed_lock_carries_marker_and_full_hash_pinned_graph` re-asserts the direct and CUDA pins
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: `hashlib.sha256(LOCK_FILE.read_bytes()).hexdigest() == lock["resolved_lock"]["sha256"]` observed True (98 225 bytes); `StructuralPinsTests.test_runtime_lock_json_schema_2_carries_provenance` recomputes both the digest and the CUDA artifact digests; `RuntimeIdAndLockTests.test_resolved_lock_sha256_mismatch_fails_closed` and `test_pytorch_artifact_sha256_drift_fails_closed` prove the fail-closed negatives; module run 24 tests OK. The landed `tests/test_687_single_opencv_wheel.py` digest binding computes the same equality dynamically and is red only on its stale literal constant
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `git status --short` and `git diff --stat` show exactly the three dependency files (5 insertions, 17 deletions) plus this SDD trio; no test, workflow, script, `worker/**` or `api/**` file is in the diff; no skip, xfail or waiver was added
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: the #687 suite is landed — RED on the pre-change tree 6 failed / 7 passed; after the landing `python3 -m pytest tests/ -q` reported 1646 passed, 2 skipped, 858 subtests, and the hash-lock module 24 tests OK. After peer-review finding F1 canonicalized the lock header, the same run reports `1 failed, 1645 passed, 2 skipped, 858 subtests passed`, the single failure being the test file's literal digest constant at `tests/test_687_single_opencv_wheel.py:241`; the one-line re-pin is owned by the test worker

## Deployment transaction audit
- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not admitted; production keeps the duplicate-OpenCV runtime graph and nothing is deployable | Retry: correct the Change Contract or the SDD artifacts and re-admit the same scope | Rollback: N/A because no mutation has started | Evidence: the PR Change Contract declares `Production impact: UBUNTU_WORKER`, `VPS deployment: NOT REQUIRED`, `Ubuntu worker/relay update: REQUIRED`, `Production safety envelope: REQUIRED`, `VPS execution capability: NOT APPLICABLE`, `Ubuntu worker execution capability: CONNECTOR`, `Operator actions expected: 0`, `Risk profile: REQUIRED` and `Specification: specs/687-single-opencv-wheel/spec.md`
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: no release is installed and the active worker runtime keeps serving the previous graph; no host file changes | Retry: fix the lockfile, digest or SDD edit and re-run the pre-merge gates | Rollback: N/A because no mutation has started | Evidence: hash-lock module 24 tests OK; digest equality observed True; graph parse shows only the headless removal; repository validators and exact-head CI are the orchestrator's pre-merge gates
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: `update-exact.sh` aborts activation and restores the previous units through `restore_previous` and `abort_activation`; `deploy-authorized.sh` restores the protected configuration and the pre-deploy service state; the active-source marker still names the previous commit; a partially prepared release or runtime directory may remain on disk | Retry: re-run the deploy for the same merged SHA, since the release is re-prepared idempotently and the new runtime is installed under a runtime directory keyed by its own 64-hex id | Rollback: revert the merge commit and redeploy the previous worker lockfile through the same deploy workflow | Evidence: `update-exact.sh` runs `install-manual.sh`, which calls `prepare-runtime.sh` with the two-phase `--require-hashes` install and the fail-closed lock validation; failure paths emit `DEPLOY_CONFIG_ROLLED_BACK` (exit 20 or 22)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: post-activation identity verification fails, `deploy-authorized.sh` runs `rollback-exact.sh` to the previous release and exits 30 with `DEPLOY_ROLLED_BACK`; if rollback itself fails it exits 31 `CRITICAL` and no `runtime_verified` manifest is written | Retry: re-run the deploy after the cause is corrected, or redeploy the previous main | Rollback: `rollback-exact.sh` restores the previous release, runtime and units, and the transaction re-verifies the restored target | Evidence: `verify_active_target` checks the active-source marker, the 64-hex runtime id, every service `ExecStart` path under `/runtimes/<runtime-id>/venv/bin/python`, the control unit pin and desired service states; success prints `DEPLOYMENT_ACCEPTED target=... runtime_id=...`
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: no `runtime_verified` deployment manifest is produced; after a successful in-script rollback the active marker and services name the previous commit, and the workflow fails before `validate_deployment_manifest.py` | Retry: redeploy the merged SHA after the cause is corrected | Rollback: revert the merge commit and redeploy the previous worker lockfile | Evidence: the manifest with `state: runtime_verified`, `runtimeVerified: true` and `rollbackTarget` is written only after `verify_active_target` passes; `DEPLOYMENT_MANIFEST path=...` plus the validated artifact are the commit record
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: the verified runtime, active marker and services are preserved; only staging backups or old unprotected release directories survive | Retry: the storage-lifecycle service prunes on its next timer run | Rollback: NOT REQUIRED solely for a housekeeping failure | Evidence: `update-exact.sh` `cleanup()` runs from an EXIT trap and removes staging, unit backups and installed-copy backups; `storage_lifecycle_inventory.py` prunes only unprotected exact releases past the minimum age, so the active release and referenced runtimes are never targets
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: the runtime is unchanged but acceptance stays unresolved until the deployment manifest and the post-merge runs are read | Retry: re-collect the uploaded deployment/execution-audit artifacts without redeploying | Rollback: decided from the runtime evidence, not from evidence-transport failure alone | Evidence: `.github/workflows/deploy-ubuntu-worker.yml` uploads `dist/deployment-manifest-ubuntu-worker.json` and `dist/execution-audit-ubuntu-worker.json`; the post-deploy probe must show one `cv2` distribution inside the new runtime id
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if `rollback-exact.sh` cannot restore the previous release the script exits 31 `CRITICAL post-activation verification failed and rollback failed`, and the previous main must be redeployed from the workflow | Retry: redeploy the previous main through the normal Ubuntu worker lane | Rollback: revert the merge commit and redeploy the previous worker lockfile | Evidence: rollback run log with `DEPLOY_ROLLED_BACK target=... restored=... config_restored=true`, the previous runtime id and service paths active again, and a post-rollback `DEPLOYMENT_ACCEPTED` or equivalent healthy activation record

## Correct-course check
- Trigger: NONE
- Issue impact: none — the work order matches issue #687 as opened (two OpenCV distributions installed; keep the one ultralytics requires, drop the duplicate)
- Specification impact: none — the spec records the manifest deletion, the exact graph delta, the digest update, the uv-version note and the no-waiver statement without widening the issue
- Plan impact: none — the emergent details (scratch-directory symlink for canonical `-r` annotations, the two cosmetic `# via` expansions, the base-SHA discrepancy) are implementation mechanics inside the admitted scope and are recorded in Decisions and Runtime feedback
- Tasks impact: none — delivery tasks executed as written; the test-side pin update, PR, CI, merge and Ubuntu worker deploy are recorded as pending owner/orchestrator/test-worker steps in tasks.md
- Authorization impact: NONE (bounded worker work order from the delivery orchestrator on branch `agent/wave6-703-702-687`; the orchestrator owns the Git lifecycle, validator runs and the deploy chain)
- Follow-up: the test worker updates `tests/test_ubuntu_worker_manual_install.py:59`; the orchestrator runs the SDD/quality validators and router/quality gates on the exact head, merges, and deploys the merged SHA through the Ubuntu worker lane; the base-SHA discrepancy is reported to the orchestrator
