from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from scripts.backfill_audit_hashes import backfill_audit_hashes, calculate_audit_hash


def make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def audit_table(metadata: sa.MetaData) -> sa.Table:
    return sa.Table(
        "audit_logs",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("actor_role", sa.String(100), nullable=True),
        sa.Column("action_type", sa.String(100), nullable=True),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("record_hash", sa.String(64), nullable=True),
    )


def setup_db(rows: list[dict]):
    engine = make_engine()
    metadata = sa.MetaData()
    table = audit_table(metadata)
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(table.insert(), rows)
    return engine, table


def row(
    row_id: int,
    tenant_id: str = "tenant-a",
    *,
    created_at: datetime | None = None,
    previous_hash: str = "",
    record_hash: str = "",
) -> dict:
    created_at = created_at or datetime(2026, 1, 1) + timedelta(minutes=row_id)
    return {
        "id": row_id,
        "tenant_id": tenant_id,
        "actor_id": "actor@example.com",
        "actor_email": "actor@example.com",
        "actor_role": "tenant_admin",
        "action_type": "create",
        "resource_type": "inspection",
        "resource_id": f"inspection-{row_id}",
        "created_at": created_at,
        "metadata_json": '{"safe":"summary"}',
        "details": '{"safe":"legacy"}',
        "previous_hash": previous_hash,
        "record_hash": record_hash,
    }


def ordered_rows(engine, table, tenant_id: str = "tenant-a") -> list[dict]:
    with engine.begin() as connection:
        rows = connection.execute(
            sa.select(table)
            .where(table.c.tenant_id == tenant_id)
            .order_by(table.c.created_at.asc(), table.c.id.asc())
        ).all()
    return [dict(item._mapping) for item in rows]


def assert_chain_valid(engine, table, tenant_id: str = "tenant-a"):
    previous_hash = ""
    rows = ordered_rows(engine, table, tenant_id)
    for item in rows:
        assert item["previous_hash"] == previous_hash
        assert item["record_hash"] == calculate_audit_hash(item, previous_hash)
        previous_hash = item["record_hash"]


def test_unhashed_records_are_backfilled():
    engine, table = setup_db([row(1), row(2)])

    summary = backfill_audit_hashes(engine)

    assert summary.records_updated == 2
    rows = ordered_rows(engine, table)
    assert rows[0]["previous_hash"] == ""
    assert len(rows[0]["record_hash"]) == 64
    assert rows[1]["previous_hash"] == rows[0]["record_hash"]
    assert_chain_valid(engine, table)


def test_existing_hashes_are_preserved_by_default():
    preserved_hash = "a" * 64
    engine, table = setup_db([
        row(1, record_hash=preserved_hash),
        row(2),
    ])

    summary = backfill_audit_hashes(engine)

    rows = ordered_rows(engine, table)
    assert summary.records_preserved == 1
    assert summary.records_updated == 1
    assert rows[0]["record_hash"] == preserved_hash
    assert rows[1]["previous_hash"] == preserved_hash


def test_force_mode_recalculates_hashes():
    engine, table = setup_db([
        row(1, record_hash="a" * 64),
        row(2, previous_hash="a" * 64, record_hash="b" * 64),
    ])

    summary = backfill_audit_hashes(engine, force=True)

    rows = ordered_rows(engine, table)
    assert summary.records_updated == 2
    assert rows[0]["record_hash"] != "a" * 64
    assert rows[1]["record_hash"] != "b" * 64
    assert_chain_valid(engine, table)


def test_backfill_is_tenant_isolated():
    engine, table = setup_db([
        row(1, tenant_id="tenant-a"),
        row(2, tenant_id="tenant-b"),
    ])

    summary = backfill_audit_hashes(engine, tenant_id="tenant-a")

    tenant_a = ordered_rows(engine, table, "tenant-a")
    tenant_b = ordered_rows(engine, table, "tenant-b")
    assert summary.tenants_seen == 1
    assert summary.records_updated == 1
    assert len(tenant_a[0]["record_hash"]) == 64
    assert tenant_b[0]["record_hash"] == ""


def test_backfilled_chain_verifies_successfully():
    engine, table = setup_db([
        row(2, created_at=datetime(2026, 1, 1, 0, 2)),
        row(1, created_at=datetime(2026, 1, 1, 0, 1)),
        row(3, created_at=datetime(2026, 1, 1, 0, 3)),
    ])

    backfill_audit_hashes(engine)

    assert [item["id"] for item in ordered_rows(engine, table)] == [1, 2, 3]
    assert_chain_valid(engine, table)


def test_dry_run_does_not_write_changes():
    engine, table = setup_db([row(1), row(2)])

    summary = backfill_audit_hashes(engine, dry_run=True)

    rows = ordered_rows(engine, table)
    assert summary.records_would_update == 2
    assert summary.records_updated == 0
    assert all(item["record_hash"] == "" for item in rows)
    assert all(item["previous_hash"] == "" for item in rows)
