# Security Metrics Framework

## Purpose and Scope

This framework defines recommended security, governance, and operational readiness metrics for LumenAI. It is designed to support executive reporting, hospital vendor assessments, internal risk management, and future readiness efforts.

The framework covers authentication, authorization, audit integrity, vulnerability management, operational security, tenant security, and abuse protection. It does not prescribe contractual service levels or formal compliance commitments.

These materials provide governance and reporting guidance only. Actual metrics, thresholds, and management decisions should be tailored to the production environment and organizational risk appetite.

## Security Governance Objectives

- Maintain visibility into security control operation and control drift.
- Track tenant isolation and object authorization enforcement outcomes.
- Monitor audit integrity, audit anchoring, and evidence preservation controls.
- Identify aging vulnerabilities, exceptions, and remediation bottlenecks.
- Provide leadership with consistent, evidence-based security status reporting.
- Escalate material risk trends before they affect enterprise customers.

## Reporting Audiences

- Executive leadership: risk posture, major trends, unresolved decisions, and investment needs.
- Security and engineering leadership: control health, remediation progress, and operational gaps.
- Compliance and readiness stakeholders: evidence availability, review cadence, and residual risks.
- Customer-facing security teams: procurement-ready summaries and factual control evidence.

## Reporting Cadence

- Weekly: operational exceptions, authentication anomalies, cross-tenant denials, rate-limit events, and high-priority remediation.
- Monthly: KPI trends, vulnerability aging, audit integrity status, migration validation, and control exceptions.
- Quarterly: management review, residual risk review, readiness evidence review, and roadmap prioritization.
- Annual: program effectiveness review, tabletop lessons learned, policy refresh, and readiness package review.

## Data Ownership

- Engineering owns application telemetry, authorization events, audit integrity checks, migration status, and CI validation results.
- Security owns risk interpretation, vulnerability triage, exception tracking, and governance reporting.
- Operations owns deployment health, backup validation evidence, incident readiness, and production monitoring handoffs.
- Product and customer teams own customer-facing evidence packaging and procurement response coordination.

## Review Process

1. Collect metrics from approved production, CI, audit, and ticketing sources.
2. Validate metric completeness and confirm no sensitive values are included in reports.
3. Compare current values against target guidance and previous reporting periods.
4. Review high-severity findings, stale remediation items, and exceptions.
5. Record decisions, accepted risks, owners, and due dates.
6. Preserve the reviewed report as readiness evidence.

## Escalation Process

Escalate when metrics indicate a material control gap, unresolved high-risk vulnerability, repeated tenant authorization denial pattern, audit chain or anchor verification failure, security validation pipeline regression, or production secret/configuration validation failure.

Escalation should include the impacted control, severity, affected tenants or systems where known, immediate containment steps, remediation owner, target date, and any customer or legal/privacy review dependency.

## Management Review Process

Management reviews should evaluate trends, unresolved decisions, policy exceptions, resource constraints, and residual risk acceptance. Each review should produce a dated record of reviewed metrics, approved remediation priorities, accepted risks, and follow-up owners.

## Recommended Metrics

### Authentication

- Failed authentication attempts: Count of failed protected-flow authentication attempts by source, actor where available, and route family.
- JWT validation failures: Count of JWT issuer, audience, expiration, signature, key, or claim validation failures.
- Tenant authorization denials: Count of authenticated users denied access because no enabled tenant membership authorized the requested object or dataset.

### Audit Integrity

- Audit chain verification status: Latest audit chain validation result by tenant.
- Audit anchor creation success rate: Percentage of scheduled or manual anchor attempts that completed successfully.
- Anchor verification failures: Count of audit anchor creation, provider, verification, or persistence failures.

### Vulnerability Management

- Open vulnerabilities: Count of active vulnerability findings by severity.
- Critical vulnerability aging: Age of unresolved critical findings from discovery date.
- Exception counts: Count of active vulnerability exceptions by severity, owner, and expiration status.
- Remediation completion rate: Percentage of due remediation items completed within the review period.

### Operational Security

- Security validation pipeline pass rate: Percentage of security validation workflows passing on pull requests and main branch updates.
- Migration validation success rate: Percentage of database migration validation runs that complete successfully.
- Secrets validation failures: Count of startup or CI failures caused by missing or unsafe production security configuration.

### Tenant Security

- JIT provisioning attempts: Count of tenant just-in-time provisioning attempts from validated identity claims.
- JIT provisioning denials: Count of denied provisioning attempts due to missing tenant claims, disallowed domains, or disallowed roles.
- SCIM provisioning events: Count of SCIM create, update, deactivate, group, and denial events.
- Cross-tenant access denials: Count of object authorization decisions denying cross-tenant access.

### Abuse Protection

- Rate-limit events: Count of requests rejected by rate limit policy by category and tenant where available.
- Abuse detection events: Count of abuse-oriented throttling or suspicious request events.
- Export throttling events: Count of export requests rejected or throttled under export limits.

## Evidence Expectations

Reports should reference source systems, date ranges, owners, and validation method. Reports must not include secrets, bearer tokens, private keys, raw JWTs, customer-sensitive payloads, or full audit metadata.
