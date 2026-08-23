# Spec: Crossing speed in registry + top-5 overlay counter classes

- Issue: #276
- Status: ACTIVE
- Runtime contour: MIXED

## Product outcome

Crossing posts carry the tracked object measured speed_kmh through canonical /crossings ingest into the objects registry, so line_crossing rows show real speeds instead of em-dash. The worker overlay counter block shows up to 5 classes instead of 3 so person is not displaced by car/bus/truck.

## User scenarios

- A car crosses the counting line at measured speed: the registry row created from the crossing shows the real km/h value on its card badge and in the edit field.
- The overlay counter block lists person alongside car/bus/truck (top-5 by total).

## Runtime feedback

- Speed values come from the already-computed detection field; no formula changes.
- Registry cards render speed via the existing speed-badge mechanism.

## Requirements

- R1: update_crossing_counts includes det speed_kmh in the crossing payload.
- R2: post_analytics_crossing persists speed_kmh into the record (registry row + store).
- R3: Overlay counter block renders up to 5 classes sorted by total.

## NFR assessment

- NFR-043-001 | Area: correctness | Target: line_crossing registry rows carry measured speed when available | Validation: unit tests for payload and persistence | Evidence: tests/test_line_crossing.py | Status: PASS
- NFR-042-002 | Area: compatibility | Target: speed formulas untouched; water passages unaffected | Validation: regression suites green | Evidence: full unittest discovery | Status: PASS

## Acceptance criteria

- AC-001: Crossing payload carries det speed_kmh.
- AC-002: Ingest with speed_kmh persists it into the registry record and store.
- AC-003: Overlay counter block shows up to 5 classes.
