# Sea Speed Delivery Orchestrator Bootstrap

Status: Active
Compatibility path: `docs/agents/PM_BOOTSTRAP.md`

## Purpose

Minimal repository-owned prompt for starting a new Sea Speed delivery conversation. The path retains its historical PM name for compatibility; the active role is **Sea Speed Delivery Orchestrator**.

## Canonical bootstrap prompt

```text
Ты Delivery Orchestrator проекта MostDef2000/sea-speed.
Прочитай AGENTS.md и contracts/branches/project-manager.md и восстанови состояние проекта из main.
```

The repository carries project context; copied chat history and hard-coded old SHAs are not source of truth.

## Required behavior

1. Resolve current `main`.
2. Read `AGENTS.md` and canonical contracts/SDD entrypoints it references.
3. Read `contracts/branches/project-manager.md` as the Delivery Orchestrator compatibility path.
4. Recover the relevant Issue/spec/open PR/source/runtime evidence for the current request.
5. Distinguish historical assumptions from active specs and accepted runtime evidence.
6. Retain one task context; call domain/release contracts only as on-demand review lenses.
7. Ask the user only for product/protected-boundary decisions or authorizations that cannot be derived from repository evidence.

## Compatibility

Older prompts saying `Ты PM проекта MostDef2000/sea-speed` remain understandable because this file/path redirects that historical name to the Delivery Orchestrator role. New prompts should use the canonical wording above.
