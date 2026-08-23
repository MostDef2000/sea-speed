# Spec: Crossing daily sync (VLZ midnight), full-class overlay, registry speed row and crossings period layer

- Issue: #278
- Status: ACTIVE
- Runtime contour: MIXED

## Product outcome

(1) Registry card description shows speed. (2) Overlay counter block shows ALL counted classes. (3) Worker live crossing counters reset at 00:00 Asia/Vladivostok (UTC+10). (4) Crossing panel headline syncs with the AI-camera overlay via state.crossings; panels show the current VLZ day. (5) Objects registry gains a crossings layer with day/period selection (VLZ) backed by summary endpoint date_from/date_to parameters.

## User scenarios

- Operator opens the registry card: speed appears in the description grid, not only on the photo badge.
- All counted classes (car, truck, bus, motorcycle, bicycle, person) are visible in the overlay counter block.
- At Vladivostok midnight the live counters start from zero; panel and overlay agree all day.
- Operator switches the registry to «Пересечения», picks a day or period, and sees per-class directional totals.

## Runtime feedback

- Worker resets counters when the VLZ calendar date changes; pending posts survive the reset.
- Summary endpoint accepts date_from/date_to (YYYY-MM-DD, VLZ days); malformed dates return 400.

## Requirements

- R1: Registry card meta grid includes a speed row.
- R2: Overlay counter renders every class present in by_class without cap.
- R3: maybe_reset_daily_crossings clears counters/by_class/track memory on VLZ date change but preserves pending posts.
- R4: Panel headline and table read state.crossings (identical numbers to the overlay).
- R5: Summary endpoint supports date_from/date_to VLZ-day windows with validation; cam1 alias included.

## NFR assessment

- NFR-044-001 | Area: correctness | Target: reset boundary is exactly VLZ midnight; pending posts never lost | Validation: unit tests with fixed timestamps | Evidence: tests/test_line_crossing.py::VlzDailyResetTests | Status: PASS
- NFR-044-002 | Area: compatibility | Target: rolling-hours summary behavior preserved when no dates supplied | Validation: existing summary tests green | Evidence: tests/test_line_crossing.py::SummaryDateRangeTests | Status: PASS
- NFR-044-003 | Area: usability | Target: period selection defaults to today VLZ and follows the domain toggle | Validation: UI-contract source pins + operator check | Evidence: objects page script | Status: PASS

## Acceptance criteria

- AC-001: Registry card description shows speed.
- AC-002: Overlay counter lists all counted classes.
- AC-003: Live counters reset at VLZ midnight; queued posts survive.
- AC-004: Panel headline equals overlay numbers via state.crossings.
- AC-005: Registry crossings layer aggregates class × direction for a selected VLZ day/period.
