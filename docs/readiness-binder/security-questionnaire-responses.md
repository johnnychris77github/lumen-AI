# Security Questionnaire Response Pack

## Use Guidance

This response pack provides reusable, procurement-ready answers for hospital vendor reviews and enterprise cybersecurity questionnaires. Responses describe current readiness, implemented controls, evidence available, residual gaps, and planned improvements. This document does not claim SOC 2 certification, HITRUST certification, HIPAA certification, or any other formal certification.

## Company/Product Overview

**Standard questionnaire answer:** LumenAI is an enterprise healthcare operations platform for inspection workflows, alerting, audit evidence, reporting, and governance processes. The platform is being hardened for hospital procurement review, vendor risk review, and future SOC 2 / HITRUST readiness.

**Evidence reference:** `docs/readiness-binder/security-questionnaire-responses.md`, `docs/deployment-baseline.md`, `docs/enterprise-readiness/object-authorization-remaining-lookup-audit-v1.md`

**Current status:** Enterprise readiness documentation and control evidence are available in repository documentation.

**Residual gap:** Formal third-party certification and customer-specific deployment evidence are not included in this repository.

**Planned improvement:** Maintain a release-by-release evidence package and deployment-specific runbook outputs.

## Data Handling

**Standard questionnaire answer:** LumenAI is designed to process tenant-scoped operational data and inspection-derived records. Access to tenant-owned data is intended to be restricted through authentication, authorization, tenant membership checks, and scoped reporting/export logic.

**Evidence reference:** PRs #4, #21, #22, #23, #24; object authorization audit at `docs/enterprise-readiness/object-authorization-remaining-lookup-audit-v1.md`

**Current status:** Multiple route groups have tenant-membership scoping and export filtering evidence.

**Residual gap:** Customer-specific data classification, retention, and DPA/BAA requirements must be validated per deployment.

**Planned improvement:** Add customer-specific data flow diagrams and retention schedules to deployment packets.

## Authentication

**Standard questionnaire answer:** Protected routes require bearer authentication. Development-token behavior is preserved for local/test workflows, while enterprise hardening adds safer token validation, API-token readiness, and JWT/OIDC readiness.

**Evidence reference:** PRs #9, #16, #17, #18, #20

**Current status:** Token hardening and JWT/OIDC readiness controls are documented and tested in hardening PRs.

**Residual gap:** Live identity-provider validation is environment-specific.

**Planned improvement:** Validate Azure AD, Okta, and Auth0 configurations in staging for each enterprise customer.

## Authorization

**Standard questionnaire answer:** Authorization separates global administrative roles from tenant-scoped users. Non-admin access is based on enabled `TenantMembership` records and should not rely on caller-supplied tenant IDs.

**Evidence reference:** PRs #4, #21, #22, #23, #24

**Current status:** Inspection, alert, history, portfolio, agent, PowerBI, analytics, reporting, QA, and digest route groups have tenant-scoping evidence.

**Residual gap:** Authorization helper deduplication remains an improvement area.

**Planned improvement:** Centralize tenant-scoped query and object authorization helpers.

## Tenant Isolation

**Standard questionnaire answer:** Tenant isolation is implemented through enabled tenant membership checks that match authenticated user email to tenant-owned records. Lists, summaries, exports, reports, and object lookups are progressively scoped to authorized tenant rows.

**Evidence reference:** PRs #4, #21, #22, #23, #24

**Current status:** Tenant isolation regression tests exist for several high-risk route groups.

**Residual gap:** New route groups require continued tenant isolation review.

**Planned improvement:** Keep object authorization audit and control matrix current with each release.

## Encryption

**Standard questionnaire answer:** Production deployments should use TLS for user traffic, API traffic, identity provider integrations, Redis, external notary providers, and storage endpoints. Encryption at rest is a deployment responsibility for database, storage, and backup services.

**Evidence reference:** Deployment baseline at `docs/deployment-baseline.md`; runbook/readiness references in PR #27 and PR #32

