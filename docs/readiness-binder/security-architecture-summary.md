# Security Architecture Summary

## High-Level Platform Architecture

LumenAI is a backend API and frontend application for inspection, alerting, audit, reporting, and enterprise governance workflows. Production-oriented deployments use:

- FastAPI backend API
- PostgreSQL database for durable data
- Redis/RQ where queued work or distributed rate limiting is enabled
- Static frontend hosting for Vite/React build output
- Nginx, CDN, or equivalent edge layer
- CI security validation for security-sensitive regression checks

## Authentication Model

Protected APIs require bearer authentication. Development tokens remain local/test conveniences. Enterprise readiness work adds API-token and JWT/OIDC validation paths, including JWKS signature validation, provider claim mapping, tenant claim extraction, and controlled tenant JIT provisioning.

## Authorization Model

Global administrative roles can perform platform-wide operations. Non-admin authorization is tenant-scoped through enabled `TenantMembership` records. Authentication failure should return 401; authenticated users outside scope should receive 403.

## Tenant Isolation Model

Tenant isolation is implemented through membership checks that compare the authenticated actor email to enabled tenant membership rows for the tenant-owned data being accessed. This model applies to inspections, alerts, history, exports, portfolio data, analytics, reporting, QA review, and digest workflows.

## Object Authorization Model

Object-level routes should load the requested object, return 404 if it does not exist, and return 403 if it exists but is outside the user's tenant scope. Lists, summaries, exports, and reports must be constructed only from scoped rows.

## Audit Integrity Model

Audit readiness includes append-only behavior, structured audit events, hash chaining, historical hash backfill, database-level update/delete safeguards for production PostgreSQL, internal anchors, scheduled anchors, and external HTTP timestamp/notary provider support.

## Reporting Isolation Model

Reporting, analytics, PowerBI, board reporting, QA, digest, and export endpoints should use scoped inspection-derived rows. Global admins may access platform-wide datasets; non-admin users receive only tenant-authorized rows.

## Security Validation Pipeline

The CI security validation pipeline is designed to compile security-sensitive backend modules, run security regression suites, validate migrations against a fresh SQLite database, perform lightweight dependency scanning, and generate a summary artifact.

## Deployment Model

Production deployments should use environment-specific secrets, PostgreSQL, approved Redis/queue services where needed, TLS, controlled static hosting headers, migration validation, backups, monitoring, and incident response procedures. Development and test workflows remain compatible with local defaults.

## Shared Responsibility Model

LumenAI is responsible for application controls, code-level tenant isolation, audit integrity features, security tests, and readiness documentation. The deploying organization is responsible for production secret storage, network controls, identity provider configuration, backup restore testing, monitoring destinations, incident escalation paths, and regulatory determinations.
