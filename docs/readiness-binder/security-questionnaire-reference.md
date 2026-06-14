# Security Questionnaire Reference

## Authentication

LumenAI protected routes require authenticated access before authorization decisions are made. Development-token behavior is preserved only for local/test workflows, while enterprise hardening work adds API-token and JWT/OIDC readiness paths. Authentication failures should return HTTP 401 without exposing credential values. Evidence is tracked in PRs #9, #16, #17, #18, #19, #20, and the control matrix.

## Authorization

Authorization distinguishes global administrative roles from tenant-scoped users. Global roles such as `admin`, `super_admin`, and `security_admin` are intended for platform-wide operations. Non-admin access is scoped through enabled `TenantMembership` records. Evidence includes object authorization and tenant scoping PRs #4, #21, #22, #23, and #24.

## Tenant Isolation

Tenant isolation is enforced by checking enabled tenant membership rows rather than trusting caller-provided tenant IDs or deprecated user tenant fields. List, detail, mutation, export, reporting, history, alert, agent, and analytics routes are progressively scoped to authorized tenant data. Evidence includes PRs #4, #21, #22, #23, and #24.

## Object-Level Authorization

Object lookups should return 404 when an object does not exist and 403 when the object exists but the authenticated user lacks tenant scope. This pattern applies to inspections, alert events, tenant portfolio records, remediations, analytics/reporting rows, QA review mutations, and exports. Evidence includes PRs #4, #21, #22, #23, and #24.

## Audit Logging

Audit logging records security-relevant activity with tenant, actor, action, resource, timestamp, request source when available, and structured metadata. Audit events are intended for operational review, forensic investigations, and enterprise evidence requests. Evidence includes PRs #5, #10, #12, #13, #14, #15, and #31.

## Audit Integrity

Audit integrity controls include append-only application behavior, hash-chain readiness, historical hash backfill, database-level update/delete safeguards for production PostgreSQL, and chain verification support. Evidence includes PRs #5, #10, #11, #12, and #13.

## Audit Anchoring

Audit anchoring creates periodic checkpoints for tenant audit chains. Internal anchors are supported first, scheduled anchors support periodic checkpoints, and external HTTP timestamp/notary provider readiness adds off-database verification capability. Evidence includes PRs #14, #15, and #31.

## Encryption

Production deployments should use TLS for user access, API traffic, identity provider integrations, Redis where applicable, external notary providers, and storage endpoints. Database and object-storage encryption at rest are deployment responsibilities and should be validated with the hosting environment. Evidence references include deployment baseline documentation and the enterprise deployment runbook.

## Secrets Management

Production secrets must not use unsafe defaults such as `dev-token`, `changeme`, `secret`, `password`, local-only placeholders, or empty values. Secrets should be provided through approved deployment secret stores and must not appear in logs, error messages, CI artifacts, static frontend bundles, or documentation. Evidence includes PRs #8, #9, #26, #27, #30, and #31.

## Rate Limiting

Rate limiting supports read, write, authentication, and export endpoint classes, with tenant, user, and IP scoping where available. Redis-backed distributed enforcement is available for multi-instance deployments, with fallback or fail-closed behavior. Evidence includes PRs #6 and #28.

## Vulnerability Management

The CI security validation workflow includes lightweight dependency safety scanning when available and security-focused regression tests. Findings should be reviewed, remediated, or risk-accepted through the security review process. Evidence includes PR #26.

## CI Security Validation

Security validation is designed to run on pull requests and pushes to `main`. It compiles security-sensitive backend modules, runs security-focused tests, validates migrations against a fresh SQLite database, performs dependency scanning, and emits a summary artifact. Evidence includes PR #26.

## Identity Federation

JWT/OIDC readiness supports issuer, audience, expiration, not-before, subject, tenant claim validation, JWKS signature validation, key rotation readiness, provider claim mapping, and controlled tenant JIT membership provisioning. Live provider integration remains environment-specific. Evidence includes PRs #16, #17, #18, #19, and #20.

## SCIM Provisioning

SCIM readiness supports disabled-by-default user and group lifecycle provisioning with a dedicated SCIM bearer token, tenant allow-lists, safe role mapping, membership deactivation instead of hard deletion, and audit events for lifecycle actions. Live Azure AD, Okta, and Auth0 validation remains customer-specific. Evidence includes PR #29.

## Incident Response

Incident response expectations include detection, triage, containment, evidence preservation, customer impact analysis, remediation, notification according to contract/law, and post-incident review. The deployment runbook provides operational expectations. Formal customer-specific procedures remain a deployment readiness activity. Evidence includes PR #27.

## Backup and Recovery

Production backup and recovery should cover the database, object/file storage, deployment configuration excluding secret values, migration history, audit hashes, and audit anchors. Restore testing should include audit chain and tenant isolation validation. Evidence includes PR #27 and database migration/backfill PRs #11 and #12.

## Secure Development Lifecycle

The secure development lifecycle uses reviewable PRs, scoped changes, regression tests, security validation workflow checks, migration governance, documentation updates, and explicit residual risk tracking. Evidence includes PRs #21, #25, #26, #27, and #32.

## Change Management

Security-sensitive changes are documented through PRs, validation commands, changed-file scope, and residual gaps. Database changes should use Alembic migrations, avoid destructive changes, and validate against non-production databases before production rollout. Evidence includes PRs #11, #25, #26, and #27.

## Certification Language

Use readiness language only. Acceptable phrases include "readiness," "preparedness," "control implementation," "evidence available," and "planned improvement." Avoid any wording that implies a completed third-party compliance attestation unless that attestation exists and has been approved for distribution.
