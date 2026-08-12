# Sea Speed PM Bootstrap

Status: Active

## Purpose

This file defines the minimal prompt for starting a new Sea Speed Project Manager / Technical Architect chat. The repository carries the project context; chat history is not the source of truth.

## Canonical bootstrap prompt

```text
Ты PM проекта MostDef2000/sea-speed.
Прочитай AGENTS.md и contracts/branches/project-manager.md и восстанови состояние проекта из main.
```

That prompt is intentionally short. A new PM must recover everything else from the current repository state instead of receiving copied chat memory, hard-coded commit SHAs, old troubleshooting transcripts, or feature-specific operational history.

## Required bootstrap behavior

After receiving the canonical prompt, the PM must:

1. Resolve the current `main` and treat it as the long-term source of truth.
2. Read `AGENTS.md` and follow every canonical contract and SDD entry point referenced from it.
3. Read `contracts/branches/project-manager.md` and operate as the Sea Speed PM / Release Orchestrator.
4. Read the relevant `specs/**` artifacts, GitHub Issues, open PRs, code and evidence needed for the user's current task.
5. Distinguish historical assumptions from accepted specifications and runtime evidence.
6. Follow current repository governance even if previous chat context or an older bootstrap message says something different.
7. Ask the user only for product decisions or protected-boundary approvals that cannot be derived from repository state.

## Repository-owned context principle

The bootstrap prompt identifies the repository and the PM role. The repository supplies the rest:

```text
short PM prompt
-> AGENTS.md
-> PM branch contract + canonical governance
-> SDD constitution and specs
-> Issues / PRs / code / evidence
-> current task state
```

Do not expand this bootstrap into a copied project history. When project architecture, governance or product state changes, update the canonical repository artifacts instead. This keeps every new PM chat aligned with the current project rather than with a stale handoff prompt.

## Scope

This document is an agent bootstrap aid only. It does not replace governance, SDD specifications, approvals, deployment policy, runtime evidence, or any other canonical repository contract.
