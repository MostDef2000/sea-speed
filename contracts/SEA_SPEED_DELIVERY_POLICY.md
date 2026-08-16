# Sea Speed Delivery Policy

Version: 1.15.0
Status: Active

## 1. Purpose

Define quality admission, release provenance, runtime applicability, production authorization, fastest-safe operator execution and completion evidence for the three production contours: VPS, Ubuntu Worker/relay, and Windows AI Worker.

## 2. Applicability

| Changed paths | VPS | Ubuntu Worker/relay | Windows AI Worker |
|---|---:|---:|---:|
| `api/**`, `frontend/**`, `deploy/vps/**` | YES | NO unless compatibility requires | NO unless compatibility requires |
| `deploy/worker/ubuntu/**`, `worker/ubuntu_*` | NO | YES | NO |
| Windows-specific `worker/*.ps1`, `worker/*.cmd`, `worker/windows/**` | NO | NO | YES |
| shared `worker/**` runtime source | NO | YES | YES |
| API contract plus shared worker consumer | YES | YES | YES |
| contracts/docs/specs/control tooling | NO | NO | NO |

`MIXED` means two or more contours apply; it never replaces exact contour fields. Ubuntu-only production source must not be reduced to CONTROL_PLANE by a generic `deploy/**` rule.

## 3. Source admission and continuation

New tasks use `OUTCOME APPROVED` after a canonical Outcome Contract / Implementation Scope Check. Historical legacy source/merge approvals remain audit evidence only.

PR admission requires an exact Change Contract, exact changed-file match, valid SDD linkage for significant work, required CI and unchanged protected boundaries. Merge additionally requires a fresh base/head comparison, zero unresolved review threads and expected-head protection when supported.

The merge-facing context remains `Quality integration gate / quality-integration`. PR checks validate source; they do not deploy production.

After `OUTCOME APPROVED`, ordinary implementation defects, test corrections and CI remediation inside the already approved exact path set are continuation work. They do not require another source-approval prompt. Reauthorization is required only for material outcome/scope/protected-boundary expansion.

A deterministic lifecycle stage, including PR creation, queued/running CI, a remediable check failure, merge readiness, packaging, or an already-authorized runtime transition, is not a valid reason to return control to the operator. Continue automatically until the terminal interaction contract in section 15 is satisfied.

Deployment/release changes and production-learning correct-course work require the linked SDD Deployment Transaction Audit defined in section 17. A narrow source diff does not justify narrow failure analysis: after production learning, inspect neighboring transaction stages before the next production attempt.

## 4. Release identity

Every new deployable release uses `sea_speed_release_manifest_v2` and identifies canonical Issue, applicable merged PR, exact source/base commits, Outcome Contract hash, Change Contract hash, approved file set, actual Git diff, deterministic scope hash, component, exact artifacts, artifact SHA-256/size, exact-artifact evidence and quality evidence.

Approved scope and actual diff are separate facts and must match. A merge-message PR number is never a canonical Issue substitute. Persisted release/deployment v1 evidence remains readable for rollback compatibility.

Deployment manifest v1 supports explicit `vps`, `ubuntu-worker`, and `windows-worker` targets.

## 5. Production authorization and execution intent

Source authorization never authorizes runtime mutation.

A runtime change requires durable exact-SHA authorization on the canonical Issue. Authorization may be recorded without execution intent:

```text
PRODUCTION APPROVED <full-lowercase-40-character-sha>
Authorization-Fingerprint: <sha256>
```

To authorize and request execution in the same user decision, add the exact third line:

```text
Execution-Intent: EXECUTE
```

The first two lines are authority; the third line is execution intent. Authorization without the third line remains authorize-only and must not trigger runtime mutation. The fingerprint does not include execution intent and continues to bind Issue, applicable merged PR, exact source SHA, Outcome Contract, exact runtime contour set, security impact, deployment target and rollback semantics. Material change makes authorization stale.

Before mutation prove:

- input is already a lowercase full SHA;
- source is on current `main` first-parent history;
- exact `quality-integration.yml` has a completed successful `push` run on `main` for that SHA;
- exactly one applicable merged PR binds the canonical Issue;
- durable authorization fingerprint is current;
- execution intent is explicit in the triggering mechanism;
- exact artifacts/release/quality evidence validate;
- rollback target and semantics are known.

`.github/workflows/deploy-runtime-request.yml` is the normal Connector-addressable two-intent router. It admits only newly created canonical-Issue comments that are exactly the three-line authorize-and-execute form, uses repository-owned parsing, independently re-runs `verify_production_authorization.py --require-execution-intent`, then routes only the runtime contours declared `REQUIRED` by the exact merged Change Contract.

The historical one-line `DEPLOY VPS <sha>` request remains backward-compatible VPS execution intent after separate durable production authorization. It is not the preferred normal path for new tasks once the two-intent runtime request is available.

## 6. Runtime execution capability contract

Every runtime-impacting Change Contract declares, for each contour, one of:

