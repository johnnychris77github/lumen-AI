# Enterprise Deployment Runbook

## Reviewer Note

These documents are internal enterprise readiness materials for deployment planning, hospital procurement review, vendor risk review, and future SOC 2/HITRUST preparation. They do not claim SOC 2, HITRUST, HIPAA, or any other formal certification.

## Deployment Overview

LumenAI is deployed as a backend API and supporting services for inspection, alert, audit, reporting, and enterprise governance workflows. The current production-oriented baseline uses:

- FastAPI backend API
- PostgreSQL database for durable application data
- Redis/RQ for queued work when enabled
- Nginx or an equivalent edge proxy
- Object/file storage for generated artifacts when configured
- GitHub Actions security validation for pull request and main-branch checks

Enterprise deployments should use separate environments for development, staging, and production. Production should not share database, Redis, signing, or storage credentials with lower environments.

## Required Environment Variables

Start from `backend/.env.example` when present and confirm required values before rollout. The current baseline expects:

| Variable | Purpose | Production expectation |
| --- | --- | --- |
| `DATABASE_URL` | Application database connection | PostgreSQL connection using a dedicated least-privilege application user |
| `REDIS_URL` | Queue/cache backend connection | Dedicated Redis instance or managed Redis endpoint |
| `QUEUE_BACKEND` | Queue mode | Explicitly set for the deployment architecture |
| `RESULT_MODE` | Result handling mode | Explicitly set and tested before go-live |
| `LUMENAI_JWT_SECRET` | Existing JWT/token signing secret | Strong random secret; never use sample values |
| `LUMENAI_DATA_DIR` | Local data/artifact path | Durable mounted volume if local storage is used |
| `LUMENAI_MODEL_PATH` | Optional local model path | Set only when local model serving is required |

Hardening PRs may also introduce or rely on these production controls:

| Variable | Purpose | Production expectation |
| --- | --- | --- |
| `LUMENAI_ENV` | Runtime environment selector | Set to `production` in production |
| `SECRET_KEY` | Application signing secret | Strong random value; required in production when supported |
| `JWT_SECRET_KEY` | JWT signing/validation secret when used | Strong random value or replaced by OIDC/JWKS mode |
| `LUMENAI_AUTH_MODE` | Auth mode: `dev_token`, `api_token`, or `jwt` | Production should use `api_token` or `jwt`; never `dev_token` |
| `LUMENAI_API_TOKEN` | Configured API token for API-token mode | Strong random value if API-token mode is used |
| `LUMENAI_JWT_ISSUER` | Expected OIDC issuer | Match enterprise IdP configuration |
| `LUMENAI_JWT_AUDIENCE` | Expected JWT audience | Match API audience registered with IdP |
| `LUMENAI_JWT_ALGORITHMS` | Allowed JWT algorithms | Prefer `RS256` for OIDC/JWKS deployments |
| `LUMENAI_JWT_JWKS_URL` | JWKS endpoint | HTTPS IdP JWKS URL |
| `LUMENAI_JWT_LEEWAY_SECONDS` | Clock skew tolerance | Keep minimal and documented |
| `LUMENAI_JWKS_CACHE_TTL_SECONDS` | JWKS cache TTL | Balance rotation responsiveness and request overhead |
| `LUMENAI_OIDC_PROVIDER` | Claim mapping profile | `generic`, `azure_ad`, `okta`, `auth0`, or `custom` |
| `LUMENAI_TENANT_JIT_ENABLED` | Tenant JIT provisioning toggle | Disabled by default; enable only after approval |
| `LUMENAI_TENANT_JIT_ALLOWED_DOMAINS` | Allowed email domains for JIT | Restrict to approved customer domains |
| `LUMENAI_TENANT_JIT_DEFAULT_ROLE` | Default JIT role | Use least privilege, typically `viewer` |
| `LUMENAI_TENANT_JIT_ALLOWED_ROLES` | Roles JIT may assign | Avoid admin roles by default |
| `LUMENAI_TENANT_JIT_REQUIRE_TENANT_CLAIM` | Require tenant claim for JIT | Keep enabled for enterprise deployments |
| `LUMENAI_AUDIT_ANCHOR_SCHEDULING_ENABLED` | Scheduled audit anchor toggle | Enable after audit anchor table migration |
| `LUMENAI_AUDIT_ANCHOR_INTERVAL_HOURS` | Anchor cadence | Choose based on audit/compliance requirements |
| `LUMENAI_AUDIT_ANCHOR_PROVIDER` | Anchor provider | `internal` until external provider support is approved |

