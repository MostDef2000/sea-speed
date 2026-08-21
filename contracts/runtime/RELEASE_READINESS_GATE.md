# Sea Speed Release Readiness Gate

Version: 1.14.0
Status: Active

## Gate

Before release execution verify:

```text
Release Readiness Gate
- Canonical Issue linked: YES/NO
- Delivery Checkpoint valid: YES/NO
- Approved scope identity current: YES/NO
- Source authorization receipt valid for same exact admitted scope: YES/NO
- State invalidation reason: NONE/<reason>
- Applicable merged PR linked: YES/NO
- Outcome Contract / approved scope current: YES/NO
- Approved source committed to main: YES/NO
- Repository visibility public: YES/NO
- Main branch protected: YES/NO
- Required source checks protected: YES/NO
- Exact source is on current main first-parent history: YES/NO
- Changed files match approved scope: YES/NO
- Aggregate quality push run on main successful for exact commit: YES/NO
- SDD linkage valid for significant change: YES/NO/NOT APPLICABLE
- Delivery quality layer valid: YES/NO/NOT APPLICABLE
- Deployment transaction audit valid: YES/NO/NOT APPLICABLE
- Risk profile applicability correct: YES/NO/NOT APPLICABLE
- Quality verdict: PASS/CONCERNS/WAIVED/NOT APPLICABLE
- Secrets/runtime artifacts absent: YES/NO
- Tool routing allowlist respected: YES/NO
- Exact artifact inventory and SHA-256 valid: YES/NO/NOT APPLICABLE
- Quality evidence valid: YES/NO/NOT APPLICABLE
- Release manifest v3 valid: YES/NO/NOT APPLICABLE
- Standing delegation required: YES/NO
- Standing delegation state: VALID/MISSING/INVALID/NOT APPLICABLE
- Production policy decision: ALLOW/DENY/NOT APPLICABLE
- Policy decision ID bound to exact release: YES/NO/NOT APPLICABLE
- VPS deployment required: YES/NO
- VPS execution capability: CONNECTOR/ONE_COMMAND_FALLBACK/NOT APPLICABLE
- Ubuntu worker/relay update required: YES/NO
- Ubuntu execution capability: CONNECTOR/ONE_COMMAND_FALLBACK/NOT APPLICABLE
- Operator actions expected: <non-negative integer>
- Mixed-contour compatibility declared: YES/NO/NOT APPLICABLE
- Rollout and rollback order declared: YES/NO/NOT APPLICABLE
- Acceptance evidence plan available: YES/NO
- Rollback target available: YES/NO/NOT APPLICABLE
- Safe to continue: YES/NO
```

## Resume/readiness boundary

Release readiness consumes durable delivery-control truth; it does not recreate source authority. **Repository/product truth** remains current `main`; **Delivery-control truth** is the canonical Issue/authorization receipt/Delivery Checkpoint and exact referenced evidence; **Transient interaction state** is the live conversation used for initial visible-Scope -> immediately-following `OUTCOME APPROVED` admission.

A durable authorization receipt is valid only for the **same exact admitted scope**. It cannot create, widen or replace source authority and never grants production authority. Context compaction, session restart, response truncation or Connector truncation does not by itself invalidate the receipt, return an admitted task to `DISCUSSION`, or require another `OUTCOME APPROVED`.

If a task must be recovered before this gate, use the bounded **Resume Probe**: current `main`, canonical Issue checkpoint, exact referenced PR/head/status/evidence whose cursor may have changed, then `Next admissible action`. Full project recovery is allowed only when the checkpoint is absent/unresolved/invalid or durable evidence materially contradicts it.

Lifecycle state is monotonic unless a concrete material invalidation is recorded: `MATERIAL_SCOPE_CHANGE`, `PROTECTED_BOUNDARY_CHANGE`, `USER_CHANGED_OUTCOME`, `MATERIAL_MAIN_DIVERGENCE`, or `EVIDENCE_CONTRADICTION`. `CONTEXT_LOSS` is not an invalidation reason.

Connector reads are cursor-bound and progressive: `known object -> metadata -> targeted detail -> failure fragment`. Equivalent re-reads with the same evidence identity and question are forbidden unless this or another canonical gate explicitly requires fresh evidence. Required fresh base/head/Quality/protection reads are therefore permitted and must be scoped to the exact gate.

## Protected source gate

On GitHub Free, Sea Speed production requires a public repository and protected `main`. `scripts/release/verify_source_protection.py` must succeed before production policy evaluation in the autonomous router and before transport in both protected deploy workflows.

The machine-verifiable minimum is `visibility=public`, `main.protected=true`, and required check contexts for `Repository validation` and `quality-integration`. Independently administered repository settings must also require PRs and disable force-push/delete/bypass paths that would defeat these checks. Repository/ruleset settings are not agent authority.