**Current status:** Encryption expectations are documented for production readiness.

**Residual gap:** Hosting-provider encryption settings must be verified per environment.

**Planned improvement:** Add customer-specific evidence for TLS, database encryption, storage encryption, and backup encryption.

## Secrets Management

**Standard questionnaire answer:** Production deployments must reject unsafe default secrets and avoid printing secret values in logs, error responses, documentation, or CI artifacts. Secrets should be provided through approved deployment secret stores.

**Evidence reference:** PRs #8, #9, #26, #27, #30, #31

**Current status:** Secrets management readiness controls and scanner checks are documented in hardening PRs.

**Residual gap:** External secret manager integration is deployment-specific.

**Planned improvement:** Add managed secret-store integration guidance for each hosting environment.

## Audit Logging

**Standard questionnaire answer:** LumenAI audit logging is intended to capture security-relevant tenant, actor, action, resource, timestamp, request source when available, and structured metadata fields.

**Evidence reference:** PRs #5, #10, #12, #13, #14, #15, #31

**Current status:** Audit control implementation and tests are tracked across enterprise hardening PRs.

**Residual gap:** Customer-specific audit retention and export evidence must be validated in deployment.

**Planned improvement:** Add deployment-specific audit retention and review procedures.

## Audit Integrity

**Standard questionnaire answer:** Audit integrity readiness includes append-only audit behavior, hash-chain support, historical hash backfill, chain verification, and production database-level protection against audit update/delete where PostgreSQL is used.

**Evidence reference:** PRs #5, #10, #11, #12, #13

**Current status:** Audit immutability, hash chain, migration, backfill, and database protection evidence are tracked.

**Residual gap:** SQLite development environments cannot enforce the same database-level protections as production PostgreSQL.

**Planned improvement:** Validate PostgreSQL trigger protections in staging and production rollout.

## Audit Anchoring

**Standard questionnaire answer:** Audit anchoring creates internal or external timestamp/notary checkpoints for audit chains. External provider support sends only safe anchor material and does not transmit full audit metadata or secrets.

**Evidence reference:** PRs #14, #15, #31

**Current status:** Internal, scheduled, and external HTTP provider readiness controls are documented and tested.

**Residual gap:** Live external notary provider selection and validation remain deployment decisions.

**Planned improvement:** Pilot approved notary provider integration and validate retention/legal acceptability.

## Database Protection

**Standard questionnaire answer:** Database protection readiness includes migration governance, backward-compatible schema changes, audit-log protection in PostgreSQL, and avoiding destructive audit history changes.

**Evidence reference:** PRs #11, #13

**Current status:** Migration foundation and audit DB protection evidence are tracked.

**Residual gap:** Production database access monitoring and break-glass controls are environment-specific.

**Planned improvement:** Add database access monitoring and privileged access review evidence to deployment packets.

## Rate Limiting

**Standard questionnaire answer:** LumenAI rate limiting supports read, write, authentication, and export endpoint classes, with tenant, user, and IP scoping where available. Redis-backed distributed enforcement supports multi-instance deployments.

**Evidence reference:** PRs #6, #28

**Current status:** Rate-limit controls and Redis-backed readiness tests are available.

**Residual gap:** Redis high-availability behavior must be validated per production topology.

**Planned improvement:** Run managed Redis failover testing in staging.

## Security Headers

**Standard questionnaire answer:** Backend/API security headers and frontend/static CSP guidance reduce browser and API attack surface. Production static hosting should apply CSP, referrer, permissions, frame, content-type, and cross-origin resource policies.

**Evidence reference:** PRs #7, #30

**Current status:** Backend headers and frontend CSP/static asset hardening guidance are documented.

**Residual gap:** Final browser-observed headers depend on customer hosting/CDN configuration.

**Planned improvement:** Add deployed-browser CSP validation to release readiness checks.

## OIDC/JWT Readiness

