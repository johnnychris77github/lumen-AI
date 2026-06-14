# Third-Party Risk Management Program

## Purpose and Scope

This program defines LumenAI readiness expectations for third-party risk management and subprocessor governance. It supports hospital procurement reviews, enterprise security assessments, subprocessor reviews, and future readiness initiatives.

This program applies to vendors, subprocessors, service providers, contractors, hosted platforms, identity providers, infrastructure providers, development tools, support tools, and other third parties that may affect security, availability, confidentiality, privacy, or evidence integrity.

These materials are governance and readiness documents only and do not represent completed vendor assessments, contractual commitments, certifications, or regulatory determinations.

## Third-Party Risk Lifecycle

1. Identify the proposed vendor, service, business owner, intended use, and expected data access.
2. Classify the vendor based on data sensitivity, operational dependency, customer impact, and security relevance.
3. Perform due diligence and security review appropriate to the classification.
4. Review contract, data protection, confidentiality, incident notification, and termination terms.
5. Approve, conditionally approve, reject, or defer the vendor based on residual risk.
6. Monitor the vendor throughout the relationship.
7. Reassess the vendor periodically and after material service changes.
8. Offboard the vendor and confirm access removal, data disposition, and evidence retention.

## Vendor Classification Methodology

Vendor classification should consider:

- Data categories processed, stored, transmitted, or accessed.
- Whether customer data, regulated data, audit evidence, credentials, or production systems are involved.
- Business criticality and service availability dependency.
- Connectivity to production, CI, identity, storage, analytics, logging, or support workflows.
- Security control maturity and availability of independent assessment evidence.
- Contractual, privacy, and customer notification implications.

Recommended classifications:

- Critical: material access to customer data, production systems, identity, audit evidence, or core availability.
- High: sensitive access or operational dependency with meaningful customer or security impact.
- Medium: limited sensitive access or moderate business dependency.
- Low: minimal access to sensitive systems or data.

## Risk Assessment Process

Risk assessments should document the business purpose, service provided, data categories, access model, security controls, compliance posture, availability dependency, incident notification expectations, residual risks, owner, approval decision, and review date.

Higher-risk vendors should receive deeper technical, contractual, privacy, and operational review before use.

## Due Diligence Process

Due diligence may include review of security questionnaires, security whitepapers, independent assessment summaries, penetration testing summaries where available, vulnerability management process, incident response process, BC/DR materials, data handling terms, encryption practices, access control model, logging practices, and subprocessor disclosures.

Due diligence evidence should be stored in the approved evidence repository and should not include vendor secrets, customer secrets, production credentials, or unapproved confidential materials.

## Security Review Requirements

Security review should evaluate authentication, authorization, encryption, logging, incident response, BC/DR, vulnerability management, secure development practices, access management, tenant isolation where applicable, data retention, data deletion, and subprocessor controls.

Security review depth should align to vendor classification and data sensitivity.

## Ongoing Monitoring Expectations

Ongoing monitoring may include annual review, contract renewal review, security bulletin review, incident review, status page monitoring, subprocessor change review, assessment evidence refresh, access review, and reassessment after material service or data use changes.

## Contract Review Considerations

Contract review should consider confidentiality, data protection, breach and incident notification, audit rights where appropriate, subprocessor disclosure, data return and deletion, service levels where applicable, termination rights, liability, support obligations, jurisdiction, and customer-specific commitments.

Legal, privacy, and procurement stakeholders should review contractual terms before approval for high-risk or critical vendors.

## Vendor Offboarding Process

Offboarding should confirm service termination, account and access removal, credential revocation, integration shutdown, data return or deletion review, contract closure, documentation retention, and final owner sign-off.

Offboarding evidence should be retained in the approved repository.

## Annual Review Guidance

At least annually, review critical and high-risk vendors for continued business need, current owner, data categories, access level, risk classification, security evidence freshness, contract status, incidents, exceptions, and residual risks.

Lower-risk vendors should be reviewed on a risk-based cadence or when service use materially changes.

## Related Readiness Controls

This program should be reviewed alongside Vulnerability Management Program, Incident Response Program, BC/DR Program, Security Governance Dashboard, Security Control Evidence Index, and Security Review Packet materials when available. The repository currently includes the [Object Authorization Remaining Lookup Audit](../enterprise-readiness/object-authorization-remaining-lookup-audit-v1.md) as supporting security readiness evidence.
