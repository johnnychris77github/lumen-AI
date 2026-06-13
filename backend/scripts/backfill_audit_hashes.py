from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import MetaData, Table, create_engine, func, select, update
from sqlalchemy.engine import Engine


GENESIS_HASH = ""
REQUIRED_COLUMNS = {"id", "tenant_id", "previous_hash", "record_hash"}


@dataclass
class BackfillSummary:
    tenants_seen: int = 0
    records_seen: int = 0
    records_updated: int = 0
    records_preserved: int = 0
    records_would_update: int = 0


def _timestamp_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None).isoformat()
    return str(value or "")


def _value(row: dict[str, Any], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return str(value)
    return ""


def calculate_audit_hash(row: dict[str, Any], previous_hash: str) -> str:
    payload = {
        "tenant_id": _value(row, "tenant_id"),
        "actor_id": _value(row, "actor_id", "actor_email"),
        "action": _value(row, "action", "action_type"),
        "resource_type": _value(row, "resource_type"),
        "resource_id": _value(row, "resource_id"),
        "timestamp": _timestamp_value(row.get("created_at") or row.get("timestamp")),
        "metadata_json": _value(row, "metadata_json", "details"),
        "previous_hash": previous_hash or "",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _audit_table(engine: Engine) -> Table:
    metadata = MetaData()
    table = Table("audit_logs", metadata, autoload_with=engine)
    missing = REQUIRED_COLUMNS - set(table.c.keys())
    if missing:
        names = ", ".join(sorted(missing))
        raise RuntimeError(f"audit_logs is missing required hash backfill columns: {names}")
    return table


def _tenant_ids(connection, table: Table, tenant_id: str | None) -> list[str]:
    if tenant_id:
        return [tenant_id]

    rows = connection.execute(
        select(table.c.tenant_id)
        .group_by(table.c.tenant_id)
        .order_by(table.c.tenant_id.asc())
    ).all()
    return [str(row[0] or "") for row in rows]


def _ordered_records(connection, table: Table, tenant_id: str, limit: int | None):
    statement = (
        select(table)
        .where(table.c.tenant_id == tenant_id)
        .order_by(table.c.created_at.asc(), table.c.id.asc())
    )
    if limit is not None:
        statement = statement.limit(limit)
    return [dict(row._mapping) for row in connection.execute(statement).all()]


def backfill_audit_hashes(
    engine: Engine,
    *,
    dry_run: bool = False,
    force: bool = False,
    tenant_id: str | None = None,
    limit: int | None = None,
) -> BackfillSummary:
    table = _audit_table(engine)
    summary = BackfillSummary()

    with engine.begin() as connection:
        for current_tenant_id in _tenant_ids(connection, table, tenant_id):
            summary.tenants_seen += 1
            previous_hash = GENESIS_HASH

            for row in _ordered_records(connection, table, current_tenant_id, limit):
                summary.records_seen += 1
                existing_hash = str(row.get("record_hash") or "")

                if existing_hash and not force:
                    previous_hash = existing_hash
                    summary.records_preserved += 1
                    continue

                next_hash = calculate_audit_hash(row, previous_hash)
                if dry_run:
                    summary.records_would_update += 1
                else:
                    connection.execute(
                        update(table)
                        .where(table.c.id == row["id"])
                        .values(previous_hash=previous_hash, record_hash=next_hash)
                    )
                    summary.records_updated += 1

                previous_hash = next_hash

    return summary


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill audit log hash-chain fields.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--tenant-id", default=None)
    parser.add_argument("--limit", type=_positive_int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL or --database-url is required")

    engine = create_engine(args.database_url, pool_pre_ping=True)
    summary = backfill_audit_hashes(
        engine,
        dry_run=args.dry_run,
        force=args.force,
        tenant_id=args.tenant_id,
        limit=args.limit,
    )

    print("Audit hash backfill complete")
    print(f"dry_run={args.dry_run}")
    print(f"force={args.force}")
    print(f"tenant_id={args.tenant_id or 'ALL'}")
    print(f"tenants_seen={summary.tenants_seen}")
    print(f"records_seen={summary.records_seen}")
    print(f"records_updated={summary.records_updated}")
    print(f"records_preserved={summary.records_preserved}")
    print(f"records_would_update={summary.records_would_update}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
