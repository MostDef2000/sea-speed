from __future__ import annotations

import ast
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
ENTRYPOINT = WORKER / "ubuntu_worker_entrypoint.py"
AI_CHILD = WORKER / "ubuntu_ai_inference_worker.py"


# Issue #573: parsed-structure twin helpers (ast.parse) — refactor-blind where
# the raw source-line pins false-failed on comments/whitespace.
def _parse_source(source: str, filename: str) -> ast.Module:
    return ast.parse(source, filename=filename)


def _parse_module(path: Path) -> ast.Module:
    return _parse_source(path.read_text(encoding="utf-8"), str(path))


def _find_function_def(
    tree: ast.Module, name: str, *, class_name: str | None = None
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Return the unique FunctionDef `name` (a method of `class_name` when given)."""
    if class_name is None:
        scope = tree.body
        where = "module top level"
    else:
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name]
        if len(classes) != 1:
            raise AssertionError(f"expected exactly one class {class_name}, found {len(classes)}")
        scope = classes[0].body
        where = f"class {class_name}"
    functions = [
        node
        for node in scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if len(functions) != 1:
        raise AssertionError(f"expected exactly one def {name} at {where}, found {len(functions)}")
    return functions[0]


def _parameter_facts(func: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, ast.expr | None]:
    """Map each declared parameter name to its default expression (None if none).

    Insertion order follows declaration order (positional, then keyword-only);
    *args/**kwargs carry no pinned contract here.
    """
    args = func.args
    facts: dict[str, ast.expr | None] = {}
    positional = list(args.posonlyargs) + list(args.args)
    offset = len(positional) - len(args.defaults)
    for index, arg in enumerate(positional):
        facts[arg.arg] = args.defaults[index - offset] if index >= offset else None
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        facts[arg.arg] = default
    return facts


class _Scalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class _Vector:
    def __init__(self, values):
        self.values = list(values)

    def tolist(self):
        return list(self.values)


class _Box:
    def __init__(self, cls_id: int, confidence: float, xyxy):
        self.cls = [_Scalar(cls_id)]
        self.conf = [_Scalar(confidence)]
        self.xyxy = [_Vector(xyxy)]


class _TrackIds:
    def __init__(self, values):
        self.values = [_Scalar(value) for value in values]

    def __getitem__(self, index):
        return self.values[index]


class _Boxes(list):
    pass


class _Result:
    def __init__(self):
        boxes = _Boxes(
            [
                _Box(0, 0.81234, [10.2, 20.3, 110.4, 80.8]),
                _Box(1, 0.45678, [120.0, 30.0, 180.0, 90.0]),
            ]
        )
        boxes.id = _TrackIds([41, 42])
        self.boxes = boxes
        self.names = {0: "boat", 1: "car"}


def _load_child_module():
    sys.path.insert(0, str(WORKER))
    try:
        spec = importlib.util.spec_from_file_location("water_recall_ai_child", AI_CHILD)
        if spec is None or spec.loader is None:
            raise RuntimeError("unable to load ubuntu AI child")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        try:
            sys.path.remove(str(WORKER))
        except ValueError:
            pass


class WaterRecallUbuntuIpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.child = _load_child_module()

    def test_child_side_channel_preserves_accepted_detection_semantics(self) -> None:
        results = [_Result()]
        legacy = self.child.serialize_detections(results, "water-v1")
        accepted, diagnostics = self.child.serialize_detection_batch(results, "water-v1")

        self.assertEqual(accepted, legacy)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(
            accepted[0],
            {
                "track_id": 41,
                "analytics_profile": "water-v1",
                "domain": "water",
                "object_type": "vessel",
                "model_class": "boat",
                "class_name": "vessel",
                "confidence": 0.81234,
                "bbox_xyxy": [10, 20, 110, 81],
            },
        )

        self.assertEqual(len(diagnostics), 2)
        accepted_diag, rejected_diag = diagnostics
        self.assertTrue(accepted_diag["class_mapping_accepted"])
        self.assertEqual(accepted_diag["semantic_class"], "vessel")
        self.assertEqual(accepted_diag["track_id"], 41)
        self.assertEqual(accepted_diag["bbox_width_px"], 100)
        self.assertEqual(accepted_diag["bbox_height_px"], 61)
        self.assertEqual(accepted_diag["bbox_area_px"], 6100)

        self.assertEqual(rejected_diag["model_class"], "car")
        self.assertFalse(rejected_diag["class_mapping_accepted"])
        self.assertIsNone(rejected_diag["semantic_class"])
        self.assertEqual(rejected_diag["track_id"], 42)
        self.assertNotIn(rejected_diag, accepted)

    def test_parent_supervisor_accepts_optional_diagnostic_sink(self) -> None:
        # Issue #573: parsed-structure twin (ast.parse) — refactor-blind where
        # the raw source-line pins false-failed on comments/whitespace.
        tree = _parse_module(ENTRYPOINT)
        # def supervised_detect_vehicles(_model, frame, diagnostics=None):
        wrapper = _find_function_def(tree, "supervised_detect_vehicles")
        facts = _parameter_facts(wrapper)
        self.assertEqual(list(facts), ["_model", "frame", "diagnostics"])
        default = facts["diagnostics"]
        self.assertIsInstance(default, ast.Constant)
        self.assertIsNone(default.value)
        # return _supervisor.detect(frame, diagnostics=diagnostics)
        returns = [
            node for node in ast.walk(wrapper) if isinstance(node, ast.Return) and node.value is not None
        ]
        self.assertEqual(len(returns), 1)
        ret_call = returns[0].value
        self.assertIsInstance(ret_call, ast.Call)
        self.assertIsInstance(ret_call.func, ast.Attribute)
        self.assertEqual(ret_call.func.attr, "detect")
        self.assertIsInstance(ret_call.func.value, ast.Name)
        self.assertEqual(ret_call.func.value.id, "_supervisor")
        self.assertEqual(len(ret_call.args), 1)
        self.assertIsInstance(ret_call.args[0], ast.Name)
        self.assertEqual(ret_call.args[0].id, "frame")
        self.assertEqual(len(ret_call.keywords), 1)
        self.assertEqual(ret_call.keywords[0].arg, "diagnostics")
        self.assertIsInstance(ret_call.keywords[0].value, ast.Name)
        self.assertEqual(ret_call.keywords[0].value.id, "diagnostics")
        # def detect(self, frame: np.ndarray, diagnostics=None)
        detect = _find_function_def(tree, "detect", class_name="BoundedYoloSupervisor")
        facts = _parameter_facts(detect)
        self.assertEqual(list(facts), ["self", "frame", "diagnostics"])
        default = facts["diagnostics"]
        self.assertIsInstance(default, ast.Constant)
        self.assertIsNone(default.value)
        # The retired raw pin carried the `frame: np.ndarray` annotation — keep it.
        annotation = detect.args.args[1].annotation
        self.assertIsInstance(annotation, ast.Attribute)
        self.assertEqual(annotation.attr, "ndarray")
        self.assertIsInstance(annotation.value, ast.Name)
        self.assertEqual(annotation.value.id, "np")
        # detections, diagnostic_records = self._roundtrip(frame, timeout_sec)
        roundtrip_assigns = [
            node
            for node in ast.walk(detect)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Tuple)
            and len(node.targets[0].elts) == 2
            and all(isinstance(elt, ast.Name) for elt in node.targets[0].elts)
            and [elt.id for elt in node.targets[0].elts] == ["detections", "diagnostic_records"]
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "_roundtrip"
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "self"
        ]
        self.assertEqual(len(roundtrip_assigns), 1)
        roundtrip_call = roundtrip_assigns[0].value
        self.assertEqual(len(roundtrip_call.args), 2)
        self.assertEqual([arg.id for arg in roundtrip_call.args], ["frame", "timeout_sec"])
        # diagnostics.extend(diagnostic_records)
        extends = [
            node
            for node in ast.walk(detect)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "extend"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "diagnostics"
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "diagnostic_records"
        ]
        self.assertEqual(len(extends), 1)
        # payload.get("diagnostics", []) in the response parser
        roundtrip_fn = _find_function_def(tree, "_roundtrip", class_name="BoundedYoloSupervisor")
        gets = [
            node
            for node in ast.walk(roundtrip_fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "payload"
            and len(node.args) == 2
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "diagnostics"
            and isinstance(node.args[1], ast.List)
            and not node.args[1].elts
        ]
        self.assertEqual(len(gets), 1)
        # 4 * 1024 * 1024 response-size ceiling (exact arithmetic structure)
        expected_cap = ast.dump(ast.parse("4 * 1024 * 1024", mode="eval").body)
        caps = [
            node for node in ast.walk(roundtrip_fn) if isinstance(node, ast.BinOp) and ast.dump(node) == expected_cap
        ]
        self.assertEqual(len(caps), 1)

    def test_ipc_diagnostics_do_not_add_an_inference_pass_or_secret_surface(self) -> None:
        # Issue #573: parsed-structure twin (ast.parse) for the call-count and
        # response-payload pins — refactor-blind where the raw source-line pins
        # false-failed on comments/whitespace.
        tree = _parse_module(AI_CHILD)
        # Any `.track(...)` attribute call counts, regardless of receiver text
        # (model / self.model / _model): strictly stronger than the retired
        # raw substring count, which a receiver rename could dodge.
        track_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "track"
        ]
        self.assertEqual(len(track_calls), 1, "exactly one .track(...) inference pass per request (any receiver)")
        response_dicts = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Dict)
            and any(
                isinstance(key, ast.Constant)
                and key.value == "detections"
                and isinstance(value, ast.Name)
                and value.id == "detections"
                for key, value in zip(node.keys, node.values)
            )
            and any(
                isinstance(key, ast.Constant)
                and key.value == "diagnostics"
                and isinstance(value, ast.Name)
                and value.id == "diagnostics"
                for key, value in zip(node.keys, node.values)
            )
        ]
        self.assertEqual(
            len(response_dicts),
            1,
            "the child response payload must carry detections and diagnostics side by side",
        )
        # STATIC_POLICY (issue #573): the media/secret env-name byte-bans stay
        # raw — absence of these names ANYWHERE in the child source (comments
        # included) IS the security contract; ast.parse drops comments, so a
        # parsed-absence twin would be weaker.
        child_source = AI_CHILD.read_text(encoding="utf-8")
        self.assertNotIn("HLS_URL", child_source)
        self.assertNotIn("SEA_SPEED_API_TOKEN", child_source)
        self.assertNotIn("SEA_SPEED_API_URL", child_source)

    def test_two_argument_calls_remain_backward_compatible_for_road(self) -> None:
        # Issue #573: parsed-structure twin (ast.parse) — refactor-blind where
        # the raw source-line pins false-failed on comments/whitespace.
        tree = _parse_module(ENTRYPOINT)
        # `diagnostics=None`: EVERY `diagnostics` parameter must default to
        # None so two-argument callers stay valid (stronger than the retired
        # substring pin, which a comment or call site could satisfy).
        with_diagnostics = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                facts = _parameter_facts(node)
                if "diagnostics" in facts:
                    with_diagnostics.append((node.name, facts["diagnostics"]))
        self.assertEqual(
            sorted(name for name, _ in with_diagnostics),
            ["detect", "supervised_detect_vehicles"],
        )
        for name, default in with_diagnostics:
            self.assertIsInstance(default, ast.Constant, f"{name}: diagnostics must default to None")
            self.assertIsNone(default.value, f"{name}: diagnostics must default to None")
        # worker.detect_vehicles = supervised_detect_vehicles
        rebinds = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Name)
            and node.value.id == "supervised_detect_vehicles"
            and any(
                isinstance(target, ast.Attribute)
                and target.attr == "detect_vehicles"
                and isinstance(target.value, ast.Name)
                and target.value.id == "worker"
                for target in node.targets
            )
        ]
        self.assertEqual(len(rebinds), 1)


if __name__ == "__main__":
    unittest.main()
