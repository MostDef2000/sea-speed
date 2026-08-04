#!/usr/bin/env python3
"""Shared deterministic helpers for Sea Speed quality checks."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:api[_-]?token|password|secret)\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
)
RETRY_ONLY_FIELDS = {
    "retry_count",
    "retry_at",
    "delivery_attempt",
    "last_error",
    "sync_status",
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def canonical_json(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_event_identity(event: dict[str, Any]) -> str:
    explicit = event.get("event_id") or event.get("object_id")
    if explicit not in (None, ""):
        return str(explicit)
    business = {key: value for key, value in event.items() if key not in RETRY_ONLY_FIELDS}
    return "derived-" + sha256_bytes(canonical_json(business))[:32]


def safe_media_key(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("media key must be a non-empty string")
    if "\\" in value:
        raise ValueError("media key must use POSIX separators")
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError("media key must remain below the media root")
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValueError("media key must remain below the media root")
    normalized = candidate.as_posix()
    if normalized.startswith("/") or ":" in candidate.parts[0]:
        raise ValueError("media key must be relative")
    return normalized


def validate_schema_instance(instance: Any, schema: dict[str, Any], root_schema: dict[str, Any], path: str = "$") -> list[str]:
    """Validate the intentionally small JSON-Schema subset used by the gate."""
    errors: list[str] = []
    if "$ref" in schema:
        ref = schema["$ref"]
        prefix = "#/$defs/"
        if not isinstance(ref, str) or not ref.startswith(prefix):
            return [f"{path}: unsupported reference {ref!r}"]
        target = root_schema.get("$defs", {}).get(ref[len(prefix):])
        if not isinstance(target, dict):
            return [f"{path}: unresolved reference {ref}"]
        return validate_schema_instance(instance, target, root_schema, path)

    expected = schema.get("type")
    type_ok = {
        "object": isinstance(instance, dict),
        "array": isinstance(instance, list),
        "string": isinstance(instance, str),
        "integer": isinstance(instance, int) and not isinstance(instance, bool),
        "number": isinstance(instance, (int, float)) and not isinstance(instance, bool),
        "boolean": isinstance(instance, bool),
        "null": instance is None,
    }
    if isinstance(expected, list):
        if not any(type_ok.get(item, False) for item in expected):
            return [f"{path}: expected one of {expected}, got {type(instance).__name__}"]
    elif isinstance(expected, str) and not type_ok.get(expected, False):
        return [f"{path}: expected {expected}, got {type(instance).__name__}"]

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value {instance!r} not in enum")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < int(schema["minLength"]):
            errors.append(f"{path}: string shorter than minLength")
        if "maxLength" in schema and len(instance) > int(schema["maxLength"]):
            errors.append(f"{path}: string longer than maxLength")
        if "pattern" in schema and re.fullmatch(str(schema["pattern"]), instance) is None:
            errors.append(f"{path}: string does not match pattern")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: value below minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: value above maximum")
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < int(schema["minItems"]):
            errors.append(f"{path}: too few items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, value in enumerate(instance):
                errors.extend(validate_schema_instance(value, item_schema, root_schema, f"{path}[{index}]"))
    if isinstance(instance, dict):
        required = schema.get("required", [])
        for name in required:
            if name not in instance:
                errors.append(f"{path}: missing required field {name}")
        properties = schema.get("properties", {})
        for name, value in instance.items():
            child = properties.get(name)
            if isinstance(child, dict):
                errors.extend(validate_schema_instance(value, child, root_schema, f"{path}.{name}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected field {name}")
    for option in schema.get("allOf", []):
        errors.extend(validate_schema_instance(instance, option, root_schema, path))
    if "oneOf" in schema:
        matches = [not validate_schema_instance(instance, option, root_schema, path) for option in schema["oneOf"]]
        if sum(matches) != 1:
            errors.append(f"{path}: expected exactly one oneOf branch")
    return errors


def assert_no_secrets(paths: Iterable[Path]) -> None:
    findings: list[str] = []
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(str(path))
                break
    if findings:
        raise ValueError("secret-like values found in evidence: " + ", ".join(sorted(findings)))
