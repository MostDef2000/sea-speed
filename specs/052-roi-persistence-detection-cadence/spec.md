# Spec: ROI persistence and measured fresh-frame detection cadence

- Issue: #299
- Status: ACTIVE
- Runtime contour: MIXED (VPS + Ubuntu Worker/relay)

## Product outcome

Road ROI behaves as server-owned configuration: user edits a draft, server confirms persistence with an atomic file transaction and a verified reload, browser distinguishes draft/persisted/error and never pretends an unsaved polygon is stored, ROI survives page reload and API restart and propagates to the Worker, and legacy/malformed ROI cannot silently masquerade as disabled empty geometry.

Detection cadence becomes measurable and governed by fresh frames: transport never ships partial raw frames or a growing backlog, telemetry reports decoded/inferred/processed/published rates and source age without double counting, the inference loop is not needlessly blocked by JPEG generation or outbound HTTP, Road and Water cadences are configured independently, and protected runtime confirms the highest sustainable Road inference rate for both solo and joint execution at 5/10/15 FPS.

Stage 3 smooth metadata overlay is explicitly out of scope.

## User scenarios

- Operator draws a Road ROI and clicks Save — UI shows Draft, Saving, Saved or Error, and shows Saved only after the server roundtrip proves the file was written and can be reloaded.
- Operator saves a ROI, refreshes `/sea-speed/road/` — same polygon is still present via normalized 0..1 geometry, even when speed config or speed-lines requests fail.
- Operator saves a ROI and API restarts — ROI is still present; Worker picks it up within its refresh interval without needing another browser save.
- Existing installation upgrades — previously saved legacy absolute ROI survives VPS migration without silent coordinate drift or file breakage.
- Operator inspects FPS — state and UI surface configured `sample_fps` and separately measured effective/inference FPS plus health age/queue telemetry rather than a single ambiguous counter.
- Operator asks for higher cadence — runtime can report real sustainable Road inference frequency for Road-only and Water+Road at 5/10/15 FPS and identify the next bottleneck.

## Requirements

- R1: Road frontend must separate Draft ROI (in-memory edit) from Persisted ROI (confirmed server geometry), show explicit Draft/Saving/Saved/Error states, report success only after POST roundtrip plus successful reload/verification, and retain an unsaved draft with an obvious unsaved indicator after a failed save.
- R2: Road ROI reload must be independent of other Road config loads; a failure of speed config or speed-lines must not suppress a valid persisted ROI response.
- R3: API must store Road ROI atomically and durably, preserve legacy geometry during migration, distinguish absent ROI from malformed/unreadable persisted ROI without silently degrading to disabled, and keep backward-compatible normalized storage.
- R4: VPS deployment migration must operate against the real production data directory, perform per-file migration with correct syntax and atomic replacement, and leave valid normalized geometry unchanged.
- R5: Worker ROI polling must eventually reflect the persisted server geometry within the configured refresh interval and must not require a browser re-save after API or Worker restart.
- R6: Frame ingress must be complete-frame only: transport reads exactly one logical frame at a time, never consumes partial raw bytes as if they were readable, never grows an unbounded backlog of stale frames, and exposes deterministic latest-slot drop/coalesce accounting.
- R7: Telemetry must report decoded, inferred/processed and published rates separately, plus source-to-inference age, stage timing (decode/inference/JPEG/HTTP) and queue depth/drops without double-counting the same logical frame.
- R8: Inference critical path must not be blocked by avoidable per-frame JPEG generation or by synchronous outbound HTTP/event work when that work can be decoupled while preserving exact snapshot consistency between frames, detections, crossings and published metadata.
- R9: Road and Water configured cadences must not be silently coupled; Road sample FPS, FP16 and related worker cadence knobs must be validated from Road-owned protected configuration rather than inherited from Water.
- R10: Protected runtime must be benchmarkable at 5/10/15 FPS for Road-alone and Water+Road concurrent execution and must identify the current stable maximum with fresh frames; reporting must remain honest when the hardware ceiling is below 10 FPS.

## NFR assessment

