"""Autonomous execution policy contract (issue #398 wave 4).

The wave-3 revision of this file pinned workflow behavior with raw
source-text ``assertIn`` markers on the workflow YAML bytes. Text pins pass
on comments and stale code alike, so every text pin now has an executable
twin against the PARSED workflow structure (``yaml.safe_load``): trigger
wiring, job conditions, step order, step gating and env wiring are read from
the parsed objects, which ignores comments entirely. The deploy workflows'
real policy checks live in the shared ``verify-exact-release`` composite
action, so the twin walks workflow -> composite-step -> composite-action and
asserts the delegation env/``require_allow`` chain end to end — stronger
than the comment text it replaces. The evaluator's "repository text is not
authority input" pins became an AST scan of its real code constants
(comment-blind, rename-tolerant). The executed evaluator-behavior tests
(contour derivation, PR metadata validation) are unchanged.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_PATH = ROOT / "scripts/release/evaluate_production_policy.py"
spec = importlib.util.spec_from_file_location("evaluate_production_policy", EVALUATOR_PATH)
assert spec and spec.loader
EVALUATOR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EVALUATOR)

CHANGE_POLICY = json.loads((ROOT / "data/contracts/change-control-policy-v1.json").read_text(encoding="utf-8"))

WORKFLOWS = ROOT / ".github/workflows"
VERIFY_RELEASE_ACTION = ROOT / ".github/actions/verify-exact-release/action.yml"


def load_workflow(path: Path) -> dict:
    """Parse a workflow/composite-action YAML file into its structure.

    PyYAML resolves the bare ``on:`` trigger key to boolean True; both
    spellings are accepted so the trigger block stays reachable.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} did not parse to a mapping"
    return data


def trigger_of(data: dict) -> dict:
    return data["on"] if "on" in data else data[True]


def iter_strings(node) -> list[str]:
    """Every string value in the parsed structure (keys and values)."""
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        out: list[str] = []
        for key, value in node.items():
            out.extend(iter_strings(key))
            out.extend(iter_strings(value))
        return out
    if isinstance(node, list):
        return [s for item in node for s in iter_strings(item)]
    return []


def steps_of(data: dict) -> list[tuple[str, dict]]:
    """(job_name, step) pairs for a workflow, or ("<composite>", step)."""
    pairs: list[tuple[str, str, dict]] = []
    jobs = data.get("jobs")
    if isinstance(jobs, dict):
        for job_name, job in jobs.items():
            for step in (job or {}).get("steps") or []:
                pairs.append((str(job_name), step))
        return pairs
    for step in (data.get("runs") or {}).get("steps") or []:
        pairs.append(("<composite>", step))
    return pairs


def run_text(step: dict) -> str:
    return str(step.get("run") or "")


