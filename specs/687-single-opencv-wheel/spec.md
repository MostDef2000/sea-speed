# Spec: Single OpenCV distribution in the Ubuntu worker runtime

- Feature: 687-single-opencv-wheel
- Issue: #687
- Status: Implemented (dependency/digest files landed; tests landed by the test worker — full suite green before the header canonicalization, see AC-005)
- Owner outcome: the Ubuntu worker runtime resolves exactly one `cv2` provider — the `opencv-python` distribution that `ultralytics` declares — instead of shipping two OpenCV distributions that both install a `cv2` package.

## Product outcome
The Ubuntu worker runtime manifest `deploy/worker/ubuntu/requirements-runtime.txt` pinned **both**
`opencv-python==5.0.0.93` and `opencv-python-headless==5.0.0.93`. Two distributions that ship the same
`cv2` package are a duplicate: the resolved graph carried both, the wheelhouse downloaded both sets of
wheels, and the installed venv contained two `cv2` distributions whose files shadow each other by install
order. That is dead weight and an undefined-winner hazard, not a capability.

The resolved lock attributes `opencv-python` to the direct manifest **and** to `ultralytics`; it attributes
`opencv-python-headless` to the direct manifest only:

```
opencv-python==5.0.0.93
    # via
    #   -r deploy/worker/ubuntu/requirements-runtime.txt
    #   ultralytics
opencv-python-headless==5.0.0.93
    # via
    #   -r deploy/worker/ubuntu/requirements-runtime.txt
```

`ultralytics` declares a requirement named `opencv-python`. A package named `opencv-python-headless`
does not satisfy a distribution requirement named `opencv-python`, so headless was never a substitute for
the ultralytics requirement — removing `opencv-python` would have forced a second provider anyway. The
architect verdict, re-derived from this repository evidence, is therefore: **keep `opencv-python==5.0.0.93`,
remove `opencv-python-headless==5.0.0.93`**.

The worker's own OpenCV usage needs no window system and no HighGUI, so the only cost of the GUI-capable
wheel is unused Qt/GTK linkage that the runtime never loads:

- `worker/worker_render.py:31,51-66,123` uses in-memory operations only: `cv2.cvtColor`, `cv2.Laplacian`,
  `cv2.rectangle`, `cv2.getTextSize`, `cv2.addWeighted`, `cv2.putText`, and
  `cv2.imwrite(..., [cv2.IMWRITE_JPEG_QUALITY, 90])`.
- `grep` over `worker/` finds no `imshow`, `namedWindow`, `waitKey`, `startWindowThread` or `VideoCapture`
  call; video input reaches the worker as raw frames from FFmpeg, not through OpenCV's capture/display.

Both wheels are the same version `5.0.0.93`, so `cv2`'s Python API and ABI are unchanged; the change removes
a distribution, not a capability. The resolved lock drops from 57 to 56 packages (1120 → 1111 hash pins:
exactly the nine `opencv-python-headless` wheel hashes), and no surviving package changes version or digest.
`resolved_lock.sha256` is `41d28eaa35caff2add5ac166ae1dbbca4553b77adf70198d944b455ca32e0517`
(SHA-256 of the 98 225-byte committed lockfile, after peer-review finding F1 restored the workflow's
canonical resolver command in the header; the pre-header-fix digest was
`93b7dbe282cb571a6d30cce8761dd5839b160867e540f16c1872dcdb5aa9a9d7` for 98 132 bytes). The new runtime id
is intended: the deploy transaction prepares a new immutable runtime and the old one stops being referenced.

## User scenarios

