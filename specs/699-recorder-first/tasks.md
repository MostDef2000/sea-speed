# Tasks: Opt-in recorder of original encoded HLS segments

- Feature: 699-recorder-first
- Specification: specs/699-recorder-first/spec.md
- Plan: specs/699-recorder-first/plan.md
- Issue: #699
- Status: Source implementation

## Delivery tasks

- [x] T001 Add `worker/recorder.py`: bounded config, playlist/`#EXT-X-MAP` parsing, relative URIs, same-origin redirects, auth scoping, chunked deadline-limited download, atomic spool, per-object rsync with bounded retry/backoff and gap counting.
- [x] T002 Wire lifecycle-only recorder launch/stop into `worker/ubuntu_worker_entrypoint.py`: one child per enabled camera, no readiness wait or media IPC, spawn failure disables recording only, process-group stop for the rsync descendant, LoadCredential key read.
- [x] T003 Add the identical opt-in block to `deploy/worker/ubuntu/worker.env.example` and `road-worker.env.example`; keep the existing `LoadCredential` line in both service templates.
- [x] T004 Add `worker/recorder.py` to the ubuntu-worker required inventory in `scripts/quality/build_exact_artifacts.py` and `scripts/quality/validate_exact_artifacts.py`; leave vps/edge unchanged.
- [x] T005 Author the SDD trio under `specs/699-recorder-first/`.
- [x] T006 Record observed static/lifecycle/artifact evidence below; dedicated `tests/**` evidence remains with the test worker.
- [ ] T007 Record required CI and exact-green-head merge evidence after the bounded PR is opened by the orchestrator (PENDING).
- [ ] T008 Record dedicated test-worker `tests/**` unit/integration evidence (PENDING — test worker owns tests/**).

## Completion gate

- [x] Exact scope verified against Issue #699 allowed paths
- [x] SDD artifacts current
- [x] Local static and scratch verification observed (py_compile, ruff, smoke, inventory, exact-artifact build/validate, validate_sdd)
- [ ] Required CI evidence recorded after PR opening (PENDING)
- [ ] Exact-green-head merge complete (PENDING)
- [ ] Dedicated test-worker `tests/**` evidence recorded (PENDING)

## Requirements traceability

- AC-001 | Task: T001, T002 | Evidence: `RecorderConfig.from_env` rejects flags other than 0/1; entrypoint `_recorder_enabled`/`_start_recorder` returns before `Popen` when the flag is not the literal `1`; env examples default to 0; dedicated test PENDING | Coverage: COVERED
- AC-002 | Task: T001 | Evidence: `download_object` streams original bytes to a `.part` file and atomically renames; `HlsRecorder.capture` rsyncs the completed object; scratch smoke observed byte-identical segment and init payloads and fake-rsync delivery; dedicated test PENDING | Coverage: COVERED
- AC-003 | Task: T001 | Evidence: `parse_playlist` handles `#EXT-X-MEDIA-SEQUENCE`/`#EXT-X-MAP`; `urljoin(final_url, uri)` resolves relative URIs; `_SameOriginRedirect` refuses cross-origin targets; `_origin` rejects non-HTTP(S) sources; scratch smoke observed same-origin redirect success, cross-origin refusal and RTSP rejection; dedicated test PENDING | Coverage: COVERED
- AC-004 | Task: T001 | Evidence: `download_object` reads `_CHUNK_BYTES` chunks under a monotonic deadline, enforces `object_max_bytes`, and `capture` raises `SpoolSpaceLow` below `min_free_bytes`; dedicated test PENDING | Coverage: COVERED
- AC-005 | Task: T001, T002 | Evidence: `HlsRecorder.upload` bounds attempts and exponential backoff, `capture` deletes the object and the loop increments `gap_count`; the recorder is a separate process with no pipe to `worker.main()`; dedicated test PENDING | Coverage: COVERED
- AC-006 | Task: T002 | Evidence: entrypoint `_start_recorder` uses `start_new_session=True` with `stdin=DEVNULL` and logs a spawn failure without raising; `_stop_recorder` `killpg`s SIGTERM then SIGKILL and reaps; `_credential_path` reads `$CREDENTIALS_DIRECTORY`/`/run/credentials` only; scratch lifecycle observed spawn, rc 143 stop and spawn-failure isolation; dedicated test PENDING | Coverage: COVERED
- AC-007 | Task: T003, T004 | Evidence: `INVENTORY_OK` observed (ubuntu-worker build/validate contain `worker/recorder.py`; vps/edge do not); both env examples inspected with the identical opt-in block; both templates retain `LoadCredential=recorder_ed25519:/etc/sea-speed/recorder_ed25519`; dedicated test PENDING | Coverage: COVERED
- AC-008 | Task: T005, T006 | Evidence: observed py_compile `PYCOMPILE_OK`, ruff `All checks passed!`, exact-artifact build exit 0 plus validation PASS; `validate_sdd.py` and git scope outputs recorded below; dedicated tests PENDING | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [ ] Required tests and evidence complete (dedicated `tests/**` evidence PENDING — test worker owns tests/**)
- [ ] Required CI green — PENDING the bounded PR's exact-head run
- [ ] Exact-green-head merge complete — PENDING the bounded PR
- [x] Deployment state resolved (Ubuntu Worker/relay REQUIRED — new recorder module, entrypoint, env examples and service templates; feature default OFF)
- [ ] Runtime acceptance resolved (PENDING by design — no production enablement in this scope)
- [x] Deferred work recorded (dedicated tests, CI/merge evidence, field enablement and dacha retention observation)
- [x] Risks resolved or explicitly accepted (RISK-001..RISK-006)
- [x] Waivers resolved or current (none required)

## Evidence (observed only)

Observed on this working tree (2026-11-25); no fabricated results:

- `python3 -m py_compile worker/recorder.py worker/ubuntu_worker_entrypoint.py
  scripts/quality/build_exact_artifacts.py scripts/quality/validate_exact_artifacts.py`
  → `PYCOMPILE_OK`.
- `python3 -m ruff check --config scripts/quality/ruff.toml worker/recorder.py
  worker/ubuntu_worker_entrypoint.py scripts/quality/build_exact_artifacts.py
  scripts/quality/validate_exact_artifacts.py` → `All checks passed!`.
- Scratch oracle `/tmp/opencode/699-recorder-first/smoke.py` → `RECORDER_SMOKE_OK`:
  - playlist parsed to init `init.mp4`, segments `seg0.ts`/`seg1.ts`, media
    sequence 7;
  - segment and init downloads matched the source bytes exactly;
  - same-origin redirect delivered the original bytes;
  - cross-origin redirect was refused;
  - RTSP source configuration was rejected;
  - `CREDENTIALS_DIRECTORY` key resolution selected the provided credential;
  - fake-rsync delivery was byte-identical and the local spool was cleaned.
- Entrypoint lifecycle scratch run (stubbed cv2/ultralytics import) → recorder
  child spawned; SIGTERM stop observed exit code `143`; spawn failure printed
  `recorder disabled spawn failure reason=OSError` and left no child; disabled
  flag spawned nothing.
- Inventory assertion over `COMPONENT_FILES` and `REQUIRED_BY_COMPONENT` →
  `INVENTORY_OK` (ubuntu-worker contains `worker/recorder.py`; vps/edge do not).
- `python3 scripts/quality/build_exact_artifacts.py --source-commit
  a66b5a8039cdba585f8b549e1091989586b0d72a --output-dir
  /tmp/opencode/699-recorder-first/dist` → exit 0; the Ubuntu Worker artifact
  inventory includes `worker/recorder.py`.
- `python3 scripts/quality/validate_exact_artifacts.py --manifest
  /tmp/opencode/699-recorder-first/dist/exact-artifacts.json` →
  `Exact artifacts valid: VPS/edge quality evidence plus Ubuntu Worker release
  inventory, digests, extraction and syntax`.
- `python3 scripts/ci/validate_sdd.py` → recorded by the final verification run
  during this task.
- `git status --short` / `git diff --stat` → recorded by the final verification
  run during this task; no commit, push or PR was made by this worker.
- Dedicated `tests/**` behaviour coverage is PENDING (test worker owns tests/**);
  no test result is claimed here.