## Production Secret Requirements

Production secrets must be unique, high entropy, environment-specific, and stored in the deployment secret manager or CI/CD secret store. Do not commit secrets to Git.

Unsafe values are not acceptable in production, including:

- `dev-token`
- `test-token`
- `changeme`
- `secret`
- `password`
- Local-only defaults
- Empty strings

Operational expectations:

- Rotate secrets during onboarding, personnel changes, suspected exposure, and scheduled maintenance windows.
- Limit secret access to deployment automation and designated administrators.
- Do not print secret values in logs, CI artifacts, error responses, support tickets, or review packets.
- Validate production configuration before exposing the deployment to users.

## Database Migration Process

1. Back up the production database.
2. Confirm the application image and migration files are from the approved release.
3. Set `LUMENAI_ENV=production` and production database credentials through the secret manager.
4. Run migrations using the approved Alembic command for the release:

   ```bash
   python -m alembic upgrade head
   ```

5. Review migration output for failures.
6. Run post-migration smoke checks for authentication, tenant-scoped reads, audit logging, and exports.
7. Record migration version, operator, timestamp, and release identifier in the deployment log.

Migration rules:

- Add nullable columns before enforcing constraints.
- Avoid destructive changes without a rollback and data-retention plan.
- Do not run production migrations from a developer laptop unless explicitly approved by operations.
- Validate migrations against a fresh SQLite or staging database in CI before production.

## Audit Hash Backfill Process

Run historical audit hash backfill only after the audit integrity columns exist.

Recommended sequence:

1. Confirm migrations adding audit hash fields have completed.
2. Run a dry run:

   ```bash
   python backend/scripts/backfill_audit_hashes.py --dry-run
   ```

3. Review safe summary counts. Do not export full metadata for review.
4. If needed, scope to one tenant:

   ```bash
   python backend/scripts/backfill_audit_hashes.py --tenant-id <tenant-id> --dry-run
   ```

5. Execute the backfill during a maintenance window:

   ```bash
   python backend/scripts/backfill_audit_hashes.py
   ```

6. Use `--force` only when approved, because it recalculates existing hashes.
7. Verify chain status after completion.

## Audit Anchor Scheduling Process

Audit anchors create periodic checkpoints for tenant audit chains. Use the internal provider until an external timestamp/notary provider is formally approved.

Configuration:

- `LUMENAI_AUDIT_ANCHOR_SCHEDULING_ENABLED=true`
- `LUMENAI_AUDIT_ANCHOR_INTERVAL_HOURS=<approved interval>`
- `LUMENAI_AUDIT_ANCHOR_PROVIDER=internal`

Operational expectations:

- Schedule the anchor runner through the approved scheduler for the environment.
- Create anchors only when new audit records exist since the last anchor.
- Store anchor records in the application database.
- Review anchor creation failures as security-relevant operational alerts.

## Rate Limiting Configuration

Default enterprise limits should be reviewed with the customer before go-live:

| Endpoint class | Default limit |
| --- | --- |
| Read endpoints | 300 requests/hour |
| Write endpoints | 100 requests/hour |
| Authentication endpoints | 20 requests/hour |
| Export endpoints | 25 requests/hour |

Rate limiting should distinguish tenant, authenticated user, and IP address when available. Exceeded limits should return HTTP 429 with retry metadata and create a safe audit event.

For multi-instance production deployments, prefer shared backing storage such as Redis so limits are enforced across all API workers.

## Security Header Configuration

