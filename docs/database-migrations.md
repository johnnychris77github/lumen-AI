# Database Migrations

## Scheduled Audit Chain Anchoring

Scheduled internal audit chain anchoring periodically records tenant audit
chain checkpoints without relying on an external vendor or network call.

Configuration:

- `LUMENAI_AUDIT_ANCHOR_SCHEDULING_ENABLED`
- `LUMENAI_AUDIT_ANCHOR_INTERVAL_HOURS`
- `LUMENAI_AUDIT_ANCHOR_PROVIDER=internal`

The scheduler scans tenants with audit records and creates an anchor only when
new audit rows exist after the tenant's latest anchor. Tenants with no new
audit activity are skipped. Scheduler output is limited to safe summary counts
and does not include audit metadata.

Run manually with:

```bash
python backend/scripts/run_audit_anchor_scheduler.py
```

This PR does not add Celery, cron, or hosted scheduler integration. Operators
can wire the script into their preferred scheduling system later.
