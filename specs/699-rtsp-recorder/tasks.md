# Tasks: RTSP stream-copy recorder arm

- Feature: 699-rtsp-recorder
- Specification: specs/699-rtsp-recorder/spec.md
- Plan: specs/699-rtsp-recorder/plan.md
- Issue: #699
- Sub-issue: #699b
- Status: Source implementation

## Delivery tasks

- [x] T001 Add the `SEA_SPEED_RECORDER_SOURCE_TYPE=hls|rtsp` selector to `worker/recorder.py`, keep the HLS arm unchanged, read the existing `HLS_URL` for RTSP, lazy-load the RTSP arm, and share the bounded upload operation.
- [x] T002 Add `worker/recorder_rtsp.py`: validated RTSP source, ffconcat credential boundary, exact FFmpeg stream-copy/Matroska argv, process-group grandchild, rollover completion witness, atomic rename plus bounded upload and delete, 30-second deadline, gap/outage accounting and `RLIMIT_FSIZE` bounds.
- [x] T003 Add the identical selector block and RTSP note to both `deploy/worker/ubuntu/worker.env.example` and `road-worker.env.example`; introduce no new URL, key or tuning knob.
- [x] T004 Add `worker/recorder_rtsp.py` to the ubuntu-worker exact-artifact inventories in `scripts/quality/build_exact_artifacts.py` and `scripts/quality/validate_exact_artifacts.py` only; change no lockfile or requirements file.
- [x] T005 Author the SDD trio under `specs/699-rtsp-recorder/`.
- [x] T006 Record observed static, SDD and exact-artifact evidence below.
- [x] T007 Record required CI and exact-green-head merge evidence after the bounded PR is opened by the orchestrator (PENDING). — auto-synced on merge to main (7c5ea3c0)
- [x] T008 Record dedicated test-worker evidence for the RTSP arm (PENDING). — auto-synced on merge to main (7c5ea3c0)

## Completion gate

- [x] Exact scope verified against the Issue #699b work order allowed paths
- [x] SDD artifacts current
- [x] Local static, SDD and exact-artifact verification observed
- [ ] Required CI evidence recorded after PR opening (PENDING)
- [x] Exact-green-head merge complete (PENDING) — auto-synced on merge to main (7c5ea3c0)
- [ ] Dedicated test-worker evidence recorded (PENDING)
- [ ] Runtime acceptance resolved (PENDING by design — no production enablement)

## Requirements traceability

- AC-001 | Task: T001 | Evidence: recorder.py returns after the disabled check before reading the selector, validating a URL or importing recorder_rtsp; env examples default to 0; test-worker oracle PENDING | Coverage: COVERED
- AC-002 | Task: T001 | Evidence: the hls branch is unchanged and still calls `_origin` on SEA_SPEED_RECORDER_HLS_URL; the RtspRecorder path is reached only when source_type is rtsp; test-worker oracle PENDING | Coverage: COVERED
- AC-003 | Task: T001, T002 | Evidence: recorder.py reads the existing HLS_URL and requires it non-empty for rtsp; validate_source rejects non-rtsp, hostless and control-character sources with no fallback; test-worker oracle PENDING | Coverage: COVERED
- AC-004 | Task: T002 | Evidence: build_ffmpeg_args pins video-only `-c:v copy` segmented Matroska with the exact verdict tail; no decode and no re-encode; test-worker oracle PENDING | Coverage: COVERED
- AC-005 | Task: T002 | Evidence: the monitor finalises a segment only when the next numbered file appears or FFmpeg exits cleanly; the argv pins `-break_non_keyframes 0`; test-worker oracle PENDING | Coverage: COVERED
- AC-006 | Task: T002 | Evidence: `_finalize` atomically renames to a unique camera-session-sequence.mkv, calls the shared bounded_upload and deletes the object; failure counts a gap; test-worker oracle PENDING | Coverage: COVERED
- AC-007 | Task: T002 | Evidence: the monitor enforces a 30-second monotonic deadline, terminates and reaps FFmpeg, discards the tail, increments gap and outage and reconnects with bounded backoff; a sparse-keyframe source that never rolls over is bounded by the 128 MiB media cap and the rc-nonzero discard path, not by that deadline; test-worker oracle PENDING | Coverage: COVERED
- AC-008 | Task: T002 | Evidence: relay argv uses `-rtsp_transport tcp`; direct Camera 1 uses write_ffconcat with CAMERA1_RTSP_TRANSPORT, mkstemp 0600 in private temp, stderr DEVNULL and safe labels; test-worker oracle PENDING | Coverage: COVERED
- AC-009 | Task: T002 | Evidence: `_fsize_limiter` applies RLIMIT_FSIZE to the FFmpeg child only; media_max_bytes is two object slots; the spool floor is checked; the spool base must exist and numbered dirs use no parent creation; test-worker oracle PENDING | Coverage: COVERED
- AC-010 | Task: T003, T004 | Evidence: both quality inventories list worker/recorder_rtsp.py for ubuntu-worker only; both env examples carry the identical selector block; no lockfile or requirements file is edited; exact-artifact build and validate observed below | Coverage: COVERED
- AC-011 | Task: T005, T006 | Evidence: the feature is default OFF with no runtime enablement; rollback is revert or rollback-exact with no media, API or receiver repair; runtime acceptance PENDING by design | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [ ] Required tests and evidence complete — dedicated test-worker oracle PENDING
- [x] Required CI green — PENDING the bounded PR's exact-head run — auto-synced on merge to main (7c5ea3c0)
- [x] Exact-green-head merge complete — PENDING the bounded PR — auto-synced on merge to main (7c5ea3c0)
- [x] Deployment state resolved (Ubuntu Worker/relay REQUIRED — new module, selector, env examples and inventories; feature default OFF)
- [ ] Runtime acceptance resolved — PENDING by design (no production enablement in this scope)
- [x] Deferred work recorded (test-worker evidence, CI/merge evidence, field enablement and relay/transport observation)
- [x] Risks resolved or explicitly accepted (RISK-001..RISK-007)
- [x] Waivers resolved or current (none required)

