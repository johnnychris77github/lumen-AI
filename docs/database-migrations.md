# Database Migrations

## Historical Audit Hash Backfill

After the audit integrity columns are deployed, existing audit records can be
linked into tenant-scoped hash chains with:

```bash
python backend/scripts/backfill_audit_hashes.py --dry-run
python backend/scripts/backfill_audit_hashes.py
```

The script reads `DATABASE_URL` by default. It also accepts:

- `--dry-run` to calculate the scope without writing changes.
- `--force` to recalculate existing hashes.
- `--tenant-id <tenant>` to process one tenant chain.
- `--limit <n>` to cap records processed per tenant.

The backfill processes records tenant-by-tenant in deterministic
`created_at, id` order. By default it preserves existing `record_hash` values
and only fills records that do not have a hash. Output is limited to safe
counts and tenant scope; audit metadata and details are not printed.

Backfilling does not mutate unrelated audit fields and does not backfill
external timestamping or notarization.
