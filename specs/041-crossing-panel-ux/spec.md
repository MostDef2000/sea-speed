# Spec: Crossing panel UX refinements

- Issue: #271
- Status: ACTIVE
- Runtime contour: VPS

## Product outcome

Crossing panel UX refinements on both main screens: «Отменить точку» becomes «Удалить линию», fully clearing the line and persisting the disabled empty state so the worker has nothing to cross; «Выключить» becomes a dynamic toggle showing «Включить» when disabled (activating the saved line) and «Выключить» when enabled.

## User scenarios

- Operator clicks «Удалить линию»: the drawn line disappears locally and the server config is updated to disabled/empty, stopping counting.
- Operator sees «Включить» after disabling; pressing it re-activates the saved line without redrawing.
- If no line exists, «Включить» explains that a line must be drawn first.

## Runtime feedback

- Config changes apply to workers within the existing 5-second config refresh window.
- Panel status text reflects each action result immediately.

## Requirements

- R1: Delete-line action clears local points and persists `{enabled:false, line:[]}`.
- R2: Toggle button label mirrors config state and switches between enable/disable semantics.
- R3: Enable without a saved line is rejected with explanatory status text.

## NFR assessment

- NFR-041-001 | Area: usability | Target: button labels and states match operator intent without extra clicks | Validation: UI-contract source pins | Evidence: tests/test_line_crossing.py::CrossingPanelUiTests | Status: PASS
- NFR-041-002 | Area: compatibility | Target: crossing-line API contract unchanged | Validation: existing API tests stay green | Evidence: full unittest discovery | Status: PASS

## Acceptance criteria

- AC-001: Crossing panel shows «Удалить линию»; activating it clears the line and persists disabled empty state.
- AC-002: Toggle button shows «Включить» when disabled and activates the saved line on press; shows «Выключить» when enabled.
- AC-003: Enable without a saved line shows explanatory status and does not call the API with an invalid payload.
