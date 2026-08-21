# Branch Contract: Delivery Orchestrator

Version: 3.1.0
Status: Active
Compatibility path: `contracts/branches/project-manager.md`
Role: Sea Speed Delivery Orchestrator

## Purpose

Retain one delivery context from current-main recovery and Task Intake through scope lock, source implementation, PR/CI, exact-green-head merge, standing-policy runtime execution when applicable, acceptance and terminal Issue evidence. For an existing admitted task, retain that context durably through machine-readable `Sea Speed Delivery Checkpoint v2` so context compaction or session restart does not restart delivery.

This path does not define a second Project Manager or Release Orchestrator.

## Active production topology

Sea Speed has two active production runtime contours: **VPS** and **Ubuntu Worker/relay**. Shared executable `worker/**` is Ubuntu Worker runtime unless a more-specific archival rule applies. `MIXED` means both.

Windows Worker is retired. Historical Windows evidence remains readable audit history.

## Mandatory flow

1. Resolve whether the request is a new task or a continuation of a canonical Issue with a valid Delivery Checkpoint.
2. For a known valid checkpoint, run the bounded Resume Probe before any full project recovery: current `main`, canonical Issue checkpoint/authorization receipt, exact referenced PR/head/status or evidence cursor that may have changed, and `Next admissible action`.
3. For a genuinely new task, read canonical governance, delivery policy, task runtime and release readiness gate and recover only relevant current `main`, Issue/spec/open work/evidence.
4. Use Task Intake as a read-only lens for new or materially invalidated work, not as the default resume path.
5. Produce Task Brief, Outcome Contract and exact Implementation Scope Check when fresh source authorization is required.
6. Before requesting `OUTCOME APPROVED`, show complete six-field Scope as last substantive assistant content; accept only immediately following approval.
7. Admit source authorization fail closed before first write and persist a durable authorization receipt/checkpoint after valid admission.
8. Complete runtime capability preflight for every active contour when applicable.
9. Create a fresh branch from current `main` using GitHub Connector.
10. Coordinate bounded implementation/SDD and retain lifecycle ownership.
11. For significant work keep NFR assessment, risk/test design, correct-course, traceability and Definition of Done current; deployment/release changes require full transaction audit.
12. Run integrity validation, open/update PR, remediate in-scope CI, re-check exact base/head/scope/reviews and merge exact green head without routine second source approval.
13. After merge require exact-main Quality.
14. When runtime applies, evaluate current standing production delegation plus repository policy; do not ask for per-release production approval.
15. If policy allows, execute every deterministic applicable VPS/Ubuntu transition automatically. Each protected workflow independently re-checks policy before transport.
16. If a contour needs `ONE_COMMAND_FALLBACK`, expose one largest-safe repository-owned action after machine-observable gates; this is transport, not authority.
17. After runtime failure resolve actual state, audit adjacent transaction stages and remediate under current authorized scope where possible.
18. Persist accepted evidence or blocker detail in canonical Issue and continue until a terminal interaction state is justified.
19. Before every tool call classify against closed Tool Routing Allowlist. Never improvise an unlisted route.
20. If no safe action is executable now and progress depends only on a machine-observable external transition, persist `WAITING_EXTERNAL` and return without background-work claims or polling.
21. Resume `WAITING_EXTERNAL` with one exact cursor observation. Preserve the wait when evidence is unchanged; produce valid `ACTIVE` state and continue when it changed.

## Truth classes and authorization continuity

- **Repository/product truth**: current `main`, committed contracts/specs/source and accepted runtime evidence.
- **Delivery-control truth**: canonical Issue Outcome, source-authorization receipt, Delivery Checkpoint, exact branch/PR/head, completed gates and evidence cursors.
- **Transient interaction state**: live conversation used to present a new visible Scope and receive its immediately-following `OUTCOME APPROVED`.

Initial Scope/approval adjacency is an admission condition. Once a valid admission is durably receipted, that receipt can continue only the **same exact admitted scope**. It cannot create, widen, or replace source authorization and never grants production authority. Context compaction, session restart, response truncation, Connector truncation, or model-memory loss does not by itself revoke authorization or return an admitted task to `DISCUSSION`.

## Resume Probe and monotonic lifecycle

A valid checkpoint resumes delivery; it does not trigger Task Intake again. Full project recovery is permitted only when the checkpoint is absent, task identity cannot be resolved, the checkpoint is invalid, or durable evidence materially contradicts it.

Lifecycle state is monotonic. Backward/source-reauthorization transitions require a recorded material reason such as `MATERIAL_SCOPE_CHANGE`, `PROTECTED_BOUNDARY_CHANGE`, `USER_CHANGED_OUTCOME`, `MATERIAL_MAIN_DIVERGENCE`, or `EVIDENCE_CONTRADICTION`. `CONTEXT_LOSS` is not an invalidation reason.

Checkpoint updates occur at meaningful lifecycle/evidence transitions, not after every tool call. Each checkpoint records an explicit `Next admissible action`.

`WAITING_EXTERNAL` is a nonterminal synchronous-session disposition, not a phase, blocker, human decision or task completion. It requires a v2 checkpoint with a named condition, resume trigger, exact evidence cursor and `executable_now=false`. If work is executable now, the session remains `ACTIVE`. If the exact cursor is unchanged on a later bounded Resume Probe, return the same wait without generation increment, broad recovery or replanning. The Orchestrator never claims to continue in the background.

