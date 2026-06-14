# Database Migrations

LumenAI uses Alembic for production schema changes. The active Alembic
configuration lives at the repository root in `alembic.ini`, with migration
scripts under `backend/alembic`.

## Running Migrations

Set `DATABASE_URL` to the target database and run:

```bash
alembic upgrade head
```

For local development and CI validation, `alembic.ini` defaults to:

```text
sqlite:///./lumenai_migrations.db
```

This default is intentionally local-only and does not require production
secrets.

## Current Foundation

The initial migration creates or updates the `audit_logs` table for
production-relevant audit integrity fields:

- `tenant_id`
- `actor_id`
- `actor_role`
- `metadata_json`
- `previous_hash`
- `record_hash`

The migration is additive and backward compatible. It does not drop legacy
columns, rename existing columns, or backfill historical audit hash values.

## Operational Notes

- Review pending migrations before production rollout.
- Back up production databases before `alembic upgrade head`.
- Run migrations during a maintenance window when schema changes may affect
  active application instances.
- Historical audit hash backfill and external hash anchoring should be handled
  by future, explicit migration or maintenance jobs.