```gherkin
Feature: The Ubuntu worker runtime ships exactly one OpenCV distribution
  Rule: the manifest names the distribution that ultralytics requires

  Scenario: the manifest carries a single OpenCV pin
    Given the worker runtime manifest `deploy/worker/ubuntu/requirements-runtime.txt`
    When a maintainer reads its package pins
    Then `opencv-python==5.0.0.93` is present
    And `opencv-python-headless` does not appear anywhere in the manifest

  Rule: the resolved lock is the complete graph for that manifest

  Scenario: the lock graph loses only the headless distribution
    Given the regenerated `requirements-runtime.lock.txt`
    When it is compared with the previous revision package-by-package
    Then `opencv-python-headless==5.0.0.93` and its nine wheel hashes are absent
    And every surviving pin keeps its exact version and every wheel hash
    And `torch==2.13.0+cu130` and `torchvision==0.28.0+cu130` keep their exact artifact digests

  Scenario: the hash-lock pair is accepted
    Given `prepare-runtime.sh` validates `runtime-lock.json` against the lockfile before any mutation
    When the new lockfile and digest are installed
    Then `resolved_lock.sha256` equals the SHA-256 of the committed lockfile bytes
    And the first line is `# sea-speed-runtime-lock-v1`
    And the CUDA provenance block and `verification_imports` are unchanged

  Scenario: a maintainer reviews the diff
    Given the branch diff for issue #687
    When the three dependency files are compared with the previous revision
    Then the manifest loses exactly one line
    And the lockfile changes only by the headless block, one `# via` reference and two cosmetic `# via` expansions
    And `runtime-lock.json` differs only in `resolved_lock.sha256`

  Scenario: the worker still imports cv2 after the change
    Given the runtime's `verification_imports` include `cv2`
    When the new graph is installed through the existing hash-locked path
    Then `cv2` imports from the retained `opencv-python` distribution
    And every other verification import (`lap`, `numpy`, `requests`, `torch`, `torchvision`, `ultralytics`) is still satisfied

  Scenario: rollback
    Given the change must be undone
    When the orchestrator reverts the merge commit and redeploys the previous worker lockfile
    Then the worker installs its previous graph through the same two-phase hash-locked path
    And the deploy transaction activates the previous runtime id
```

## Requirements
1. Manifest single-wheel rule: `deploy/worker/ubuntu/requirements-runtime.txt` must contain exactly one
   OpenCV pin, `opencv-python==5.0.0.93`; the `opencv-python-headless` line is removed and nothing else in
   the manifest changes.
2. Wheel choice is evidence-based, not preference-based: `opencv-python` stays because `ultralytics`
   (a direct pin) requires the distribution named `opencv-python`, and headless cannot satisfy a
   requirement of that name; the runtime's OpenCV use is in-memory drawing/conversion/JPEG encoding with
   no HighGUI, so the GUI-capable wheel adds only unused linkage.
3. Lock regeneration, not lock hand-editing: `deploy/worker/ubuntu/requirements-runtime.lock.txt` is
   produced by `uv pip compile --generate-hashes --index-url https://download.pytorch.org/whl/cu130
   --extra-index-url https://pypi.org/simple --index-strategy unsafe-best-match --python-version 3.14`
   over `runtime-lock-input.txt` (`-r deploy/worker/ubuntu/requirements-runtime.txt` plus the sorted
   `torch`/`torchvision` cu130 pins from `runtime-lock.json`), with a temporary constraints file pinning
   every surviving package to its current version. For a pure deletion no `--upgrade-package` target exists.
4. Minimal graph delta: the only disappearing package is `opencv-python-headless==5.0.0.93` with its nine
   wheel hashes; every surviving pin keeps its exact version and hash lines, and the `torch`/`torchvision`
   artifact digests named by `runtime-lock.json` remain present in the lockfile's hash lines.
5. Self-contained artifact with the workflow's canonical header: the header is restored to the exact command
   shape `.github/workflows/resolve-runtime-lock.yml:68-75` emits — `uv pip compile --generate-hashes
   --index-url https://download.pytorch.org/whl/cu130 --extra-index-url https://pypi.org/simple
   --index-strategy unsafe-best-match --python-version 3.14 runtime-lock-input.txt -o
   requirements-runtime.lock.txt` (the workflow's `$PYTORCH_INDEX_URL` resolves to the literal cu130 URL
   from `runtime-lock.json.pytorch.index_url`; the literal is written so the header is self-describing) —
   under `# sea-speed-runtime-lock-v1`, and every temporary `-c <constraints-file>` annotation is stripped
   from the `# via` comments; the committed file references only files that exist in the repository.
6. Digest pair: `deploy/worker/ubuntu/runtime-lock.json` changes only in `resolved_lock.sha256`, set to
   `41d28eaa35caff2add5ac166ae1dbbca4553b77adf70198d944b455ca32e0517` (the SHA-256 of the final lockfile
   bytes, header fix included); `python`, `pytorch` (index URLs,
   provenance, pins, `artifact_sha256`) and `verification_imports` stay byte-identical.
