#!/usr/bin/env python3
"""Validate aggregate-gate and controlled-deployment workflow policy."""
from __future__ import annotations

import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.quality.common import repository_root


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    root = repository_root()
    quality_path = root / ".github/workflows/quality-integration.yml"
    deploy_path = root / ".github/workflows/deploy-vps.yml"
    quality = quality_path.read_text(encoding="utf-8-sig")
    deploy = deploy_path.read_text(encoding="utf-8-sig")

    for marker in (
        "name: Quality integration gate",
        "pull_request:",
        "push:",
        "workflow_dispatch:",
        "contents: read",
        "static-contract-security:",
        "property-fuzz-reliability:",
        "exact-artifact-e2e:",
        "release-deployment-evidence:",
        "quality-integration:",
        "if: always()",
    ):
        if marker not in quality:
            fail(f"quality workflow marker missing: {marker}")
    if re.search(r"^\s+paths(?:-ignore)?:", quality, re.MULTILINE):
        fail("aggregate workflow must not use path filters")
    aggregate_block = quality[quality.index("  quality-integration:"):]
    for dependency in (
        "static-contract-security",
        "property-fuzz-reliability",
        "exact-artifact-e2e",
        "release-deployment-evidence",
    ):
        if dependency not in aggregate_block:
            fail(f"aggregate job does not depend on {dependency}")

    on_block = deploy.split("permissions:", 1)[0]
    if "workflow_dispatch:" not in on_block:
        fail("VPS deployment must be manually dispatched")
    if re.search(r"^\s{2}(push|pull_request):", on_block, re.MULTILINE):
        fail("VPS production deployment must not run on push or pull request")
    for marker in (
        "commit_sha:",
        "required: true",
        "environment: production",
        "verify_quality_status.py",
        "--required-name quality-integration",
        "Build exact deployment artifacts",
        "Build and validate quality evidence",
    ):
        if marker not in deploy:
            fail(f"controlled deployment marker missing: {marker}")

    allowed_actions = {"actions/checkout", "actions/setup-python", "actions/setup-node", "actions/upload-artifact"}
    for workflow_path in (quality_path, deploy_path):
        text = workflow_path.read_text(encoding="utf-8-sig")
        for match in re.finditer(r"uses:\s*([^@\s]+)@", text):
            action = match.group(1)
            if action not in allowed_actions:
                fail(f"unapproved action {action} in {workflow_path}")

    print("Workflow policy valid: aggregate gate always runs; deployment is explicit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
