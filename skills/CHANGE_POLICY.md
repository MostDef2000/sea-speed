# Skills Change Policy

## Canonical rule

Files in `skills/` are controlled compatibility entrypoints. Canonical workflow rules live in `contracts/**`.

## Approval

Changes under `skills/**` require both:

```text
COMMIT APPROVED
SKILL UPDATE APPROVED
```

Approved equivalents may authorize repository writes, but `SKILL UPDATE APPROVED` remains mandatory for skill-file changes.

## Allowed without approval

- read or quote skill files;
- inspect linked contracts;
- propose changes and diffs;
- analyze workflow behavior.

## Forbidden without approval

- create, overwrite, rename or delete skill files;
- silently expand skill scope;
- make a skill conflict with its canonical branch contract.

## Review rule

Every skill change must state the changed file, reason, affected workflow, linked canonical contract and risk. Skills must stay concise and route to contracts rather than duplicate the full control plane.