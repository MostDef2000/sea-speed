"""Shared worker-source loader and AST-inspection helpers (issue #398 Wave A, Slice 0).

Issue #398 converts worker-referencing source-text pins (assertIn on the worker
file text) into structural (AST) or behavioral (exec) checks so the #397
decomposition can move worker code between files without false test failures.

This module is the single implementation of the AST function-extract + exec
harness for worker-referencing tests: test_worker_contract.py,
test_line_crossing.py, test_water_detection_pipeline.py, test_worker_roi_pipeline.py,
test_worker_tracking_overlay.py, test_road_event_hygiene.py, test_water_passage.py,
test_analytics_profiles.py, test_frame_quality.py and test_worker_rtsp_media_security.py
all import it — no private copies remain (the last single-file private scan,
test_water_detection_pipeline.load_nodes, was converted to this loader in the
#398 wave A review follow-ups).

Path resolution supports BOTH the current single-file worker layout and a future
multi-file layout: set ``SEA_SPEED_WORKER_SOURCE`` to one or more paths joined by
``os.pathsep`` to retarget the harness without rewriting it (the #397 waves only
need to change the env override or the default list below).
"""
from __future__ import annotations

import ast
import copy
import os
import textwrap
from pathlib import Path
from typing import Any, Iterable, cast

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKER_SOURCES = ("worker/hls_motion_yolo_worker_events.py",)

FunctionLike = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
FunctionDefLike = ast.FunctionDef | ast.AsyncFunctionDef


def worker_source_paths() -> tuple[Path, ...]:
    """Resolve the worker source files the harness parses.

    Env override ``SEA_SPEED_WORKER_SOURCE``: one or more paths separated by
    os.pathsep, resolved against ROOT when relative. Missing files fail closed.
    """
    override = os.environ.get("SEA_SPEED_WORKER_SOURCE", "").strip()
    if override:
        paths: list[Path] = []
        for part in override.split(os.pathsep):
            candidate = Path(part)
            if not candidate.is_absolute():
                candidate = ROOT / candidate
            paths.append(candidate)
    else:
        paths = [ROOT / relative for relative in DEFAULT_WORKER_SOURCES]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise AssertionError(f"worker source file(s) not found: {missing}")
    return tuple(paths)


def module_trees(paths: Iterable[Path] | None = None) -> list[ast.Module]:
    """Parse every resolved worker source file into its own AST module."""
    resolved = tuple(paths) if paths is not None else worker_source_paths()
    return [ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path)) for path in resolved]


def walk_all(trees: Iterable[ast.AST] | None = None) -> Iterable[ast.AST]:
    """Walk every node of every resolved (or given) tree."""
    for tree in module_trees() if trees is None else trees:
        yield from ast.walk(tree)


def extract_nodes(names: set[str], paths: Iterable[Path] | None = None) -> list[FunctionLike]:
    """Collect deep-copied top-level function/class nodes by name across the sources.

    First definition wins across the merged source list, mirroring the proven
    pre-#398 per-test harnesses.
    """
    wanted = set(names)
    selected: list[FunctionLike] = []
    found: set[str] = set()
    for path, tree in zip(worker_source_paths() if paths is None else tuple(paths), module_trees(paths)):
        for node in tree.body:
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.name in wanted
                and node.name not in found
            ):
                selected.append(copy.deepcopy(node))
                found.add(node.name)
    missing = wanted - found
    if missing:
        raise AssertionError(f"missing worker functions: {sorted(missing)}")
    return selected


def load_functions(
    names: set[str],
    namespace: dict[str, Any],
    paths: Iterable[Path] | None = None,
) -> dict[str, Any]:
    """Extract named worker functions and exec them into ``namespace`` (mutated in place).

    Mirrors the proven pre-#398 harness contract: the caller supplies the stub
    namespace (env/requests/cv2/np fakes etc.) and gets the same dict back with
    the extracted functions defined in it.
    """
    selected = extract_nodes(names, paths)
    module = ast.Module(body=cast(list["ast.stmt"], selected), type_ignores=[])
    ast.fix_missing_locations(module)
    sources = worker_source_paths() if paths is None else tuple(paths)
    exec(compile(module, str(sources[0]), "exec"), namespace)
    return namespace


def function_nodes(names: set[str], trees: Iterable[ast.Module] | None = None) -> dict[str, FunctionDefLike]:
    """Locate top-level function nodes by name WITHOUT copying or exec-ing (AST-only checks)."""
    wanted = set(names)
    found: dict[str, FunctionDefLike] = {}
    for tree in module_trees() if trees is None else trees:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted:
                found.setdefault(node.name, node)
    missing = wanted - set(found)
    if missing:
        raise AssertionError(f"missing worker functions: {sorted(missing)}")
    return found


def function_node(name: str, trees: Iterable[ast.Module] | None = None) -> FunctionDefLike:
    """Return the single top-level function node ``name`` (raises if missing)."""
    return function_nodes({name}, trees)[name]


def dump(node: ast.AST) -> str:
    """Normalized structural identity of an AST node (formatting-independent)."""
    return ast.dump(node)


def expr_dump(snippet: str) -> str:
    """Normalized structural identity of a snippet expression (for dump comparisons)."""
    return dump(_snippet_expr(snippet))


