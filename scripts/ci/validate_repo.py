#!/usr/bin/env python3
"""Repository validation entrypoint for Sea Speed CI."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALLOWED_TOP_LEVEL = {
    ".github",
    ".gitignore",
    "README.md",
    "api",
    "contracts",
    "deploy",
    "docs",
    "frontend",
    "scripts",
    "skills",
    "worker",
}

REQUIRED_FILES = {
    "README.md",
    "api/app/main.py",
    "frontend/sea-speed/index.html",
    "worker/hls_motion_yolo_worker_events.py",
    "contracts/SEA_SPEED_GOVERNANCE.md",
    "contracts/SEA_SPEED_DELIVERY_POLICY.md",
    "contracts/runtime/SEA_SPEED_TASK_RUNTIME.md",
    "contracts/runtime/RELEASE_READINESS_GATE.md",
}

FORBIDDEN_DIRECTORY_NAMES = {
    ".venv",
    "venv",
    "__pycache__",
    "output",
    "snapshots",
    "overlays",
}

FORBIDDEN_PATH_PREFIXES = {
    "worker/runtime",
    "worker/events",
    "worker/output",
    "api/data",
    "api/media",
}

FORBIDDEN_FILENAMES = {
    ".env",
    ".env.local",
}

FORBIDDEN_SUFFIXES = {
    ".engine",
    ".jpeg",
    ".jpg",
    ".log",
    ".mkv",
    ".mp4",
    ".onnx",
    ".png",
    ".pt",
    ".pyc",
}

SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "hard-coded Sea Speed token": re.compile(
        r"(?im)^\s*(?:set\s+\"?)?SEA_SPEED_API_TOKEN\s*=\s*[^\s\"']+"
    ),
    "hard-coded HLS auth": re.compile(
        r"(?im)^\s*(?:set\s+\"?)?HLS_BASIC_AUTH_BASE64\s*=\s*[^\s\"']+"
    ),
}

TEXT_SUFFIXES = {
    ".cmd",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".txt",
    ".yaml",
    ".yml",
}


class HtmlStructureValidator(HTMLParser):
    """Track essential document elements and inline scripts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.has_html = False
        self.has_head = False
        self.has_body = False
        self.inline_scripts: list[str] = []
        self._script_buffer: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "html":
            self.has_html = True
        elif tag == "head":
            self.has_head = True
        elif tag == "body":
            self.has_body = True
        elif tag == "script":
            attributes = dict(attrs)
            if not attributes.get("src"):
                self._script_buffer = []

    def handle_data(self, data: str) -> None:
        if self._script_buffer is not None:
            self._script_buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._script_buffer is not None:
            self.inline_scripts.append("".join(self._script_buffer))
            self._script_buffer = None


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]


def validate_paths(files: list[Path]) -> None:
    missing = sorted(path for path in REQUIRED_FILES if not (ROOT / path).is_file())
    if missing:
        fail("required files are missing: " + ", ".join(missing))

    for path in files:
        top = path.parts[0]
        if top not in ALLOWED_TOP_LEVEL:
            fail(f"unexpected top-level path: {path}")

        normalized = path.as_posix().lower()
        directory_parts = {part.lower() for part in path.parts[:-1]}

        if path.name.lower() in FORBIDDEN_FILENAMES:
            fail(f"local environment file is tracked: {path}")

        if directory_parts & FORBIDDEN_DIRECTORY_NAMES:
            fail(f"runtime or local directory is tracked: {path}")

        if any(normalized == prefix or normalized.startswith(prefix + "/") for prefix in FORBIDDEN_PATH_PREFIXES):
            fail(f"runtime data path is tracked: {path}")

        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            fail(f"forbidden generated or binary artifact is tracked: {path}")


def validate_python(files: list[Path]) -> None:
    python_files = [path for path in files if path.suffix.lower() == ".py"]
    for path in python_files:
        full_path = ROOT / path
        try:
            source = full_path.read_text(encoding="utf-8-sig")
            compile(source, str(path), "exec")
        except (SyntaxError, UnicodeDecodeError) as exc:
            fail(f"Python syntax failed for {path}: {exc}")


def validate_frontend() -> None:
    html_path = ROOT / "frontend/sea-speed/index.html"
    parser = HtmlStructureValidator()
    try:
        parser.feed(html_path.read_text(encoding="utf-8-sig"))
        parser.close()
    except Exception as exc:
        fail(f"HTML parsing failed: {exc}")

    if not (parser.has_html and parser.has_head and parser.has_body):
        fail("frontend HTML must contain html, head and body elements")

    with tempfile.TemporaryDirectory(prefix="sea-speed-js-") as temp_dir:
        for index, script in enumerate(parser.inline_scripts, start=1):
            if not script.strip():
                continue
            script_path = Path(temp_dir) / f"inline-{index}.js"
            script_path.write_text(script, encoding="utf-8")
            result = subprocess.run(
                ["node", "--check", str(script_path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            if result.returncode != 0:
                details = (result.stderr or result.stdout).strip()
                fail(f"JavaScript syntax failed for inline script {index}: {details}")


def validate_secrets(files: list[Path]) -> None:
    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"README.md", ".gitignore"}:
            continue

        full_path = ROOT / path
        try:
            content = full_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            fail(f"text file is not valid UTF-8: {path}")

        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                fail(f"possible {label} detected in {path}")


def main() -> int:
    files = tracked_files()
    validate_paths(files)
    validate_python(files)
    validate_frontend()
    validate_secrets(files)

    print("Sea Speed repository validation passed")
    print(f"Tracked files checked: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
