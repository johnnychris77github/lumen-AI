"""add audit chain anchors

Revision ID: 20260612_0003
Revises: 20260612_0002
Create Date: 2026-06-12

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260612_0003"
down_revision: Union[str, Sequence[str], None] = "20260612_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_chain_anchors",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), nullable=False),
        sa.Column("anchor_hash", sa.String(length=64), nullable=False),
        sa.Column("last_audit_log_id", sa.Integer(), nullable=False),
        sa.Column("records_covered", sa.Integer(), nullable=False),
        sa.Column("anchor_provider", sa.String(length=100), nullable=False, server_default="internal"),
        sa.Column("anchor_reference", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_chain_anchors_id", "audit_chain_anchors", ["id"])
    op.create_index("ix_audit_chain_anchors_tenant_id", "audit_chain_anchors", ["tenant_id"])
    op.create_index("ix_audit_chain_anchors_anchor_hash", "audit_chain_anchors", ["anchor_hash"])


def downgrade() -> None:
    op.drop_index("ix_audit_chain_anchors_anchor_hash", table_name="audit_chain_anchors")
    op.drop_index("ix_audit_chain_anchors_tenant_id", table_name="audit_chain_anchors")
    op.drop_index("ix_audit_chain_anchors_id", table_name="audit_chain_anchors")
    op.drop_table("audit_chain_anchors")
