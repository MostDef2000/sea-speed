#!/usr/bin/env python3
"""Static Ubuntu compatibility contract for the Sea Speed worker.

This check is intentionally dependency-free. It validates source-level contracts
that can be proven before the physical Ubuntu worker host exists.

Issue #397 wave 2: the worker is a multi-file module. The contract below is
enforced across every worker source file in MODULE_SOURCES (the gate-side
mirror of tests/support/worker_source.py DEFAULT_WORKER_SOURCES). Scans are
unions across all files, so a required call site satisfies the contract from
whichever module it lives in. A missing source file fails closed (gate
validity): the scan never silently narrows to the files that happen to exist.
`--worker` remains an explicit single-file debug override only.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKER = ROOT / "worker" / "hls_motion_yolo_worker_events.py"

MODULE_SOURCES = (
    ROOT / "worker" / "hls_motion_yolo_worker_events.py",
    ROOT / "worker" / "worker_media.py",
)

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


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def inspect_worker(path: Path | list[Path] | tuple[Path, ...]) -> dict[str, object]:
    paths = (path,) if isinstance(path, Path) else tuple(path)
    if not paths:
        raise SystemExit("no worker sources given")

    for source_path in paths:
        if not source_path.is_file():
            raise SystemExit(f"worker source not found: {source_path}")

    imports: set[str] = set()
    calls: list[ast.Call] = []
    string_literals: list[str] = []
    sources: list[str] = []

    for source_path in paths:
        source = source_path.read_text(encoding="utf-8-sig")
        sources.append(source)
        tree = ast.parse(source, filename=str(source_path))

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
        "worker": ", ".join(display_path(p) for p in paths),
        "uses_pathlib": "pathlib" in imports,
        "uses_subprocess": "subprocess" in imports,
        "subprocess_uses_argument_list": subprocess_uses_argument_list,
        "required_environment_names_present": sorted(REQUIRED_ENV_NAMES & env_names),
        "missing_required_environment_names": sorted(REQUIRED_ENV_NAMES - env_names),
        "forbidden_markers": sorted(
            marker
            for marker in FORBIDDEN_SOURCE_MARKERS
            if any(marker in source for source in sources)
            or marker in string_literals
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
    parser.add_argument("--worker", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.worker is not None:
        worker = args.worker.resolve()
        if not worker.is_file():
            raise SystemExit(f"worker source not found: {worker}")
        sources: list[Path] = [worker]
    else:
        missing = [p for p in MODULE_SOURCES if not p.is_file()]
        if missing:
            raise SystemExit(
                "worker source(s) missing from checked-out tree: "
                + ", ".join(str(p) for p in missing)
            )
        sources = [p.resolve() for p in MODULE_SOURCES]

    findings = inspect_worker(sources)
    if args.json:
        print(json.dumps(findings, indent=2, sort_keys=True))
    else:
        for key, value in findings.items():
            print(f"{key}={value}")

    return 0 if findings["compatible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
