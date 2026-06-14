# Breach Notification Readiness

## Disclaimer

These documents are readiness materials only and do not constitute legal advice or a formal breach determination. Actual notification obligations must be reviewed with legal, privacy, and customer stakeholders.

## Healthcare Customer Notification Considerations

Healthcare customer notification requires fact-specific review. Consider:

- Customer contract terms
- Business associate or vendor role
- Potential PHI involvement
- Tenant/customer scope
- Jurisdiction
- Timeline of discovery and containment
- Whether data was accessed, acquired, used, disclosed, altered, or unavailable
- Whether risk of harm can be mitigated or ruled out

## PHI/Data Exposure Assessment Checklist

- [ ] Identify affected tenant or customer.
- [ ] Identify affected records, exports, files, or reports.
- [ ] Determine whether PHI or sensitive operational data may be involved.
- [ ] Determine whether data was viewed, exported, modified, deleted, or transmitted.
- [ ] Confirm whether encryption or access controls limited exposure.
- [ ] Review audit logs, identity logs, and export logs.
- [ ] Document uncertainty and open investigation items.
- [ ] Send findings to legal/privacy reviewers.

## Tenant Impact Review Checklist

- [ ] List potentially affected tenants.
- [ ] Confirm tenant-scoped records involved.
- [ ] Confirm cross-tenant exposure did or did not occur.
- [ ] Confirm affected users, roles, IPs, and access paths.
- [ ] Confirm whether customer-facing reports or exports were generated.
- [ ] Preserve evidence supporting scope decisions.
- [ ] Assign customer communications owner.

## Timeline Tracking Template

| Time | Event | Source | Owner | Notes |
| --- | --- | --- | --- | --- |
| TBD | Detection | TBD | TBD | Initial alert/report. |
| TBD | Triage started | TBD | TBD | Severity assigned. |
| TBD | Containment action | TBD | TBD | Access blocked or control applied. |
| TBD | Customer impact review | TBD | TBD | Tenant scope assessed. |
| TBD | Legal/privacy review | TBD | TBD | Notification obligations reviewed. |
| TBD | Recovery validated | TBD | TBD | Controls validated. |

## Evidence Collection Checklist

- [ ] Application logs
- [ ] Audit logs and audit hash-chain status
- [ ] Audit anchor records and external notary references
- [ ] Identity provider logs
- [ ] SCIM provisioning events
- [ ] Database access logs
- [ ] Export generation logs
- [ ] Rate-limit/abuse detection logs
- [ ] Deployment and change history
- [ ] Screenshots or copies of alerts
- [ ] Customer communications and approvals

## Legal/Privacy Review Placeholder

Legal/privacy reviewer:

Review started:

Review completed:

Determination summary:

Approved customer communication:

Regulatory notification analysis:

## Customer Communication Template

Subject: Security Incident Readiness Notice - [Customer/Tenant Name]

Hello [Customer Contact],

We are notifying you of a security incident investigation involving [brief factual description]. Our current assessment is:

- Detection time: [time]
- Affected environment: [environment]
- Tenant/customer scope: [scope]
- Data involved: [known data categories]
- Containment actions: [actions taken]
- Current status: [status]
- Next update: [timeframe]

We are continuing to investigate and will provide updates as additional facts are confirmed. This notice is provided for readiness and transparency and should be coordinated with the appropriate legal, privacy, and security stakeholders.

## Regulatory Notification Disclaimer

This document does not determine whether regulatory notification is required. Regulatory notification decisions must be made with legal, privacy, and customer stakeholders based on confirmed facts, contracts, applicable law, and customer obligations.