class AutonomousExecutionPolicyTests(unittest.TestCase):
    def test_legacy_comment_trigger_workflows_are_absent(self):
        self.assertFalse((ROOT / ".github/workflows/deploy-runtime-request.yml").exists())
        self.assertFalse((ROOT / ".github/workflows/deploy-vps-request.yml").exists())

    def test_autonomous_router_uses_current_tip_quality_trusted_environment_and_source_protection(self):
        data = load_workflow(WORKFLOWS / "deploy-runtime-autonomous.yml")
        trigger = trigger_of(data)
        # The router fires only from the trusted Quality integration gate
        # workflow_run — no comment-trigger surface may exist.
        self.assertEqual(trigger["workflow_run"]["workflows"], ["Quality integration gate"])
        self.assertIn("completed", trigger["workflow_run"]["types"])
        self.assertNotIn("issue_comment", trigger)
        evaluate = data["jobs"]["evaluate"]
        for condition in (
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.event == 'push'",
            "github.event.workflow_run.head_branch == 'main'",
        ):
            self.assertIn(condition, evaluate["if"])
        self.assertEqual(evaluate["environment"], "production")
        steps = [step for _, step in steps_of(data)]
        # The quality-approved commit is bound exactly, then gated on being
        # the current main tip (or a tree-modulo-tasks descendant).
        self.assertEqual(steps[0].get("id"), "release")
        freshness = next(step for step in steps if step.get("id") == "freshness")
        self.assertEqual(freshness.get("name"), "Require quality commit is current main tip")
        freshness_run = freshness["run"]
        self.assertIn("refs/remotes/origin/main", freshness_run)
        self.assertIn("merge-base --is-ancestor", freshness_run)
        self.assertIn("':(glob,exclude)specs/*/tasks.md'", freshness_run)
        self.assertIn("fresh_basis=tree-modulo-tasks", freshness_run)
        self.assertIn("fresh_basis=tip", freshness_run)
        self.assertIn("Ignoring stale successful Quality run", freshness_run)
        # Every downstream step (source protection, policy) is gated on the
        # freshness output, and source protection runs BEFORE the policy
        # evaluation.
        protection = next(step for step in steps if "verify_source_protection.py" in (step.get("run") or ""))
        policy = next(step for step in steps if "evaluate_production_policy.py" in (step.get("run") or ""))
        self.assertLess(steps.index(protection), steps.index(policy))
        for step in (protection, policy):
            self.assertEqual(step.get("if"), "${{ steps.freshness.outputs.fresh == 'true' }}")
        self.assertIn("Repository validation", protection["run"])
        self.assertIn("quality-integration", protection["run"])
        self.assertEqual(
            policy["env"]["SEA_SPEED_PRODUCTION_DELEGATION_V1"],
            "${{ vars.SEA_SPEED_PRODUCTION_DELEGATION_V1 }}",
        )
        # Repository text (comments included) is never an authority input.
        joined = "\n".join(iter_strings(data))
        self.assertNotIn("PRODUCTION APPROVED", joined)
        self.assertNotIn("Execution-Intent: EXECUTE", joined)

    def test_sync_merged_tasks_bot_stages_only_its_tasks_md_pathspec(self):
        data = load_workflow(WORKFLOWS / "sync-merged-tasks.yml")
        runs = "\n".join(run_text(step) for _, step in steps_of(data))
        self.assertIn("git add -- ':(glob)specs/*/tasks.md'", runs)
        self.assertNotIn("git add -A", runs)
        self.assertIn("sync_tasks_md.py", runs)
        self.assertIn("build_sync_pr_body.py", runs)
        # #477 contract transfer: the sync rides a PR flow now; the bot commit
        # and the squash-merge subject are both the deterministic sha-suffixed
        # "chore(sdd): auto-sync tasks.md completion (<source-sha8>)".
        subject = "chore(sdd): auto-sync tasks.md completion (${SOURCE_SHA:0:8})"
        self.assertIn(f'git commit -m "{subject}"', runs)
        self.assertIn(f'--subject "{subject}"', runs)
        job = next(iter(data["jobs"].values()))
        self.assertIn("github.event.workflow_run.event == 'push'", job["if"])
        self.assertIn("github.event.workflow_run.head_branch == 'main'", job["if"])

    def test_protected_deploy_workflows_re_evaluate_policy_and_source_protection(self):
        # The real checks live in the shared composite action: source
        # protection runs BEFORE the policy evaluation, and the policy step
        # fails closed with --require-allow when the workflow passes
        # require_allow: 'true' (both protected deploy workflows do).
        composite = load_workflow(VERIFY_RELEASE_ACTION)
        composite_steps = [step for _, step in steps_of(composite)]
        protection = next(step for step in composite_steps if "verify_source_protection.py" in (step.get("run") or ""))
        policy = next(step for step in composite_steps if "evaluate_production_policy.py" in (step.get("run") or ""))
        self.assertLess(composite_steps.index(protection), composite_steps.index(policy))
        policy_run = policy["run"]
        self.assertIn("--require-allow", policy_run)
        self.assertIn('[[ "$REQUIRE_ALLOW" == "true" ]]', policy_run)
        self.assertEqual(
            policy["env"]["SEA_SPEED_PRODUCTION_DELEGATION_V1"],
            "${{ env.SEA_SPEED_PRODUCTION_DELEGATION_V1 }}",
        )
        for name in ("deploy-vps.yml", "deploy-ubuntu-worker.yml"):
            data = load_workflow(WORKFLOWS / name)
            verify_step = next(
                step
                for _, step in steps_of(data)
                if step.get("uses") == "./.github/actions/verify-exact-release"
            )
            self.assertEqual(verify_step["with"]["require_allow"], "true")
            self.assertEqual(
                verify_step["env"]["SEA_SPEED_PRODUCTION_DELEGATION_V1"],
                "${{ vars.SEA_SPEED_PRODUCTION_DELEGATION_V1 }}",
            )
            joined = "\n".join(iter_strings(data))
            self.assertNotIn("verify_production_authorization.py", joined)
            self.assertNotIn("PRODUCTION APPROVED", joined)

    def test_ubuntu_workflow_uses_zero_touch_connector(self):
        data = load_workflow(WORKFLOWS / "deploy-ubuntu-worker.yml")
        runs = "\n".join(run_text(step) for _, step in steps_of(data))
        # The transport is the restricted ssh config written by the workflow
        # (jump host -> worker) and the forced-command protocol invocation.
        self.assertIn("ProxyJump sea-speed-vps-jump", runs)
        self.assertIn("User sea-speed-deploy", runs)
        self.assertIn("sea-speed-ubuntu-deploy-v1 $DEPLOY_SHA $CANONICAL_ISSUE $ARTIFACT_SHA", runs)
        self.assertIn("Operator actions expected: 0", runs)
        self.assertNotIn("ubuntu-worker-one-command.sh", runs)

    def test_repository_text_cannot_become_authority_input(self):
        tree = ast.parse(EVALUATOR_PATH.read_text(encoding="utf-8"))
        constants = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        self.assertTrue(
            any("SEA_SPEED_PRODUCTION_DELEGATION_V1" in constant for constant in constants),
            "evaluator never references the standing delegation variable",
        )
        for banned in ("/comments", "PRODUCTION APPROVED", "authorizedActors"):
            self.assertFalse(
                any(banned in constant for constant in constants),
                f"evaluator code contains banned authority literal {banned!r}",
            )
        identifiers = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        } | {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        self.assertNotIn("authorizedActors", identifiers)

    def test_runtime_contours_are_derived_from_exact_source_paths(self):
        vps, active_vps = EVALUATOR.derive_release_contract(["api/app/main.py"], CHANGE_POLICY)
        self.assertEqual(vps, {"productionImpact": "VPS", "vps": "REQUIRED", "ubuntuWorkerRelay": "NOT REQUIRED"})
        self.assertEqual(active_vps, {"VPS"})
        mixed, active_mixed = EVALUATOR.derive_release_contract(
            ["frontend/sea-speed/index.html", "worker/runtime.py"], CHANGE_POLICY
        )
        self.assertEqual(mixed["productionImpact"], "MIXED")
        self.assertEqual(active_mixed, {"VPS", "UBUNTU_WORKER"})

    def test_authentik_blueprint_routes_to_ubuntu_not_vps(self):
        contours, active = EVALUATOR.derive_release_contract(
            ["deploy/vps/authentik/blueprints/sea-speed-auth-v1.yaml"], CHANGE_POLICY
        )
        self.assertEqual(
            contours,
            {"productionImpact": "UBUNTU_WORKER", "vps": "NOT REQUIRED", "ubuntuWorkerRelay": "REQUIRED"},
        )
        self.assertEqual(active, {"UBUNTU_WORKER"})

    def test_mutable_pr_runtime_metadata_must_match_derived_contours(self):
        derived = {"productionImpact": "VPS", "vps": "REQUIRED", "ubuntuWorkerRelay": "NOT REQUIRED"}
        valid = {
            "Production impact": "VPS",
            "VPS deployment": "REQUIRED",
            "Ubuntu worker/relay update": "NOT REQUIRED",
            "VPS execution capability": "CONNECTOR",
            "Ubuntu worker execution capability": "NOT APPLICABLE",
        }
        self.assertEqual(
            EVALUATOR.validate_pr_runtime_metadata(valid, derived, {"VPS"}),
            {"vps": "CONNECTOR", "ubuntuWorkerRelay": "NOT APPLICABLE"},
        )
        tampered = dict(valid)
        tampered["VPS deployment"] = "NOT REQUIRED"
        with self.assertRaises(EVALUATOR.PolicyError):
            EVALUATOR.validate_pr_runtime_metadata(tampered, derived, {"VPS"})


if __name__ == "__main__":
    unittest.main()
