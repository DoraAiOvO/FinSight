"""FinSight API — evidence-first stock analysis."""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models.schemas import (
    AnalysisResponse,
    CompareResponse,
    HistoryResponse,
    NewsResponse,
    Overview,
)
from .services import ai, market_data
from .services.analysis import DISCLAIMER, build_comparison, build_insights

app = FastAPI(title="FinSight API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_enabled": bool(settings.ANTHROPIC_API_KEY)}


@app.get("/api/stocks/{ticker}", response_model=Overview)
def stock_overview(ticker: str):
    try:
        return market_data.get_overview(ticker)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")


@app.get("/api/stocks/{ticker}/history", response_model=HistoryResponse)
def stock_history(ticker: str, period: str = Query("6mo", pattern="^(1mo|3mo|6mo|1y|2y|5y)$")):
    try:
        points = market_data.get_history(ticker, period)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")
    if not points:
        raise HTTPException(status_code=404, detail=f"No price history for '{ticker}'")
    return {"ticker": ticker.upper(), "period": period, "points": points}


@app.get("/api/news/{ticker}", response_model=NewsResponse)
def stock_news(ticker: str):
    try:
        items = market_data.get_news(ticker)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")
    return {
        "ticker": ticker.upper(),
        "items": items,
        "ai_summary": ai.summarize_news(ticker.upper(), items),
    }


@app.get("/api/analysis/{ticker}", response_model=AnalysisResponse)
def stock_analysis(ticker: str):
    try:
        metrics = market_data.get_overview(ticker)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Data provider error: {e}")
    insights = build_insights(metrics)
    return {
        "ticker": ticker.upper(),
        "insights": insights,
        "ai_narrative": ai.narrate_analysis(ticker.upper(), metrics, insights),
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/compare", response_model=CompareResponse)
def compare(tickers: str = Query(..., description="Comma-separated tickers, e.g. AAPL,MSFT")):
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()][:5]
    if len(symbols) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two tickers")
    overviews = []
    for s in symbols:
        try:
            overviews.append(market_data.get_overview(s))
        except LookupError:
            raise HTTPException(status_code=404, detail=f"No data found for ticker '{s}'")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Data provider error: {e}")
    return {"tickers": symbols, "rows": build_comparison(overviews)}
