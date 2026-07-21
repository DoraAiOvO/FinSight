"""Persistence model and PostgreSQL-compatibility tests."""

import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateTable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base  # noqa: E402
from app.db.models import (  # noqa: E402
    AlertPreference,
    CustomerProfile,
    Feedback,
    ResearchSession,
    SavedReport,
    Thesis,
    ThesisAssumption,
    ThesisAssumptionHistory,
    User,
    Watchlist,
    WatchlistItem,
)


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
}


def sqlite_engine():
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_metadata_creates_all_persistence_tables():
    engine = sqlite_engine()
    Base.metadata.create_all(engine)

    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_models_persist_a_complete_customer_research_graph():
    engine = sqlite_engine()
    Base.metadata.create_all(engine)

    user = User(email="researcher@example.com", display_name="Researcher")
    user.customer_profile = CustomerProfile(
        experience_level="intermediate",
        research_horizon="5_plus_years",
        priorities=["growth", "stability"],
        risk_comfort="medium",
        preferred_report_depth="standard",
        industries_of_interest=["semiconductors"],
    )
    user.watchlists.append(
        Watchlist(
            name="Core research",
            is_default=True,
            items=[WatchlistItem(ticker="NVDA", notes="Track data-center growth")],
        )
    )
    research = ResearchSession(
        ticker="NVDA", request_payload={"period": "1y"}, result_payload={"status": "ok"}
    )
    user.research_sessions.append(research)
    report = SavedReport(
        ticker="NVDA",
        title="NVDA evidence brief",
        content={"summary": "Evidence-backed report"},
        research_session=research,
    )
    user.saved_reports.append(report)
    thesis = Thesis(
        ticker="NVDA",
        title="Data-center demand",
        statement="Demand remains durable over the research horizon.",
        confidence=0.7,
        research_session=research,
        assumptions=[
            ThesisAssumption(
                description="Data-center revenue keeps growing",
                condition_type="metric",
                metric_key="data_center_revenue_growth",
                operator=">",
                target_value="0",
                position=1,
                history=[
                    ThesisAssumptionHistory(
                        change_type="created",
                        current_values={"current_status": "unreviewed"},
                    )
                ],
            )
        ],
    )
    user.theses.append(thesis)
    user.feedback.append(
        Feedback(
            research_session=research,
            saved_report=report,
            feedback_type="helpful",
            rating=5,
            context={"section": "risks"},
        )
    )
    user.alert_preferences.append(
        AlertPreference(
            ticker="NVDA",
            alert_type="thesis_assumption_changed",
            channel="in_app",
            conditions={"minimum_severity": "medium"},
        )
    )

    with Session(engine) as session:
        session.add(user)
        session.commit()
        session.expire_all()

        stored = session.scalar(select(User).where(User.email == user.email))
        assert stored is not None
        assert stored.customer_profile.priorities == ["growth", "stability"]
        assert stored.watchlists[0].items[0].ticker == "NVDA"
        assert stored.research_sessions[0].saved_reports[0].content["summary"].startswith(
            "Evidence"
        )
        assert stored.theses[0].assumptions[0].target_value == "0"
        assert stored.theses[0].assumptions[0].history[0].change_type == "created"
        assert stored.alert_preferences[0].is_enabled is True

        stored.customer_profile.priorities.append("income")
        stored.alert_preferences[0].conditions["minimum_severity"] = "high"
        session.commit()
        session.expire_all()

        updated = session.scalar(select(User).where(User.email == user.email))
        assert updated.customer_profile.priorities[-1] == "income"
        assert updated.alert_preferences[0].conditions["minimum_severity"] == "high"


def test_research_session_can_remain_anonymous():
    engine = sqlite_engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(ResearchSession(ticker="AAPL", request_payload={"period": "6mo"}))
        session.commit()

        stored = session.scalar(select(ResearchSession))
        assert stored is not None
        assert stored.user_id is None
        assert stored.ticker == "AAPL"


def test_schema_compiles_for_postgresql():
    ddl = "\n".join(
        str(CreateTable(table).compile(dialect=postgresql.dialect()))
        for table in Base.metadata.sorted_tables
    )

    assert "CREATE TABLE users" in ddl
    assert "UUID" in ddl
    assert "JSON" in ddl
    assert "ON DELETE CASCADE" in ddl
