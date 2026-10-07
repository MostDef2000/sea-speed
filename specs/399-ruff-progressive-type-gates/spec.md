# Spec: Ruff and progressive mypy quality gates

- Issue: #399
- Specification: specs/399-ruff-progressive-type-gates/spec.md

## Product outcome

The merge-facing aggregate `Quality integration gate` gains two static-analysis
steps inside its existing `static-contract-security` domain: a non-mutating
Ruff lint gate (pinned `ruff==0.16.10`, rule set `select = ["E9", "F"]`,
`fix = false`) and a progressive mypy gate (pinned `mypy==1.18.2`, committed
`mypy.ini` baseline with a permissive global section and per-module
`strict = True` sections). Both tools are installed as plain pip installs with
exact version pins — no native toolchain, no runtime downloads — and both run
the exact commands documented in `docs/quality/testing-policy.md`.

The 14 lint findings that Ruff's E9+F rule set reports on main are resolved
mechanically (unused imports removed, dead locals removed, one f-string
prefix dropped, five `collections.deque[float]` annotations added), so the
gate starts green with zero findings and no suppressions. The change is
strictly additive at the gate level: no existing validator, test,
exact-artifact check, workflow job, trigger or permission is modified.

## User scenarios

- US-1: A contributor opens a PR or pushes to main; the
  `static-contract-security` job runs the Ruff and mypy steps autonomously
  with zero operator actions, and any new lint or strict-typing finding fails
  the merge-facing aggregate.
- US-2: A contributor introduces an unused import or an f-string without
  placeholders; `ruff check .` exits nonzero naming file and rule, and the
  contributor removes the dead code instead of suppressing it.
- US-3: A contributor edits one of the five strict modules in a way that
  breaks full strict typing; the mypy step exits nonzero with the exact
  error, holding new code to strict typing without a mass legacy rewrite.
- US-4: A maintainer reviews the gate design from repository sources alone:
  `ruff.toml` and `mypy.ini` are committed, pins are exact, the policy and
  the deterministic local invocation are documented in
  `docs/quality/testing-policy.md`, and `fix = false` proves CI can never
  rewrite source.

## Requirements

- R-1: A non-mutating Ruff gate runs inside the existing
  `static-contract-security` domain of the merge-facing aggregate: step
  `Ruff lint (non-mutating)` installs `ruff==0.16.10` (exact pin) and runs
  `ruff check .` against the committed `ruff.toml` with
  `select = ["E9", "F"]` and `fix = false`. Zero blanket ignores: any future
  suppression must be narrow (per-file ignore for a named rule or an inline
  `# noqa: CODE` with the specific code) with written justification in
  review. CI never rewrites source.
- R-2: A progressive mypy gate runs in the same domain: step
  `Progressive mypy (strict baseline)` installs `mypy==1.18.2` (exact pin —
  last release line with pure-Python dependencies; 1.19+ requires the librt
  C extension; 2.x additionally requires the Rust-based `ast_serialize`
  parser) and runs `mypy --config-file mypy.ini` over the five strict
  modules. The committed `mypy.ini` keeps the global section permissive;
  per-module `strict = True` sections are the adoption mechanism; new small,
  pure, well-tested modules enter the strict set during code review;
  suppressions must be narrow `# type: ignore[code]` only.
- R-3: The gate is calibrated low-noise on main: zero findings at merge. The
  14 baseline findings (10 F401, 3 F841, 1 F541 measured with ruff 0.16.10
  on base 27c90b7) are resolved mechanically, each verified side-effect-free:
  1. F401 `deploy/worker/ubuntu/storage_lifecycle_common.py:7` — unused `import shutil` removed.
  2. F401 `deploy/worker/ubuntu/storage_lifecycle_inventory.py:15` — unused `LifecycleError` removed from the multi-line from-import.
  3. F401 `scripts/ci/sync_tasks_md.py:20` — unused `import sys` removed.
  4. F401 `scripts/quality/verify_quality_status.py:8` — unused `import re` removed.
  5. F401 `scripts/worker/benchmark_detector_frequency.py:4` — unused `statistics` removed from the combined import.
  6. F401 `tests/test_camera_preview_gallery.py:4` — unused `import re` removed.
  7. F401 `tests/test_roi_normalization.py:4` — unused `import json` removed.
  8. F401 `tests/test_roi_normalization.py:6` — unused `import tempfile` removed.
  9. F401 `tests/test_worker_operator_control.py:4` — unused `import os` removed.
  10. F401 `worker/hls_motion_yolo_worker_events.py:1966` — vestigial `from detection_performance import PerformanceTracker as _PT` removed (try block keeps its remaining statements).
  11. F841 `worker/detection_performance.py:39` — dead `now = ingest_mono if ingest_mono else time.monotonic()` removed.
  12. F841 `worker/hls_motion_yolo_worker_events.py:816` — dead `max_text_width = ...` removed (never read).
  13. F841 `tests/test_mediamtx_compatibility_remediation.py:194` — unused `result` binding on a `check=True` `subprocess.run` removed (call retained).
  14. F541 `worker/hls_motion_yolo_worker_events.py:797` — f-string without placeholders loses its `f` prefix.
  Additionally, the five deque fields in `worker/detection_performance.py`
  (lines 23-27) are annotated `collections.deque[float]` (float timestamps;
  lazy under `from __future__ import annotations`) so the module is strict-clean.
