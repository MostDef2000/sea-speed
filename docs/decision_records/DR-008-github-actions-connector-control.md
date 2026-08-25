# DR-008: GitHub Actions Connector Control

Status: Accepted
Date: 2026-08-25
Issue: #310

## Context

Sea Speed routes durable GitHub lifecycle and CI evidence through the GitHub Connector, but the local OpenCode project configuration used deprecated npm package `@modelcontextprotocol/server-github`. Its exposed surface covered repository, Issue and PR operations but did not expose GitHub Actions run/job/log/artifact reads or workflow rerun/dispatch. Issue #305 reached exact-main Quality and production-policy ALLOW, then could not continue a failed deployment run without a manual Actions button even after the Ubuntu Worker became available.

GitHub's official `github/github-mcp-server` supports OpenCode through the hosted MCP endpoint and provides exact Actions tools `actions_list`, `actions_get`, `get_job_logs`, and `actions_run_trigger`. The consolidated trigger tool also exposes cancellation and log deletion, so capability must be narrower than authority.

## Decision

Track a secret-free project `opencode.json` using GitHub's official remote MCP endpoint, `{env:GH_TOKEN}`, and only `context,repos,issues,pull_requests,actions`. OpenCode startup performs an exact capability preflight rather than inferring Actions support from generic Connector availability.

Allow workflow/run/job/artifact reads and bounded failure-log retrieval. Allow only `run_workflow`, `rerun_workflow_run`, and `rerun_failed_jobs` through `actions_run_trigger`, and only when the canonical Issue checkpoint records that exact method and target as `Next admissible action`. Treat `cancel_workflow_run` and `delete_workflow_run_logs` as destructive methods requiring a new explicit six-field Scope and fresh source authorization.

OpenCode loads configuration at process startup. When current `main` already contains the correct configuration but the live process lacks the tools, delivery records the exact restart and post-restart discovery prerequisite. It does not substitute a manual web action, `gh`, or an ad-hoc API client.

Workflow rerun and dispatch are transport capabilities only. Existing protected-source, exact-main Quality, standing-delegation, deterministic production-policy, provenance, rollback and runtime-acceptance gates remain authoritative.

## Consequences

- Deterministic CI and deployment continuation can remain inside the Connector route.
- The tracked configuration contains no token value and can be validated with repository source.
- Startup detects missing Actions capability before a task reaches an otherwise avoidable manual-button blocker.
- Destructive Actions methods remain fail closed despite sharing the trigger transport tool.
- A one-time OpenCode restart is required after configuration changes; future sessions load the capability automatically.

## Runtime impact

CONTROL_PLANE only. This decision changes orchestration capability, not production policy or application/runtime source. Any later protected workflow invocation remains independently gated.
