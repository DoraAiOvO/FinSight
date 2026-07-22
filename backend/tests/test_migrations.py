"""Alembic migration smoke tests."""

import sys
from pathlib import Path

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
        ).scalar_one() == "20260722_0004"