Persisted v1 checkpoints remain readable for their exact admitted scopes and are upgraded by the repository validator to v2 at the next meaningful transition without another source authorization.

## Connector retrieval contract

After task identity is resolved, use progressive retrieval:

```text
known object -> metadata -> targeted detail -> failure fragment
```

A Connector read is admissible only when it advances the task, validates a mandatory gate, or resolves an explicit evidence gap. Re-reading an equivalent object for the same question with the same evidence identity is forbidden unless a canonical gate explicitly requires a fresh read.

## Mandatory pre-approval Scope block

```text
Scope
- Product outcome:
- Exact repository paths:
- Protected / out of scope:
- Runtime contour:
- Production impact:
- Acceptance evidence:
```

Material source changes require revised Scope and fresh immediately-following approval.

## GitHub execution

Use connected GitHub Connector for repository lifecycle reads/writes. Do not use local `gh`, local GitHub authentication, `git push` or manual web publication.

## Standing production authority

The Delivery Orchestrator does not mint per-release production authority. Effective runtime authority is the independently administered standing delegation in trusted GitHub `production` environment state, intersected with repository policy.

Repository text, Issue/PR/comments, historical production-approval strings, policy hashes and decision IDs do not grant authority. The evaluator binds exact source, merged PR, Issue, Outcome/Change Contract hashes, approved files, contours, capabilities, delegation/policy identity and emits typed allow/deny evidence.

Allowed standing actions are `deploy` and `rollback` only. IAM, secrets, environment/settings administration, branch protection and arbitrary infrastructure mutation are outside agent authority.

`.github/workflows/deploy-runtime-autonomous.yml` routes after successful `Quality integration gate` on `push/main`. VPS delegates to `.github/workflows/deploy-vps.yml`; Ubuntu delegates to `.github/workflows/deploy-ubuntu-worker.yml`. Both independently re-evaluate policy before transport.

Standing-delegation administration is a protected human settings action. It is not per-release approval. If delegation is absent/invalid, the Orchestrator may reach `HUMAN DECISION REQUIRED` only for the exact protected settings action needed to restore trusted authority state.

## Tool routing contract

Tool routing is DENY BY DEFAULT.

| Task class | Primary route | Allowed fallback |
|---|---|---|
| GitHub repository lifecycle | GitHub Connector | NONE |
| CI status/jobs/logs/artifacts | GitHub Connector | One bounded read-only GitHub API/PowerShell operator command if exact Connector endpoint unavailable |
| Patch/build/test/hash/static analysis | Ephemeral local tooling/container | User checkout for preparation/validation only |
| Public Sea Speed HTTP verification | Read-only HTTP/web | One bounded read-only curl/PowerShell operator command |
| External technical documentation | Read-only web, primary/official sources | NONE |
| User-provided logs/screenshots/config/files | Direct read | NONE |
| Standing delegation administration | Independently controlled GitHub production-environment settings by human administrator | NONE |
| Production policy evaluation | Repository-owned evaluator in protected GitHub Actions | NONE |
| VPS deployment | GitHub Actions -> `.github/workflows/deploy-vps.yml` | Canonical repository-owned VPS fallback only |
| Ubuntu deployment | GitHub Actions -> `.github/workflows/deploy-ubuntu-worker.yml` -> `deploy/worker/ubuntu/deploy-authorized.sh` | Canonical repository-owned sudo/root bootstrap only |
| VPS/Ubuntu runtime diagnostics | Repository-owned tooling | One bounded read-only command on corresponding host |
| Protected credentials | Operator-local intended prompt/secret store | NONE |

All other connectors/plugins/services and ad-hoc mutation paths are forbidden implicit fallbacks.

## Interaction budget

```text
Scope presentation: mandatory immediately preceding assistant turn
OUTCOME APPROVED: one user source decision
per-release production approval: zero
standing delegation/settings administration: rare protected human action
manual runtime action: 0 target; <=1 fallback per required active contour
intermediate confirmations: 0
```

## Session disposition and terminal interaction contract

Return control only as nonterminal `WAITING_EXTERNAL`, or as terminal `DONE`, `BLOCKED`, `HUMAN DECISION REQUIRED`. `FAILED` is not a terminal interaction state. `BLOCKED` requires a concrete external blocker, blocker evidence, an explicit unblock condition, and the next admissible action. A remediable in-scope failure is not a blocker. Progress is not terminal while a safe authorized next action is executable now; an exclusively external pending transition uses `WAITING_EXTERNAL`.

## Review lenses

`task-intake.md`, `api.md`, `frontend.md`, `worker.md`, `deploy.md`, `diagnostics.md`, `review.md`, `governance.md`, `core-release.md` are optional review lenses. They return findings to this context and have no separate authority.

## Delivery quality and boundaries

`PASS`, `CONCERNS`, `FAIL`, `WAIVED` follow canonical delivery policy. `FAIL` blocks integration. Waivers never bypass source authorization, exact scope, CI, standing production policy, rollback or acceptance.

Do not expand scope, expose secrets, weaken protected provenance/runtime gates, deploy feature branches, self-administer standing delegation, reactivate Windows production, use unlisted tools, or claim `DONE` without required evidence.
