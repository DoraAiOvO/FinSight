"""Alembic migration smoke tests."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


EXPECTED_TABLES = {
    "users",
    "customer_profiles",
    "watchlists",
    "watchlist_items",
    "research_sessions",
    "saved_reports",
    "theses",
    "thesis_assumptions",
    "thesis_assumption_history",
    "feedback",
    "alert_preferences",
    "investment_policies",
    "investment_policy_proposals",
    "policy_versions",
    "policy_principles",
    "policy_market_scopes",
    "policy_sector_preferences",
    "policy_theme_preferences",
    "policy_metric_rules",
    "policy_constraints",
    "policy_valuation_rules",
    "policy_portfolio_rules",
    "policy_alert_rules",
}


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_initial_migration_upgrades_and_downgrades(tmp_path):
    database_path = tmp_path / "migration.sqlite3"
    database_url = f"sqlite:///{database_path}"
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())
    command.check(config)

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}


def test_hosted_startup_migration_uses_alembic_head(tmp_path):
    from app.db.migrations import upgrade_database

    database_path = tmp_path / "hosted-startup.sqlite3"
    engine = create_engine(f"sqlite:///{database_path}")

    upgrade_database(engine)

    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one() == "20260723_0005"


def test_postgres_startup_migration_uses_one_atomic_locked_transaction(monkeypatch):
    from app.db import migrations

    connection = MagicMock()
    connection.dialect = SimpleNamespace(name="postgresql")
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection
    upgrade_calls = []

    monkeypatch.setattr(
        migrations.command,
        "upgrade",
        lambda config, revision: upgrade_calls.append((config, revision)),
    )

    migrations.upgrade_database(engine)

    engine.begin.assert_called_once_with()
    connection.execute.assert_called_once()
    statement, parameters = connection.execute.call_args.args
    assert "pg_advisory_xact_lock" in str(statement)
    assert parameters == {"lock_id": migrations.POSTGRES_MIGRATION_LOCK_ID}
    assert parameters["lock_id"] == 4_604_733_744_581_681_417
    assert upgrade_calls[0][0].attributes["connection"] is connection
    assert upgrade_calls[0][1] == "head"
