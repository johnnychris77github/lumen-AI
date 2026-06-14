"""add database-level audit log mutation protection

Revision ID: 20260612_0002
Revises: 20260612_0001
Create Date: 2026-06-12

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "20260612_0002"
down_revision: Union[str, Sequence[str], None] = "20260612_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CREATE_AUDIT_IMMUTABILITY_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION audit_logs_prevent_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'audit_logs are append-only; UPDATE is not permitted';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'audit_logs are append-only; DELETE is not permitted';
    END IF;

    RETURN NEW;
END;
$$;
"""


CREATE_AUDIT_IMMUTABILITY_TRIGGERS_SQL = """
DO $$
BEGIN
    IF to_regclass('public.audit_logs') IS NOT NULL THEN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_trigger
            WHERE tgname = 'trg_audit_logs_prevent_update'
        ) THEN
            CREATE TRIGGER trg_audit_logs_prevent_update
            BEFORE UPDATE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION audit_logs_prevent_mutation();
        END IF;

        IF NOT EXISTS (
            SELECT 1
            FROM pg_trigger
            WHERE tgname = 'trg_audit_logs_prevent_delete'
        ) THEN
            CREATE TRIGGER trg_audit_logs_prevent_delete
            BEFORE DELETE ON audit_logs
            FOR EACH ROW
            EXECUTE FUNCTION audit_logs_prevent_mutation();
        END IF;
    END IF;
END;
$$;
"""


DROP_AUDIT_IMMUTABILITY_SQL = """
DROP TRIGGER IF EXISTS trg_audit_logs_prevent_update ON audit_logs;
DROP TRIGGER IF EXISTS trg_audit_logs_prevent_delete ON audit_logs;
DROP FUNCTION IF EXISTS audit_logs_prevent_mutation();
"""


def _is_postgresql() -> bool:
    bind = op.get_bind()
    return bind.dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgresql():
        return

    op.execute(CREATE_AUDIT_IMMUTABILITY_FUNCTION_SQL)
    op.execute(CREATE_AUDIT_IMMUTABILITY_TRIGGERS_SQL)


def downgrade() -> None:
    if not _is_postgresql():
        return

    op.execute(DROP_AUDIT_IMMUTABILITY_SQL)
