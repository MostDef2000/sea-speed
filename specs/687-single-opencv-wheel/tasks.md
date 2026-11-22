# Tasks: Single OpenCV distribution in the Ubuntu worker runtime

- Spec: specs/687-single-opencv-wheel/spec.md
- Plan: specs/687-single-opencv-wheel/plan.md
- Issue: #687

## Delivery tasks
- [x] Root cause confirmed from repository evidence: `deploy/worker/ubuntu/requirements-runtime.txt` pinned both
  `opencv-python==5.0.0.93` and `opencv-python-headless==5.0.0.93`, while the resolved lock attributes
  `opencv-python` to the direct manifest and `ultralytics` but `opencv-python-headless` to the direct manifest
  only — two distributions shipping the same `cv2` package, one of them not satisfying the ultralytics
  requirement name
- [x] Decision recorded: keep `opencv-python==5.0.0.93`, remove `opencv-python-headless==5.0.0.93`; worker OpenCV
  use is in-memory drawing/conversion/JPEG writing (`worker/worker_render.py:31,51-66,123`) with no HighGUI call
  sites (`grep` over `worker/` for `imshow|namedWindow|waitKey|startWindowThread|VideoCapture` → none) and video
  input as FFmpeg raw frames
- [x] Manifest updated: `deploy/worker/ubuntu/requirements-runtime.txt` loses exactly the
  `opencv-python-headless==5.0.0.93` line; every other pin, including `opencv-python==5.0.0.93`, is untouched
- [x] Lockfile regenerated (not hand-edited) with
  `uv pip compile --generate-hashes --index-url https://download.pytorch.org/whl/cu130 --extra-index-url
  https://pypi.org/simple --index-strategy unsafe-best-match --python-version 3.14 -c <constraints> runtime-lock-input.txt
  -o new-raw.lock.txt` (exit 0), where the input is the workflow's `-r` manifest line plus the sorted cu130
  torch/torchvision pins and the constraints file pin every surviving package to its current version
- [x] Graph verified: 57 → 56 packages; the only absent package is `opencv-python-headless==5.0.0.93` with its nine
  wheel hashes; no surviving package's version or hash set changed (1120 → 1111 hash pins); `torch==2.13.0+cu130`
  and `torchvision==0.28.0+cu130` hash sets identical
- [x] Self-containment restored: canonical 3-line header and `# sea-speed-runtime-lock-v1` marker restored, and the
  temporary `-c` annotation lines stripped from every `# via` comment; the committed file references only files
  that exist in the repository
- [x] Two cosmetic `# via` expansions disclosed (not a waiver): the committed file carried two historical
  single-line comments — `certifi` via `requests` and `six` via `torch`, both `git blame`-dated to the #392 lock
  (commit `1f81c5e`) — that neither uv 0.9.26 nor uv 0.9.8 emits; the regenerated file writes them in the normal
  multi-line form. No pin, hash or provenance line is affected
- [x] `deploy/worker/ubuntu/runtime-lock.json` updated only in `resolved_lock.sha256`, finally to
  `41d28eaa35caff2add5ac166ae1dbbca4553b77adf70198d944b455ca32e0517` (SHA-256 of the final 98 225-byte committed
  lockfile, after the F1 header fix; the pre-F1 digest was
  `93b7dbe282cb571a6d30cce8761dd5839b160867e540f16c1872dcdb5aa9a9d7` for 98 132 bytes); `python`, the whole
  `pytorch` provenance block and `verification_imports` are unchanged
- [x] Peer-review finding F1 fixed: lock line 3 now carries the workflow's exact resolver command
  `uv pip compile --generate-hashes --index-url https://download.pytorch.org/whl/cu130 --extra-index-url
  https://pypi.org/simple --index-strategy unsafe-best-match --python-version 3.14 runtime-lock-input.txt -o
  requirements-runtime.lock.txt` (the literal the workflow's `$PYTORCH_INDEX_URL` resolves to from
  `runtime-lock.json.pytorch.index_url`); no pin or hash line was touched, and the digest was rebound to the
  new bytes
