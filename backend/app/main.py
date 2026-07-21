"""FinSight API — evidence-first stock analysis."""
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import settings
from .db.session import get_db
from .models.schemas import (
    AnalysisResponse,
    CompareResponse,
    CustomerProfilePreferences,
    CustomerProfileResponse,
    FilingDetailResponse,
    FilingListResponse,
    FilingQuestionRequest,
    FilingQuestionResponse,
    HistoryResponse,
    NewsResponse,
    Overview,
    ResearchSessionCreate,
    ResearchSessionResponse,
    ResearchSessionSummary,
    ThesisAssumptionCreate,
    ThesisAssumptionResponse,
    ThesisAssumptionUpdate,
    ThesisCreate,
    ThesisResponse,
    ThesisStatus,
    ThesisUpdate,
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistResponse,
    WhatChangedRequest,
    WhatChangedResponse,
)
from .services import (
    ai,
    benchmarks,
    market_data,
    research_workspace,
    sec_filings,
    thesis_ledger,
)
from .services.analysis import DISCLAIMER, build_comparison, build_insights
from .services.customer_profiles import (
    create_customer_profile,
    get_customer_profile,
    serialize_profile,
    update_customer_profile,
)
from .services.presentation import organize_report
from .services.tickers import normalize_comparison, normalize_ticker