7. Bounded surface: only the three dependency files and this SDD trio change. No `worker/**`, `api/**`,
   `tests/**`, `.github/**`, `scripts/**`, deploy script, unit file or other lockfile is edited.
8. Resolver version note (disclosed, accepted): the workflow `.github/workflows/resolve-runtime-lock.yml`
   pins `uv==0.9.8` while the implementation environment provides `uv 0.9.26`. CI audits the committed
   lockfile; it does not re-resolve. Two control resolutions (unchanged manifest with all 57 pins
   constrained, run under 0.9.26 and under 0.9.8) reproduced the committed graph's versions and hashes
   exactly, proving the resolver-version difference does not alter resolution output. The only visible
   difference is comment formatting: the committed file carries two historical single-line `# via`
   comments (`certifi` via `requests`, `six` via `torch`) that `git blame` dates to the #392 lock and that
   neither uv version emits, so the regenerated file expands exactly those two into the multi-line form.
   That is disclosed here and in plan.md; it is cosmetic, touches no pin, hash or provenance line, and is
   not a waiver of anything.
9. Verification: `tests/test_ubuntu_worker_runtime_hash_lock.py` stays green (24 tests observed OK) and the
   hash-lock module's assertions (marker, per-line hash pins, direct-requirement uniqueness, digest equality,
   CUDA artifact digests, fail-closed negatives) cover the new pair.
