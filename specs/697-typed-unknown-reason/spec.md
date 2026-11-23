# Spec — Issue #697 typed reason for every unknown speed status

- Issue: #697
- Specification: specs/697-typed-unknown-reason/spec.md
- Authorization: wave-8 admission (issue #697), branch `agent/wave8-697-700`,
  base `83e8851a896b795786fc4db7c3f6fe7088436302`.
- Related: issue #700 (frame-quality reasons, reserved here but not emitted),
  specs/024-water-passage-registry/spec.md (passage registry contract),
  specs/698-log-redaction/spec.md (release-relative api/app helper precedent).

## Product outcome

A persisted vessel passage whose `speed_status` is `unknown` currently says
nothing about *why*. An operator cannot tell "the boat was seen but there are
not enough timed observations yet" apart from "the two-gate speed geometry is
disabled or unusable", and a client sees an opaque `unknown`. Issue #697 makes
the reason explicit and machine-readable: every unknown speed status produced
by the worker carries a typed `unknown_reason` inside the existing
`measurement_meta` JSON, and the API presents the same field on read —
supplying `legacy_unspecified` for historical rows that predate the change
without rewriting stored history. The change is additive: no new database
column, no new top-level payload field, no UI change; existing readers keep
working and a measured/incomplete row never carries a reason.

## User scenarios

- SC-1: a passage is tracking with a usable gate but too few observations; the
  API exposes `speed_status=unknown` with `measurement_meta.unknown_reason =
  "too_few_observations"`.
- SC-2: the two-gate geometry is disabled or unusable while a vessel is
  observed; the reason is `gate_unavailable` (an observation exists — it is a
  configuration gap, not "no detection").
- SC-3: a historical `unknown` row written before #697 reads back with
  `legacy_unspecified`; the stored row is unchanged.
- SC-4: a passage reaches `measured` (two-gate or calibrated); no
  `unknown_reason` is present, and a late unknown write cannot demote it.
- SC-5: a client attempts to POST a reason outside the closed set; the API
  rejects the write with HTTP 400.

## Requirements

- R-1: `api/app/unknown_reason.py` is stdlib-only, imports neither the API
  application nor the worker, and defines one closed string set:
  `too_few_observations`, `gate_unavailable`, `legacy_unspecified` (emitted
  today) and `black_frame`, `slate_frame`, `frozen_frame` (reserved for #700).
  It exposes the value constants, an ordered tuple, frozensets
  (`UNKNOWN_REASON_SET`, `EMITTED_UNKNOWN_REASONS`,
  `RESERVED_UNKNOWN_REASONS`) and `is_unknown_reason()`.
- R-2: the worker attaches the reason *inside* `measurement_meta` of the
  SELECTED measurement only, using a release-relative, cwd-independent import
  of the shared module (`Path(__file__).resolve().parents[1] / "api" / "app"`).
- R-3: the worker reason mapping is exactly the per-path table below; a
  measured or incomplete result carries no reason, and an unknown reason never
  survives promotion to a known status.
- R-4: `worker/worker_transport.py` appends ` unknown_reason=<value>` to the
  existing `POST passage ok` success log only when a reason is present.
- R-5: the API boundary accepts old writes with no reason; rejects a newly
  supplied `measurement_meta.unknown_reason` that is not a member of the closed
  set (non-string or unknown value → HTTP 400); and on read supplies
  `legacy_unspecified` for an `unknown` row without a recorded valid reason,
  while dropping any reason from a known-status row. Stored history is never
  rewritten.
- R-6: the existing rank-merge rule is unchanged: a late `unknown` write never
  demotes a `measured` row, and its `measurement_meta` (and reason) is not
  adopted over the measured row's metadata.
- R-7: `api/app/unknown_reason.py` ships in the vps, ubuntu-worker and edge
  required inventories (the edge bundle still ships `worker/water_passage.py`)
  in both quality scripts, and is mirrored through every module touchpoint of
  `deploy/vps/deploy.sh` (target, `release_complete`, download/install loop,
  bootstrap capture, `.next` staging, activation and rollback removal).
- R-8: #700's `black_frame`, `slate_frame` and `frozen_frame` are part of the
  closed set so readers already accept them, but #697 does NOT emit them; a
  #700 release can start emitting without a second vocabulary change.

## Per-path reason table

| Worker path | Condition | `speed_status` | `unknown_reason` |
|---|---|---|---|
| `_PassageState.measurement` default | initial passage, no measurement yet | unknown | `too_few_observations` |
| `_PassageState.calibrated_measurement` default | initial calibrated fallback | unknown | `too_few_observations` |
| `TwoGateSpeedEstimator.__init__` result | initial two-gate result | unknown | `too_few_observations` |
| `TwoGateSpeedEstimator.update` (disabled) | gate disabled or geometry/distance unusable, observation seen | unknown | `gate_unavailable` |
| `TwoGateSpeedEstimator.update` (measuring) | gate enabled, crossing progress incomplete | measuring | none |
| `TwoGateSpeedEstimator.update` (measured) | both gates crossed | measured | none |
| `TwoGateSpeedEstimator.finalize` | gate disabled/unusable | unknown | `gate_unavailable` |
| `TwoGateSpeedEstimator.finalize` | gate enabled, zero observations | unknown | `too_few_observations` |
| `TwoGateSpeedEstimator.finalize` | gate enabled, observations but no completed pair | incomplete | none (unchanged) |
| calibrated update/finalize | samples below threshold | measuring/incomplete | none |
| calibrated update/finalize | median reached | measured | none |

Selection note: only the SELECTED result is described. A reason is never
borrowed from a discarded candidate, and selecting a measured calibrated
result discards any unknown reason from the gate candidate.

## Additive JSON contract

- The reason lives inside the existing `measurement_meta` object, at
  `measurement_meta.unknown_reason`; there is no new database column, no new
  top-level passage field, and no UI change.
- `measurement_meta` is already JSON-serialized to
  `water_passages.measurement_meta_json`, so the addition is
  schema-compatible and size-bounded by the existing 8192-byte guard.
- The field is optional on the write path (old workers omit it) and present on
  the read path for every `unknown` row (recorded reason else
  `legacy_unspecified`).
- The vocabulary is closed; reserved #700 values are accepted but not emitted.

## Legacy policy

- Accept old writes with no reason (absent is valid).
- On read, an `unknown` row without a recorded valid reason is presented with
  `legacy_unspecified` in the returned dict only.
- Storage/history is never rewritten: no migration, no backfill, no update of
  existing rows.
- The write response also reflects the inferred reason: because the API returns
  the persisted row through the same read-normalization path, a POST that omits
  the reason comes back with `legacy_unspecified` while the stored history is
  left unchanged.
- A row promoted to a known status never surfaces a reason.

## Gherkin scenarios

```gherkin
Feature: Typed reason for an unknown speed status

  Rule: The worker explains every unknown status it produces
    Scenario: Too few observations
      Given a usable two-gate geometry
      And a vessel passage with observations but no completed gate pair
      When the passage is still tracking or is finalized
      Then measurement_meta.unknown_reason is "too_few_observations"

    Scenario: Gate unavailable
      Given a disabled or unusable two-gate geometry
      And a vessel has been observed
      When the worker publishes the measurement
      Then the speed status is "unknown"
      And measurement_meta.unknown_reason is "gate_unavailable"

  Rule: A known status never carries a reason
    Scenario: Promotion to measured
      Given a passage whose gate later measures a speed
      When the measurement is published
      Then speed_status is "measured"
      And measurement_meta has no unknown_reason

  Rule: The API boundary is backward compatible and closed
    Scenario: Legacy unknown row
      Given a stored unknown passage written before issue 697
      When the passage is read through the API
      Then the response carries unknown_reason "legacy_unspecified"
      And the stored row is unchanged

    Scenario: Invalid supplied reason
      Given a POST that supplies measurement_meta.unknown_reason "made_up"
      When the API validates the payload
      Then the write is rejected with HTTP 400

    Scenario: Late unknown cannot demote a measured row
      Given a measured passage with a known speed
      When a late unknown write for the same passage arrives
      Then speed_status remains "measured"
      And no unknown_reason is present
```

## Acceptance criteria

- AC-001: the closed vocabulary module exists, is stdlib-only, and exposes the
  emitted values, the reserved #700 values, the set/tuple/frozensets and
  `is_unknown_reason()`.
- AC-002: worker initial/default/disabled-gate/finalize paths emit exactly the
  per-path table reasons (`too_few_observations` / `gate_unavailable`), with
  `incomplete` left unchanged.
- AC-003: measured/measuring results carry no `unknown_reason`, and a measured
  calibrated result wins without inheriting a reason from a discarded gate
  candidate.
- AC-004: the worker `POST passage ok` log appends ` unknown_reason=<value>`
  only when present.
- AC-005: the API rejects a non-string or non-enum supplied reason with HTTP
  400 while continuing to accept writes with no reason.
- AC-006: the API read path supplies `legacy_unspecified` for an unknown row
  without a valid recorded reason and never rewrites stored history.
- AC-007: the rank-merge rule is unchanged: a late unknown cannot demote a
  measured row or attach a reason to it.
- AC-008: `api/app/unknown_reason.py` is in the vps, ubuntu-worker and edge
  required inventories and every `deploy/vps/deploy.sh` module site, and the
  exact-artifact build + validate plus convergence check are green.

## Runtime feedback

- RF-001: operator actions expected: 0 — both active contours (VPS API and
  Ubuntu Worker) ride the normal release lanes. Runtime acceptance is
  exact-head CI green, then the lane-A VPS deploy probe (`GET
  /sea-speed/api/passages` shows `unknown_reason` on unknown rows) and the
  Ubuntu worker update/progression gate.
- RF-002: additive, observable-only change: stored rows and the passage
  payload shape are otherwise unchanged; the only delta is the
  `measurement_meta.unknown_reason` value on unknown statuses.

## NFR assessment

- NFR-001 | Area: Observability | Target: every unknown speed status carries exactly one typed reason from the closed set, with legacy rows readable as legacy_unspecified | Validation: per-path unit scenarios plus API read/write boundary scenarios (test worker) | Evidence: tests/test_697_typed_unknown_reason.py — 35 passed, 58 subtests passed, 0 failed; worker/API wiring recorded in plan.md | Status: PASS
- NFR-002 | Area: Compatibility | Target: additive JSON only — no new column, no top-level field, no UI change; old writes without a reason keep working and history is never rewritten | Validation: boundary scenarios for absent reason, invalid reason and legacy read; diff inspection of the storage schema | Evidence: tests/test_697_typed_unknown_reason.py — 35 passed, 58 subtests passed, 0 failed; water_passages.py validation/read diff; no schema change | Status: PASS
- NFR-003 | Area: Operability | Target: the shared vocabulary ships on every contour that can load water_passage.py and is mirrored through every deploy touchpoint | Validation: exact-artifact build+validate, edge archive inventory, deploy convergence check | Evidence: build/validate and convergence output recorded in plan.md | Status: PASS
