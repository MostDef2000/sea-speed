# Feature Specification: Auth outage fallback

- Feature: 033-auth-outage-fallback
- Issue: #250
- Status: Active

## Product outcome

When the private Ubuntu Worker/Auth v1 dependency is unavailable, Sea Speed keeps the protected boundary fail-closed while presenting a VPS-hosted HTTP 503 outage response instead of the default nginx error page.

## Requirements

- Protected Sea Speed routes remain authenticated.
- No protected frontend/API/media content is returned anonymously.
- The fallback asset is served from VPS-local storage only.
- Normal Authentik authentication resumes after dependency recovery.
- Ordinary application failures remain distinguishable from authentication dependency outage.

## NFR assessment

- NFR-SEC-001: no authentication bypass through outage handling.
- NFR-REL-001: degraded authentication dependency state has deterministic user feedback.
- NFR-OPS-001: deployment rollback remains bounded and auditable.
