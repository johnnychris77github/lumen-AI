"""add audit log integrity columns

Revision ID: 20260612_0001
Revises:
Create Date: 2026-06-12

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260612_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


AUDIT_LOG_COLUMNS = {
    "tenant_id": sa.Column("tenant_id", sa.String(length=100), nullable=True),
    "actor_id": sa.Column("actor_id", sa.String(length=255), nullable=True),
    "actor_role": sa.Column("actor_role", sa.String(length=100), nullable=True),
    "metadata_json": sa.Column("metadata_json", sa.Text(), nullable=True),
    "previous_hash": sa.Column("previous_hash", sa.String(length=64), nullable=True),
    "record_hash": sa.Column("record_hash", sa.String(length=64), nullable=True),
}


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if not _table_exists("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.String(length=100), nullable=True),
            sa.Column("tenant_name", sa.String(length=255), nullable=True),
            sa.Column("actor_email", sa.String(length=255), nullable=True),
            sa.Column("actor_id", sa.String(length=255), nullable=True),
            sa.Column("actor_role", sa.String(length=100), nullable=True),
            sa.Column("action_type", sa.String(length=100), nullable=True),
            sa.Column("resource_type", sa.String(length=100), nullable=True),
            sa.Column("resource_id", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=True),
            sa.Column("request_method", sa.String(length=20), nullable=True),
            sa.Column("request_path", sa.String(length=500), nullable=True),
            sa.Column("client_ip", sa.String(length=100), nullable=True),
            sa.Column("details", sa.String(length=4000), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("compliance_flag", sa.Boolean(), nullable=True),
            sa.Column("previous_hash", sa.String(length=64), nullable=True),
            sa.Column("record_hash", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
        op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
        op.create_index("ix_audit_logs_actor_email", "audit_logs", ["actor_email"])
        op.create_index("ix_audit_logs_action_type", "audit_logs", ["action_type"])
        op.create_index("ix_audit_logs_record_hash", "audit_logs", ["record_hash"])
        return

    existing_columns = _column_names("audit_logs")
    for name, column in AUDIT_LOG_COLUMNS.items():
        if name not in existing_columns:
            op.add_column("audit_logs", column.copy())

    existing_columns = _column_names("audit_logs")
    if "record_hash" in existing_columns:
        op.create_index(
            "ix_audit_logs_record_hash",
            "audit_logs",
            ["record_hash"],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    # Enterprise migrations are intentionally non-destructive in this foundation.
    pass