- [x] Control runs recorded: with the unchanged manifest and all 57 pins constrained, resolution under local
  `uv 0.9.26` and under the workflow-pinned `uv 0.9.8` both reproduced the committed versions and every hash
  exactly; only comment formatting differed — evidence that the resolver-version difference does not alter
  resolution output
- [x] Scope verified: `git status --short` and `git diff --stat` show exactly the three dependency files
  (5 insertions, 17 deletions) plus this SDD trio; no `worker/**`, `api/**`, `tests/**`, `.github/**`,
  `scripts/**`, deploy script or other lockfile change
- [x] Hash-lock module green: `python3 -m unittest tests.test_ubuntu_worker_runtime_hash_lock -v` → Ran 24 tests, OK
- [x] Digest and schema checked: `json.load` of `runtime-lock.json` succeeds and
  `hashlib.sha256(lockfile bytes) == resolved_lock.sha256` is True
- [x] Test worker landed (not edited here): `tests/test_ubuntu_worker_manual_install.py` now asserts
  `opencv-python==5.0.0.93` only; `tests/test_687_single_opencv_wheel.py` and
  `tests/support/opencv_lock_baseline_687.json` carry the literal oracles. Observed RED on the pre-change tree
  6 failed / 7 passed; after the landing 1646 passed, 2 skipped, 858 subtests; hash-lock module 24 tests OK
- [ ] FOLLOW-UP (test worker, after F1): the lock digest moved, so the landed test's literal `LOCK_SHA256` constant
  (`tests/test_687_single_opencv_wheel.py:59`, used at line 241) needs a one-line re-pin to
  `41d28eaa35caff2add5ac166ae1dbbca4553b77adf70198d944b455ca32e0517`; until then exactly that assertion is red.
  Reported here, not suppressed, and no waiver exists
- [ ] PENDING orchestrator: PR Change Contract declares `Production impact: UBUNTU_WORKER`,
  `VPS deployment: NOT REQUIRED`, `Ubuntu worker/relay update: REQUIRED`, `Production safety envelope: REQUIRED`,
  `VPS execution capability: NOT APPLICABLE`, `Ubuntu worker execution capability: CONNECTOR`,
  `Operator actions expected: 0`, plus `Risk profile: REQUIRED` and
  `Specification: specs/687-single-opencv-wheel/spec.md`
- [ ] PENDING orchestrator: exact-head CI on the PR including the full suite after the test-side pin update, the
  SDD/quality validators, ruff and the contract gates
- [ ] PENDING orchestrator: exact-green-head merge to main, then Ubuntu worker deploy of the merged SHA through
  `.github/workflows/deploy-ubuntu-worker.yml` producing a `runtime_verified` deployment manifest with the new
  64-hex runtime id
- [ ] PENDING orchestrator: post-deploy acceptance probes — every service `ExecStart` under
  `/runtimes/<new-runtime-id>/venv/bin/python`, `cv2` imported from the retained `opencv-python` distribution, and
  no `opencv-python-headless` distribution inside the new runtime

## Evidence
- Base-SHA discrepancy: the work order named base `e2ef5562667bedc50f1bd26da41116c32262c35d`, which is absent
  locally (`git cat-file -t` → fatal). Branch head at admission:
  `39ff43644c54a1dd92558b0eefa37808c9cb5329` (merge of `origin/main` `6fa1a5b` into
  `agent/wave6-703-702-687`). Working tree was clean and its content matched the order's premise.
- Real resolution command (scratch directory `/tmp/opencode/687/work` with a `deploy` symlink so `-r` annotations
  stay canonical):
  `uv pip compile --generate-hashes --index-url https://download.pytorch.org/whl/cu130 --extra-index-url
  https://pypi.org/simple --index-strategy unsafe-best-match --python-version 3.14 -c
  /tmp/opencode/687/constraints-687.txt runtime-lock-input.txt -o new-raw.lock.txt`
  → exit 0, 56 packages, no `opencv-python-headless` reference in the output.
- Graph/hash parse comparison (name+version → sorted sha256 set), previous lock vs committed lock:
  `old packages 57 new packages 56`, `only old: [('opencv-python-headless', '5.0.0.93')]`, `only new: []`,
  `hash-set changed: []`, `total hashes old 1120 new 1111`, `torch hashes identical: True`,
  `torchvision hashes identical: True`.
