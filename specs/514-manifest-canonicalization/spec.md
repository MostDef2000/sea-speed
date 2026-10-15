# Spec: #514 runtime manifest canonicalization (write+verify)

- Issue: #514
- Specification: specs/514-manifest-canonicalization/spec.md

## Product outcome

Every Ubuntu-worker deploy since the manifest gate landed logs the same failure pair: `RUNTIME_VERIFY_FAILED ... check=manifest_python` (`typing-extensions expected=4.16.0 actual=None`) → `RUNTIME_QUARANTINED` → `RUNTIME_REBUILT` (3/3 deploys: 38601346768, 38610257974, 38677673628). The root cause (verified line-precise on main b337549): `deploy/worker/ubuntu/prepare-runtime.sh` normalized lock pin names with `.lower()` when building the expected graph, but baked the installed-manifest keys from the lowercased dist metadata `Name` — so the manifest carries `typing_extensions` while the verify lookup asks for `typing-extensions`, misses, and reports the installed package as absent (`actual=None`). The package IS installed; only the key spelling differs. The rebuild path then "fixes" it by running verify WITHOUT the manifest and re-baking the same underscore key, so the next deploy fails identically — a self-perpetuating loop that wastes a full torch re-bake on every deploy and masks real drift.

The fix is ONE shared PEP 503 canonicalization (lowercase; runs of `-_.` collapse to a single `-`) defined once in prepare-runtime.sh and injected into BOTH embedded python blocks (verify + manifest write). The verifier side is the load-bearing half: manifests on target boxes are chmod 0444 immutable and can never be rewritten in place, so the verifier canonicalizes manifest keys at READ time before lookup — pre-fix manifests with underscore keys verify cleanly instead of forcing a rebuild. The write side bakes canonical keys, so new manifests are canonical from birth and the recurrence loop is closed. Verify strictness is unchanged for genuinely missing or version-mismatched packages (negative control).

Deliberate non-changes (recorded): `validate_runtime_lock` keeps `.lower()` and the pip argument naming is untouched — every package name in the committed lock/requirements/runtime-lock.json inputs is already PEP 503 canonical (all 57 lock names enumerated in review), so behavior there is identical; a future non-canonical lock spelling still fails closed at validation (exit 3) rather than being silently healed.

## User scenarios

- US-1: a worker host runs a pre-fix 0444 manifest keyed `typing_extensions` → the verifier builds `installed_canonical` (read-time canonicalization) and looks up `_pypi_canon("typing-extensions")` → match found → `RUNTIME_REUSED`, no quarantine, no rebuild.
- US-2: a fresh install writes a manifest → keys are baked canonical (`_pypi_canon(metadata Name)`) → a subsequent verify with the manifest passes on the first try (no rebuild → re-bake → fail loop).
- US-3: a package is genuinely missing (or version-drifted) → the canonicalization cannot invent a match → verify still fails with the graph-drift message and the runtime rebuilds (fail-closed preserved).
- US-4: a caller tries to override the canonicalization source via the environment → the script's unconditional assignment + export overwrites any inherited value before either block runs → script-owned bytes, fail-closed `KeyError` if absent.
- US-5: CI runs the rebuild harness → the two behavioral tests fail against the pre-fix script with the EXACT production signature and pass against the fix; the negative control passes in both worlds.

## Scope

- `deploy/worker/ubuntu/prepare-runtime.sh`: ADD the shared `SEA_SPEED_PYPI_CANON_SRC` definition + export; in the verify block: `import os` + exec-inject, `_pypi_canon(...)` for lock-pin graph keys and requirements cross-check, read-time `installed_canonical` map + canonical lookup; in the write block: `import os` + exec-inject, `_pypi_canon(...)` for the dist metadata Name key. NOTHING else changes (manifest fields, hashes, JSON formatting byte-identical).
- `tests/test_ubuntu_worker_runtime_rebuild.py`: 4 new tests — metadata-Name-keyed manifest verifies WITHOUT rebuild (RED on base, exact incident signature); genuinely-missing-package negative control still fails+rebuilds; re-baked manifest keys asserted canonical and re-verified on a second run (closes the 3/3 recurrence); structural pin (exactly one `_pypi_canon` definition, exactly two exec-injections feeding both blocks, write-side key expression, read-time map, no `.lower()` in the verify block).
- OUT of scope: everything else — no workflow edits, no other deploy scripts, no worker/*.py, no API/frontend changes, no test weakening.

## Requirements

- R-1 (AC-001): ONE canonicalization definition feeds BOTH embedded python blocks (verify + write); no second normalization for manifest keys exists in the script; the injection is script-owned (caller env cannot win).
- R-2 (AC-002): verify accepts manifests whose keys canonicalize to the expected names (read-time tolerance) — pre-fix underscore-key manifests verify without rebuild; `typing-extensions` is an idempotent fixed point; `typing_extensions` and `typing-extensions` collide to the same key.
- R-3 (AC-003): write bakes canonical keys; the re-baked manifest re-verifies on the next run with no verify failure (recurrence loop closed).
- R-4 (AC-004): fail-closed semantics preserved — a genuinely missing package still yields `runtime manifest graph drift ... actual=None` → `RUNTIME_VERIFY_FAILED` → `RUNTIME_QUARANTINED` → `RUNTIME_REBUILT`.
- R-5 (AC-005): no behavior change on committed lock inputs — every name in requirements-runtime.lock.txt / requirements-runtime.txt / runtime-lock.json is already PEP 503 canonical, so `validate_runtime_lock`'s `.lower()` and the pip args are behavior-identical.
- R-6 (AC-006): full battery green (1031 baseline + 4 new, 4 skipped); validate_repo, validate_sdd, gate CLI, `bash -n prepare-runtime.sh` all green; ruff introduces zero new findings.

## Acceptance criteria

- AC-001: structural pin passes (exactly one `def _pypi_canon(`, exactly two `exec(os.environ["SEA_SPEED_PYPI_CANON_SRC"])` injections, write-side key expression and read-time map exact, no `.lower()` in the verify block slice); RED on base.
- AC-002: `test_issue_514_metadata_name_manifest_key_verifies_without_rebuild` passes on the fix and FAILS on base with the exact incident signature (`runtime manifest graph drift: typing-extensions expected=4.16.0 actual=None` → `RUNTIME_VERIFY_FAILED ... check=manifest_python` → `RUNTIME_QUARANTINED`) — re-observed by the orchestrator via the documented `SEA_SPEED_426_PREPARE_RUNTIME_PATH` override, not taken from worker prose.
- AC-003: `test_issue_514_rebaked_manifest_keys_are_canonical_and_reverify` passes (second run: `RUNTIME_REUSED`, canonical keys, underscore key absent).
- AC-004: `test_issue_514_genuinely_missing_manifest_package_still_fails` passes and is independent of the fix (empty installed map fails identically in both worlds).
- AC-005: reviewer enumeration confirms all committed lock names are canonical; the deliberate non-changes are documented in the commit body.
- AC-006: battery `1035 passed, 4 skipped`; validate_repo `Tracked files checked: 736` green; validate_sdd green; gate `compatible=True` (8 files); `bash -n` OK.