**Standard questionnaire answer:** LumenAI includes JWT/OIDC readiness for issuer, audience, expiration, not-before, subject, tenant claim validation, JWKS signature verification, provider claim mapping, and controlled tenant JIT provisioning.

**Evidence reference:** PRs #16, #17, #18, #19, #20

**Current status:** OIDC/JWT readiness controls are implemented and tested without requiring a live provider in unit tests.

**Residual gap:** Live provider validation is customer-specific.

**Planned improvement:** Complete customer IdP staging validation and document claim mapping.

## SCIM Readiness

**Standard questionnaire answer:** SCIM readiness supports disabled-by-default user and group lifecycle provisioning, a dedicated SCIM bearer token, tenant allow-lists, safe role mapping, membership deactivation rather than hard deletion, and SCIM audit events.

**Evidence reference:** PR #29

**Current status:** SCIM lifecycle provisioning tests cover disabled mode, token rejection, provisioning, role mapping, deactivation, cross-tenant denial, and audit events.

**Residual gap:** Minimal SCIM compatibility does not represent full SCIM specification coverage.

**Planned improvement:** Validate with Azure AD, Okta, and Auth0 and expand compatibility based on customer needs.

## CI/Security Validation

**Standard questionnaire answer:** CI security validation is designed to run on pull requests and pushes to `main`, compiling security-sensitive modules, running security regression tests, validating migrations, scanning dependencies, and producing a summary artifact.

**Evidence reference:** PR #26

**Current status:** CI security validation workflow is documented as readiness evidence.

**Residual gap:** Branch protection must require the workflow in GitHub settings.

**Planned improvement:** Enforce required checks in repository branch protection.

## Vulnerability Management

**Standard questionnaire answer:** Vulnerability management readiness includes lightweight dependency scanning in CI when available, security regression tests, reviewable PRs, and explicit residual risk tracking.

**Evidence reference:** PRs #25, #26, #32

**Current status:** Dependency scan readiness and evidence tracking are documented.

**Residual gap:** Formal vulnerability management SLAs and third-party penetration test evidence are not included in this repository.

**Planned improvement:** Define SLAs, add Dependabot/SCA policy, and schedule penetration testing.

## Incident Response

**Standard questionnaire answer:** Incident response expectations include detection, triage, containment, evidence preservation, impact analysis, remediation, customer notification according to contract/law, and post-incident review.

**Evidence reference:** PR #27, readiness binder residual risk register

**Current status:** Incident response expectations are documented as readiness material.

**Residual gap:** Customer-specific contacts, notification timing, and escalation procedures must be completed per deployment.

**Planned improvement:** Add deployment-specific incident response appendix.

## Backup and Recovery

**Standard questionnaire answer:** Backup and recovery readiness should cover databases, object/file storage, configuration excluding secret values, migration history, audit hashes, and audit anchors. Restore testing should validate tenant isolation and audit integrity.

**Evidence reference:** PRs #11, #12, #27

**Current status:** Backup and recovery expectations are documented.

**Residual gap:** Restore test evidence is deployment-specific.

**Planned improvement:** Run restore drills before production go-live.

## Business Continuity

**Standard questionnaire answer:** Business continuity readiness depends on deployment architecture, backups, restore procedures, monitoring, incident response, and operational runbooks. The repository provides readiness guidance; customer-hosted or managed environments must validate their own continuity controls.

**Evidence reference:** PR #27, `docs/deployment-baseline.md`

**Current status:** Operational expectations are documented.

**Residual gap:** RTO/RPO targets and failover evidence must be defined per customer contract.

**Planned improvement:** Add customer-specific RTO/RPO and continuity test records.

## Change Management

**Standard questionnaire answer:** Security-sensitive changes are tracked through scoped PRs, changed files, validation commands, tests, and documentation updates. Database changes should use migration governance and avoid destructive schema changes where possible.

**Evidence reference:** PRs #11, #25, #26, #27, #32

