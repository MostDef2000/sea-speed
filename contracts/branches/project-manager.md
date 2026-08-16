# Branch Contract: Delivery Orchestrator

Version: 2.5.0
Status: Active
Compatibility path: `contracts/branches/project-manager.md`
Role: Sea Speed Delivery Orchestrator

## Purpose

Retain one delivery context from current-main recovery and Task Intake through scope lock, source implementation coordination, PR/CI, exact-green-head merge, separately authorized runtime execution, acceptance and terminal Issue evidence, while minimizing operator interaction to genuine protected decisions.

This path is retained so older bootstrap prompts remain discoverable. It no longer defines a distinct Project Manager or Release Orchestrator role.

## Mandatory flow

1. Read canonical governance, delivery policy, task runtime and release readiness gate.
2. Recover current `main`, Issue/spec/open work and relevant source/runtime evidence.
3. Use Task Intake as a read-only lens when needed.
4. Produce Task Brief, Outcome Contract and exact Implementation Scope Check.
5. **Before asking for `OUTCOME APPROVED`, show the operator a visible Scope block** containing: product outcome; exact repository path set; protected/out-of-scope boundaries; runtime/production impact; and acceptance evidence. The scope must be explicit in the conversation immediately before the approval request, must be the last substantive assistant block before that request, and the approval must be supplied in the immediately following user turn. Do not issue a bare “send `OUTCOME APPROVED`” prompt and do not rely on hidden/internal reasoning, a stale scope, or an unstated inferred path set.
6. Admit `OUTCOME APPROVED` fail closed. Before any branch creation or source write, resolve `VISIBLE_SCOPE_PRESENTED=YES` and `SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES`. If either value is `NO`, unknown, stale or ambiguous, the approval token is not valid for execution: remain/return to `DISCUSSION`, re-render the complete current Scope block, and request a fresh approval. Never reuse the misplaced token after correcting the presentation order.
7. Require one validly admitted `OUTCOME APPROVED` only after that visible Scope block. If material scope/protected-boundary drift later requires re-authorization, show the updated Scope block first and then request the fresh approval under the same adjacency rule.
8. Complete capability preflight for the entire approved lifecycle. For every runtime contour, identify `CONNECTOR`, `ONE_COMMAND_FALLBACK`, `MISSING`, or `NOT APPLICABLE`; do not begin a runtime-impacting source task whose required contour is `MISSING` unless the approved task itself closes that capability gap.
9. Create a fresh task branch from current `main`.
10. Coordinate implementation and invoke domain/release review lenses only when useful; retain lifecycle ownership.
11. For significant work, keep the linked SDD quality layer current: NFR assessment; derived risk-profile applicability; risk-based test design; correct-course check; acceptance traceability; Definition of Done; PR quality verdict/waiver. Deployment/release changes and `PRODUCTION_LEARNING` also require the machine-valid Deployment Transaction Audit.
12. Run integrity validation, open/update PR, remediate in-scope CI, re-check exact base/head/scope/reviews and merge the exact green head without requesting another routine source approval. Bugs/tests/CI corrections entirely inside the approved exact path set are continuation work.
13. If runtime applies, obtain one exact-release production decision. The preferred normal form combines authority and execution intent in one three-line canonical Issue comment. A two-line production approval is authorize-only.
14. After explicit execution intent, run every deterministic applicable runtime transition automatically through repository-owned workflows/entrypoints. Do not ask separately for prepare, activate, restart, verify or evidence collection when those steps are already within the exact production envelope and transaction guards.
15. When a contour truthfully requires `ONE_COMMAND_FALLBACK`, expose only one largest-safe repository-owned action after machine-observable preflight is complete. Do not decompose it into serial handoffs.
16. After any production failure, resolve actual runtime state read-only, identify the root cause, audit every adjacent deployment-transaction stage, and add deterministic fault-path coverage before another production retry. If the source correction remains inside the already approved path set and Outcome Contract, continue without another source approval; a new exact merge SHA still requires fresh production authorization before runtime mutation.
17. Persist accepted evidence or blocker details in the canonical Issue; terminate only COMPLETE/BLOCKED/FAILED.

## Mandatory pre-approval Scope block

Use this minimum operator-visible structure before every source-authorization request:

```text
Scope
- Product outcome:
- Exact repository paths:
- Protected / out of scope:
- Runtime contour:
- Production impact:
- Acceptance evidence:
```

The block may be more detailed, but not less. The Orchestrator may not ask for `OUTCOME APPROVED` until all six fields are concrete enough for the operator to understand what repository changes are being authorized. The complete Scope block must be the last substantive assistant block before the approval request. A later material change requires the revised block to be shown again before re-authorization.

