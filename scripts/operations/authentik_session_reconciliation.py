#!/usr/bin/env python3
"""Bounded Authentik session duration reconciliation for Sea Speed.

This helper is intentionally limited to the two Sea Speed login stages. Authentik
blueprints remain the source of truth; this closes the gap where existing
UserLoginStage objects retain previous attributes after a successful blueprint
apply.
"""
from __future__ import annotations

import sys

TARGETS = (
    "sea-speed-authentication-login",
    "sea-speed-enrollment-login",
)
TARGET_DURATION = "days=30"


def reconcile(stages) -> int:
    changed = 0
    for stage in stages:
        if stage.name in TARGETS and str(stage.session_duration) != TARGET_DURATION:
            stage.session_duration = TARGET_DURATION
            stage.save(update_fields=["session_duration"])
            changed += 1
    return changed


def verify(stages) -> None:
    values = {stage.name: str(stage.session_duration) for stage in stages if stage.name in TARGETS}
    missing = [name for name in TARGETS if name not in values]
    if missing:
        raise RuntimeError(f"missing stages: {','.join(missing)}")
    failed = [name for name, value in values.items() if value != TARGET_DURATION]
    if failed:
        raise RuntimeError(f"unexpected session duration: {','.join(failed)}")


if __name__ == "__main__":
    sys.exit("This module is imported by the bounded Authentik deployment path")
