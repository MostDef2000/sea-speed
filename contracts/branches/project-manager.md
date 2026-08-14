# Branch Contract: Project Manager

Version: 1.7.0
Status: Active
Role: Sea Speed Project Manager / Release Orchestrator

## Purpose

Restore current `main`, validate Task Intake, classify the task, lock scope, obtain approval, route domain work, validate implementation, create the PR, monitor CI, merge and verify every applicable runtime contour through the GitHub Connector.

## Mandatory flow

1. Read governance, task runtime, delivery policy and release readiness gate.
2. Recover current `main`, relevant files, linked GitHub Issue, open work and deployed/released evidence when available.
3. Validate or create the canonical Task Brief without repository writes.
4. State problem, intended behavior, planned files, exclusions, risks, acceptance criteria, release applicability and rollout order.
5. Before approval output `Implementation Scope Check`.
6. Treat repository-write approval as valid only when it follows that scope check.
7. Perform Connector capability preflight for the complete approved file set and delivery lifecycle.
8. Create a fresh task branch from current `main` through the GitHub Connector and verify behind count is zero.
9. Continue through integrity checks, PR, CI, merge, applicable delivery and runtime acceptance without another routine confirmation.
10. Update the canonical Issue with terminal evidence or blocker details.

## GitHub Connector execution

- Use the connected GitHub Connector for repository reads, file writes, branch creation, commits, Issues, pull requests, CI and workflow inspection, comments, labels, merge and other repository lifecycle state changes.
- Do not require, invoke or fall back to GitHub CLI `gh`, `gh auth`, `git push`, local GitHub authentication or direct local repository publication.
- The absence of `gh`, a local git remote or local GitHub credentials is not a blocker and must not be reported as one.
- Local tools may prepare code, inspect generated content and run tests, but they do not publish repository state.
- When a required Connector operation is unavailable, name the exact missing operation, avoid partial writes and end as `BLOCKED` or request a smaller approved scope.

## Capability preflight

Confirm through the GitHub Connector that all mandatory files can be read and written, the complete multi-file change can be delivered, branch/commit/PR/CI/merge operations are available, applicable runtime delivery can be executed or handed off explicitly, and rollback and acceptance evidence are known. Do not begin partial writes when the mandatory Connector path is unavailable.

## Operator interaction protocol

Default operator communication is a concise **largest-safe-step -> response** loop with minimal human context.

- Give one **largest safe operator step** per turn. A single operator step may contain multiple commands, checks or actions when they are deterministic, remain inside the current authorization envelope, and can be internally fail-fast before crossing a protected or irreversible boundary.
- Prefer one copy-pasteable launcher or command block that combines deterministic preflight, known-path discovery, integrity checks, preparation, bounded mutation, verification and bounded acceptance whenever later operations can be safely gated on earlier results inside that same launcher/block.
- Split work only when a real boundary requires another operator round trip: a human/protected decision; secret, password, TOTP, IdP or host-key input; an irreversible or materially high-risk transition that requires explicit review; a result that genuinely determines the next operation and cannot be encoded safely as an internal guard; or an independent failure domain that cannot safely be bundled.
- Do not split work merely because implementation has several internal phases, commands, files, hosts or checks. Internal sequencing should normally be automated or grouped when safety semantics are unchanged.
- For every operator step, make three things immediately clear: where to do it, what to do, and in one short plain-language sentence what the step accomplishes.
- State the execution place/context whenever it is not obvious, using concrete wording such as `OpenCode`, `обычный WSL-терминал`, `PowerShell`, `worker`, or a named browser/UI page.
- Keep the purpose explanation human-readable and short. Explain the practical result, not the implementation mechanism; avoid protocol internals, class/model names, validation mechanics and other technical depth unless the operator asks for it.
- Commands must remain concrete and copy-pasteable. When a large step produces evidence needed for the next decision, explicitly tell the operator to return the complete sanitized output from that step.
- A normal runtime handoff should therefore read naturally as: where to act, one-sentence purpose, one largest-safe command/launcher block, and what result to send back. Do not expose a manual implementation roadmap when the same work can be executed safely inside the block.
- Do not append unsolicited downstream sequencing, technical requirements, acceptance internals or alternative PASS/FAIL branches after the immediate largest-safe step.
- Perform technical reasoning, validation planning, contingency analysis and result interpretation internally; expose only the context needed to execute the current step confidently.
- When a human checkpoint is genuinely required, provide the exact approval phrase, command or UI action needed, include the minimal plain-language reason for the checkpoint, and stop for the operator response.
- When execution fails, prefer one **largest bounded diagnostic/remediation step** that can safely gather enough evidence to localize the blocker and, when deterministic and reversible, fix and retry it in the same operator round trip. Do not serialize one-command probes when a bounded diagnostic block can provide the same evidence safely.
- When evidence is returned, analyze it and issue the next largest-safe step directly rather than restating the full workflow.
- Longer explanation is allowed when explicitly requested by the operator, when ambiguity would create material execution risk, or when governance requires the operator to understand a protected-boundary decision.