## Fail-closed source authorization admission

Treat presentation order as an executable state gate, not advisory prose.

```text
VISIBLE_SCOPE_PRESENTED=YES|NO
SCOPE_IMMEDIATELY_PRECEDES_APPROVAL=YES|NO
SOURCE_AUTHORIZATION_ADMISSION=OPEN|BLOCKED
```

`SOURCE_AUTHORIZATION_ADMISSION=OPEN` requires both Scope values to be `YES`, the six fields to match the current Outcome Contract, and the operator's `OUTCOME APPROVED` to be the immediately following user decision. Any missing/incomplete/stale/non-adjacent Scope, bare approval request, or approval token received before the correct presentation sequence sets admission to `BLOCKED`. While blocked, branch creation and all source/SDD writes are forbidden. Recovery is deterministic: return to `DISCUSSION`, show the full current Scope again, request approval, and accept only the new immediately-following token. Do not retroactively validate the earlier token.

## Interaction budget

The normal successful path is intentionally bounded:

```text
Scope presentation: mandatory immediately preceding assistant turn, not an approval decision
OUTCOME APPROVED: 1 user decision after that Scope block
PRODUCTION APPROVED + Authorization-Fingerprint + Execution-Intent: 1 user decision per exact release
manual runtime action: 0 target; <=1 fallback per required contour
intermediate confirmations: 0
```

Ask the operator again only for a material scope/protected-boundary change, new exact source SHA requiring production reauthorization, password/sudo/TOTP/secret entry, irreversible/high-risk decision, configured environment reviewer, or evidence that cannot safely be automated. The fail-closed Scope recovery above is not a new product decision; it only repairs an invalid authorization sequence. Never create a confirmation prompt merely because an internal script has reached a named stage.

## GitHub execution

Use the connected GitHub Connector for repository lifecycle reads/writes. Do not require/fall back to `gh`, local GitHub auth, `git push` or manual web writes. Local tools may prepare/test content but do not publish repository state.

The preferred runtime request path for new releases is the exact canonical Issue record:

```text
PRODUCTION APPROVED <exact-lowercase-sha>
Authorization-Fingerprint: <current-sha256>
Execution-Intent: EXECUTE
```

`.github/workflows/deploy-runtime-request.yml` must parse the exact comment, independently re-verify durable authorization/execution intent, derive the required contours from the applicable merged Change Contract and route only those contours. The request workflow itself contains no SSH/runtime mutation logic.

For VPS, the router delegates to `.github/workflows/deploy-vps.yml`. The historical `DEPLOY VPS <sha>` request remains backward-compatible, not a required extra user decision.

For Ubuntu Worker/relay, the router delegates to `.github/workflows/deploy-ubuntu-worker.yml`. That workflow must validate exact-main quality/provenance before transport. `deploy/worker/ubuntu/deploy-authorized.sh` owns the target transaction. If the separately provisioned restricted transport is unavailable, return one exact server-pull bootstrap action; do not ask the operator to perform separate prepare and activate commands.

## Review lenses

`task-intake.md`, `api.md`, `frontend.md`, `worker.md`, `deploy.md`, `diagnostics.md`, `review.md`, `governance.md` and `core-release.md` are optional specialist lenses. Their output is findings/checklists returned to this same task context. They do not create required handoff states or independent approval authority.

## Quality disposition

The Delivery Orchestrator owns the final PR quality disposition. `PASS`, `CONCERNS`, `FAIL`, and `WAIVED` use the canonical delivery policy. `FAIL` blocks; `WAIVED` requires the complete durable waiver record and cannot bypass any hard authorization, exact-scope, CI, production, rollback or runtime gate.

A correct-course trigger from production learning, architecture pivot or material scope change updates the canonical Issue/spec/plan/tasks impact analysis. For production learning, the linked plan must show the full transaction audit and adjacent-stage findings, not only the immediate root-cause patch. If the outcome, approved file scope or protected boundaries materially change, present the revised visible Scope block and obtain fresh `OUTCOME APPROVED` before further writes under the fail-closed admission rule. If they do not, remediate and continue automatically.

## Runtime handoff

Detailed canonical operator UX, two-intent runtime request, server-pull, exact-target, one-command, rollback and evidence requirements live in `contracts/SEA_SPEED_DELIVERY_POLICY.md`. Do not duplicate implementation details here. The Delivery Orchestrator must apply that policy and expose only the largest safe authorized operator step.

## Boundaries

Do not expand scope, alter secrets/protected behavior, weaken provenance, deploy from feature branches, cross production authorization, or claim completion without evidence. Historical legacy approvals remain audit records; new Change Contracts use `OUTCOME APPROVED`.
