#!/usr/bin/env python3
"""Validate versioned quality contracts, fixtures, rollout state and accepted-risk state."""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.quality.common import load_json, repository_root, validate_schema_instance

EXPECTED_CONTRACTS = {
    "sea_speed_edge_event_v1",
    "sea_speed_media_ref_v1",
    "sea_speed_event_sync_v1",
    "sea_speed_worker_state_v2",
    "sea_speed_object_v2",
    "sea_speed_release_manifest_v2",
    "sea_speed_media_boundary_v1",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    root = repository_root()
    schema = load_json(root / "data/contracts/sea-speed-contracts-v1.schema.json")
    fixtures = load_json(root / "data/contracts/fixtures-v1.json")
    policy = load_json(root / "data/contracts/contract-policy-v1.json")
    gates = load_json(root / "data/quality/quality-gates-v1.json")
    budget = load_json(root / "data/quality/reliability-budget-v1.json")
    risks = load_json(root / "data/quality/accepted-risks-v1.json")

    definitions = set(schema.get("$defs", {}))
    missing = EXPECTED_CONTRACTS - definitions
    if missing:
        fail("contract definitions missing: " + ", ".join(sorted(missing)))

    fixture_count = 0
    for fixture in fixtures.get("fixtures", []):
        fixture_count += 1
        contract = fixture.get("contract")
        contract_schema = schema.get("$defs", {}).get(contract)
        if not isinstance(contract_schema, dict):
            fail(f"fixture {fixture.get('name')} references unknown contract {contract}")
        errors = validate_schema_instance(fixture.get("payload"), contract_schema, schema)
        if contract == "sea_speed_media_boundary_v1" and fixture.get("payload", {}).get("mode") == "edge_v2":
            payload = fixture["payload"]
            if payload.get("edge_durable_media") is not True or payload.get("vps_durable_media") is not False:
                errors.append("$: edge_v2 requires edge durable media and forbids VPS durable media")
        expected_valid = bool(fixture.get("valid"))
        if expected_valid and errors:
            fail(f"positive fixture {fixture.get('name')} failed: {'; '.join(errors)}")
        if not expected_valid and not errors:
            fail(f"negative fixture {fixture.get('name')} unexpectedly passed")

    if fixture_count < 6:
        fail("fixture set is too small")
    if policy.get("active_media_mode") != "mvp_v1" or policy.get("target_media_mode") != "edge_v2":
        fail("media migration modes are not declared")
    if policy.get("rules", {}).get("edge_v2_forbids_vps_durable_media") is not True:
        fail("edge_v2 durable-media boundary is not enforced")
    if gates.get("required_context") != "Quality integration gate / quality-integration":
        fail("aggregate quality context is incorrect")
    if gates.get("state") not in {"aggregate_installed_not_enforced", "aggregate_enforced"}:
        fail("quality rollout state is invalid")

    limits = budget.get("limits", {})
    if int(limits.get("minimum_deterministic_fuzz_cases", 0)) < 128:
        fail("fuzz budget must require at least 128 deterministic cases")

    risk_by_id = {item.get("id"): item for item in risks.get("risks", [])}
    for risk_id in ("RISK-MEDIA-001", "RISK-EDGE-E2E-001", "RISK-ACTIONS-PIN-001"):
        if risk_id not in risk_by_id:
            fail(f"required risk record missing: {risk_id}")
    actions_risk = risk_by_id["RISK-ACTIONS-PIN-001"]
    if actions_risk.get("status") != "closed" or not actions_risk.get("resolution_evidence"):
        fail("RISK-ACTIONS-PIN-001 must remain as a closed audit record with resolution evidence")

    critical_open = [item for item in risks.get("risks", []) if item.get("severity") == "critical" and item.get("status") != "closed"]
    if len(critical_open) > int(limits.get("maximum_open_critical_risks", 0)):
        fail("open critical risks exceed the reliability budget")

    print(f"Quality contracts valid: {len(EXPECTED_CONTRACTS)} contracts, {fixture_count} fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
