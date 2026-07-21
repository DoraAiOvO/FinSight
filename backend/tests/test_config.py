"""Environment configuration tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import database_url_from_environment, normalize_database_url  # noqa: E402


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
