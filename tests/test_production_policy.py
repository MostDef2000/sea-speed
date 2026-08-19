from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/release/production_policy.py"
spec = importlib.util.spec_from_file_location("production_policy", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

POLICY = {
    "schema": "sea-speed-production-autonomy-policy/v1",
    "version": "1.0.0",
    "allowedRepositories": ["MostDef2000/sea-speed"],
    "allowedEnvironments": ["production"],
    "allowedActions": ["deploy", "rollback"],
    "requiredDelegationMode": "autonomous",
    "requiredPrincipal": "sea-speed-delivery-orchestrator",
}


def delegation(**overrides):
    value = {
        "schema": "sea_speed_standing_production_delegation_v1",
        "delegationId": "prod-autonomy-v1",
        "principal": "sea-speed-delivery-orchestrator",
        "repository": "MostDef2000/sea-speed",
        "environment": "production",
        "permissions": ["deploy", "rollback"],
        "mode": "autonomous",
        "policyHash": module.policy_hash(POLICY),
        "enabled": True,
    }
    value.update(overrides)
    return value


def decision(*, action="deploy", delegated=True, active_delegation=None, policy=None):
    active_policy = policy or POLICY
    if active_delegation is None and delegated:
        active_delegation = delegation()
    return module.decision_payload(
        policy=active_policy,
        delegation=active_delegation if delegated else None,
        repository="MostDef2000/sea-speed",
        environment="production",
        action=action,
        source_commit="a" * 40,
        canonical_issue=229,
        pull_request=230,
        outcome_contract_hash="b" * 64,
        change_contract_hash="c" * 64,
        approved_files=["a.txt"],
        runtime_contours={"productionImpact": "VPS", "vps": "REQUIRED", "ubuntuWorkerRelay": "NOT REQUIRED"},
        execution_capabilities={"vps": "CONNECTOR", "ubuntuWorkerRelay": "NOT APPLICABLE"},
    )


class ProductionPolicyTests(unittest.TestCase):
    def test_valid_standing_delegation_allows_exact_deploy(self):
        value = decision()
        self.assertEqual(value["decision"], "allow")
        self.assertEqual(value["delegationId"], "prod-autonomy-v1")
        module.validate_decision(value, require_allow=True)

    def test_missing_delegation_denies_without_magic_text(self):
        value = decision(delegated=False)
        self.assertEqual(value["decision"], "deny")
        self.assertEqual(value["reason"], "standing_delegation_missing")
        with self.assertRaises(module.PolicyError):
            module.validate_decision(value, require_allow=True)

    def test_invalid_standing_delegation_denies_fail_closed(self):
        cases = (
            delegation(enabled=False),
            delegation(policyHash="f" * 64),
            delegation(principal="other-principal"),
            delegation(mode="manual"),
        )
        for active in cases:
            with self.subTest(active=active):
                value = decision(active_delegation=active)
                self.assertEqual(value["decision"], "deny")
                self.assertTrue(str(value["reason"]).startswith("standing_delegation_invalid:"))

    def test_malformed_delegation_json_is_rejected(self):
        for raw in ("{", "[]", '"text"'):
            with self.subTest(raw=raw):
                with self.assertRaises(module.PolicyError):
                    module.parse_delegation(raw)

    def test_repository_policy_cannot_widen_trusted_permissions(self):
        limited = delegation(permissions=["deploy"])
        widened_policy = dict(POLICY)
        widened_policy["allowedActions"] = ["deploy", "iam", "rollback"]
        limited["policyHash"] = module.policy_hash(widened_policy)
        value = module.decision_payload(
            policy=widened_policy,
            delegation=limited,
            repository="MostDef2000/sea-speed",
            environment="production",
            action="iam",
            source_commit="a" * 40,
            canonical_issue=229,
            pull_request=230,
            outcome_contract_hash="b" * 64,
            change_contract_hash="c" * 64,
            approved_files=["a.txt"],
            runtime_contours={"productionImpact": "VPS", "vps": "REQUIRED", "ubuntuWorkerRelay": "NOT REQUIRED"},
            execution_capabilities={"vps": "CONNECTOR", "ubuntuWorkerRelay": "NOT APPLICABLE"},
        )
        self.assertEqual(value["decision"], "deny")
        self.assertEqual(value["reason"], "action_not_delegated")

    def test_wrong_environment_or_repository_denies(self):
        for overrides, expected in (
            ({"repository": "other/repo"}, "delegation_repository_mismatch"),
            ({"environment": "staging"}, "delegation_environment_mismatch"),
        ):
            active = delegation(**overrides)
            value = decision(active_delegation=active)
            self.assertEqual(value["decision"], "deny")
            self.assertEqual(value["reason"], expected)

    def test_unsupported_action_denies_even_if_policy_and_delegation_are_tampered_to_include_it(self):
        widened_policy = dict(POLICY)
        widened_policy["allowedActions"] = ["deploy", "iam", "rollback"]
        active = delegation(permissions=["deploy", "iam", "rollback"], policyHash=module.policy_hash(widened_policy))
        value = decision(action="iam", active_delegation=active, policy=widened_policy)
        self.assertEqual(value["decision"], "deny")
        self.assertEqual(value["reason"], "unsupported_action")

    def test_policy_hash_is_not_authority(self):
        raw = json.dumps({"schema": "sea_speed_standing_production_delegation_v1", "policyHash": module.policy_hash(POLICY)})
        with self.assertRaises(module.PolicyError):
            module.validate_delegation(module.parse_delegation(raw), POLICY)

    def test_decision_id_detects_tampering(self):
        value = decision()
        value["action"] = "rollback"
        with self.assertRaises(module.PolicyError):
            module.validate_decision(value)


if __name__ == "__main__":
    unittest.main()