- `CONNECTOR`: repository-owned execution can proceed without an operator runtime command after valid production intent;
- `ONE_COMMAND_FALLBACK`: the largest safe repository-owned runtime step requires one operator action;
- `MISSING`: no safe execution path exists;
- `NOT APPLICABLE`: contour is not part of this exact diff.

A contour declared deployment `REQUIRED` may not use `MISSING` or `NOT APPLICABLE`. A contour declared `NOT REQUIRED` must use `NOT APPLICABLE`. `Operator actions expected` is the number of required contours using `ONE_COMMAND_FALLBACK`. This count excludes the source approval and the exact-release production approval/execution-intent decision themselves.

If environment provisioning later enables a previously documented restricted Connector transport, the runtime capability may become zero-touch without weakening the exact-SHA, protected-environment or target-side transaction gates. Source must not claim a secret, route, sudo policy or runner exists unless independently verified.

## 7. Mixed-contour rollout

Before a mixed runtime merge, declare compatibility, schema/migration requirements, exact contour set, rollout order, acceptance checks and rollback order. VPS, Ubuntu Worker/relay and Windows AI Worker are independent failure domains unless an approved architecture explicitly requires host-to-host orchestration.

## 8. Canonical operator execution context

Current non-secret operator targets, subject to fresh runtime verification:

```text
Production VPS: root@82.146.37.153:22
Expected VPS hostname: mostdef.fvds.ru
Ubuntu worker: seaspeedadmin@10.123.239.102:22
Worker transport: ZeroTier
```

The operator establishes a target shell/SSH boundary only when a runtime contour still needs an interactive handoff. Credentials, private keys, passwords, camera secrets, TOTP and populated environment values remain local/trusted and never enter chat or Git.

For normal new releases, the operator should not be asked to click Actions or approve preparation/activation separately when the exact three-line Issue record already contains both current production authority and explicit execution intent.

## 9. Repository-owned server-pull model

The default interactive VPS/Ubuntu runtime fallback is target-local server-pull from canonical GitHub source at the exact approved SHA when technically available and safe:

```text
operator opens named target shell
-> one bootstrap selects repository + exact SHA
-> target retrieves/stages exact source
-> repository-owned entrypoint performs bounded operation
-> sanitized acceptance evidence is returned
```

Substantive deployment logic must be repository-owned before production handoff. The bootstrap is transport only; it must not embed the deployment algorithm, rollback state machine or acceptance suite.

Repository-owned entrypoints own applicable exact-source/integrity checks, host validation, prerequisite discovery, backups/rollback preparation, mutation, restart/reload, bounded health/smoke checks, evidence and safe retry/restore logic.

If the exact approved SHA lacks a required safe operation, production stops for normal source implementation. Control-laptop `.sh`/`.ps1`/`.zip` staging is fallback-only and must preserve exact provenance/integrity.

## 10. Fastest-safe operator UX

Normal successful-task budget:

```text
OUTCOME APPROVED: 1
PRODUCTION APPROVED + Authorization-Fingerprint + Execution-Intent: 1 per exact release
manual runtime command: 0 target, <=1 fallback per required contour
intermediate deterministic confirmation prompts: 0
```

Expose the largest safe authorized step. Do not split deterministic internal phases merely because they are separate scripts. Keep extra human checkpoints only for a genuine protected interaction: material reauthorization, a new exact source SHA, password/sudo/TOTP/IdP secret entry, host-key trust, configured environment reviewer, irreversible/high-risk decision, or a result automation cannot safely handle.

Known deterministic prerequisites, integrity checks, backups, preparation, activation, restart, smoke, evidence collection and safe retry should be encoded in the repository entrypoint rather than emitted as serial operator commands. Never reduce exact-SHA binding, host validation, authorization, backup, rollback, integrity or fail-closed behavior for convenience.

When an allowed protected interaction is required, return control as `HUMAN DECISION REQUIRED` and state the exact decision, bounded options/consequences where alternatives exist, and exact reply/action format. Do not use a generic status handoff.

## 11. VPS execution and evidence

`.github/workflows/deploy-vps.yml` remains the single protected VPS implementation. It supports reusable `workflow_call` and emergency/operator `workflow_dispatch`, retains `environment: production`, and performs all admission checks before SSH. The two-intent runtime router may call it directly for an applicable VPS contour.

A VPS release is complete only when exact deployed source, successful exact `push/main` aggregate quality evidence, current durable authorization, exact release/artifact/evidence identity, applicable API/frontend checks and known rollback target are proven.

The known production FastAPI loopback origin is `127.0.0.1:8010`; public protected `/sea-speed/api/health` is an authentication-boundary check, not origin-health proof.

## 12. Ubuntu Worker/relay execution and evidence

`.github/workflows/deploy-ubuntu-worker.yml` is the protected reusable Ubuntu orchestrator. It performs current-main/quality/authorization/provenance admission before any runtime transport decision. `deploy/worker/ubuntu/deploy-authorized.sh` is included in the deterministic `ubuntu-worker` exact artifact and owns the target-side deployment transaction: exact-main staging, durable authorization plus execution-intent verification, exact updater activation, exact worker/control identity verification, deployment-manifest evidence, and rollback to the previously active exact release on post-activation verification failure.

