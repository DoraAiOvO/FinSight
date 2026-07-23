"""Environment configuration tests."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import (  # noqa: E402
    auto_migrate_database_from_environment,
    database_url_from_environment,
    normalize_database_url,
)


def test_hosted_postgres_urls_use_psycopg_driver():
    assert normalize_database_url("postgres://user:pass@db/finsight") == (
        "postgresql+psycopg://user:pass@db/finsight"
    )
    assert normalize_database_url("postgresql://user:pass@db/finsight") == (
        "postgresql+psycopg://user:pass@db/finsight"
    )


def test_explicit_driver_and_sqlite_urls_are_unchanged():
    assert normalize_database_url("postgresql+psycopg://db/finsight") == (
        "postgresql+psycopg://db/finsight"
    )
    assert normalize_database_url("sqlite:///./finsight.db") == "sqlite:///./finsight.db"


def test_vercel_marketplace_database_url_is_supported(monkeypatch):
    monkeypatch.delenv("FINSIGHT_DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgres://marketplace:secret@db/finsight")

    assert database_url_from_environment() == (
        "postgresql+psycopg://marketplace:secret@db/finsight"
    )


def test_vercel_postgres_enables_startup_migrations(monkeypatch):
    monkeypatch.delenv("FINSIGHT_AUTO_MIGRATE", raising=False)
    monkeypatch.setenv("VERCEL", "1")

    assert auto_migrate_database_from_environment(
        "postgresql+psycopg://db/finsight"
    ) is True
    assert auto_migrate_database_from_environment("sqlite:///./finsight.db") is False

    monkeypatch.setenv("FINSIGHT_AUTO_MIGRATE", "false")
    assert auto_migrate_database_from_environment(
        "postgresql+psycopg://db/finsight"
    ) is False


def test_vercel_backend_allows_startup_migrations_to_finish():
    project_root = Path(__file__).resolve().parents[2]
    vercel_config = json.loads((project_root / "vercel.json").read_text())

    backend_functions = vercel_config["services"]["backend"]["functions"]

    assert backend_functions["app/main.py"]["maxDuration"] >= 60
