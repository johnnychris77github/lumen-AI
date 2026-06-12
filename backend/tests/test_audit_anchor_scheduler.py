from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import settings as settings_module
from app.services.audit_anchor_scheduler import run_scheduled_audit_anchors


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def reset_tables():
    metadata = sa.MetaData()
    metadata.reflect(bind=engine)
    metadata.drop_all(bind=engine)

    metadata = sa.MetaData()
    sa.Table(
        "audit_logs",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    sa.Table(
        "audit_chain_anchors",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("anchor_hash", sa.String(64), nullable=False),
        sa.Column("last_audit_log_id", sa.Integer, nullable=False),
        sa.Column("records_covered", sa.Integer, nullable=False),
        sa.Column("anchor_provider", sa.String(100), nullable=False),
        sa.Column("anchor_reference", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    metadata.create_all(bind=engine)


def insert_audit_log(db, tenant_id: str, log_id: int, record_hash: str | None = None):
    db.execute(
        text(
            """
            INSERT INTO audit_logs (id, tenant_id, record_hash, metadata_json, created_at)
            VALUES (:id, :tenant_id, :record_hash, :metadata_json, :created_at)
            """
        ),
        {
            "id": log_id,
            "tenant_id": tenant_id,
            "record_hash": record_hash or (str(log_id) * 64)[:64],
            "metadata_json": '{"secret":"do-not-print"}',
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        },
    )


def anchor_rows(db, tenant_id: str | None = None):
    sql = "SELECT * FROM audit_chain_anchors"
    params = {}
    if tenant_id:
        sql += " WHERE tenant_id = :tenant_id"
        params["tenant_id"] = tenant_id
    sql += " ORDER BY id ASC"
    return db.execute(text(sql), params).mappings().all()


def run_with_db():
    settings_module.settings.LUMENAI_AUDIT_ANCHOR_PROVIDER = "internal"
    db = TestingSessionLocal()
    try:
        summary = run_scheduled_audit_anchors(db)
        rows = anchor_rows(db)
        return summary, rows
    finally:
        db.close()


def test_anchor_created_when_audit_records_exist_and_no_prior_anchor_exists():
    reset_tables()
    db = TestingSessionLocal()
    try:
        insert_audit_log(db, "tenant-a", 1, "a" * 64)
        db.commit()
    finally:
        db.close()

    summary, rows = run_with_db()

    assert summary["anchors_created"] == 1
    assert summary["tenants_seen"] == 1
    assert rows[0]["tenant_id"] == "tenant-a"
    assert rows[0]["last_audit_log_id"] == 1
    assert rows[0]["records_covered"] == 1


def test_anchor_skipped_when_no_new_records_exist():
    reset_tables()
    db = TestingSessionLocal()
    try:
        insert_audit_log(db, "tenant-a", 1, "a" * 64)
        db.commit()
        run_scheduled_audit_anchors(db)
        second_summary = run_scheduled_audit_anchors(db)
        rows = anchor_rows(db, "tenant-a")
    finally:
        db.close()

    assert second_summary["anchors_created"] == 0
    assert second_summary["tenants_skipped"] == 1
    assert len(rows) == 1


def test_anchor_created_when_newer_audit_records_exist_after_prior_anchor():
    reset_tables()
    db = TestingSessionLocal()
    try:
        insert_audit_log(db, "tenant-a", 1, "a" * 64)
        db.commit()
        run_scheduled_audit_anchors(db)
        insert_audit_log(db, "tenant-a", 2, "b" * 64)
        db.commit()
        second_summary = run_scheduled_audit_anchors(db)
        rows = anchor_rows(db, "tenant-a")
    finally:
        db.close()

    assert second_summary["anchors_created"] == 1
    assert len(rows) == 2
    assert rows[-1]["last_audit_log_id"] == 2
    assert rows[-1]["records_covered"] == 2


def test_multiple_tenants_are_handled_independently():
    reset_tables()
    db = TestingSessionLocal()
    try:
        insert_audit_log(db, "tenant-a", 1, "a" * 64)
        insert_audit_log(db, "tenant-b", 2, "b" * 64)
        db.commit()
        summary = run_scheduled_audit_anchors(db)
        rows_a = anchor_rows(db, "tenant-a")
        rows_b = anchor_rows(db, "tenant-b")
    finally:
        db.close()

    assert summary["anchors_created"] == 2
    assert summary["tenants_seen"] == 2
    assert len(rows_a) == 1
    assert len(rows_b) == 1


def test_summary_output_does_not_expose_metadata_or_secrets():
    reset_tables()
    db = TestingSessionLocal()
    try:
        insert_audit_log(db, "tenant-a", 1, "a" * 64)
        db.commit()
        summary = run_scheduled_audit_anchors(db)
    finally:
        db.close()

    rendered = str(summary)
    assert "secret" not in rendered
    assert "do-not-print" not in rendered
    assert summary == {
        "provider": "internal",
        "tenants_seen": 1,
        "anchors_created": 1,
        "tenants_skipped": 0,
        "records_covered": 1,
    }