Changing repository visibility to private, removing main protection or removing required checks is production deny until the protected state is restored.

## Capability preflight

Active production contours are VPS and Ubuntu Worker/relay. After zero-touch activation the normal Ubuntu capability is `CONNECTOR` with `Operator actions expected: 0`. Historical `ONE_COMMAND_FALLBACK` declarations remain valid audit history but are not the target steady state.

## Tool routing admission

Tool capability is not self-authorizing. GitHub lifecycle uses GitHub Connector only. Runtime policy evaluation and protected deployment use repository-owned GitHub Actions. Standing delegation and branch/ruleset administration use independently controlled GitHub settings by a human administrator and have no agent fallback. Protected credential entry remains operator-local.

If the required route is unavailable and no exact approved fallback exists, return `HUMAN DECISION REQUIRED`; do not discover another service.

## Terminal interaction gate

Return control only as `DONE`, `BLOCKED`, `HUMAN DECISION REQUIRED`. `FAILED` is not a terminal interaction state; it is an internal observation. `BLOCKED` requires a concrete external blocker, evidence, unblock condition and next admissible action. A remediable in-scope source/test/CI/metadata failure is not a blocker and must be remediated automatically before this gate can justify returning control. PR created, CI running, checkpoint updated, merge ready, release built and deployment prepared are not terminal while a safe authorized next action exists.

## Aggregate quality gate

The merge-facing context remains `Quality integration gate / quality-integration`. It succeeds only when all required independent domains succeed. Workflow presence does not prove branch protection; protected source evidence is checked separately.

## Delivery quality gate

Significant work includes current NFR assessment, risk/test design, correct-course, acceptance traceability and Definition of Done. Full risk profile derives from security/schema/destructive/data-migration/MIXED/other explicit high-risk triggers. A waiver never bypasses a hard gate: source authorization, exact scope, protected source, required CI, standing production policy, rollback and runtime acceptance remain mandatory.

## Release provenance gate

New runtime delivery uses `sea_speed_release_manifest_v3`, binding Issue, PR, Outcome/Change Contract hashes, exact base/source, approved/actual files, scope hash, artifacts, quality evidence, delegation ID, policy version/hash and policy decision ID. Historical v1/v2/Windows evidence remains readable audit history only.

## Standing production policy gate

Production never runs merely because of source approval, push, merge, Issue/PR/comment text or a known hash. Runtime authority is a current independently administered standing delegation intersected with repository policy.

Before transport verify exact lowercase current-main first-parent SHA, successful exact `push/main` Quality, one applicable merged PR/canonical Issue, protected public source, valid current standing delegation, requested action in both trusted permissions and repository policy, matching policy hash, deterministic typed `allow`, exact artifacts/release evidence and rollback target.

The standing action set is `deploy`, `rollback` only. IAM/secrets/settings administration is excluded. Missing/invalid delegation is deny. Legacy per-release comment authorization is non-authoritative historical evidence.

## VPS gate

When VPS is required, `.github/workflows/deploy-vps.yml` verifies protected source, exact source/Quality/policy/provenance, health/source identity, applicable product/security smoke and rollback target.

## Ubuntu Worker/relay gate

When Ubuntu is required, `.github/workflows/deploy-ubuntu-worker.yml` verifies protected source, exact source/Quality/policy/artifacts before transport. The runner reaches `sea-speed-deploy@10.123.239.102` only through strict-host-key VPS ProxyJump. The Worker key is restricted by OpenSSH `restrict` and a forced command. `scripts/operations/sea_speed_ubuntu_zero_touch_gate.sh` accepts only exact SHA/Issue/artifact-digest requests and invokes `deploy/worker/ubuntu/deploy-authorized.sh` through the narrowly scoped root boundary.

A missing zero-touch key/host-key/jump credential is deny with no runtime mutation. There is no recurring one-command operator fallback in the steady-state workflow.

## Mixed-contour gate

When both active contours apply, exact VPS/Ubuntu flags remain authoritative. Completion of one contour never substitutes for the other.

## Documentation/control-plane rule

Governance, SDD, documentation and control tooling with `CONTROL_PLANE` impact require authorized source lifecycle and PR/post-merge Quality only. Runtime deployment is `NOT REQUIRED` unless the Outcome explicitly includes later settings/runtime acceptance evidence.

## Deployment transaction gate

Deployment/release-affecting significant work covers `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, `ROLLBACK`, including mutation possibility, failure disposition, safe retry, rollback and evidence.

## Evidence rule

Green PR is not deployment evidence. Merge is not release. Release is not deployment. Deployment is not acceptance. A successful runtime execution must retain typed policy-decision, release-manifest-v3, deployment and execution-audit evidence before terminal acceptance.