Zero-touch Ubuntu execution requires a separately provisioned restricted production transport/privilege boundary. This repository task does not create credentials, weaken sudo, expose a public runner or grant arbitrary root shell. When that protected transport is not independently available, the workflow must produce one exact bootstrap action that stages the authorized main SHA and hands off to `deploy-authorized.sh`; the workflow must not report runtime success before that fallback actually runs.

Ubuntu completion requires exact source/package/runtime identity, preservation of protected local state, valid deployment evidence, successful service state, matching source/runtime identity, advancing freshness/frame state when desired state is running and applicable relay/AI telemetry. Hosted CI does not prove NVIDIA/CUDA/physical-camera behavior.

## 13. Windows AI Worker evidence

Windows completion requires exact package/install identity, preservation of local protected state, valid deployment evidence, restart/process verification, matching source identity, freshness and applicable telemetry. Until a dedicated Connector execution path is implemented, Windows runtime work must declare its repository-owned one-command fallback rather than `MISSING`.

## 14. Media and security boundaries

The active media mode remains `mvp_v1`; `edge_v2` is a separate protected migration. Runtime identity fields are additive and must not redefine detection/tracking/calibration/speed/event formulas.

## 15. Completion and terminal interaction

Merge is not release. Release is not deployment. Deployment is not acceptance. `DONE` requires evidence for every applicable contour and the product verdict rules in `docs/evidence/POST_RELEASE_REVIEW.md`.

The Delivery Orchestrator may return control to the operator only in exactly one terminal interaction state:

- `DONE`: all mandatory evidence for the approved Outcome is satisfied.
- `BLOCKED`: a concrete external blocker makes continuation objectively impossible. The response records the blocker, supporting evidence, unblock condition and next admissible action. A remediable in-scope source/test/CI/PR-metadata failure is not a blocker.
- `HUMAN DECISION REQUIRED`: continuation requires a genuine human decision, authorization, protected input, configured environment review, or irreversible/high-risk choice. The response records the exact decision, bounded options and consequences when alternatives exist, and the exact response/action format; deterministic execution resumes after the decision.

`FAILED` is an event, not a terminal interaction state. Remediate it automatically when possible; otherwise classify the real boundary as `BLOCKED` or `HUMAN DECISION REQUIRED`. Never terminate on PR creation, queued/running CI, a remediable failed check, merge readiness, package creation, deployment preparation, or deployment start while an authorized safe next step exists.

## 16. Delivery quality admission

A linked significant PR is quality-enabled only when its canonical SDD includes the current NFR, risk/test-design, correct-course, traceability and Definition-of-Done sections and the Change Contract declares the derived `Risk profile` applicability plus a quality verdict.

Full risk profiling is required for security impact, API/event/state/storage schema impact, destructive/data migration, `MIXED` runtime impact, or an explicit other high-risk trigger. Risk records use categories `TECH`, `SEC`, `PERF`, `DATA`, `BUS`, `OPS`; probability and impact are scored 1-5 and the score is their product. Test design identifies `unit`, `integration`, `end-to-end`, or `runtime-manual` evidence with priority `P0` through `P3`.

The quality verdict is advisory with respect to product confidence but machine-enforced for admission: `FAIL` blocks; `PASS` and `CONCERNS` proceed subject to all hard gates; `WAIVED` proceeds only with a complete durable waiver record. A waiver never changes runtime applicability or production authorization and never converts missing mandatory evidence into success. A quality `FAIL` is not itself a terminal interaction state; in-scope remediation continues unless an actual external/human boundary is reached.

Production-equivalent deterministic deployment tests should execute the real repository-owned transaction entrypoint with isolated fake external/runtime boundaries. String-presence assertions are insufficient when the defect class is executable shell state/order/exit behavior.

## 17. Deployment transaction audit

For linked significant work, `scripts/ci/validate_sdd.py` requires a Deployment Transaction Audit when any of the following is true:

- a changed path is under `deploy/**` or `scripts/release/**`;
- a changed workflow is a deployment workflow;
- any Change Contract runtime deployment field is `REQUIRED`;
- the correct-course trigger is `PRODUCTION_LEARNING`.

The audit contains exactly one record for each stage: `ADMISSION`, `PRE-MUTATION`, `MUTATION`, `VERIFICATION`, `STATE-COMMIT`, `HOUSEKEEPING`, `EVIDENCE`, and `ROLLBACK`. Every stage declares mutation possibility, failure disposition, state after failure, safe retry, rollback semantics and evidence.

A `PRODUCTION_LEARNING` additionally requires `Adjacent-stage review: COMPLETE`, a concrete root cause, and concrete adjacent-stage findings. Before proposing the next production retry, review the entire transaction around the failure rather than only the final error line. Minimal source scope remains desirable, but analysis and fault-path testing must be broad enough to expose neighboring failure modes.