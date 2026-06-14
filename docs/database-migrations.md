# Database Migrations

## Audit Chain Timestamp Anchoring

Audit chain anchors let LumenAI periodically record a digest of a tenant audit
hash chain outside the audit log table itself. This reduces rollback and
full-database tampering risk because operators can compare the current audit
chain against previously recorded anchors.

The initial provider is `internal` and requires no external network dependency.
It calculates `anchor_hash` from:

- `tenant_id`
- `last_audit_log_id`
- `records_covered`
- the latest audit `record_hash`
- anchor creation timestamp

Use `POST /api/audit/integrity/anchor` to create an anchor for the authorized
tenant and `GET /api/audit/integrity/anchors` to review tenant-scoped anchor
history.

Future providers can add external timestamping, notarization, or vendor-backed
anchoring without changing the audit chain hash logic.
