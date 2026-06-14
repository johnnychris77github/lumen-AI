# Backup and Recovery Guidance

## Disclaimer

These materials are operational readiness documents and do not represent guaranteed service levels. Actual recovery objectives, backup strategies, and customer commitments must be defined in production deployment and contractual agreements.

## Backup Strategy Recommendations

- Back up PostgreSQL database using managed backup or approved database backup tooling.
- Back up object/file storage where generated artifacts or evidence exports are stored.
- Preserve migration files and deployment configuration, excluding secret values.
- Preserve audit logs, audit hashes, and audit anchors.
- Separate production backups from development/test environments.

## Backup Retention Guidance

Retention should be defined by customer contract, legal/privacy requirements, operational needs, and storage capabilities. Recommended readiness posture:

- Define short-term operational backups.
- Define longer-term compliance/evidence retention where required.
- Document deletion/expiration behavior.
- Review retention after customer contract changes.

## Encryption Recommendations

- Encrypt backups at rest.
- Encrypt backup transfer paths.
- Restrict backup decryption permissions.
- Store backup encryption keys in an approved secret/key management system.
- Do not place keys in source control, logs, or documentation.

## Backup Verification Process

1. Confirm backup job completed successfully.
2. Confirm backup is stored in expected location.
3. Confirm backup is encrypted.
4. Confirm backup is within retention policy.
5. Confirm restore metadata is recorded.
6. Periodically restore to a non-production environment.

## Restore Testing Guidance

- Test database restore before production go-live.
- Test object/file storage restore if artifacts are used.
- Validate schema/migration compatibility after restore.
- Validate tenant isolation after restore.
- Validate audit logs and audit anchors after restore.
- Record test date, owner, result, gaps, and corrective actions.

## Audit Record Preservation Considerations

Audit records should be preserved through backup and restore operations. Avoid editing or deleting audit records during recovery. If hash backfill, verification, or anchoring is performed after restore, document timing, operator, and validation results.

## Tenant Data Recovery Considerations

- Confirm restored data is scoped to the correct tenant when performing tenant-specific recovery.
- Validate tenant memberships after restore.
- Avoid cross-tenant data exposure during partial restore.
- Document customer approval and recovery scope for tenant-specific recovery activities.
