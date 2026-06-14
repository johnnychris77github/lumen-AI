# Business Continuity Plan

## Disclaimer

These materials are operational readiness documents and do not represent guaranteed service levels. Actual recovery objectives, backup strategies, and customer commitments must be defined in production deployment and contractual agreements.

## Purpose and Scope

This plan documents business continuity readiness for LumenAI enterprise healthcare deployments. It supports vendor risk review, operational resilience planning, customer procurement review, and future SOC 2/HITRUST readiness. It covers continuity of application operations, customer support, incident coordination, audit evidence handling, and recovery communications.

## Critical Business Functions

- Authenticated access to tenant-scoped inspection and reporting workflows
- Tenant isolation and authorization controls
- Alerting, audit logging, and audit evidence preservation
- Export and reporting availability
- Customer support and incident coordination
- Deployment, migration, and recovery operations
- Security monitoring and escalation

## Recovery Priorities

1. Protect people, customer trust, and sensitive data.
2. Preserve audit logs, audit hashes, anchors, and incident evidence.
3. Restore authentication, authorization, and tenant isolation controls.
4. Restore API and database availability.
5. Restore reporting, exports, background jobs, and notifications.
6. Communicate status to internal and customer stakeholders.

## Service Dependency Inventory

| Dependency | Continuity consideration |
| --- | --- |
| Backend API | Requires healthy runtime, configuration, secrets, database access, and network access. |
| PostgreSQL database | Primary source of tenant data, audit records, and operational state. |
| Redis/queue services | Required where background jobs, distributed rate limiting, or queues are enabled. |
| Static frontend hosting | Required for browser access to the application. |
| Identity provider | Required for SSO/JWT/OIDC deployments. |
| SCIM provider | Required for automated lifecycle provisioning where enabled. |
| Object/file storage | Required for generated artifacts and evidence exports where configured. |
| External notary provider | Required only when external audit anchoring is configured with fail-closed behavior. |
| Monitoring/alerting | Required for operational visibility and incident response. |

## Internal Communication Plan

- Open an internal continuity channel.
- Assign an incident or continuity commander.
- Assign technical, operations, customer communications, and leadership owners.
- Post status updates on a scheduled cadence.
- Record decisions, assumptions, and recovery actions.
- Escalate customer-impacting or security-impacting events to legal/privacy review when needed.

## Customer Communication Readiness

Customer communication should be factual, approved, and scoped to confirmed impact. Communications should include:

- Affected environment or service
- Customer/tenant impact when known
- Current status
- Recovery actions underway
- Next update timing
- Support contact

Avoid speculation and avoid sharing sensitive operational details that could increase security risk.

## Continuity Assumptions

- Production secrets are stored outside source control.
- Backups are configured, monitored, and periodically tested.
- Production deployments have documented owners and escalation paths.
- Customer-specific recovery objectives are defined in contractual or deployment documents.
- Restore procedures preserve audit evidence and tenant isolation.

## Continuity Procedures

1. Detect service disruption or continuity event.
2. Assign severity and continuity owner.
3. Preserve logs, audit records, and relevant evidence.
4. Identify affected dependencies.
5. Execute approved recovery or failover procedure.
6. Validate authentication, tenant isolation, audit logging, and customer workflows.
7. Communicate status internally and externally as appropriate.
8. Track corrective actions after recovery.

## Vendor Dependency Considerations

Vendor dependencies may include hosting, managed database, Redis, storage, identity provider, monitoring, email/notification provider, and external notary provider. Each production deployment should maintain a vendor dependency register with support contacts, status pages, SLAs, and escalation paths.

## Staffing Continuity Considerations

- Maintain primary and backup owners for engineering, operations, security, customer communications, and legal/privacy review.
- Document access paths for on-call personnel.
- Ensure break-glass access is controlled, logged, and reviewed.
- Avoid single-person dependency for production recovery.

## Periodic Testing Recommendations

- Run annual or semiannual business continuity tabletop exercises.
- Test backup restore and database recovery before production go-live.
- Validate identity provider outage handling.
- Validate communication workflow and customer update templates.
- Record results, gaps, owners, and remediation due dates.

## Document Maintenance Process

Review this plan:

- Before production go-live
- After material architecture changes
- After continuity events
- After incident response exercises
- At least annually

Document owner, review date, changes made, and next review date in customer-specific deployment records.
