#!/usr/bin/env python3
"""Static Ubuntu compatibility contract for the Sea Speed worker.

This check is intentionally dependency-free. It validates source-level contracts
that can be proven before the physical Ubuntu worker host exists.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKER = ROOT / "worker" / "hls_motion_yolo_worker_events.py"

REQUIRED_ENV_NAMES = {
    "HLS_URL",
    "SEA_SPEED_API_URL",
    "SEA_SPEED_API_TOKEN",
    "MODEL_NAME",
}

FORBIDDEN_SOURCE_MARKERS = (
    "D:\\\\sea-speed",
    "C:\\\\",
    "powershell.exe",
    "cmd.exe",
    "run_event_worker_forever.cmd",
)


def inspect_worker(path: Path) -> dict[str, object]:
    source = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(source, filename=str(path))

    imports = set()
    calls: list[ast.Call] = []
    string_literals: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Call):
            calls.append(node)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            string_literals.append(node.value)

    env_names = {
        node.args[0].value
        for node in calls
        if isinstance(node.func, ast.Name)
        and node.func.id in {"env_str", "env_int", "env_float"}
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }

    subprocess_uses_argument_list = any(
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "Popen"
        and node.args
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "cmd"
        for node in calls
    )

    findings = {
        "worker": str(path.relative_to(ROOT)),
        "uses_pathlib": "pathlib" in imports,
        "uses_subprocess": "subprocess" in imports,
        "subprocess_uses_argument_list": subprocess_uses_argument_list,
        "required_environment_names_present": sorted(REQUIRED_ENV_NAMES & env_names),
        "missing_required_environment_names": sorted(REQUIRED_ENV_NAMES - env_names),
        "forbidden_markers": sorted(
            marker
            for marker in FORBIDDEN_SOURCE_MARKERS
            if marker in source or marker in string_literals
        ),
    }
    findings["compatible"] = bool(
        findings["uses_pathlib"]
        and findings["uses_subprocess"]
        and findings["subprocess_uses_argument_list"]
        and not findings["missing_required_environment_names"]
        and not findings["forbidden_markers"]
    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path, default=DEFAULT_WORKER)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    worker = args.worker.resolve()
    if not worker.is_file():
        raise SystemExit(f"worker source not found: {worker}")

    findings = inspect_worker(worker)
    if args.json:
        print(json.dumps(findings, indent=2, sort_keys=True))
    else:
        for key, value in findings.items():
            print(f"{key}={value}")

    return 0 if findings["compatible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