app = FastAPI(title="FinSight API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

LANG_PATTERN = "^(en|es|fr|zh)$"


def _raise_sec_error(error: sec_filings.SecError):
    if isinstance(error, sec_filings.SecNotFoundError):
        raise HTTPException(status_code=404, detail=str(error))
    if isinstance(error, sec_filings.SecRateLimitError):
        raise HTTPException(
            status_code=503,
            detail=str(error),
            headers={"Retry-After": "60"},
        )
    raise HTTPException(status_code=502, detail=str(error))


def _raise_workspace_error(error: research_workspace.WorkspaceError):
    if isinstance(error, research_workspace.WorkspaceNotFoundError):
        raise HTTPException(status_code=404, detail=str(error))
    if isinstance(error, research_workspace.WorkspaceConflictError):
        raise HTTPException(status_code=409, detail=str(error))
    if isinstance(error, research_workspace.WorkspaceValidationError):
        raise HTTPException(status_code=400, detail=str(error))
    raise HTTPException(status_code=500, detail="Research workspace error")


def _raise_thesis_error(error: thesis_ledger.ThesisLedgerError):
    if isinstance(error, thesis_ledger.ThesisLedgerNotFoundError):
        raise HTTPException(status_code=404, detail=str(error))
    if isinstance(error, thesis_ledger.ThesisLedgerValidationError):
        raise HTTPException(status_code=400, detail=str(error))
    raise HTTPException(status_code=500, detail="Thesis ledger error")


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_enabled": bool(settings.ANTHROPIC_API_KEY)}


@app.post(
    "/api/customer-profiles",
    response_model=CustomerProfileResponse,
    status_code=201,
)
def create_profile(
    preferences: CustomerProfilePreferences,
    db: Session = Depends(get_db),
):
    try:
        profile = create_customer_profile(db, preferences)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Customer profiles are unavailable")
    return serialize_profile(profile)


@app.get(
    "/api/customer-profiles/{customer_id}",
    response_model=CustomerProfileResponse,
)
def read_profile(customer_id: UUID, db: Session = Depends(get_db)):
    try:
        profile = get_customer_profile(db, customer_id)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Customer profiles are unavailable")
    if profile is None:
        raise HTTPException(status_code=404, detail="Customer profile not found")
    return serialize_profile(profile)


@app.put(
    "/api/customer-profiles/{customer_id}",
    response_model=CustomerProfileResponse,
)
def replace_profile(
    customer_id: UUID,
    preferences: CustomerProfilePreferences,
    db: Session = Depends(get_db),
):
    try:
        profile = get_customer_profile(db, customer_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Customer profile not found")
        profile = update_customer_profile(db, profile, preferences)
    except HTTPException:
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Customer profiles are unavailable")
    return serialize_profile(profile)


@app.get(
    "/api/customers/{customer_id}/theses",
    response_model=list[ThesisResponse],
)
def read_theses(
    customer_id: UUID,
    ticker: str | None = Query(None),
    status: ThesisStatus | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        return thesis_ledger.list_theses(
            db, customer_id, ticker=ticker, status=status
        )
    except thesis_ledger.ThesisLedgerError as error:
        _raise_thesis_error(error)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Thesis ledger is unavailable")


@app.post(
    "/api/customers/{customer_id}/theses",
    response_model=ThesisResponse,
    status_code=201,
)
def create_research_thesis(
    customer_id: UUID,
    request: ThesisCreate,
    db: Session = Depends(get_db),
):
    try:
        return thesis_ledger.create_thesis(db, customer_id, request)
    except thesis_ledger.ThesisLedgerError as error:
        db.rollback()
        _raise_thesis_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Thesis ledger is unavailable")


@app.get(
    "/api/customers/{customer_id}/theses/{thesis_id}",
    response_model=ThesisResponse,
)
def read_research_thesis(
    customer_id: UUID,
    thesis_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        return thesis_ledger.get_thesis(db, customer_id, thesis_id)
    except thesis_ledger.ThesisLedgerError as error:
        _raise_thesis_error(error)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Thesis ledger is unavailable")


@app.put(
    "/api/customers/{customer_id}/theses/{thesis_id}",
    response_model=ThesisResponse,
)
def replace_research_thesis(
    customer_id: UUID,
    thesis_id: UUID,
    request: ThesisUpdate,
    db: Session = Depends(get_db),
):
    try:
        return thesis_ledger.update_thesis(db, customer_id, thesis_id, request)
    except thesis_ledger.ThesisLedgerError as error:
        db.rollback()
        _raise_thesis_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Thesis ledger is unavailable")


@app.delete(
    "/api/customers/{customer_id}/theses/{thesis_id}",
    status_code=204,
)
def remove_research_thesis(
    customer_id: UUID,
    thesis_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        thesis_ledger.delete_thesis(db, customer_id, thesis_id)
    except thesis_ledger.ThesisLedgerError as error:
        db.rollback()
        _raise_thesis_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Thesis ledger is unavailable")


@app.post(
    "/api/customers/{customer_id}/theses/{thesis_id}/assumptions",
    response_model=ThesisAssumptionResponse,
    status_code=201,
)
def create_thesis_assumption(
    customer_id: UUID,
    thesis_id: UUID,
    request: ThesisAssumptionCreate,
    db: Session = Depends(get_db),
):
    try:
        return thesis_ledger.create_assumption(
            db, customer_id, thesis_id, request
        )
    except thesis_ledger.ThesisLedgerError as error:
        db.rollback()
        _raise_thesis_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Thesis ledger is unavailable")


@app.put(
    "/api/customers/{customer_id}/theses/{thesis_id}/assumptions/{assumption_id}",
    response_model=ThesisAssumptionResponse,
)
def replace_thesis_assumption(
    customer_id: UUID,
    thesis_id: UUID,
    assumption_id: UUID,
    request: ThesisAssumptionUpdate,
    db: Session = Depends(get_db),
):
    try:
        return thesis_ledger.update_assumption(
            db, customer_id, thesis_id, assumption_id, request
        )
    except thesis_ledger.ThesisLedgerError as error:
        db.rollback()
        _raise_thesis_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Thesis ledger is unavailable")


@app.delete(
    "/api/customers/{customer_id}/theses/{thesis_id}/assumptions/{assumption_id}",
    status_code=204,
)
def remove_thesis_assumption(
    customer_id: UUID,
    thesis_id: UUID,
    assumption_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        thesis_ledger.delete_assumption(
            db, customer_id, thesis_id, assumption_id
        )
    except thesis_ledger.ThesisLedgerError as error:
        db.rollback()
        _raise_thesis_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Thesis ledger is unavailable")


@app.get(
    "/api/customers/{customer_id}/watchlists",
    response_model=list[WatchlistResponse],
)
def read_watchlists(customer_id: UUID, db: Session = Depends(get_db)):
    try:
        return research_workspace.list_watchlists(db, customer_id)
    except research_workspace.WorkspaceError as error:
        _raise_workspace_error(error)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Watchlists are unavailable")


@app.post(
    "/api/customers/{customer_id}/watchlists",
    response_model=WatchlistResponse,
    status_code=201,
)
def create_watchlist(
    customer_id: UUID,
    request: WatchlistCreate,
    db: Session = Depends(get_db),
):
    try:
        return research_workspace.create_watchlist(db, customer_id, request)
    except research_workspace.WorkspaceError as error:
        db.rollback()
        _raise_workspace_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Watchlists are unavailable")


@app.delete(
    "/api/customers/{customer_id}/watchlists/{watchlist_id}",
    status_code=204,
)
def remove_watchlist(
    customer_id: UUID,
    watchlist_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        research_workspace.delete_watchlist(db, customer_id, watchlist_id)
    except research_workspace.WorkspaceError as error:
        db.rollback()
        _raise_workspace_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Watchlists are unavailable")


@app.post(
    "/api/customers/{customer_id}/watchlists/{watchlist_id}/items",
    response_model=WatchlistResponse,
    status_code=201,
)
def add_watchlist_stock(
    customer_id: UUID,
    watchlist_id: UUID,
    request: WatchlistItemCreate,
    db: Session = Depends(get_db),
):
    try:
        return research_workspace.add_watchlist_item(
            db, customer_id, watchlist_id, request
        )
    except research_workspace.WorkspaceError as error:
        db.rollback()
        _raise_workspace_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Watchlists are unavailable")


@app.delete(
    "/api/customers/{customer_id}/watchlists/{watchlist_id}/items/{ticker}",
    response_model=WatchlistResponse,
)
def remove_watchlist_stock(
    customer_id: UUID,
    watchlist_id: UUID,
    ticker: str,
    db: Session = Depends(get_db),
):
    try:
        return research_workspace.remove_watchlist_item(
            db, customer_id, watchlist_id, ticker
        )
    except research_workspace.WorkspaceError as error:
        db.rollback()
        _raise_workspace_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Watchlists are unavailable")


@app.get(
    "/api/customers/{customer_id}/research-sessions",
    response_model=list[ResearchSessionSummary],
)
def read_research_sessions(
    customer_id: UUID,
    ticker: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        return research_workspace.list_research_sessions(
            db, customer_id, ticker=ticker, limit=limit
        )
    except research_workspace.WorkspaceError as error:
        _raise_workspace_error(error)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Saved research is unavailable")


@app.post(
    "/api/customers/{customer_id}/research-sessions",
    response_model=ResearchSessionResponse,
    status_code=201,
)
def save_research_session(
    customer_id: UUID,
    request: ResearchSessionCreate,
    db: Session = Depends(get_db),
):
    try:
        return research_workspace.create_research_session(db, customer_id, request)
    except research_workspace.WorkspaceError as error:
        db.rollback()
        _raise_workspace_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Saved research is unavailable")


@app.get(
    "/api/customers/{customer_id}/research-sessions/{research_session_id}",
    response_model=ResearchSessionResponse,
)
def read_research_session(
    customer_id: UUID,
    research_session_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        research = research_workspace.get_research_session(
            db, customer_id, research_session_id
        )
        return research_workspace.serialize_research_session(research)
    except research_workspace.WorkspaceError as error:
        _raise_workspace_error(error)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Saved research is unavailable")


@app.delete(
    "/api/customers/{customer_id}/research-sessions/{research_session_id}",
    status_code=204,
)
def remove_research_session(
    customer_id: UUID,
    research_session_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        research_workspace.delete_research_session(
            db, customer_id, research_session_id
        )
    except research_workspace.WorkspaceError as error:
        db.rollback()
        _raise_workspace_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Saved research is unavailable")


@app.post(
    "/api/customers/{customer_id}/what-changed/{ticker}",
    response_model=WhatChangedResponse,
)
def what_changed_since_last_research(
    customer_id: UUID,
    ticker: str,
    request: WhatChangedRequest,
    db: Session = Depends(get_db),
):
    try:
        return research_workspace.what_changed(
            db,
            customer_id,
            ticker,
            request.snapshot,
            baseline_session_id=request.baseline_session_id,
        )
    except research_workspace.WorkspaceError as error:
        _raise_workspace_error(error)
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Change tracking is unavailable")


@app.get("/api/stocks/{ticker}", response_model=Overview)
def stock_overview(ticker: str):
    try:
        ticker = normalize_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        return market_data.get_overview(ticker)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")


@app.get("/api/stocks/{ticker}/history", response_model=HistoryResponse)
def stock_history(ticker: str, period: str = Query("6mo", pattern="^(1mo|3mo|6mo|1y|2y|5y)$")):
    try:
        ticker = normalize_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        points = market_data.get_history(ticker, period)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")
    if not points:
        raise HTTPException(status_code=404, detail=f"No price history for '{ticker}'")
    return {"ticker": ticker.upper(), "period": period, "points": points}


@app.get("/api/news/{ticker}", response_model=NewsResponse)
def stock_news(ticker: str, lang: str = Query("en", pattern=LANG_PATTERN)):
    try:
        ticker = normalize_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        items = market_data.get_news(ticker)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")
    return {
        "ticker": ticker.upper(),
        "items": items,
        "ai_summary": ai.summarize_news(ticker.upper(), items, lang=lang),
    }


@app.get("/api/filings/{ticker}", response_model=FilingListResponse)
def recent_filings(ticker: str, limit: int = Query(12, ge=1, le=20)):
    try:
        ticker = normalize_ticker(ticker)
        return sec_filings.list_filings(ticker, limit=limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except sec_filings.SecError as error:
        _raise_sec_error(error)


@app.get(
    "/api/filings/{ticker}/{accession_number}",
    response_model=FilingDetailResponse,
)
def filing_detail(ticker: str, accession_number: str):
    try:
        ticker = normalize_ticker(ticker)
        return sec_filings.get_filing(ticker, accession_number)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except sec_filings.SecError as error:
        _raise_sec_error(error)


@app.post(
    "/api/filings/{ticker}/{accession_number}/questions",
    response_model=FilingQuestionResponse,
)
def ask_filing_question(
    ticker: str,
    accession_number: str,
    request: FilingQuestionRequest,
):
    try:
        ticker = normalize_ticker(ticker)
        return sec_filings.answer_question(
            ticker,
            accession_number,
            request.question,
            lang=request.lang.value,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except sec_filings.SecError as error:
        _raise_sec_error(error)


@app.get("/api/analysis/{ticker}", response_model=AnalysisResponse)
def stock_analysis(
    ticker: str,
    lang: str = Query("en", pattern=LANG_PATTERN),
    customer_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
):
    try:
        ticker = normalize_ticker(ticker)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        metrics = market_data.get_overview(ticker)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")
    profile = None
    if customer_id is not None:
        try:
            profile = get_customer_profile(db, customer_id)
        except SQLAlchemyError:
            # A profile lookup must never break the existing anonymous report.
            profile = None
    benchmark_context = benchmarks.build_benchmark_context(ticker, metrics)
    insights, presentation = organize_report(
        metrics,
        build_insights(metrics, benchmark_context),
        profile,
    )
    return {
        "ticker": ticker.upper(),
        "insights": insights,
        "benchmarks": benchmark_context,
        "ai_narrative": ai.narrate_analysis(
            ticker.upper(),
            metrics,
            insights,
            lang=lang,
            explanation_depth=presentation.explanation_depth.value,
        ),
        "presentation": presentation,
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/compare", response_model=CompareResponse)
def compare(tickers: str = Query(..., description="Comma-separated tickers, e.g. AAPL,MSFT")):
    try:
        symbols = normalize_comparison(tickers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    overviews = []
    for s in symbols:
        try:
            overviews.append(market_data.get_overview(s))
        except LookupError:
            raise HTTPException(status_code=404, detail=f"No data found for ticker '{s}'")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Data provider error: {e}")
    return {"tickers": symbols, "rows": build_comparison(overviews)}