- NFR-052-001 | Area: reliability | Target: POST → disk → GET → reload roundtrip succeeds and survives simulated API restart, with corrupted JSON reported distinctly from absent ROI | Validation: API persistence roundtrip + restart simulation + frontend reload independence test | Evidence: tests/test_api_contract.py, tests/test_roi_normalization.py, tests/test_vps_deploy_transaction.py, tests/test_frontend_contract.py | Status: PASS
- NFR-052-002 | Area: usability | Target: failed Save leaves Draft visibly marked as unsaved and does not masquerade as Saved; speed-config failure does not hide persisted ROI | Validation: frontend draft/error + independent-load contract tests | Evidence: tests/test_frontend_contract.py | Status: PASS
- NFR-052-003 | Area: reliability | Target: VPS migration against `/opt/sea-speed-api/data` migrates legacy absolute geometry to normalized form without drift >1px on 1920×1080, preserves already-normalized files byte-identically (aside from atomic rename), and never produces broken JSON | Validation: executed migration harness against production data directory layout + atomicity test | Evidence: tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-052-004 | Area: performance | Target: frame ingress maintains exactly one complete fresh frame invariant, drops are counted/coalesced deterministically, and no partial-frame byte consumption path exists | Validation: frame-queue unit test including partial-read and backlog scenarios | Evidence: tests/test_detection_runtime_optimization.py | Status: PASS
- NFR-052-005 | Area: observability | Target: FPS and age telemetry correctly separate decoded, inferred, processed and published rates, report source age and stage p50/p95 without double-counting | Validation: performance-tracker unit test with controlled timing/board | Evidence: tests/test_detection_runtime_optimization.py, tests/test_ubuntu_worker_observability.py, schemas/telemetry.schema.json | Status: PASS
- NFR-052-006 | Area: performance | Target: avoidable per-frame JPEG/HTTP work off critical inference path while preserving exact frame/metadata/crossing snapshot consistency; baseline inference loop latency reduced vs current synchronous JPEG-per-frame behavior | Validation: critical-path regression test + benchmark harness marks | Evidence: tests/test_detection_runtime_optimization.py, tests/test_frame_quality.py | Status: PASS
- NFR-052-007 | Area: compatibility | Target: Road protected cadence configuration independent of Water, with validated 1..15 FPS range and explicit fallback/default behavior distinct from legacy Water 5 FPS | Validation: profile/configuration unit tests | Evidence: tests/test_analytics_profiles.py, tests/test_ubuntu_worker_ai_supervision.py | Status: PASS
- NFR-052-008 | Area: reliability | Target: protected benchmark establishes maximum stable fresh-frame Road inference FPS for Road-only and Water+Road at 5/10/15 and reports measured ceiling without false PASS when <10 FPS sustainable | Validation: protected-runtime benchmark report checked in runtime evidence, not shallow unit simulation | Evidence: runtime report referenced by tasks | Status: PASS

## Acceptance criteria

- AC-001: Road draft ROI and persisted ROI are distinct; only a verified POST→GET roundtrip transitions Draft to Saved; failed save leaves Draft marked as unsaved.
- AC-002: Successful ROI survives browser reload and simulated API restart; reloading ROI does not depend on successful speed-config/speed-lines endpoints.
- AC-003: Corrupt/malformed persisted ROI is distinguished from absent/disabled ROI and fails visibly rather than silently presenting as empty/disabled.
- AC-004: VPS migration targets `/opt/sea-speed-api/data`, handles per-file legacy→normalized migration atomically, and keeps already-normalized files intact; no migration path writes partially broken JSON.
- AC-005: Worker observes updated persisted ROI within its configured refresh interval and after Worker restart without requiring another browser save.
- AC-006: Frame path never consumes partial raw frames; backlog does not accumulate stale frames; latest-slot drops/coalesces are counted deterministically and fresh frames are delivered.
- AC-007: Telemetry reports decoded, inferred/processed and published FPS separately, plus source age, stage timing and queue depth/drops, with no double counting of a single logical frame.
- AC-008: Per-frame JPEG generation and outbound state/event/crossing HTTP do not block ordered inference while snapshot-bound consistency is preserved.
- AC-009: Road sample FPS is resolved independently from Water preserved configuration and validated within an explicit range; legacy Water 5 FPS cannot silently cap Road.
- AC-010: Protected runtime benchmark for Road-alone and Water+Road at 5/10/15 FPS exists, reports measured stable maximum with fresh frames, and targets sustained Road inference ≥10 FPS while motion-active or honestly records the measured ceiling.
- AC-011: Validators + relevant unit/integration suite PASS; PR Validation + four-domain Quality PASS; exact-main Quality PASS; MIXED runtime_verified (VPS + Ubuntu).

## Runtime feedback

- Prior evidence 696e5e3 exposes unreliable effective_fps, backlog/partial-read risks, synchronous JPEG/HTTP on the inference loop, and Water-coupled Road cadence configuration.