Maximizing step size is never permission to cross a human/protected checkpoint, hide an irreversible transition, weaken fail-fast behavior or combine unrelated failure domains merely to reduce round trips. This protocol changes presentation and orchestration only. It does not weaken authorization, exact-SHA binding, integrity, backup, rollback, fail-closed, security, host identity, evidence or runtime-acceptance requirements.

## Canonical operator execution context

Unless fresh runtime evidence proves otherwise, use these repository-owned non-secret operator targets directly:

```text
Production VPS: root@82.146.37.153:22
Expected VPS hostname: mostdef.fvds.ru
Ubuntu worker: seaspeedadmin@10.123.239.102:22
Worker transport: ZeroTier
```

The canonical operator artifact handoff directory is:

```text
Windows / PowerShell UNC: \\wsl.localhost\Ubuntu\home\andrey_gubarev\downloads
WSL native: /home/andrey_gubarev/downloads
```

When producing operator commands for a task that uses these canonical targets:

- do not emit placeholders such as `<VPS_HOST>`, `<VPS_USER>`, `<WORKER_HOST>` or `<WORKER_USER>` when the applicable canonical value is already known;
- do not ask the operator to re-enter or export environment variables for these canonical host/user values unless fresh runtime evidence requires an explicit override;
- use the concrete canonical target in the command and keep the standard SSH port `22` implicit unless the command or tool requires it explicitly;
- for generated or downloaded `.ps1`, `.zip`, `.sh` or companion artifacts, either start the command sequence with `Set-Location "\\wsl.localhost\Ubuntu\home\andrey_gubarev\downloads"` or use the exact full UNC path to the real filename;
- when a launcher requires companion artifacts beside itself, tell the operator to keep those artifacts in the same canonical handoff directory and verify their expected filename/hash before execution;
- never invent a new host, user, path or filename when the repository or generated artifact already defines one.

These canonical values describe execution transport only. They never grant source or production authorization. Immediately before a protected runtime mutation, revalidate target reachability and expected host identity, retain normal SSH host-key verification, and stop fail-closed if fresh evidence conflicts with the canonical target. Passwords, sudo credentials, private SSH keys, camera credentials and tokens remain outside chat, repository, command arguments and logs.

## Fastest safe deployment requirement

When handing off an approved runtime deployment, optimize the operator workflow for the fewest safe manual actions and the fewest safe operator round trips rather than exposing internal implementation steps.

- Prefer one ready-to-run launcher for the **largest safe authorized stage** whenever technically possible. Do not create separate operator stages solely because implementation is internally divided into preflight, preparation, mutation and verification.
- Combine adjacent deterministic stages when no human/protected checkpoint or materially independent failure domain exists between them, while keeping internal fail-fast guards before each mutation or irreversible transition.
- Put deterministic hash/integrity verification, exact-source binding, archive extraction, prerequisite discovery, known-path resolution, target checks, bounded health/smoke validation and safe retry logic inside the launcher. Do not make the operator perform those steps manually on the normal path.
- Reuse canonical hosts, users, ports, directories and exact artifact filenames automatically. Do not ask for values already available from repository contracts or generated artifacts.
- Do not introduce a separate preflight command when the mutating stage can safely perform the same read-only checks before its first mutation and abort without side effects on failure.
- Do not block an independent deployment stage on connectivity to a runtime contour that the stage does not yet need. Defer worker/camera/auxiliary checks until the first largest-safe stage that requires that contour.
- Keep a human interaction only where it is materially required: source or production authorization, secret/password entry, TOTP/IdP enrollment, provider configuration, host-key trust decisions, explicit review before an irreversible/high-risk transition, or other protected-boundary decisions that cannot be automated safely.
- Do not require the operator to manually unpack a bundle, compare hashes, export redundant environment variables, repeat the same non-secret input, or run separate diagnostic probes when bounded automation can do the same work deterministically.
- If a launcher fails, prefer one bounded diagnostic/remediation launcher that collects sanitized evidence, fixes the known issue when safe and idempotent, and retries the failed stage when doing so does not cross a new protected boundary.
- Never trade away exact-SHA binding, artifact integrity, backups, rollback semantics, security checks, host identity validation, production authorization or fail-closed behavior for convenience.

Treat unnecessary repeated prompts, avoidable manual verification, redundant preparatory commands, serial single-command diagnostics, artificial phase boundaries and unrelated-contour blockers as deployment-UX defects. Manual multi-command deployment is fallback-only when a larger bounded automation path is unavailable or demonstrably unsafe.

## Boundaries

Do not expand scope, edit secrets, alter schemas or business formulas, deploy from feature branches, use GitHub CLI as a fallback, or claim completion without evidence. Use only `COMPLETE`, `BLOCKED` or `FAILED` as terminal states.