Security headers should be applied centrally by middleware. Expected defaults:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Resource-Policy: same-origin`
- Conservative API Content Security Policy:
  - `default-src 'none';`
  - `frame-ancestors 'none';`
  - `base-uri 'none';`

HSTS should be enabled only when HTTPS is detected or explicitly configured:

- `Strict-Transport-Security: max-age=31536000; includeSubDomains`

Confirm CORS behavior remains compatible with approved frontend origins.

## OIDC/JWT Configuration

Enterprise identity federation should use `LUMENAI_AUTH_MODE=jwt` after validation in staging.

Required planning inputs:

- Identity provider: Azure AD, Okta, Auth0, generic OIDC, or custom
- Issuer
- Audience
- JWKS URL
- Allowed algorithms
- Claim mapping for actor ID, name, email, role, tenant ID, and tenant name
- Clock skew tolerance
- Key rotation expectations

Production expectations:

- Reject placeholder tokens.
- Validate signature before trusting claims.
- Validate issuer, audience, expiration, not-before, subject, and tenant claims when required.
- Do not log JWTs, claims containing sensitive values, or key material.
- Return 401 for missing or invalid credentials and 403 for authenticated users who lack authorization.

## Tenant JIT Configuration

Tenant just-in-time provisioning should remain disabled unless the customer explicitly approves it.

Recommended production posture:

- `LUMENAI_TENANT_JIT_ENABLED=false` by default
- Require tenant claim when enabled
- Restrict allowed domains
- Assign least-privilege default role
- Do not auto-create admin roles by default
- Do not escalate existing roles automatically
- Audit allowed and denied provisioning attempts

## Backup and Recovery Expectations

Backups must cover:

- PostgreSQL database
- Object/file storage for generated artifacts and evidence exports
- Deployment configuration excluding secret values
- Migration history
- Audit anchor records

Recovery expectations:

- Define recovery point objective and recovery time objective per customer contract.
- Test restore procedures before production go-live.
- Validate audit chain and anchor status after restore.
- Confirm tenant isolation and authentication after restore.

## Monitoring and Alerting Expectations

Monitor at minimum:

- API health and latency
- Authentication failures and authorization denials
- Rate-limit violations
- Export generation volume
- Audit logging failures
- Audit chain verification failures
- Anchor creation failures
- Migration failures
- Database and Redis resource saturation
- Background worker failures

Alerts should route to the responsible operations team with severity, affected environment, tenant scope when safe, and a runbook link. Do not include secrets, tokens, raw PHI, or sensitive metadata in alert payloads.

## Incident Response Expectations

Maintain an incident process covering:

1. Detection and triage
2. Containment
3. Evidence preservation
4. Tenant/customer impact analysis
5. Remediation
6. Customer notification according to contract and law
7. Post-incident review

Security-relevant incidents include suspected tenant data exposure, audit tampering, credential exposure, unauthorized export generation, failed integrity checks, and abnormal authentication activity.

## Rollback Considerations

Rollback planning must account for application and database state:

- Prefer forward fixes for migrations that add columns or tables.
- Do not drop audit records, audit hashes, anchors, or migration history during rollback.
- If a release introduces new data writes, confirm older application versions can tolerate the new schema.
- Keep a tested backup from before migration.
- Document any skipped backfill, anchor, or migration step before rollback.

## Operational Checklist

Before production go-live:

- [ ] Production environment variables configured through the secret manager.
- [ ] Unsafe default secrets rejected or replaced.
- [ ] Database migrations validated in CI and staging.
- [ ] Production database backup completed.
- [ ] Audit logging, hash chaining, and anchor process validated where enabled.
- [ ] Historical audit hash backfill plan approved if legacy data exists.
- [ ] Rate limits reviewed and configured.
- [ ] Security headers verified over HTTPS.
- [ ] OIDC/JWT configuration validated in staging, or approved API-token mode documented.
- [ ] Tenant JIT disabled or approved with allowed domains and least-privilege roles.
- [ ] TenantMembership-based tenant isolation tested for representative tenants.
- [ ] Export/reporting scoping validated.
- [ ] Monitoring and alerting destinations tested.
- [ ] Backup restore test completed or scheduled before go-live.
- [ ] Incident response contacts and escalation path documented.
- [ ] Rollback plan reviewed by engineering and operations.

## Evidence References

- Security review packet: `docs/security-review-packet.md`
- Security control evidence index: `docs/security-control-evidence-index.md`
- Object authorization audit: `docs/enterprise-readiness/object-authorization-remaining-lookup-audit-v1.md`
- Deployment baseline: `docs/deployment-baseline.md`
