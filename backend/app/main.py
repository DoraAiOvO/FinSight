"""FinSight API — evidence-first stock analysis."""
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import settings
from .db.migrations import upgrade_database
from .db.session import get_db
from .models.schemas import (
    AnalysisResponse,
    AssistantChatRequest,
    AssistantChatResponse,
    CompareResponse,
    CompanySearchResultResponse,
    CustomerProfilePreferences,
    CustomerProfileResponse,
    FilingDetailResponse,
    FilingListResponse,
    FilingQuestionRequest,
    FilingQuestionResponse,
    HistoryResponse,
    InvestmentPolicyCreate,
    InvestmentPolicyResponse,
    InvestmentPolicySummary,
    InvestmentPolicyUpdate,
    NewsResponse,
    Overview,
    PolicyExtractionRequest,
    PolicyExtractionResponse,
    PolicyProposalConfirmRequest,
    ResearchReportAuditResponse,
    ResearchReportDraft,
    ResearchSessionCreate,
    ResearchSessionResponse,
    ResearchSessionSummary,
    PolicyVersionCreate,
    PolicyVersionResponse,
    ThesisAssumptionCreate,
    ThesisAssumptionResponse,
    ThesisAssumptionUpdate,
    ThesisCreate,
    ThesisResponse,
    ThesisStatus,
    ThesisUpdate,
    ValuationAssumptions,
    ValuationResponse,
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistResponse,
    WhatChangedRequest,
    WhatChangedResponse,
)
from .services import (
    ai,
    assistant,
    benchmarks,
    company_search,
    evidence_auditor,
    investment_policies,
    market_data,
    policy_builder,
    research_workspace,
    sec_filings,
    thesis_ledger,
    valuations,
)
from .services.analysis import (
    DISCLAIMER,
    build_comparison,
    build_insights,
    build_neutral_evidence,
)
from .services.assistant_controls import rate_limiter as assistant_rate_limiter
from .services.customer_profiles import (
    create_customer_profile,
    get_customer_profile,
    serialize_profile,
    update_customer_profile,
)
from .services.presentation import (
    build_personalized_interpretation,
    organize_report,
)
from .services.tickers import normalize_comparison, normalize_ticker

@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.AUTO_MIGRATE_DATABASE:
        await run_in_threadpool(upgrade_database)
    yield


app = FastAPI(title="FinSight API", version="0.1.0", lifespan=lifespan)

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


def _raise_policy_error(error: investment_policies.InvestmentPolicyError):
    if isinstance(error, investment_policies.InvestmentPolicyNotFoundError):
        raise HTTPException(status_code=404, detail=str(error))
    if isinstance(error, investment_policies.InvestmentPolicyConflictError):
        raise HTTPException(status_code=409, detail=str(error))
    if isinstance(error, investment_policies.InvestmentPolicyValidationError):
        raise HTTPException(status_code=400, detail=str(error))
    raise HTTPException(status_code=500, detail="Investment policy error")


def _raise_policy_builder_error(error: policy_builder.PolicyBuilderError):
    if isinstance(error, policy_builder.PolicyBuilderUnavailableError):
        raise HTTPException(status_code=503, detail=str(error))
    if isinstance(error, policy_builder.PolicyBuilderExtractionError):
        raise HTTPException(status_code=502, detail=str(error))
    raise HTTPException(status_code=500, detail="Investment policy extraction error")


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_enabled": bool(settings.ANTHROPIC_API_KEY)}


@app.get(
    "/api/search/companies",
    response_model=list[CompanySearchResultResponse],
)
def search_public_companies(
    q: str = Query(..., min_length=1, max_length=120),
    limit: int = Query(8, ge=1, le=20),
):
    """Search live symbols with a cached, maintained-index fallback."""
    return company_search.search_companies(q, limit=limit)