- R-4: Existing validators, behavioral tests and exact-artifact gates remain
  authoritative and untouched: no workflow trigger, permission, job,
  `if: always()` aggregate logic, validator script, test or deploy path is
  modified beyond the two inserted steps; all workflow-policy substring
  markers remain byte-identical.
- R-5: Deterministic documented local invocation: after
  `pip install ruff==0.16.10 mypy==1.18.2`, from the repository root,
  `ruff check .` and the exact mypy command from the workflow (same five
  modules, same config file) reproduce the CI steps; the commands are
  documented in `docs/quality/testing-policy.md`.
- R-6: No source mutation by CI: `fix = false` in `ruff.toml`; the mypy step
  is analysis-only; neither step writes, rewrites or reformats any file; no
  heredocs and no new `uses:` entries are introduced.

## Acceptance criteria

- AC-001: The `Ruff lint (non-mutating)` step is present in the
  `static-contract-security` job of `.github/workflows/quality-integration.yml`
  (after the JSON/py_compile step, before the unittest step) and the step is
  green — `ruff check .` exits zero on the merged head with the calibrated
  fixes applied.
  Validation: workflow diff review plus local `ruff check .` (exit 0).
- AC-002: The `Progressive mypy (strict baseline)` step is present in the
  same job in the same position and is green — mypy 1.18.2 over the five
  strict modules exits zero.
  Validation: workflow diff review plus the local mypy command (exit 0).
- AC-003: The local battery is green: `ruff check .`, the mypy strict
  command, `scripts/quality/validate_workflow_policy.py`,
  `scripts/ci/validate_repo.py`, `scripts/ci/validate_contracts.py`,
  `scripts/quality/validate_quality_contracts.py`,
  `python -m py_compile scripts/quality/*.py scripts/release/*.py` and
  `python -m unittest discover -s tests -p 'test_*.py' -v` (expected
  baseline: Ran 649 tests, OK, skipped=3) all pass.
  Validation: local battery output recorded in the PR.
- AC-004: Documentation is complete: `docs/quality/testing-policy.md`
  carries the `## Static analysis (Ruff and mypy)` section documenting the
  domain placement, both pins with rationale, the progressive-strict policy,
  the no-blanket-ignores rule and the exact local commands; the
  `Status: Active` marker is untouched.
  Validation: read of `docs/quality/testing-policy.md`.
- AC-005: The diff equals exactly the allowed files: `ruff.toml`, `mypy.ini`,
  `.github/workflows/quality-integration.yml`, `docs/quality/testing-policy.md`,
  the 11 calibrated source files and the `specs/399-ruff-progressive-type-gates/`
  trio — nothing else.
  Validation: `git diff --stat` review; PR files-changed list.
- AC-006: The Change Contract is valid and classified CONTROL_PLANE, and the
  merge is an exact-green-head merge of the linked PR with required CI green.
  Validation: Change Contract in the PR body; exact-green-head merge
  evidence recorded by the Delivery Orchestrator.

## Runtime feedback

- RF-001: Operator actions expected: 0; both steps execute autonomously
  inside the existing aggregate on pull_request, push to main and
  workflow_dispatch.
- RF-002: Evidence recorded in the PR: CI run links (PR-triggered and
  push-to-main runs of "Quality integration gate" showing both new steps
  green), local battery outputs and the `git diff --stat` scope review.
- RF-003: Known initial state (observed on base 27c90b7): ruff 0.16.10 with
  `select = ["E9", "F"]` reports exactly 14 findings (10 F401, 3 F841,
  1 F541) — all resolved mechanically in this change, so the gate starts at
  zero findings with zero suppressions. The full default E4/E7/E9/F set
  measures 290 findings and stays deferred (plan DEC-3).
- RF-004: The gate does not alter the deployment transaction chain: the
  autonomous router triggers on `quality-integration` success only, and the
  two steps are internal to the existing `static-contract-security` job.

## NFR assessment

- NFR-SECURITY | Area: Security | Target: Security impact NONE — no permission change, no secrets, no new actions, no heredocs; the gate only fails builds on findings and never mutates source (`fix = false`) | Validation: scripts/quality/validate_workflow_policy.py plus diff review of the two inserted steps | Evidence: validator output and PR files-changed list recorded in the PR | Status: PASS
- NFR-SUPPLY-CHAIN | Area: supply chain | Target: both tools installed from exact pins (`ruff==0.16.10`, `mypy==1.18.2`) as pure pip installs with no runtime downloads, no node/rust toolchain fetch and no heredocs | Validation: run-block review of the two steps (pip install lines pinned; no curl/wget) | Evidence: workflow source plus PR files-changed list | Status: PASS
- NFR-MAINTAINABILITY | Area: maintainability | Target: zero ruff findings and a committed progressive mypy baseline at merge; strict adoption path documented so new modules can be held to strict typing at review | Validation: local `ruff check .` (exit 0) and mypy strict command (exit 0); docs section review | Evidence: local battery output recorded in the PR | Status: PASS
- NFR-SCOPE | Area: maintainability | Target: diff limited to the 18 allowed files (2 config + 2 docs/workflow + 11 calibrated sources + 3 SDD artifacts); no validator, test, deploy path or other workflow touched | Validation: git diff --stat review | Evidence: PR files-changed list | Status: PASS
