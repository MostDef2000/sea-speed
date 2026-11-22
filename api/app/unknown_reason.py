"""Closed vocabulary of typed reasons for an unknown vessel speed status.

Issue #697: every persisted passage whose ``speed_status`` is ``unknown`` must
carry an explicit, machine-readable reason inside ``measurement_meta`` so an
operator can tell "not enough evidence yet" apart from "the speed gate is not
configured". The vocabulary is a *closed* set: the worker only emits the
values defined here and the API rejects anything outside it.

This module is the single source of truth for both runtime contours. By
contract it is stdlib-only: it imports neither the API application nor the
worker, so the VPS release, the Ubuntu Worker release and the archival edge
bundle all ship and load the exact same bytes.

Issue #700 will add frame-quality reasons. ``black_frame``, ``slate_frame``
and ``frozen_frame`` are RESERVED here (already part of the closed set so
older readers reject nothing and newer writers do not need a second release),
but #697 does NOT emit them.
"""

from __future__ import annotations

# Emitted by the worker today (issue #697).
TOO_FEW_OBSERVATIONS = "too_few_observations"
GATE_UNAVAILABLE = "gate_unavailable"
# Applied by the API on read for legacy rows that predate #697. Never written
# back to storage: history is not rewritten.
LEGACY_UNSPECIFIED = "legacy_unspecified"

# Reserved for issue #700 frame-quality explanations. Part of the closed set,
# deliberately NOT emitted by #697.
BLACK_FRAME = "black_frame"
SLATE_FRAME = "slate_frame"
FROZEN_FRAME = "frozen_frame"

# The complete closed set (accepted by the API boundary).
UNKNOWN_REASONS = (
    TOO_FEW_OBSERVATIONS,
    GATE_UNAVAILABLE,
    LEGACY_UNSPECIFIED,
    BLACK_FRAME,
    SLATE_FRAME,
    FROZEN_FRAME,
)
UNKNOWN_REASON_SET = frozenset(UNKNOWN_REASONS)

# Values the #697 worker is allowed to emit; #700 extends this set.
EMITTED_UNKNOWN_REASONS = frozenset(
    {TOO_FEW_OBSERVATIONS, GATE_UNAVAILABLE, LEGACY_UNSPECIFIED}
)
RESERVED_UNKNOWN_REASONS = frozenset({BLACK_FRAME, SLATE_FRAME, FROZEN_FRAME})

__all__ = [
    "TOO_FEW_OBSERVATIONS",
    "GATE_UNAVAILABLE",
    "LEGACY_UNSPECIFIED",
    "BLACK_FRAME",
    "SLATE_FRAME",
    "FROZEN_FRAME",
    "UNKNOWN_REASONS",
    "UNKNOWN_REASON_SET",
    "EMITTED_UNKNOWN_REASONS",
    "RESERVED_UNKNOWN_REASONS",
    "is_unknown_reason",
]


def is_unknown_reason(value: object) -> bool:
    """Return True only for a string member of the closed reason set."""
    return isinstance(value, str) and value in UNKNOWN_REASON_SET
