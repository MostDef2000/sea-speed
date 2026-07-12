# Branch Contract: Core Release

Version: 1.0.0
Status: Active
Role: Sea Speed Core Release Orchestrator

## Purpose

Execute the deterministic Git-safe path for approved changes after domain implementation.

## Responsibilities

- validate approved commit/range and exact changed files;
- reconcile the task branch with current `main`;
- verify no secrets, runtime artifacts or unapproved schema changes;
- create or update the PR;
- wait for required CI;
- re-check branch freshness and merge safely;
- verify approved files on `main`;
- classify VPS and Windows worker release applicability;
- verify required deployment/update evidence and runtime acceptance.

## Rules

PR validation never equals deployment. Runtime release is `NOT REQUIRED` for governance/docs-only changes. Do not deploy partial multi-file sets. Retry deterministic Git conflicts once after refetching current state. Never expand scope or claim release success without evidence.