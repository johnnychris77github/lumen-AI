# Security Review Packet

## Reviewer Note

This document is an internal enterprise readiness material for hospital procurement, vendor risk review, and future SOC 2/HITRUST preparation. It does not claim SOC 2, HITRUST, HIPAA, or any other formal certification.

## Platform Security Overview

LumenAI is a tenant-aware healthcare operations platform with backend controls for authentication, authorization, auditability, reporting, and operational governance. Enterprise hardening work focuses on preventing cross-tenant access, preserving audit evidence, validating security-sensitive code paths in CI, and preparing the platform for federated identity and formal security review.

Security review should be based on merged code, validation results, and the control evidence index at `docs/security-control-evidence-index.md`.

## Authentication and Authorization Model

Protected backend routes authenticate the caller before evaluating authorization. Production deployments should use configured API-token or JWT/OIDC modes rather than development tokens.

Authorization decisions should distinguish:

- Authentication failure: return HTTP 401.
- Authenticated user without required role or tenant scope: return HTTP 403.
- Requested object does not exist: return HTTP 404.

Global administrative roles are intended for platform-wide access:

- `admin`
- `super_admin`
- `security_admin`

Non-global users should be authorized through enabled tenant membership records, not through caller-supplied tenant identifiers.

## Tenant Isolation Model

Tenant isolation is based on `TenantMembership` records. Non-admin tenant access should require:

- `TenantMembership.user_email == current_user.email`
- `TenantMembership.tenant_id == tenant-owned record tenant_id`
- `TenantMembership.is_enabled is True`

This model is intended to protect inspection, alert, history, portfolio, analytics, reporting, audit, and export workflows from cross-tenant reads or mutations.

## Object-Level Authorization Model

Object-level authorization applies when a route loads a tenant-owned object by ID, such as an inspection, alert event, tenant record, remediation, CAPA-like record, quality event, or export source.

Expected behavior:

- Load the object.
- Return 404 if it does not exist.
- Authorize the tenant scope before returning or mutating data.
- Return 403 if the object exists but the caller is outside tenant scope.
- Build lists, summaries, exports, reports, and digests only from authorized rows.

Recent and planned evidence is tracked in the object authorization audit and security control evidence index.

## Audit Integrity Model

Audit logging is intended to provide durable records for security investigations, operational review, and customer evidence requests. Audit records should include tenant, actor, action, resource, timestamp, request source when available, and structured metadata.

Audit records should not expose secrets, bearer tokens, private keys, or raw sensitive payloads in logs or exported evidence.

## Audit Immutability and Hash Chaining

The enterprise audit posture is append-only:

- Existing audit records should not be modified.
- Existing audit records should not be deleted.
- Updates should create new audit records.

Hash chaining makes audit records tamper-evident by linking each record to the previous record hash and calculating a SHA-256 record hash from stable audit fields. Historical audit records can be backfilled into tenant-scoped chains after the required columns are present.

## Database-Level Audit Protection

Production PostgreSQL deployments should add database-level safeguards for audit logs, including triggers/functions that prevent UPDATE and DELETE operations on audit records while preserving INSERT. SQLite remains useful for development and tests but does not provide equivalent production-grade enforcement.

Database-level protections reduce risk from direct SQL tampering but do not replace database access control, backup protection, and privileged access monitoring.

## Secrets Management

Production deployments must reject missing or unsafe secrets. Secrets should be managed outside source control and never printed in logs or error responses.

Unsafe production values include:

- `dev-token`
- `test-token`
- `changeme`
- `secret`
- `password`
- Empty strings
- Local-only defaults

Required production secrets should include database credentials, signing keys, JWT/API-token secrets, audit/evidence signing material when configured, and storage credentials for non-local storage.

## Rate Limiting and Abuse Protection

Rate limiting should protect read, write, authentication, export, audit, enterprise, alert, and inspection endpoints. Limits should be evaluated by tenant, authenticated user, and IP address where available.

Expected default limits:

- Read endpoints: 300 requests/hour
- Write endpoints: 100 requests/hour
- Authentication endpoints: 20 requests/hour
- Export endpoints: 25 requests/hour

Exceeded limits should return HTTP 429 with retry metadata and create a safe audit event.

## Security Headers

The backend API should add centralized HTTP security headers:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Resource-Policy: same-origin`
- Conservative API Content Security Policy
- HSTS only over HTTPS or when explicitly enabled

CORS behavior should remain compatible with approved frontend origins.

## CI Security Validation

The CI security validation workflow is expected to run on pull requests and pushes to `main`. It validates:

- Python compilation for security-sensitive backend modules
- Security-focused regression tests when present on the branch
- Alembic migration execution against a fresh SQLite test database
- Lightweight dependency safety scanning
- A summary artifact for review evidence

This validation reduces regression risk but does not replace manual security review for high-risk changes.

## Migration Governance

Schema changes should be delivered through migration files, validated in CI, and applied through a controlled production process. Production migrations should be backward compatible where possible:

- Add nullable columns before enforcing constraints.
- Avoid destructive changes.
- Do not drop legacy columns or audit evidence without a retention-approved process.
- Keep SQLite development compatibility where practical.

## OIDC/JWT Readiness

LumenAI is being prepared for enterprise identity federation using JWT/OIDC scaffolding:

- Issuer validation
- Audience validation
- Expiration and not-before validation
- Subject validation
- JWKS signature validation and key rotation readiness
- Provider-specific claim mapping for generic OIDC, Azure AD, Okta, Auth0, and custom providers

Production deployments should verify IdP configuration in staging before enabling JWT mode.

## Tenant JIT Provisioning

Tenant JIT provisioning can create tenant memberships from validated OIDC claims when explicitly enabled. It should be controlled by:

- Allowed domains
- Required tenant claims
- Least-privilege default roles
- Allowed role list
- No automatic role escalation
- Audit events for created and denied attempts

Tenant JIT should remain disabled by default.

## Analytics and Reporting Export Tenant Scoping

Analytics, reporting, QA review, board reporting, digest, PowerBI, alert-history, and inspection-history exports should be built only from rows the caller is authorized to access. Global admins may access platform-wide data. Non-admin users should only receive data for tenants where they have enabled `TenantMembership`.

Export routes are high-risk because they can aggregate many rows. Reviewers should prioritize export scoping tests and code review before merge.

## Residual Risks

Known residual gaps to track:

- Live OIDC provider integration and customer-specific IdP validation
- External timestamp/notary provider for audit anchors
- Redis-backed distributed rate limiting for horizontally scaled production
- Full CI security workflow adoption across all branches
- SCIM or group lifecycle sync for enterprise identity operations
- Production deployment runbook rehearsal and sign-off
- Frontend CSP/static asset hardening
- Formal SOC 2/HITRUST evidence packet and third-party audit
- Privileged database access monitoring and break-glass procedures

## Shared Responsibility Model

LumenAI is responsible for:

- Application security controls
- Tenant isolation logic
- Audit logging and integrity controls
- Secure defaults and configuration validation
- Security-focused CI validation
- Documentation for deployment and review

The deploying organization or customer is responsible for:

- Identity provider configuration
- Network access controls
- Production secret storage
- Backup retention and restore testing
- Monitoring destinations and incident escalation contacts
- User provisioning and deprovisioning processes
- Regulatory determinations and contractual compliance obligations

## Evidence Index Reference

Control-by-control evidence should be reviewed in:

- `docs/security-control-evidence-index.md`

Related supporting documents:

- `docs/enterprise-deployment-runbook.md`
- `docs/enterprise-readiness/object-authorization-remaining-lookup-audit-v1.md`
- `docs/deployment-baseline.md`
