#!/usr/bin/env python3
"""Fail closed unless Sea Speed production source protection is active."""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


class SourceProtectionError(ValueError):
    pass


def github_json(url: str, token: str | None = None) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sea-speed-source-protection",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise SourceProtectionError(f"unexpected GitHub response from {url}")
    return payload


def normalized_contexts(branch: dict[str, Any]) -> set[str]:
    protection = branch.get("protection")
    if not isinstance(protection, dict):
        return set()
    required = protection.get("required_status_checks")
    if not isinstance(required, dict):
        return set()
    contexts: set[str] = set()
    for value in required.get("contexts") or []:
        if isinstance(value, str) and value.strip():
            contexts.add(value.strip())
    for item in required.get("checks") or []:
        if isinstance(item, dict):
            value = item.get("context")
            if isinstance(value, str) and value.strip():
                contexts.add(value.strip())
    expanded = set(contexts)
    for context in contexts:
        if "/" in context:
            expanded.add(context.rsplit("/", 1)[-1].strip())
    return expanded


def validate_source_state(
    repository: dict[str, Any],
    branch: dict[str, Any],
    *,
    required_contexts: tuple[str, ...] = (),
) -> None:
    if repository.get("private") is not False or repository.get("visibility") != "public":
        raise SourceProtectionError("production repository must be public on the GitHub Free control plane")
    if branch.get("name") != "main":
        raise SourceProtectionError("production source branch must be main")
    if branch.get("protected") is not True:
        raise SourceProtectionError("main branch protection is not active")
    observed = normalized_contexts(branch)
    missing = [context for context in required_contexts if context not in observed]
    if missing:
        raise SourceProtectionError(
            "main branch protection is missing required status checks: " + ", ".join(missing)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, help="owner/name")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--require-context", action="append", default=[])
    args = parser.parse_args()
    if args.branch != "main":
        print("ERROR: production source-protection verifier only admits main", file=sys.stderr)
        return 2
    token = os.environ.get("GITHUB_TOKEN", "").strip() or None
    base = f"https://api.github.com/repos/{args.repository}"
    try:
        repository = github_json(base, token)
        branch = github_json(f"{base}/branches/{args.branch}", token)
        validate_source_state(repository, branch, required_contexts=tuple(args.require_context))
    except (SourceProtectionError, urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    contexts = sorted(normalized_contexts(branch))
    print(
        "Source protection verified: "
        f"repository={args.repository} visibility=public branch=main protected=true "
        f"required_contexts={','.join(args.require_context) or 'none'} "
        f"observed_contexts={','.join(contexts) or 'unknown'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
