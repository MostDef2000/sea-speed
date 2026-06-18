# Sea Speed

Camera-based vehicle detection and speed-estimation project.

## Architecture

```text
camera / HLS stream
-> Windows AI worker
-> VPS FastAPI backend
-> operator web UI
```

## Goal

Detect passing vehicles, show reliable evidence in the operator UI, store event snapshots, and estimate speed in a reviewable way.

## Repository Layout

```text
worker/      Windows AI worker source and runtime scripts
api/         FastAPI backend
frontend/    Operator web UI
deploy/      VPS and Windows deployment helpers
docs/        Decisions, operations, calibration, troubleshooting
```

## Source of Truth

GitHub is the source of truth for code and project history.

VPS holds the main deployed working copy.

Windows laptop is used for AI compute and runs only the worker runtime.

## Secrets Policy

Never commit tokens, passwords, private camera credentials, `.env` files, runtime logs, event snapshots, or local model binaries unless explicitly approved.