- Textual diff: 19 changed lines from the regeneration — the headless pin, its nine `--hash` lines and its
  `# via` block, the `#   opencv-python-headless` entry in numpy's `# via` list, and the two disclosed `# via`
  expansions — plus F1's single header line; no pin or hash line changed by F1.
- F1 header before:
  `#    uv pip compile --generate-hashes --index-strategy unsafe-best-match --python-version 3.14 runtime-lock-input.txt -o requirements-runtime.lock.txt`
  → after:
  `#    uv pip compile --generate-hashes --index-url https://download.pytorch.org/whl/cu130 --extra-index-url https://pypi.org/simple --index-strategy unsafe-best-match --python-version 3.14 runtime-lock-input.txt -o requirements-runtime.lock.txt`
  (matches `.github/workflows/resolve-runtime-lock.yml:68-75`, whose `PYTORCH_INDEX_URL` is written from
  `runtime-lock.json.pytorch.index_url`).
- Digest/schema:
  `python3 -c "import json; json.load(open('deploy/worker/ubuntu/runtime-lock.json'))"` → `json OK; digest =
  41d28eaa35caff2add5ac166ae1dbbca4553b77adf70198d944b455ca32e0517`;
  `sha256(bytes) == resolved_lock.sha256` → `True` for 98 225 bytes. Old digest before the F1 header fix:
  `93b7dbe282cb571a6d30cce8761dd5839b160867e540f16c1872dcdb5aa9a9d7` (98 132 bytes).
- Hash-lock module: `python3 -m unittest tests.test_ubuntu_worker_runtime_hash_lock -v` → `Ran 24 tests in
  2.740s / OK`.
- Landed test suite (test worker): pre-change RED `6 failed, 7 passed`; post-landing
  `1646 passed, 2 skipped, 858 subtests passed`.
