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
    HistoryResponse,
    NewsResponse,
    Overview,
)
from .services import ai, market_data
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
    insights, presentation = organize_report(metrics, build_insights(metrics), profile)
    return {
        "ticker": ticker.upper(),
        "insights": insights,
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
