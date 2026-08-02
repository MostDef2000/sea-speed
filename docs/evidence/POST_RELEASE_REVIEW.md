# Sea Speed post-release evidence review

Status: Active  
Issue: #28

## Purpose

Determine whether a deployed Sea Speed change is accepted, regressed or lacks sufficient evidence. The review uses deployment manifests and sanitized runtime telemetry; it does not store credentials, raw private media, model files or environment values.

## Required identity

```text
Issue:
Pull request:
Merge commit:
VPS release manifest:
VPS deployment manifest:
Worker release manifest:
Worker deployment manifest:
API source_commit:
Worker worker_source_commit:
Telemetry schema:
Calibration version:
Evidence window UTC:
```

## Runtime gates

The evidence window is valid only when:

- the VPS manifest identifies the expected merge commit;
- the Windows deployment manifest identifies the installed worker commit;
- `/api/health` succeeds and reports `api_schema` and `source_commit`;
- `worker_online` is true;
- `updated_at` advances between observations;
- `frame_no` advances between observations;
- state telemetry validates as `sea_speed_worker_state_v1`;
- sampled events validate as `sea_speed_vehicle_event_v1`;
- overlay and event snapshots are checked when affected by the release;
- a rollback target exists for every changed runtime contour.

## Quality observations

Record only aggregate or approved sanitized evidence:

```text
State samples:
State validation failures:
Event samples:
Event validation failures:
Events with worker source identity:
Events with calibration identity:
Events with speed_kmh:
Operator-confirmed valid events:
Operator-confirmed false positives:
Operator-confirmed missed vehicles:
Observed runtime errors:
```

Do not claim accuracy improvement unless the before and after windows use compatible camera, calibration, ROI and review procedures.

## Verdicts

Use exactly one:

### `accepted`

All required runtime gates passed, no material regression was observed, and the evidence window is sufficient for the approved acceptance criteria.

### `regressed`

A required health, freshness, schema, event, overlay or product-quality criterion failed. Open a linked regression Issue and identify whether rollback is required.

### `insufficient_evidence`

The release is installed and healthy, but the observation window or reviewed sample is insufficient to make the approved product-quality decision. Keep the evidence task open; do not represent this verdict as product acceptance.

## Feedback action

```text
Verdict: accepted / regressed / insufficient_evidence
Rollback required: YES/NO
New Issue required: YES/NO
New Issue:
Evidence retained:
Secrets or private media retained: NO
```

`COMPLETE` requires a valid runtime verdict for every applicable contour. An `insufficient_evidence` product verdict may complete the deployment operation only when the approved task explicitly allows deferred product evaluation; otherwise the task remains open.
