# Tasks: Ubuntu worker dependency remediation — clear the four advisory-bearing transitive pins in the runtime lockfile

- Spec: specs/716-worker-dependency-remediation/spec.md
- Plan: specs/716-worker-dependency-remediation/plan.md
- Issue: #716

## Delivery tasks
- [x] Root cause confirmed on branch agent/fix-716-worker-deps: the gating audit read only `deploy/worker/ubuntu/requirements-runtime.txt` (7 direct pins), so the #686 full-lockfile audit that reads `deploy/worker/ubuntu/requirements-runtime.lock.txt` found 58 advisories in four transitive packages — pillow 12.3.0 (42, fix 13.0.0), filelock 4.0.12 (13, fix 4.2.1), certifi 2026.7.22 (2, fix 2026.10.18) and setuptools 84.0.0 (1, fix 84.1.0) — while the direct-manifest audit stayed green
- [x] Lockfile regenerated with `uv pip compile --generate-hashes --index-url https://download.pytorch.org/whl/cu130 --extra-index-url https://pypi.org/simple --index-strategy unsafe-best-match --python-version 3.14`, using a temporary constraints file that pinned all 53 non-target packages to their existing versions and `--upgrade-package` for the four targets
- [x] Exactly four version changes landed: certifi 2026.7.22 to 2026.11.20, filelock 4.0.12 to 4.3.0, pillow 12.3.0 to 13.0.0, setuptools 84.0.0 to 84.2.1; all other 53 pins keep their previous exact versions and hash lines, including torch 2.13.0+cu130 and torchvision 0.28.0+cu130
- [x] Self-containment restored: the temporary `-c runtime-constraints.txt` references were stripped from the generated `# via` comments and the header was restored to the canonical resolver command, so the committed lockfile references only files that exist in the repository and keeps `# sea-speed-runtime-lock-v1` as its first line
- [x] `deploy/worker/ubuntu/runtime-lock.json` updated only in `resolved_lock.sha256` to `e20d765263221f52ac4b7cb55a522d627eec122b300514e5012b37b300aebbca`, the SHA-256 of the new lockfile bytes; the `pytorch` provenance block is byte-identical
- [x] No other file changed: no `worker/**` source, no test, no deploy script, no workflow, no lock input and no API lockfile is in the diff
- [x] Hash-lock test green: `python3 -m unittest tests.test_ubuntu_worker_runtime_hash_lock -v` — 24 passed (marker, hash integrity, `resolved_lock.sha256` equality, PyTorch artifact pins, fail-closed negatives)
- [x] Full battery and static gates green: 1439 tests OK (skipped=2); repo, contracts, quality, workflow and token validators PASS; ruff PASS
- [x] Full-lockfile audit green locally: `pip-audit --disable-pip --vulnerability-service osv` reports 57 dependencies and 0 vulnerabilities for the new worker lockfile, and 23 dependencies and 0 vulnerabilities for the API lockfile
- [x] Write the SDD trio `specs/716-worker-dependency-remediation/{spec,plan,tasks}.md`
- [ ] PR Change Contract declares exactly `Production impact: UBUNTU_WORKER`, `VPS deployment: NOT REQUIRED`, `Ubuntu worker/relay update: REQUIRED`, `Production safety envelope: REQUIRED`, `VPS execution capability: NOT APPLICABLE`, `Ubuntu worker execution capability: CONNECTOR`, `Operator actions expected: 0`, plus `Risk profile: REQUIRED` and `Specification: specs/716-worker-dependency-remediation/spec.md`
- [ ] Exact-head CI on the PR is green, including the hash-lock test, the SDD validator for this trio, the contracts/quality/workflow/token validators, ruff, and the full-lockfile audit
- [ ] Exact-green-head merge of the PR to main
- [ ] Ubuntu worker deploy of the merged main SHA through `.github/workflows/deploy-ubuntu-worker.yml` produces a deployment manifest with `state: runtime_verified` and the new 64-hex runtime id
- [ ] Post-deploy acceptance: `verify_active_target` evidence shows every service `ExecStart` under `/runtimes/<runtime-id>/venv/bin/python`, and the merged-SHA Security gates run reports 0 lockfile advisories for the worker and API contours

