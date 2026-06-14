# Penetration Testing Policy

## Purpose and Scope

This policy defines LumenAI readiness expectations for penetration testing and security assessment activities. It supports hospital cybersecurity reviews, vendor risk assessments, third-party security testing engagements, and future readiness initiatives.

This document applies to application, API, authentication, tenant isolation, reporting/export, audit integrity, configuration, and deployment security testing. It is a planning document and does not represent a completed penetration test, security assessment, certification, attestation, or regulatory determination.

## Testing Objectives

- Validate authentication, session, and token controls.
- Validate object-level authorization and tenant isolation controls.
- Assess audit logging, audit integrity, and evidence preservation behavior.
- Evaluate rate limiting, abuse protection, and export throttling behavior.
- Review secrets handling, security headers, deployment configuration, and CI validation controls.
- Produce actionable findings, remediation owners, and retest evidence.

## Internal Testing Guidance

Internal testing should be performed by authorized personnel using approved test accounts, test tenants, and non-production data whenever possible. Testing should focus on reproducible security scenarios, control validation, and regression prevention.

Internal tests must avoid destructive actions, unauthorized access to production customer data, credential harvesting, social engineering, denial-of-service testing, or unapproved persistence mechanisms.

## Third-Party Testing Guidance

Third-party assessments should be governed by a signed scope, rules of engagement, test window, escalation contacts, data handling expectations, reporting format, and remediation/retest process. Testers should receive only the minimum access needed to complete the approved scope.

## Authorized Testing Requirements

- Written authorization is required before testing begins.
- Scope must identify target environments, excluded systems, test accounts, permitted techniques, and timing limits.
- Emergency contacts and stop-test criteria must be documented.
- Customer-impacting tests require explicit approval.
- Testing must not include real customer data unless separately approved by legal, privacy, security, and customer stakeholders.

## Frequency Recommendations

- Perform external third-party testing after material architecture changes and at a planned recurring cadence.
- Perform targeted internal testing for high-risk changes to authentication, authorization, audit integrity, exports, and tenant isolation.
- Retest remediated high-risk findings before closure.
- Refresh the readiness package before major enterprise procurement reviews.

## Rules of Engagement

- Use only approved accounts, tenants, IP ranges, tooling, and test windows.
- Do not perform denial-of-service, destructive data modification, phishing, malware deployment, physical attacks, or social engineering unless explicitly authorized.
- Report suspected access to sensitive data immediately and stop testing that path until reviewed.
- Do not exfiltrate production data; use sanitized proof where possible.
- Preserve evidence in a safe, non-secret-bearing format.

## Environment Considerations

Testing should prefer staging or dedicated assessment environments that mirror production controls. Production testing, if approved, should be narrowly scoped, monitored, rate-limited, and coordinated with operations.

Test environments should include representative tenant memberships, role assignments, audit records, exports, and identity-provider flows where practical.

## Reporting Expectations

Reports should include executive summary, scope, methodology, findings by severity, reproduction summary, business impact, recommended remediation, affected components, evidence, owner, status, and validation notes.

Reports must not include secrets, bearer tokens, private keys, raw JWTs, production credentials, customer data, or unnecessary sensitive payloads.

## Remediation Expectations

Each accepted finding should have an owner, severity, target date, remediation plan, validation approach, and status. Exceptions should document business justification, compensating controls, expiration date, and approval authority.

## Retest Expectations

Retesting should verify the original issue is corrected, no obvious regression was introduced, and relevant automated tests or control checks were updated where practical. Retest evidence should be retained with the finding record.

## Evidence Retention Recommendations

Retain final reports, scope approvals, rules of engagement, remediation evidence, exception records, and retest results in the approved evidence repository. Redact sensitive details before external sharing.

## Related Controls

This policy should be reviewed alongside the Security Control Evidence Index, Security Metrics Framework, Vulnerability Management Program, Incident Response Readiness, BC/DR Readiness, and CI Security Validation materials when those evidence packages are available.

## Disclaimer

These materials are readiness and planning documents only. They do not represent a completed penetration test, security assessment, certification, attestation, or regulatory determination.