10. Test-side landing (completed by the test worker, tests not edited here): `tests/test_ubuntu_worker_manual_install.py`
    now asserts `opencv-python==5.0.0.93` only (no headless line), and
    `tests/test_687_single_opencv_wheel.py` plus `tests/support/opencv_lock_baseline_687.json` carry the
    literal oracles for this change (manifest, 56-package graph, 1111 hash pins, marker/header, digest
    binding, scope guard). Observed: RED on the pre-change tree 6 failed / 7 passed; green after the landing
    1646 passed, 2 skipped, 858 subtests; hash-lock module 24 tests OK. The test file's literal
    `LOCK_SHA256` constant still names the pre-header-fix digest, so the F1 header canonicalization requires
    a one-line re-pin in that test file by the test worker (tests are outside this change's write scope);
    until it lands, that single assertion is red and is reported here rather than waived.

## Acceptance criteria
- AC-001: `deploy/worker/ubuntu/requirements-runtime.txt` contains `opencv-python==5.0.0.93`, contains no
  `opencv-python-headless` entry, and differs from the previous revision by exactly the one removed line.
- AC-002: the committed `requirements-runtime.lock.txt` resolves to exactly 56 packages; the only package
  absent relative to the previous lock is `opencv-python-headless==5.0.0.93` with its nine wheel hashes;
  no surviving package's version or hash set changed (1120 → 1111 hash pins); `torch==2.13.0+cu130` and
  `torchvision==0.28.0+cu130` hash sets are identical to the previous lock.
- AC-003: `deploy/worker/ubuntu/runtime-lock.json` `resolved_lock.sha256` equals the SHA-256 of the
  committed lockfile bytes (`41d28eaa35caff2add5ac166ae1dbbca4553b77adf70198d944b455ca32e0517` for the
  98 225-byte file), the `# sea-speed-runtime-lock-v1` marker is the first line, and the `pytorch`
  provenance block plus `verification_imports` are unchanged.
- AC-004: the change is bounded to the three dependency files plus this SDD trio, and no check is weakened,
  removed, skipped or waived to obtain green.
- AC-005: the test worker's suite has landed — `tests/test_ubuntu_worker_manual_install.py` asserts
  `opencv-python` only and `tests/test_687_single_opencv_wheel.py` carries the literal oracles (RED on the
  pre-change tree 6 failed / 7 passed; 1646 passed, 2 skipped, 858 subtests after the landing; hash-lock
  module 24 tests OK). After peer-review finding F1 canonicalized the lock header the digest moved, so the
  test file's literal digest constant needs a one-line re-pin by the test worker; this criterion stays open
  until that re-pin is observed, and it is not claimed or waived here. Runtime acceptance through the Ubuntu
  worker deploy is separately pending.

## Runtime feedback
- The duplication was cost, not capability: both distributions were the same version, so the second set of
  wheels added nothing except a second `cv2` provider and ~one extra wheel set in the venv and wheelhouse.
- The wheel decision is a requirement-name fact, not a philosophical one: `ultralytics` requires
  `opencv-python`; a differently named headless distribution cannot satisfy it, and "the server has no
  display" does not rename a dependency requirement.
- A controlled regeneration is what made a pure deletion safe: pinning all 56 survivors in a temporary
  constraints file meant the resolver could not move any other package, and the root-cause of any diff is
  therefore unambiguous. The two control runs (all 57 pinned, unchanged manifest, uv 0.9.26 and 0.9.8)
  reproduced the committed graph exactly, which isolates the resolver-version difference to comment
  formatting.
- The only non-graph diff is cosmetic: two historical single-line `# via` comments expand to the multi-line
  form. It is disclosed rather than hidden, and it does not touch a pin, hash or provenance line.
- Peer review finding F1 (header parity): the committed header omitted `--index-url`/`--extra-index-url`,
  while the workflow emits them. The header now carries the workflow's exact command with literal index URLs
  (`https://download.pytorch.org/whl/cu130`, `https://pypi.org/simple`), which changes the bytes and therefore
  the digest — recomputed to `41d28eaa…0517`; no pin or hash changed. The landed test file pins the previous
  literal digest, so the follow-up is a one-line test re-pin by the test worker, reported verbatim rather
  than waived.
- Residual coupling: the landed tests are green except the literal digest constant in
  `tests/test_687_single_opencv_wheel.py`, which the F1 header fix necessarily moved. That is a test
  ownership boundary (tests are outside this change's write scope), recorded as a pending re-pin in
  tasks.md, not a reason to keep a duplicate wheel, revert the canonical header, or add a waiver.

## NFR assessment
- NFR-001 | Area: Security | Target: the worker runtime installs exactly one `cv2` distribution, eliminating the double-provider shadowing where install order decides which `cv2` files win | Validation: package-by-package parse of the committed lock before/after plus the manifest diff, and the existing per-line hash-pin assertions | Evidence: lock resolves 56 packages; the sole absent package is `opencv-python-headless==5.0.0.93`; manifest carries one OpenCV pin; `tests/test_ubuntu_worker_runtime_hash_lock.py` 24 tests OK | Status: PASS
- NFR-002 | Area: Reliability | Target: the lockfile bytes and `runtime-lock.json` remain a matching pair so `prepare-runtime.sh` never fails its digest cross-check at deploy time | Validation: recompute SHA-256 over the committed lockfile bytes and compare with `resolved_lock.sha256`; fail-closed negatives in the hash-lock module | Evidence: sha256(bytes) == `41d28eaa35caff2add5ac166ae1dbbca4553b77adf70198d944b455ca32e0517` → True for 98 225 bytes; `test_resolved_lock_sha256_mismatch_fails_closed` and the 24-test module run OK | Status: PASS
- NFR-003 | Area: Compatibility | Target: the worker's `cv2` API surface is unchanged because the retained wheel is the same `5.0.0.93` release that produced the API the worker already uses | Validation: version equality of the retained pin plus the runtime's `verification_imports` (`cv2` included) exercised by the hash-lock module's import/install checks | Evidence: retained `opencv-python==5.0.0.93`; lock's numpy `# via` list drops only the headless entry; 24 tests OK including verification-import coverage | Status: PASS
- NFR-004 | Area: Operability | Target: one dependency deletion with a single-revert rollback and no operator action | Validation: diff inspection of the branch, the repository validators and the deployment transaction audit in plan.md | Evidence: `git diff --stat` shows 3 files, 5 insertions and 17 deletions; digest updated in the same landing; `Operator actions expected: 0` in the Change Contract; rollback is a merge revert plus redeploy | Status: PASS

## Waivers and non-waivers
NO WAIVER is requested, proposed or granted by this specification. No test is skipped, no assertion is
relaxed, no gate is bypassed and no fail-closed path is disabled. The test worker has landed the #687 suite
(`tests/test_687_single_opencv_wheel.py`, `tests/support/opencv_lock_baseline_687.json`) and the updated
`tests/test_ubuntu_worker_manual_install.py`; the observed landing evidence is RED on the pre-change tree
(6 failed / 7 passed) and 1646 passed, 2 skipped, 858 subtests with 24 hash-lock tests OK. Peer-review
finding F1 then canonicalized the lock header, which moves the lock digest by design, so the test file's
literal `LOCK_SHA256` constant needs a one-line re-pin by the test worker. That single assertion is
currently red, is reported verbatim in tasks.md, and is never suppressed or waived.