## Completion gate
- The source diff contains only `deploy/worker/ubuntu/requirements-runtime.lock.txt` (four pins moved with regenerated hashes, canonical header, marker intact) and `deploy/worker/ubuntu/runtime-lock.json` (`resolved_lock.sha256` only); no other source, test, workflow or deploy-script change exists beyond this SDD trio
- The lockfile and the digest are a matching pair: `resolved_lock.sha256` equals the SHA-256 of the committed lockfile bytes, and `prepare-runtime.sh` would accept the pair and reject a mismatch before any mutation
- The full-lockfile audit is 0 for both contours (worker 57 dependencies, API 23 dependencies), and the CI full-lockfile audit on the exact head re-verifies with the default advisory service that produced the original 58 findings
- The PR Change Contract declares the Ubuntu worker REQUIRED fields listed in the delivery tasks, because `deploy/worker/ubuntu/**` is in the diff and the autonomous policy derives `Production impact: UBUNTU_WORKER` from the path
- Exact-head CI green on the PR, PR merged to main with exact-green-head evidence, then the Ubuntu worker deploy of that merged SHA completes with a `runtime_verified` manifest and the post-activation identity checks
- Runtime acceptance is the deployed worker running the new graph with 0 known advisories and the existing verification imports intact; the rollback is the single revert of the merge commit plus a redeploy of the previous worker lockfile

## Requirements traceability
- AC-001 | Task: only the four advisory-bearing pins move — certifi 2026.11.20, filelock 4.3.0, pillow 13.0.0, setuptools 84.2.1 — while all 53 other pins keep their previous exact versions | Evidence: branch diff of `deploy/worker/ubuntu/requirements-runtime.lock.txt` shows exactly those four version lines changed, and `tests/test_ubuntu_worker_runtime_hash_lock.py::StructuralPinsTests.test_committed_lock_carries_marker_and_full_hash_pinned_graph` asserts every direct requirement and both PyTorch closure pins are uniquely present, exact-version and hash-pinned | Coverage: COVERED
- AC-002 | Task: `runtime-lock.json` `resolved_lock.sha256` matches the new lockfile bytes and the hash-lock validator accepts the pair | Evidence: the field equals `e20d765263221f52ac4b7cb55a522d627eec122b300514e5012b37b300aebbca`; `StructuralPinsTests.test_runtime_lock_json_schema_2_carries_provenance` compares it to `hashlib.sha256(LOCK_FILE.read_bytes())`; `RuntimeIdAndLockTests.test_resolved_lock_sha256_mismatch_fails_closed` proves the fail-closed negative; the module run is 24 passed | Coverage: COVERED
- AC-003 | Task: a full-lockfile audit reports 0 vulnerabilities for both contours | Evidence: local `pip-audit --disable-pip --vulnerability-service osv` reports 57 dependencies and 0 vulnerabilities for the worker lockfile and 23 dependencies and 0 vulnerabilities for `api/requirements-api.txt`; CI's full-lockfile audit on the exact head re-verifies with the default advisory service that produced the original 58 in Security gates run 44975403396 | Coverage: COVERED
- AC-004 | Task: full battery, validators and lint stay green and the worker runtime still imports its verification modules | Evidence: full Python suite 1439 tests OK (skipped=2); repo, contracts, quality, workflow and token validators PASS; ruff PASS; `tests/test_ubuntu_worker_runtime_hash_lock.py` executes the two-phase `--require-hashes` install mechanics and the real `verify_python` over the `verification_imports` set (cv2, lap, numpy, requests, torch, torchvision, ultralytics) | Coverage: COVERED

## Definition of Done
- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current