**Current status:** Change evidence is tracked through hardening PRs and readiness documentation.

**Residual gap:** Formal release approval workflow may vary by deployment.

**Planned improvement:** Add release approval checklist and production change log.

## Access Reviews

**Standard questionnaire answer:** Access review readiness is supported by role-based access, tenant membership records, audit logging, and SCIM/OIDC lifecycle readiness. Formal recurring access review operations are deployment responsibilities.

**Evidence reference:** PRs #4, #19, #20, #29

**Current status:** Technical controls for tenant membership and lifecycle provisioning are available.

**Residual gap:** Recurring access review cadence and evidence must be operationalized.

**Planned improvement:** Add quarterly access review procedure and evidence template.

## Logging and Monitoring

**Standard questionnaire answer:** Logging and monitoring readiness includes audit events, rate-limit violation audit events, anchor failures, authentication failures, authorization denials, export generation, migration status, and platform health checks. Monitoring destinations are deployment-specific.

**Evidence reference:** PRs #5, #6, #14, #15, #26, #27, #28, #31

**Current status:** Application-level audit and validation evidence exists.

**Residual gap:** Central SIEM/log retention integration is deployment-specific.

**Planned improvement:** Add SIEM forwarding and alert routing documentation.

## Vendor/Subprocessor Management

**Standard questionnaire answer:** Vendor and subprocessor management depends on selected hosting, identity, Redis, storage, email, notary, and monitoring providers. LumenAI documentation identifies integration points but does not bundle a universal subprocessor list.

**Evidence reference:** Deployment runbook/readiness binder, PRs #27, #28, #31

**Current status:** Provider dependency categories are documented.

**Residual gap:** Customer-specific subprocessor list and DPAs are deployment/commercial responsibilities.

**Planned improvement:** Maintain a deployment-specific subprocessor register.

## Compliance Readiness

**Standard questionnaire answer:** LumenAI maintains security readiness documentation, control evidence mapping, and residual risk tracking for future SOC 2 and HITRUST readiness efforts. The repository does not provide a completed SOC 2 report, HITRUST certification, HIPAA certification, or other formal attestation.

**Evidence reference:** PRs #25, #27, #32; readiness binder documents

**Current status:** Readiness documentation and evidence mapping are available.

**Residual gap:** Formal third-party assessment has not been completed through this repository evidence package.

**Planned improvement:** Engage qualified advisors/auditors and build a formal evidence packet.

## Short-Form Common Answers

| Question | Short answer |
| --- | --- |
| Do you support SSO? | JWT/OIDC readiness is implemented for enterprise SSO preparation; live IdP validation is customer-specific. |
| Do you support MFA? | MFA is expected to be enforced by the customer's identity provider in OIDC/SSO deployments. |
| Do you support SCIM? | SCIM readiness exists for user/group lifecycle provisioning; it is disabled by default and requires a dedicated bearer token. |
| Is audit logging available? | Yes, audit logging readiness is available for security-relevant events and enterprise evidence workflows. |
| Are audit logs immutable? | Audit immutability readiness includes append-only behavior, hash-chain support, backfill, and database-level protections where supported. |
| Do you support tenant isolation? | Yes, tenant isolation is based on enabled tenant membership checks and scoped route/query behavior. |
| Do you encrypt data? | TLS and encryption-at-rest expectations are documented; final encryption evidence depends on deployment infrastructure. |
| Do you have incident response procedures? | Incident response expectations are documented; customer-specific contacts and procedures must be completed per deployment. |
| Do you have SOC 2? | No completed SOC 2 report is claimed in this repository; SOC 2 readiness documentation and evidence mapping are available. |
| Do you have HITRUST? | No HITRUST certification is claimed in this repository; HITRUST readiness tracking is documented as a planned effort. |
| Do you conduct penetration testing? | Penetration testing is listed as a planned vulnerability management improvement unless customer-specific evidence is provided separately. |