- Post-F1 full suite: `python3 -m pytest tests/ -q` → `1 failed, 1645 passed, 2 skipped, 858 subtests passed in
  152.37s`; the failure is
  `tests/test_687_single_opencv_wheel.py::DigestBindingTests::test_resolved_lock_sha256_binds_the_lockfile_bytes`
  at `tests/test_687_single_opencv_wheel.py:241` (`AssertionError` comparing the recomputed digest with the
  literal pre-F1 `93b7dbe2…`). tests/** is outside this change's write scope; the one-line re-pin is the test
  worker's follow-up. Reported verbatim, not waived.
- Control runs: unchanged manifest with all 57 pins constrained under uv 0.9.26 → identical versions and hashes,
  only `# via` grouping differed; the same under uv 0.9.8 → same result, proving the two single-line leftovers are
  historical, not version output.
- Scope: `git status --short` → `M` for `deploy/worker/ubuntu/requirements-runtime.lock.txt`,
  `deploy/worker/ubuntu/requirements-runtime.txt`, `deploy/worker/ubuntu/runtime-lock.json`;
  `git diff --stat` → 3 files changed, 5 insertions(+), 17 deletions(-). This SDD trio is untracked new work.

## Completion gate
- The source diff contains only `deploy/worker/ubuntu/requirements-runtime.txt` (one removed line),
  `deploy/worker/ubuntu/requirements-runtime.lock.txt` (headless block and its nine hashes removed, canonical
  header and marker restored, temporary `-c` annotations stripped) and `deploy/worker/ubuntu/runtime-lock.json`
  (`resolved_lock.sha256` only), plus this SDD trio; no source, test, workflow or deploy-script change exists
  beyond that
- The manifest carries exactly one OpenCV pin, and it is the `opencv-python` distribution `ultralytics` requires
- The lockfile and the digest are a matching pair: `resolved_lock.sha256` equals the SHA-256 of the committed
  bytes, and `prepare-runtime.sh` would accept the pair and reject a mismatch before any mutation
- The hash-lock module is green (24 tests OK), and the test-side manual-install pin is either updated by the test
  worker or explicitly reported as red — never waived
- The PR Change Contract declares the Ubuntu worker REQUIRED fields because `deploy/worker/ubuntu/**` is in the
  diff and the autonomous policy derives `Production impact: UBUNTU_WORKER` from the path
- Exact-head CI is green after the test-side update, the PR merges with exact-green-head evidence, and the Ubuntu
  worker deploy of that merged SHA completes with a `runtime_verified` manifest
- Runtime acceptance is the deployed worker importing `cv2` from the retained distribution with no
  `opencv-python-headless` distribution present; rollback is the single revert of the merge commit plus a redeploy
  of the previous worker lockfile

## Requirements traceability
- AC-001 | Task: manifest carries only `opencv-python==5.0.0.93` and loses exactly the headless line | Evidence: `git diff` of `deploy/worker/ubuntu/requirements-runtime.txt` shows the single removed line; `StructuralPinsTests.test_committed_lock_carries_marker_and_full_hash_pinned_graph` iterates the manifest and pins each entry uniquely, exact-version and hashed (module 24 tests OK) | Coverage: COVERED
- AC-002 | Task: the regenerated lock resolves 56 packages and loses only `opencv-python-headless==5.0.0.93` and its nine hashes, with every surviving pin and hash unchanged | Evidence: parse comparison observed `old 57 / new 56`, `only old: opencv-python-headless 5.0.0.93`, `only new: []`, `hash-set changed: []`, 1120 → 1111 hashes, torch/torchvision hash sets identical | Coverage: COVERED
- AC-003 | Task: `runtime-lock.json` digest equals the committed lockfile bytes, marker is first line, and CUDA provenance plus `verification_imports` are unchanged | Evidence: `sha256(bytes) == resolved_lock.sha256` → True (98 225 bytes); `test_runtime_lock_json_schema_2_carries_provenance` recomputes the digest and CUDA artifact digests; fail-closed negatives pass in the 24-test run; the landed `tests/test_687_single_opencv_wheel.py` binding computes the same equality and currently fails only on its stale literal digest constant | Coverage: COVERED
- AC-004 | Task: change bounded to the three dependency files plus this trio, and no check weakened or waived | Evidence: `git status --short` / `git diff --stat` show exactly the three dependency files; no skip/xfail/waiver added; the SDD states NO WAIVER explicitly | Coverage: COVERED
- AC-005 | Task: the test worker's #687 suite is landed and green (pre-change RED 6 failed / 7 passed; post-landing 1646 passed, 2 skipped, 858 subtests; hash-lock module 24 OK), with one assertion awaiting the digest re-pin after the F1 header fix; runtime acceptance still awaits the Ubuntu worker deploy | Evidence: `python3 -m pytest tests/ -q` after F1 → `1 failed, 1645 passed, 2 skipped, 858 subtests passed`; the single failure is `tests/test_687_single_opencv_wheel.py:241`'s literal `93b7dbe2…` digest versus the recomputed `41d28eaa…`, quoted verbatim in Evidence | Coverage: RUNTIME-MANUAL | Reason: runtime acceptance through the Ubuntu worker deploy is still pending, and one test-side literal digest constant needs a re-pin after the F1 header canonicalization moved the lock digest; tests are outside this change's write scope, and the state is reported rather than waived

## Definition of Done
- Issue/spec/plan/tasks current — issue #687, this trio, and the three landed dependency files agree
- Exact changed-file scope verified — only the allowed dependency files and this SDD trio changed
- Required tests and evidence complete — hash-lock module 24 tests OK; #687 suite landed (1646 passed, 2
  skipped, 858 subtests pre-F1); one literal digest-constant assertion awaits the test worker's re-pin after F1
- Required CI green — PENDING the orchestrator on the exact head (not claimed here)
- Exact-green-head merge complete — PENDING the orchestrator (not claimed here)
- Deployment state resolved — PENDING the Ubuntu worker deploy of the merged SHA (not claimed here)
- Runtime acceptance resolved — PENDING post-deploy probes: `cv2` from the retained `opencv-python`, no headless
  distribution in the new runtime
- Deferred work recorded — test-side digest re-pin (test worker); PR/CI/merge/deploy (orchestrator)
- Risks resolved or explicitly accepted — RISK-001/002/004 mitigated, RISK-003 mitigated with one pending
  test-side digest re-pin recorded
- Waivers resolved or current — none requested, none granted, none current; explicitly recorded in spec.md
