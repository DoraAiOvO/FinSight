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
    "feedback",
    "alert_preferences",
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
