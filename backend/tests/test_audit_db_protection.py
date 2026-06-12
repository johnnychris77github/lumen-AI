from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    REPO_ROOT
    / "backend"
    / "alembic"
    / "versions"
    / "20260612_0002_audit_log_db_protection.py"
)


def load_migration():
    spec = importlib.util.spec_from_file_location("audit_db_protection_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_file_exists():
    assert MIGRATION_PATH.exists()


def test_postgresql_trigger_sql_is_present():
    migration = load_migration()

    trigger_sql = migration.CREATE_AUDIT_IMMUTABILITY_TRIGGERS_SQL
    function_sql = migration.CREATE_AUDIT_IMMUTABILITY_FUNCTION_SQL

    assert "CREATE OR REPLACE FUNCTION audit_logs_prevent_mutation" in function_sql
    assert "RAISE EXCEPTION 'audit_logs are append-only; UPDATE is not permitted'" in function_sql
    assert "RAISE EXCEPTION 'audit_logs are append-only; DELETE is not permitted'" in function_sql
    assert "BEFORE UPDATE ON audit_logs" in trigger_sql
    assert "BEFORE DELETE ON audit_logs" in trigger_sql


def test_sqlite_upgrade_and_downgrade_paths_do_not_execute_sql(monkeypatch):
    migration = load_migration()
    executed = []
    fake_op = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="sqlite")),
        execute=lambda sql: executed.append(sql),
    )

    monkeypatch.setattr(migration, "op", fake_op)

    migration.upgrade()
    migration.downgrade()

    assert executed == []


def test_postgresql_upgrade_executes_function_and_triggers(monkeypatch):
    migration = load_migration()
    executed = []
    fake_op = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
        execute=lambda sql: executed.append(sql),
    )

    monkeypatch.setattr(migration, "op", fake_op)

    migration.upgrade()

    assert executed == [
        migration.CREATE_AUDIT_IMMUTABILITY_FUNCTION_SQL,
        migration.CREATE_AUDIT_IMMUTABILITY_TRIGGERS_SQL,
    ]


def test_app_level_audit_immutability_tests_still_pass_if_available():
    optional_test = REPO_ROOT / "backend" / "tests" / "test_audit_immutability.py"

    if not optional_test.exists():
        pytest.skip("app-level audit immutability tests are not present on this branch")

    assert pytest.main([str(optional_test)]) == 0