@app.post("/api/assistant/chat", response_model=AssistantChatResponse)
def assistant_chat(
    chat_request: AssistantChatRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Route locally first, then use the low-cost education model only if needed."""
    ip_address = request.client.host if request.client else "unknown"
    quota = assistant_rate_limiter.check(
        ip_address,
        str(chat_request.customer_id) if chat_request.customer_id else None,
    )
    if not quota.allowed:
        raise HTTPException(
            status_code=429,
            detail="Assistant request limit reached. Please try again shortly.",
            headers={"Retry-After": str(quota.retry_after)},
        )
    response.headers["X-RateLimit-Remaining"] = str(
        min(quota.user_remaining, quota.ip_remaining)
    )

    profile = None
    if chat_request.customer_id is not None:
        try:
            profile = get_customer_profile(db, chat_request.customer_id)
        except SQLAlchemyError:
            # Anonymous/default explanations remain available if profile storage is down.
            profile = None

    report_context = chat_request.current_report
    if chat_request.report_id is not None:
        try:
            report_context = assistant.load_saved_report_context(
                db, chat_request.customer_id, chat_request.report_id
            )
        except research_workspace.WorkspaceError as error:
            _raise_workspace_error(error)
        except SQLAlchemyError:
            raise HTTPException(status_code=503, detail="Saved report is unavailable")

    return assistant.answer_chat(
        chat_request,
        profile=profile,
        report_context=report_context,
        ip_address=ip_address,
    )


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


@app.get(
    "/api/customers/{customer_id}/investment-policies",
    response_model=list[InvestmentPolicySummary],
)
def read_investment_policies(
    customer_id: UUID, db: Session = Depends(get_db)
):
    try:
        return investment_policies.list_policies(db, customer_id)
    except investment_policies.InvestmentPolicyError as error:
        _raise_policy_error(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Investment policies are unavailable"
        )


@app.post(
    "/api/customers/{customer_id}/investment-policy-proposals",
    response_model=PolicyExtractionResponse,
    status_code=201,
)
def extract_investment_policy_proposal(
    customer_id: UUID,
    request: PolicyExtractionRequest,
    db: Session = Depends(get_db),
):
    """Extract a review-only proposal. This endpoint never creates a policy."""
    try:
        return policy_builder.extract_proposal(db, customer_id, request)
    except investment_policies.InvestmentPolicyError as error:
        db.rollback()
        _raise_policy_error(error)
    except policy_builder.PolicyBuilderError as error:
        db.rollback()
        _raise_policy_builder_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503, detail="Investment policy extraction is unavailable"
        )


@app.post(
    (
        "/api/customers/{customer_id}/investment-policy-proposals/"
        "{proposal_id}/confirm"
    ),
    response_model=InvestmentPolicyResponse,
    status_code=201,
)
def confirm_investment_policy_proposal(
    customer_id: UUID,
    proposal_id: UUID,
    request: PolicyProposalConfirmRequest,
    db: Session = Depends(get_db),
):
    """Persist an edited proposal only after an explicit confirmation value."""
    try:
        return policy_builder.confirm_proposal(
            db, customer_id, proposal_id, request
        )
    except investment_policies.InvestmentPolicyError as error:
        db.rollback()
        _raise_policy_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503, detail="Investment policies are unavailable"
        )


@app.post(
    "/api/customers/{customer_id}/investment-policies",
    response_model=InvestmentPolicyResponse,
    status_code=201,
)
def create_investment_policy(
    customer_id: UUID,
    request: InvestmentPolicyCreate,
    db: Session = Depends(get_db),
):
    try:
        return investment_policies.create_policy(db, customer_id, request)
    except investment_policies.InvestmentPolicyError as error:
        db.rollback()
        _raise_policy_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503, detail="Investment policies are unavailable"
        )


@app.get(
    "/api/customers/{customer_id}/investment-policies/{policy_id}",
    response_model=InvestmentPolicyResponse,
)
def read_investment_policy(
    customer_id: UUID,
    policy_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        return investment_policies.get_policy(db, customer_id, policy_id)
    except investment_policies.InvestmentPolicyError as error:
        _raise_policy_error(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Investment policies are unavailable"
        )


@app.put(
    "/api/customers/{customer_id}/investment-policies/{policy_id}",
    response_model=InvestmentPolicyResponse,
)
def replace_investment_policy_metadata(
    customer_id: UUID,
    policy_id: UUID,
    request: InvestmentPolicyUpdate,
    db: Session = Depends(get_db),
):
    try:
        return investment_policies.update_policy(
            db, customer_id, policy_id, request
        )
    except investment_policies.InvestmentPolicyError as error:
        db.rollback()
        _raise_policy_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503, detail="Investment policies are unavailable"
        )


@app.delete(
    "/api/customers/{customer_id}/investment-policies/{policy_id}",
    status_code=204,
)
def remove_investment_policy(
    customer_id: UUID,
    policy_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        investment_policies.delete_policy(db, customer_id, policy_id)
    except investment_policies.InvestmentPolicyError as error:
        db.rollback()
        _raise_policy_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503, detail="Investment policies are unavailable"
        )


@app.get(
    "/api/customers/{customer_id}/investment-policies/{policy_id}/versions",
    response_model=list[PolicyVersionResponse],
)
def read_policy_versions(
    customer_id: UUID,
    policy_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        return investment_policies.list_policy_versions(
            db, customer_id, policy_id
        )
    except investment_policies.InvestmentPolicyError as error:
        _raise_policy_error(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Investment policies are unavailable"
        )


@app.post(
    "/api/customers/{customer_id}/investment-policies/{policy_id}/versions",
    response_model=PolicyVersionResponse,
    status_code=201,
)
def create_policy_version(
    customer_id: UUID,
    policy_id: UUID,
    request: PolicyVersionCreate,
    db: Session = Depends(get_db),
):
    try:
        return investment_policies.create_policy_version(
            db, customer_id, policy_id, request
        )
    except investment_policies.InvestmentPolicyError as error:
        db.rollback()
        _raise_policy_error(error)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503, detail="Investment policies are unavailable"
        )


@app.get(
    "/api/customers/{customer_id}/investment-policies/{policy_id}/versions/{version_id}",
    response_model=PolicyVersionResponse,
)
def read_policy_version(
    customer_id: UUID,
    policy_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        return investment_policies.get_policy_version(
            db, customer_id, policy_id, version_id
        )
    except investment_policies.InvestmentPolicyError as error:
        _raise_policy_error(error)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503, detail="Investment policies are unavailable"
        )


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


@app.post("/api/reports/audit", response_model=ResearchReportAuditResponse)
def audit_research_report(report: ResearchReportDraft):
    """Audit and sanitize a complete report before factual conclusions display."""
    return evidence_auditor.audit_research_report(report)


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
    neutral_insights = build_insights(metrics, benchmark_context)
    organized_insights, presentation = organize_report(
        metrics, neutral_insights, profile
    )
    policy = None
    if customer_id is not None:
        try:
            policy = investment_policies.get_default_published_policy(
                db, customer_id
            )
        except SQLAlchemyError:
            # Policy interpretation is optional and must not affect evidence.
            policy = None
    narrative = ai.narrate_analysis(
        ticker.upper(),
        metrics,
        neutral_insights,
        lang=lang,
        # Narrative content belongs to neutral evidence. User preferences may
        # change expansion/display only, never the generated factual synthesis.
        explanation_depth="standard",
    )
    return {
        "ticker": ticker.upper(),
        "neutral_evidence": build_neutral_evidence(
            metrics,
            benchmark_context,
            neutral_insights,
            narrative,
        ),
        "personalized_interpretation": build_personalized_interpretation(
            metrics,
            neutral_insights,
            organized_insights,
            presentation,
            policy,
        ),
        "disclaimer": DISCLAIMER,
    }


def _deterministic_valuation(
    ticker: str,
    assumptions: ValuationAssumptions | None = None,
):
    try:
        ticker = normalize_ticker(ticker)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    try:
        inputs = market_data.get_valuation_inputs(ticker)
        overview = market_data.get_overview(ticker)
        benchmark_context = benchmarks.build_benchmark_context(ticker, overview)
        return valuations.build_valuation(
            ticker,
            inputs,
            benchmark_context,
            assumptions=assumptions,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except valuations.ValuationDataUnavailableError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except valuations.ValuationError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Data provider error: {error}")


@app.get("/api/valuation/{ticker}", response_model=ValuationResponse)
def default_valuation(ticker: str):
    """Calculate valuation with transparent code-defined default assumptions."""
    return _deterministic_valuation(ticker)


@app.post("/api/valuation/{ticker}", response_model=ValuationResponse)
def calculate_valuation(ticker: str, assumptions: ValuationAssumptions):
    """Recalculate every valuation output from explicit user assumptions."""
    return _deterministic_valuation(ticker, assumptions)


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
