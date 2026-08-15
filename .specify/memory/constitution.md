# Sea Speed SDD Constitution

Version: 1.1.0
Status: Active
Ratified: 2026-08-12
Amended: 2026-08-15

This constitution configures the SDD artifact layer. Canonical delivery/authorization remains in Sea Speed governance contracts.

## I. Product outcome before implementation
Every significant feature starts from observable outcome and protected boundaries before implementation details.

## II. Specifications are durable product intent
`specs/<feature>/spec.md` records WHAT/WHY. GitHub Issues remain canonical backlog, authorization and audit history.

## III. Plans explain architecture and decisions
`plan.md` records HOW, affected contours, compatibility, decisions/rejected alternatives and validation. Accepted runtime architecture differences are written back.

## IV. Tasks are executable and bounded
`tasks.md` records bounded delivery work and completion gates. Material scope change uses normal authorization.

## V. Runtime reality feeds SDD
Production acceptance/regressions/operational discoveries update active feature artifacts. Historical Issues/PRs/accepted decision records are not rewritten to hide prior assumptions.

## VI. Simplicity
Prefer the smallest operable architecture satisfying the outcome and compatibility boundaries.

## VII. Governance authority
SDD tooling does not grant source/merge/production authorization. New source work uses `OUTCOME APPROVED`; production remains separately exact-SHA authorized.

## VIII. Traceability
A significant PR links exactly one feature spec. Required `spec.md`, `plan.md`, `tasks.md` are CI validated. Docs/spec-only maintenance may remain lightweight.

## IX. Feature identity
The canonical feature identifier is the **full directory name**, for example `002-sdd-adoption`. Numeric prefixes are sequencing aids. The existing historical pair `002-camera-preview-gallery` / `002-sdd-adoption` is grandfathered and retained for compatibility/audit history. New duplicate numeric prefixes are prohibited.

## X. Automation without hidden state
Required product decisions live in GitHub artifacts, not only agent memory/chat.

## Standard lifecycle

```text
Issue + Outcome Contract
-> spec / plan / tasks
-> OUTCOME APPROVED
-> implementation
-> CI consistency + quality
-> exact-green-head merge
-> separately authorized runtime acceptance when applicable
-> runtime feedback written back
```