def calls_with_constant_arg(scope: ast.AST, name: str, value: Any, index: int = 0) -> list[ast.Call]:
    """Calls to the plain name ``name`` whose positional arg ``index`` is the literal ``value``."""
    matches = []
    for call in calls_named(scope, name):
        if len(call.args) <= index:
            continue
        argument = call.args[index]
        if isinstance(argument, ast.Constant) and argument.value == value:
            matches.append(call)
    return matches


def _snippet_expr(snippet: str) -> ast.expr:
    return ast.parse(textwrap.dedent(snippet).strip(), mode="eval").body  # type: ignore[return-value]


def _snippet_stmts(snippet: str) -> list[ast.stmt]:
    return ast.parse(textwrap.dedent(snippet).strip()).body


def expr_nodes(scope: ast.AST, snippet: str) -> list[ast.expr]:
    """All nodes inside ``scope`` whose normalized AST equals the snippet expression.

    This is the formatting-independent equivalent of a substring search for the
    expression: same sensitivity to semantic edits, immune to whitespace,
    comments, line wrapping and quote style.
    """
    pattern = dump(_snippet_expr(snippet))
    return [node for node in ast.walk(scope) if dump(node) == pattern and isinstance(node, ast.expr)]  # type: ignore[list-item]


def contains_expr(scope: ast.AST, snippet: str) -> bool:
    """True when ``scope`` contains an exact structural match for the snippet expression."""
    return bool(expr_nodes(scope, snippet))


def stmt_dumps(scope: ast.AST, snippet: str) -> list[str]:
    """Normalized dumps of the snippet's statements that appear inside ``scope``.

    Used for multi-line pins (e.g. a 2-line ``if``); every top-level statement
    of the snippet must be matched by some node in the scope. Exact subtree
    equality — an ``if`` body line only matches inside the same ``if``.
    """
    patterns = [dump(statement) for statement in _snippet_stmts(snippet)]
    haystack = {dump(node) for node in ast.walk(scope)}
    return [pattern for pattern in patterns if pattern in haystack]


def contains_stmt(scope: ast.AST, snippet: str) -> bool:
    """True when every statement of the snippet appears structurally inside ``scope``."""
    patterns = [dump(statement) for statement in _snippet_stmts(snippet)]
    haystack = {dump(node) for node in ast.walk(scope)}
    return all(pattern in haystack for pattern in patterns)


def find_stmt(scope: ast.AST, snippet: str) -> list[ast.stmt]:
    """All statement nodes inside ``scope`` matching the single-statement snippet.

    The snippet must contain exactly one top-level statement; the returned
    nodes are the live matches (so callers can assert source order via lineno).
    Multi-statement snippets fail closed — use ``contains_stmt`` for those.
    """
    stmts = _snippet_stmts(snippet)
    if len(stmts) != 1:
        raise AssertionError(
            f"find_stmt snippet must contain exactly one statement, got {len(stmts)}"
        )
    pattern = dump(stmts[0])
    return [node for node in ast.walk(scope) if isinstance(node, ast.stmt) and dump(node) == pattern]


def find_assignments(scope: ast.AST, target: str) -> list[ast.Assign]:
    """All Assign nodes inside ``scope`` assigning to the given name.

    Matches bare-name targets and names inside tuple/list unpacking targets
    (e.g. ``processing_frame, roi_points = ...`` matches both names).
    """
    matches = []
    for node in ast.walk(scope):
        if not isinstance(node, ast.Assign):
            continue
        for target_node in node.targets:
            if isinstance(target_node, ast.Name) and target_node.id == target:
                matches.append(node)
                break
            if isinstance(target_node, (ast.Tuple, ast.List)) and any(
                isinstance(elt, ast.Name) and elt.id == target for elt in target_node.elts
            ):
                matches.append(node)
                break
    return matches


def calls_named(scope: ast.AST, name: str) -> list[ast.Call]:
    """All Call nodes inside ``scope`` whose callee is the given plain name."""
    return [
        node
        for node in ast.walk(scope)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
    ]


def method_calls(scope: ast.AST, obj: str, method: str) -> list[ast.Call]:
    """All Call nodes inside ``scope`` shaped like ``obj.method(...)``."""
    return [
        node
        for node in ast.walk(scope)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == obj
        and node.func.attr == method
    ]


def string_constants(scope: ast.AST) -> list[str]:
    """All string literal values inside ``scope``, including f-string literal parts."""
    values: list[str] = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.append(node.value)
    return values


def joined_string_constants(scope: ast.AST) -> list[str]:
    """Literal (non-interpolated) parts of every f-string inside ``scope``."""
    parts: list[str] = []
    for node in ast.walk(scope):
        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    parts.append(value.value)
    return parts


def tuple_constants(scope: ast.AST) -> list[tuple[Any, ...]]:
    """All literal tuple values inside ``scope`` (overlay colors etc.)."""
    values: list[tuple[Any, ...]] = []
    for node in ast.walk(scope):
        if isinstance(node, ast.Tuple):
            try:
                values.append(tuple(ast.literal_eval(node)))
            except Exception:
                continue
    return values


def references_name(trees: Iterable[ast.Module], name: str) -> bool:
    """True when ``name`` appears as a Name, string constant or attribute in the trees."""
    for node in walk_all(trees):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Constant) and node.value == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
    return False
