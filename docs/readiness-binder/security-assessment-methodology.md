# Security Assessment Methodology

## Assessment Lifecycle

Security assessments should follow a repeatable lifecycle: planning, scoping, technical assessment, findings review, risk rating, reporting, remediation tracking, validation, and closure.

These materials are readiness and planning documents only. They do not represent a completed penetration test, security assessment, certification, attestation, or regulatory determination.

## Planning Phase

- Identify assessment sponsor, technical contacts, escalation contacts, and approval authority.
- Define assessment objectives, business drivers, timing constraints, and evidence needs.
- Confirm data handling rules, test accounts, environment readiness, and monitoring expectations.
- Identify dependencies on identity providers, CI validation, logging, audit integrity, or deployment controls.

## Scoping Phase

- Define in-scope applications, APIs, endpoints, roles, tenants, exports, and environments.
- Identify out-of-scope systems, prohibited techniques, rate limits, and stop-test criteria.
- Confirm whether production testing is permitted and under what constraints.
- Document assumptions, test credentials, test tenants, and third-party dependencies.

## Technical Assessment Phase

Assessment activities may include authentication testing, authorization testing, tenant isolation testing, API security review, export and reporting review, audit integrity validation, rate-limit checks, secrets exposure checks, security header review, JWT/OIDC control review, CI validation review, logging review, and deployment hardening review.

Testing should use safe proof-of-concept evidence and should avoid collecting secrets, private keys, raw tokens, customer data, or unnecessary sensitive payloads.

## Findings Review Process

Findings should be reviewed with engineering and security owners before finalization to confirm technical accuracy, affected components, severity, remediation path, and any compensating controls.

Duplicate, accepted, false-positive, and out-of-scope findings should be tracked with rationale.

## Risk Rating Methodology

Severity should consider exploitability, required privileges, tenant impact, data exposure risk, audit/evidence impact, business impact, detectability, and compensating controls.

Recommended severity bands:

- Critical: likely material customer impact, cross-tenant exposure, credential compromise, or loss of audit integrity.
- High: exploitable control weakness with significant data, authorization, or operational impact.
- Medium: meaningful weakness requiring remediation but limited by prerequisites or compensating controls.
- Low: defense-in-depth issue, configuration improvement, or low-impact weakness.
- Informational: observation or improvement opportunity without confirmed exploit path.

## Reporting Process

Assessment reports should include scope, methodology, findings by severity, executive summary, technical evidence, business impact, remediation recommendations, management response, and residual risks.

Reports should be sanitized before external sharing and should avoid sensitive values.

## Remediation Tracking Process

Track each finding with owner, severity, status, target date, remediation plan, linked code or configuration change, validation evidence, and exception status if applicable.

Remediation should be prioritized by severity, tenant impact, exploitability, customer commitments, and control dependencies.

## Validation and Closure Process

Closure requires evidence that the remediation addresses the finding and that the validated behavior matches expectations. Where feasible, automated regression tests or CI checks should be added to prevent recurrence.

Residual risks should be documented when a finding is accepted, deferred, partially mitigated, or dependent on future architecture work.

## Related Controls

Assessment planning should reference the Security Control Evidence Index, Security Metrics Framework, Vulnerability Management Program, Incident Response Readiness, BC/DR Readiness, and CI Security Validation materials when available.
