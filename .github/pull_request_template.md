## Canonical task

- Issue: #
- Specification: `specs/NNN-feature/spec.md` / NOT REQUIRED
- Approved scope:
- Source authorization: OUTCOME APPROVED
- Approval recorded after Implementation Scope Check: YES/NO
- Material scope/protected-boundary change since authorization: NO/YES
- Acceptance criteria:
- Risk profile: REQUIRED / NOT REQUIRED
- Quality verdict: PASS / CONCERNS / FAIL / WAIVED
- Quality finding: NONE / [finding]
- Waiver reason: [required only if WAIVED, else omit or NOT REQUIRED]
- Waiver approved by: [required only if WAIVED]
- Waiver review/expiry date: [YYYY-MM-DD, required only if WAIVED]
- Waiver compensating controls: [required only if WAIVED]
- Waiver follow-up/remediation target: [Issue/target, required only if WAIVED]

## Change

- Intended behavior:
- Changed files:
  - `path/to/file`
- Out of scope:

## Impact

- Production impact: NONE / CONTROL_PLANE / VPS / UBUNTU_WORKER / MIXED
- Production-impact rationale:
- Security impact: NONE / [impact]
- API/event/state/storage schema impact: NONE / [impact]
- Detection/tracking/calibration/speed formula impact:
- Destructive/data migration impact: YES/NO
- Other high-risk trigger: YES/NO
- Backward compatibility:

## Delivery

- VPS deployment: [required only if runtime VPS/UBUNTU_WORKER/MIXED, else omit or NOT REQUIRED]
- Ubuntu worker/relay update: [required only if runtime, else omit or NOT REQUIRED]
- Production safety envelope: [required only if runtime, else omit or NOT REQUIRED]
- VPS execution capability: [required only if runtime, else omit or NOT APPLICABLE]
- Ubuntu worker execution capability: [required only if runtime, else omit or NOT APPLICABLE]
- Operator actions expected: [required only if runtime, else omit or 0]
- Rollout order: [required only if VPS/UBUNTU_WORKER/MIXED, else omit]
- Release manifest: [required only if runtime, else omit]
- Rollback target: [required only if runtime, else omit]

## Validation

- Local checks:
- PR checks:
- Runtime acceptance plan:
- Telemetry/evidence plan:

## Completion

- [ ] Exact changed-file scope verified
- [ ] Linked SDD artifacts and delivery-quality sections are current when required
- [ ] Risk-profile applicability matches derived high-risk triggers
- [ ] Secrets and runtime artifacts absent
- [ ] Required tests passed
- [ ] Quality verdict is not FAIL; any WAIVED verdict has a complete durable waiver record
- [ ] Applicable release and deployment evidence identified
- [ ] `COMPLETE` will not be claimed before applicable runtime acceptance
