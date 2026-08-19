#!/usr/bin/env python3
"""Retired compatibility tombstone for the former per-release authorization verifier.

Active production execution uses standing delegation and
`scripts/release/evaluate_production_policy.py`. This historical path is retained
only because the canonical contract inventory requires the file to remain
addressable. It deliberately cannot authorize or verify a production release.
"""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "ERROR: per-release production authorization verification is retired; "
        "use standing production policy evaluation",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