## Evidence (observed only)

Observed on this working tree (2026-11-26); no fabricated results. The dedicated
test-worker oracle remains PENDING and is not claimed.

- `python3 -m py_compile worker/recorder.py worker/recorder_rtsp.py scripts/quality/build_exact_artifacts.py scripts/quality/validate_exact_artifacts.py` → `PYCOMPILE_OK`.
- `python3 -m ruff check --config scripts/quality/ruff.toml worker/recorder.py worker/recorder_rtsp.py scripts/quality/build_exact_artifacts.py scripts/quality/validate_exact_artifacts.py` → `All checks passed!` (exit 0).
- `python3 scripts/ci/validate_sdd.py` → `Sea Speed SDD validation passed` (exit 0).
- Scratch oracle over the real modules (relay argv, direct ffconcat, source rejection, HLS arm) → `relay_argv_ok`, `direct_ffconcat_ok 0o600`, `rejections_ok`, `hls_ok`:
  - disabled RTSP selector returns before source validation and leaves `source_type=hls`;
  - relay argv pins `-rtsp_transport tcp`, `-c:v copy` and the `%09d/clip.mkv.part` pattern;
  - direct Camera 1 writes a `0o600` ffconcat with `option rtsp_transport udp` and the credential never appears in argv;
  - `http://`, relative, hostless, control-character and single-quote sources are rejected;
  - the default `hls` arm still reads `SEA_SPEED_RECORDER_HLS_URL`.
- `python3 scripts/quality/build_exact_artifacts.py --source-commit c689947350f141aada84943a6e06a71e3cbb28b4 --output-dir /tmp/opencode/699b-rtsp-recorder/dist` → exit 0; `worker/recorder_rtsp.py` present in the ubuntu-worker release artifact and absent from vps/edge.
- `python3 scripts/quality/validate_exact_artifacts.py --manifest /tmp/opencode/699b-rtsp-recorder/dist/exact-artifacts.json` → `Exact artifacts valid: VPS/edge quality evidence plus Ubuntu Worker release inventory, digests, extraction and syntax` (exit 0).
- `git status --short` → modified `deploy/worker/ubuntu/road-worker.env.example`, `deploy/worker/ubuntu/worker.env.example`, `worker/recorder.py`, `scripts/quality/build_exact_artifacts.py`, `scripts/quality/validate_exact_artifacts.py` (plus the orchestrator's pre-existing `scripts/ci/validate_sdd.py`); untracked `worker/recorder_rtsp.py` and `specs/699-rtsp-recorder/`. `git diff --stat` → 6 files changed, 120 insertions(+), 46 deletions(-), excluding the new untracked files.
- Existing #699 regression suite `python3 -m pytest tests/test_699_recorder.py tests/test_699_recorder_lifecycle.py -q` → `1 failed, 49 passed, 60 subtests passed`. The single failure is `RecorderScopeGuardTests::test_change_set_touches_only_the_699_surface`, which pins the #699 allowed-path set and therefore rejects this branch's #699b paths (the orchestrator's `scripts/ci/validate_sdd.py` edit plus `specs/699-rtsp-recorder/**` and `worker/recorder_rtsp.py`); all HLS behavior tests pass, confirming the HLS arm is unchanged.
- Dedicated #699b test-worker oracle for the RTSP arm → PENDING (owned by the separate test worker; not claimed here).
