# Database Migrations

## Audit Log Database Protection

Production PostgreSQL deployments should enforce audit immutability at the
database layer as well as in application code. Migration `20260612_0002`
installs PostgreSQL triggers that reject `UPDATE` and `DELETE` operations on
`audit_logs` with clear append-only error messages. Normal `INSERT` operations
remain allowed so audit events can continue to be recorded.

SQLite is still supported for local development and tests, but it does not
provide the same production-grade trigger/function model used by PostgreSQL in
this migration. The SQLite migration path is intentionally a no-op so local and
test workflows continue to work.

This migration does not alter audit hash logic, rewrite historical audit rows,
drop columns, or expose audit metadata in database error messages.
