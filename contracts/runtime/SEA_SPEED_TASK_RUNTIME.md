# Sea Speed Task Runtime

Version: 1.2.1
Status: Active

## States

```text
DISCUSSION
READY_FOR_IMPLEMENTATION
IMPLEMENTING
MODULE_COMMITTED
HANDOFF_VALIDATED
CORE_RELEASE_INTEGRATING
SOURCE_INTEGRATED
ACTIONS_REQUIRED
ACTIONS_RUNNING
ACTIONS_COMPLETED
RUNTIME_ACCEPTANCE
COMPLETE
BLOCKED
FAILED
```

## Semantics

- `DISCUSSION` includes read-only Task Intake, repository discovery and Task Brief preparation.
- `READY_FOR_IMPLEMENTATION` requires a canonical Task Brief, an Implementation Scope Check and valid repository-write approval.
- `SOURCE_INTEGRATED` means source is verified on `main`; it does not mean VPS deployment or Windows worker update.
- `ACTIONS_REQUIRED` is manual fallback only.
- `ACTIONS_COMPLETED` may mean a package or deployment action completed; it is not runtime acceptance by itself.
- `RUNTIME_ACCEPTANCE` verifies provenance, health, freshness, telemetry and product evidence for the applicable VPS and/or worker contour.
- Terminal states are only `COMPLETE`, `BLOCKED`, and `FAILED`.

## Canonical Task Brief

Implementation tasks should be represented in the linked GitHub Issue with:

```text
Task Brief
- Original request:
- Problem:
- Expected behavior:
- Scope:
- Out of scope:
- Responsible area:
- Likely files:
- Acceptance criteria:
- Security impact:
- API compatibility impact:
- Runtime contour:
- VPS deployment required:
- Windows worker update required:
- Rollout order:
- Risks:
```

Task Intake prepares this brief without repository writes. The Project Manager validates it against current repository state before requesting approval.

## Required status block

```text
Sea Speed Task Runtime
- Task:
- Issue:
- Responsible agent:
- Current phase:
- Branch:
- Approved commit/range:
- Changed files:
- main updated: YES/NO
- Release manifest: NOT REQUIRED/PENDING/VALID/INVALID
- VPS deployment: NOT REQUIRED/PENDING/RUNNING/SUCCESS/FAILED
- VPS deployment manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Windows worker package: NOT REQUIRED/PENDING/PACKAGED/FAILED
- Windows worker installation: NOT REQUIRED/PENDING/INSTALLED/FAILED
- Windows deployment manifest: NOT REQUIRED/PENDING/VALID/INVALID
- Runtime telemetry: NOT REQUIRED/PENDING/VALID/INVALID
- Evidence verdict: NOT REQUIRED/PENDING/accepted/regressed/insufficient_evidence
- User action:
- Final state: PENDING/COMPLETE/BLOCKED/FAILED
```

## Continuation rule

After approval, continue automatically through every deterministic safe transition. Do not wait for another user message between implementation, integrity checks, PR, CI, merge, release execution and verification.

New approval is required only for scope expansion, destructive action, secrets, protected files, schema incompatibility, data migration or behavior redesign.

## Capability rule

Before the first write, verify that the full approved file set and required delivery lifecycle are executable. Do not create a partial implementation when mandatory files, PR operations, CI evidence, merge, release, deployment, verification or rollback paths are unavailable.

## Remote worker execution boundary

The normal interactive operations station for the Ubuntu worker is the operator-managed Windows laptop running OpenCode. OpenCode is not installed on the production worker solely to administer that worker.

The canonical primary SSH target for the commissioned worker is:

```text
alias: sea-speed-worker
user: seaspeedadmin
host: 10.123.239.102
port: 22
transport: ZeroTier
```

Before a protected operation, runtime reachability must still be checked because network addresses and routes are runtime facts rather than repository proof.

If direct ZeroTier SSH is unavailable, the approved fallback is an operator-owned SSH tunnel that exposes the worker locally as `127.0.0.1:2222`. The terminal holding that tunnel must remain open for the lifetime of the fallback connection. The fallback route is transport only; it does not grant additional deployment or privilege authorization.

OpenCode should execute ordinary unprivileged worker diagnostics and approved configuration preparation remotely through SSH. When root is required, OpenCode prepares a bounded helper or exact command, validates it where possible, and stops at the privilege boundary. The human operator runs the bounded command with `sudo` and enters the sudo password locally. Sudo passwords, private keys, camera credentials, API tokens, GitHub tokens and protected environment contents must not be passed to OpenCode prompts, command arguments, logs or repository files.

Production start, stop, restart, enable, activation, rollback and other protected runtime transitions remain subject to the task's explicit approval and evidence gates. SSH reachability or OpenCode access does not authorize those actions.

Repository source publication remains GitHub-Connector-only. Runtime SSH access must not be used as a substitute for repository branch, commit, PR, merge or source-of-truth operations.

Operational details and the primary/fallback connection procedure are defined in `docs/operations/OPENCODE_WORKER_REMOTE_ACCESS.md`.

## Integrity rule

After each write, fetch the complete file, verify its start and ending, validate syntax where applicable, compare the branch with `main`, and confirm the changed-file list remains in scope.

## Evidence hierarchy

Completion evidence is evaluated in this order:

```text
approved scope
→ exact changed files
→ PR validation
→ merge commit on main
→ release manifest and artifact identity
→ deployment manifest for each applicable contour
→ runtime source identity and health
→ advancing worker freshness and frame evidence
→ telemetry validation
→ post-release evidence verdict
```

A process running, an open PR, green CI, a merge, an uploaded package or a deployment start is not sufficient by itself.

## Runtime acceptance

For a worker-affecting task, observe at least two state samples and verify:

- matching `worker_source_commit`;
- `worker_online=true`;
- later `updated_at`;
- later `frame_no`;
- valid state schema;
- valid event schema when events are affected;
- overlay/event behavior when affected.

For an API-affecting task, verify health, `api_schema`, `source_commit` and the VPS deployment manifest.

## Feedback decision

Use `docs/evidence/POST_RELEASE_REVIEW.md`. A regression creates a linked Issue and requires an explicit rollback decision. `insufficient_evidence` must not be represented as acceptance.

## Terminal response gate

After repository-write approval, a final response is permitted only in `COMPLETE`, `BLOCKED`, or `FAILED`. Waiting for CI, mergeability, deployment or publication is not itself a blocker. A required physical Windows action may enter `ACTIONS_REQUIRED` and must include exact commands and evidence to return.
