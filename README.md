<div align="center">

<img src="docs/banner.svg" alt="FinSight — see beyond the numbers" width="100%" />

# FinSight

**See beyond the numbers.**

An evidence-first stock research assistant that turns fundamentals, market news,
peer comparisons, and risk signals into one balanced research brief — and always
shows its work.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](backend)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)](backend/app/main.py)
[![React](https://img.shields.io/badge/React-frontend-61DAFB?logo=react&logoColor=black)](frontend)
[![Vite](https://img.shields.io/badge/Vite-build-646CFF?logo=vite&logoColor=white)](frontend/vite.config.js)
[![Claude](https://img.shields.io/badge/Claude-optional_AI_layer-D97757?logo=anthropic&logoColor=white)](backend/app/services/ai.py)

*Designed to support your judgment — not to tell you what to buy or sell.*

</div>

---

## Why FinSight?

Investment research is scattered across financial statements, news articles,
market data, and company reports. FinSight turns that fragmented information
into a clear, explainable view of a company, so you can understand both the
opportunity **and** the uncertainty.

Every insight cites its evidence: the metric, the observed value, and the
benchmark it was judged against. The optional AI layer narrates those findings —
it never generates conclusions of its own and never recommends buying or selling.

## What it does

| Capability | Description |
|---|---|
| 📊 **Financial analysis** | Organizes key company data and surfaces meaningful trends |
| 📰 **News summaries** | Condenses relevant headlines and explains why they may matter |
| ⚖️ **Company comparisons** | Compares 2–5 businesses side by side using consistent criteria |
| 🔍 **Risk & opportunity analysis** | Flags strengths, catalysts, uncertainties, and warning signs |
| 🧾 **Evidence-based explanations** | Shows the reasoning and data behind every insight |
| 🌐 **Multilingual research** | Localizes the interface, rule-based evidence, and AI summaries in English, Spanish, French, or Simplified Chinese |
| 🧭 **Customer research profile** | Organizes the same evidence around experience, horizon, priorities, risk comfort, report depth, language, and industries of interest |
| 🏛️ **SEC filings** | Lists recent 10-K, 10-Q, and 8-K filings, extracts decision-useful sections and earnings exhibits, and answers questions with citations to the original filing |
| 📐 **Relative benchmarks** | Compares metrics with industry, sector, automatically selected peers, and the company’s own annual history—and explains which benchmark is primary and why |
| 🧠 **Research memory** | Persists grouped watchlists and research snapshots, then shows what changed in metrics, news, filings, signals, and thesis assumptions |
| 📒 **Thesis Ledger** | Records a research thesis, measurable metric or event assumptions, evidence on both sides, status, and an append-only change history |
| 🧭 **Investment policies** | Stores multiple versioned policies per customer and returns policy fit, preference matches, constraint checks, ranking rationale, emphasis, and alert relevance in a separate personalized layer—without changing objective evidence or benchmarks |
| ✍️ **Natural-language policy builder** | Extracts multilingual and code-switched preferences into a review-only structured draft, exposes ambiguities and conflicts, and saves a versioned policy only after explicit user confirmation |
| 🧮 **Valuation & scenarios** | Calculates DCF, reverse DCF, selected-peer multiples, three scenario cases, and a sensitivity matrix entirely in deterministic code |
| 🛡️ **Evidence Auditor** | Checks every assembled report for unsupported claims, stale evidence, missing citations, source conflicts, incorrect units, and inconsistent numbers before generated conclusions are displayed or saved |
| ✅ **Product evaluation** | Runs a fixed offline report suite across citation, numeric, freshness, contradiction, coverage, readability, personalization, and multilingual quality gates |

## Quick start

The MVP is a **FastAPI** backend (market data via Yahoo Finance) plus a
**React/Vite** frontend. An optional Anthropic API key adds AI news summaries
and analysis narratives; without it, insights come from the transparent rules
engine alone.

**Backend** (Python 3.10+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** (Node 18+):

```bash
cd frontend
pnpm install
pnpm dev           # http://localhost:5173 (proxies /api to :8000)
```

**Optional AI layer:** `cp .env.example .env` and set `ANTHROPIC_API_KEY`.

**SEC access:** FinSight uses the public SEC EDGAR submissions API without an
API key. For deployed environments, set a declared contact in the request
User-Agent as required by the SEC:

```bash
export FINSIGHT_SEC_USER_AGENT="FinSight your-email@example.com"
```

SEC metadata is cached for six hours and filing documents for 24 hours by
default. Override these process-local cache windows with
`FINSIGHT_SEC_CACHE_TTL` and `FINSIGHT_SEC_DOCUMENT_CACHE_TTL` (seconds).

**Tests:** `cd backend && pytest`; `cd frontend && pnpm test`

### Persistent database

The stock overview, history, news, analysis, and comparison endpoints remain
anonymous and do not require a database connection. Persistence is available as
an independent SQLAlchemy layer for customer profiles, watchlists, research
sessions, saved reports, theses, investment policies, feedback, and alert
preferences.

For the quickest local setup, leave `FINSIGHT_DATABASE_URL` unset. SQLAlchemy
then uses `sqlite:///./finsight.db`. Create or update the schema from `backend/`:

```bash
cd backend
alembic upgrade head
```

To develop against PostgreSQL 16 instead:

```bash
docker compose up -d db
export FINSIGHT_DATABASE_URL=postgresql+psycopg://finsight:finsight@localhost:5432/finsight
cd backend
alembic upgrade head
```

Useful migration commands:

```bash
alembic current              # show the database revision
alembic history              # list available revisions
alembic downgrade -1         # roll back one revision
alembic revision --autogenerate -m "describe schema change"
```

Run `alembic upgrade head` before using future authenticated or saved-research
features. The application never calls `create_all()` at startup; Alembic is the
single source of truth for schema changes.

On Vercel, a Marketplace Postgres connection exposed as `DATABASE_URL` or
`POSTGRES_URL` is detected automatically. The serverless app runs the same
Alembic migrations before accepting requests, protected by a Postgres advisory
lock so concurrent cold starts cannot migrate the schema at the same time.

### Customer onboarding and safe personalization

On first visit, customers can complete or skip a three-step research-profile
flow. A completed profile is stored in the database and its anonymous customer
UUID is kept in that browser's local storage. Authentication and cross-device
identity are intentionally outside this phase.

Every analysis response is divided into `neutral_evidence` and
`personalized_interpretation`. The neutral layer always contains facts,
benchmarks, risks, opportunities, uncertainties, sources, freshness, conflicts,
and missing-data disclosures. The profile or default published investment policy
may only affect the personalized layer, including:

- report section order;
- which existing metrics and insights are visually highlighted; and
- whether explanations use simple, standard, or professional detail.

It never removes evidence, changes deterministic risk or opportunity signals,
or produces personalized buy, sell, or suitability instructions. Only the
neutral, standard explanation depth is passed to the optional AI narrative
layer, so preferences cannot alter the factual synthesis. The frontend can
switch explicitly between **Personalized View** and **Neutral Evidence View**.

## Architecture

```
├── backend/            FastAPI + yfinance
│   ├── app/
│   │   ├── main.py             API routes
│   │   ├── config.py           env-based settings
│   │   ├── db/                  SQLAlchemy models + session factory
│   │   ├── models/schemas.py   Pydantic response models
│   │   ├── services/
│   │   │   ├── market_data.py  Yahoo Finance access + cache
│   │   │   ├── benchmarks.py   industry, sector, peer, and historical context
│   │   │   ├── analysis.py     transparent risk/opportunity rules
│   │   │   ├── presentation.py profile-driven organization and highlights
│   │   │   ├── customer_profiles.py  onboarding persistence
│   │   │   ├── research_workspace.py watchlists, snapshots, and deterministic diffs
│   │   │   ├── thesis_ledger.py  thesis and assumption CRUD with audit history
│   │   │   ├── investment_policies.py versioned policy CRUD and ownership checks
│   │   │   ├── policy_builder.py review-only AI extraction and explicit confirmation
│   │   │   ├── valuations.py    deterministic DCF, reverse DCF, peers, and sensitivity
│   │   │   ├── evidence_auditor.py deterministic report validation and conclusion blocking
│   │   │   ├── sec_filings.py  SEC metadata, extraction, cache, and Q&A retrieval
│   │   │   └── ai.py           optional Anthropic layer
│   │   └── evaluation/          deterministic product-quality metrics and CLI
│   ├── evals/          versioned report datasets and evaluation methodology
│   ├── alembic/        versioned database migrations
│   └── tests/          unit tests (no network needed)
└── frontend/           React + Vite single-page app
```

### API

| Endpoint | Description |
|---|---|
| `POST /api/assistant/chat` | Multilingual, intent-routed assistant with local glossary/help answers, grounded report Q&A, safe ticker lookup, and advice boundaries |
| `GET /api/stocks/{ticker}` | Normalized fundamentals overview |
| `GET /api/stocks/{ticker}/history?period=6mo` | Daily closes (1mo–5y) |
| `GET /api/news/{ticker}` | Recent headlines + optional AI theme summary |
| `GET /api/analysis/{ticker}` | Policy-independent facts, benchmarks, risks, opportunities, uncertainty, provenance, freshness, conflicts, and missing data |
| `GET /api/analysis/{ticker}?customer_id={uuid}` | Identical neutral evidence plus a separate profile/default-policy interpretation |
| `GET /api/compare?tickers=AAPL,MSFT` | Side-by-side comparison (2–5 tickers) |
| `GET /api/valuation/{ticker}` | Deterministic valuation using disclosed code-defined defaults |
| `POST /api/valuation/{ticker}` | Recalculate all valuation models from explicit user assumptions |
| `POST /api/reports/audit` | Validate and sanitize an assembled report before generated factual conclusions are displayed |
| `GET /api/filings/{ticker}` | Recent 10-K, 10-Q, and 8-K filings from SEC EDGAR |
| `GET /api/filings/{ticker}/{accession}` | Important extracted sections from one filing |
| `POST /api/filings/{ticker}/{accession}/questions` | Filing-grounded answer plus original-section citations |
| `POST /api/customer-profiles` | Create a browser-scoped customer profile |
| `GET /api/customer-profiles/{customer_id}` | Restore a customer profile |
| `PUT /api/customer-profiles/{customer_id}` | Replace customer research preferences |
| `GET/POST /api/customers/{customer_id}/watchlists` | List or create persistent watchlist groups |
| `POST /api/customers/{customer_id}/watchlists/{watchlist_id}/items` | Add a normalized ticker to a watchlist |
| `DELETE /api/customers/{customer_id}/watchlists/{watchlist_id}/items/{ticker}` | Remove a ticker from a watchlist |
| `GET/POST /api/customers/{customer_id}/theses` | List or create research theses, optionally filtered by ticker and status |
| `GET/PUT/DELETE /api/customers/{customer_id}/theses/{thesis_id}` | Read, update, or delete one owned thesis |
| `POST /api/customers/{customer_id}/theses/{thesis_id}/assumptions` | Add a measurable metric or event assumption |
| `PUT/DELETE /api/customers/{customer_id}/theses/{thesis_id}/assumptions/{assumption_id}` | Update or delete an assumption; updates append history |
| `GET/POST /api/customers/{customer_id}/research-sessions` | List or save validated research snapshots |
| `GET/DELETE /api/customers/{customer_id}/research-sessions/{session_id}` | Restore or delete a saved research session |
| `POST /api/customers/{customer_id}/what-changed/{ticker}` | Compare current evidence with the latest or selected saved session |
| `GET/POST /api/customers/{customer_id}/investment-policies` | List or create user-owned, versioned investment policies |
| `GET/PUT/DELETE /api/customers/{customer_id}/investment-policies/{policy_id}` | Read, update metadata, or delete one owned policy |
| `GET/POST /api/customers/{customer_id}/investment-policies/{policy_id}/versions` | List immutable policy snapshots or add the next numbered version |
| `POST /api/customers/{customer_id}/investment-policy-proposals` | Use AI to extract multilingual natural-language preferences into a persisted, non-active review draft |
| `POST /api/customers/{customer_id}/investment-policy-proposals/{proposal_id}/confirm` | Save the user-edited proposal as published version 1; requires an explicit confirmation value and acknowledgment of extraction issues |
| `GET /api/health` | Status + whether the AI layer is enabled |

### FinSight Assistant safety and cost controls

The floating Assistant uses the selected site language as its initial/default
language, then detects explicit language changes and natural code-switching in
each message. The website remains localized in English, Spanish, French, and
Simplified Chinese; the Assistant additionally accepts Japanese, Korean,
German, Portuguese, Italian, and Arabic. Site help and common financial
concepts are served from a cached multilingual knowledge base;
company lookups use the company-search service; and report questions can quote
only structured evidence supplied by the open report or an owned saved-report
ID. Every company-specific answer includes evidence metadata.

Recommendation, target-price, guaranteed-return, and prediction requests are
redirected to evidence-based comparison. The API applies message limits,
moderation, per-user and per-IP quotas, bounded context with a text-free topic
summary for older turns, and a final numeric guard on optional model output.
Usage logs contain user/intent/token counters and a one-way IP hash, not message
text. `FINSIGHT_ASSISTANT_MODEL` selects the lower-cost fallback model; without
an Anthropic key, deterministic features remain fully available.

The policy builder uses `FINSIGHT_AI_MODEL` only for schema extraction. Model
output cannot create or publish an `InvestmentPolicy`: extraction first stores a
separate `pending_review` proposal. The confirmation endpoint validates the
edited schema and conflicts again in deterministic code, requires
`confirmed: true`, and only then writes the first published policy version.

### Data provenance contract

API financial values use a shared `DataPoint` object, and sourced or generated
claims use a shared `Evidence` object. Both include `provider`, `source`,
`as_of_date`, `fetched_at`, `freshness_status`, `confidence`, and an optional
`source_url`. This contract applies consistently across overview, price history,
analysis, comparison, valuation, and news responses; the frontend unwraps the payloads
without changing the report's presentation.

Generated `Evidence` additionally carries independently auditable statements
and report-local citation paths. Sourced and deterministic evidence keeps these
fields empty; it is never forced to cite itself.

SEC results add official filing, reporting-period, acceptance, fetch, and cache
timestamps. Filing questions retrieve the most relevant extracted passages
first; the optional AI layer may explain those passages, but citation selection
is deterministic and every citation links back to the original SEC document.
For earnings-related 8-K filings, FinSight also reads matching EX-99 earnings
release exhibits from the same EDGAR filing package.
Without an Anthropic key, the endpoint returns an extractive answer with the
same citations instead of disabling filing questions.

### Research memory and change tracking

Customers with a browser-scoped profile can create multiple watchlist groups and
save the currently visible research brief as a persistent, schema-validated
snapshot. FinSight automatically selects the latest saved session for the same
ticker as the comparison baseline; callers may also select a specific baseline
session through the API.

The “What changed since last research?” report is deterministic. It compares:

- financial metrics, with a 1% noise tolerance and directional labels only where
  “improved” or “worsened” has a defensible financial meaning;
- newly observed news and SEC filings;
- new, resolved, strengthened, or weakened risk and opportunity signals; and
- thesis-assumption statuses already stored in the research workspace.

Price, valuation multiples, market capitalization, beta, dividend yield, and
analyst targets are labeled as changed rather than automatically better or worse.
The optional LLM is not used to calculate or classify any difference. The
current Thesis Ledger assumptions are injected into each saved snapshot, so a
later status or condition update appears in the next deterministic change report.

### Deterministic valuation and scenarios

The valuation lab starts from sourced revenue, free cash flow, cash, debt,
shares outstanding, current price, and—when available—trailing EPS. Backend code
projects revenue and free cash flow, discounts the explicit period, calculates a
Gordon-growth terminal value, bridges enterprise value to equity value, and
divides by code-projected diluted shares. Users can change projection years,
revenue growth, free-cash-flow margin, discount rate, terminal growth, and annual
share dilution.

The same engine also calculates conservative, base, and optimistic cases; a
discount-rate/terminal-growth sensitivity matrix; a reverse DCF solved by
bisection; and P/E or Price/Sales estimates from the automatically selected-peer
median. Every assumption and result carries provenance. The valuation routes do
not invoke the optional LLM, and valuation snapshots can be saved with the rest
of a research session.

### Evidence Auditor and conclusion blocking

The frontend submits every complete company brief and peer-comparison report to
the deterministic Evidence Auditor before displaying it. The auditor runs six checks:

- every generated factual statement has one or more report-local citations;
- every citation resolves to a provenance-bearing claim or data point;
- evidence explicitly marked stale is surfaced as a warning;
- same-date values for the same fact are compared across report sections and
  providers;
- known financial metrics use compatible currency, ratio, percentage, share,
  factor, or per-share units; and
- numbers in generated statements match the cited evidence.

AI summaries are requested as independently cited statements. The auditor does
not use another model to judge them: it resolves their citations and checks the
structured data directly. A statement with missing or invalid citations, bad
units, conflicting support, or an uncited number is removed from the sanitized
report. Supported statements may remain even when another statement in the same
AI response is blocked. The API returns the sanitized report plus a structured
audit result with issue counts, paths, severity, and blocked-statement count.

Saved research is re-audited on the server, so a browser cannot bypass the
control by submitting an unaudited or modified snapshot. Stale or conflicting
source warnings remain visible for human review; unsupported generated factual
conclusions never appear as report conclusions.

### Repeatable product evaluation

The versioned offline suite evaluates complete report variants without calling
market-data providers or using an LLM to grade another LLM. From `backend/`:

```bash
python -m app.evaluation evals/stock_research_reports.v1.json
python -m app.evaluation evals/stock_research_reports.v1.json \
  --output /tmp/finsight-evaluation.json
```

The command exits non-zero when any configured quality threshold fails. A prior
JSON result can be supplied with `--baseline`; a score drop greater than the
dataset's maximum regression allowance also fails the run. Results contain the
eight dimension scores, thresholds, individual observations, overall score,
and pass/fail status in machine-readable JSON. The fixture includes profile
variants plus English, Spanish, French, and Simplified Chinese narratives over
the same sourced facts. See [the evaluation methodology](backend/evals/README.md)
for scoring rules and instructions for adding cases.

### Thesis Ledger

Customers can record multiple company-specific research theses. Each thesis can
contain up to 20 assumptions, expressed either as a metric threshold (for
example, `revenue_growth >= 20%`) or as an observable event condition. Every
assumption has one of five explicit states: unreviewed, monitoring, supported,
challenged, or invalidated.

Supporting and contradicting evidence are stored separately with a source,
as-of date, optional URL, recorded timestamp, and user-selected confidence.
Creating an assumption and every later status, condition, description, or
evidence update writes an append-only history entry with the before/after values
and an optional reason. This is user-authored research memory; it does not
generate buy, sell, or suitability instructions.

### Benchmark methodology

The analysis endpoint no longer judges company fundamentals against universal
P/E, margin, growth, leverage, liquidity, beta, or dividend cutoffs. It asks
Yahoo Finance for companies in the same industry and sector, prioritizes the
same trading region, removes duplicate listings, and ranks candidates by market
capitalization proximity. The four closest same-industry companies become the
selected peers; a broader sector cohort adds up to five nearby companies from
other industries.

For every available metric, FinSight displays the cohort median and middle 50%
range. Annual Yahoo Finance income statements, balance sheets, and cash-flow
statements provide the company’s own reported range for revenue growth, margins,
leverage, liquidity, and free-cash-flow margin. The primary benchmark favors the
most specific cohort with enough observations: industry, selected peers, sector,
then company history. Missing providers or sparse samples are shown as explicit
limitations and never trigger a fallback to the old universal thresholds.

## How a research brief comes together

1. **Choose** a stock or a group of companies to research.
2. **Collect** relevant financial data and market news.
3. **Analyze** the company and compare it with peers.
4. **Review** potential risks, opportunities, and the evidence behind them.
5. **Decide** independently, using the research as support.

## Product principles

- **Evidence first** — conclusions are supported by relevant data and sources.
- **Explainable by default** — you can always see how an insight was reached.
- **Balanced analysis** — opportunities and risks are presented together.
- **User agency** — FinSight assists with research; you make the final decision.
- **Responsible communication** — never implies guaranteed returns.

## Roadmap

- [x] Define the MVP user journey and research report format
- [x] Select reliable financial-data and news sources (Yahoo Finance via yfinance)
- [x] Build stock search and company overview
- [x] Add financial and news analysis
- [x] Add company comparison
- [x] Add risk and opportunity reporting with source references
- [x] Add the SQLAlchemy and Alembic persistence foundation
- [x] Add customer onboarding and presentation-only research profiles
- [x] Add repeatable quality gates for generated research reports
- [x] Add SEC 10-K, 10-Q, and earnings-related 8-K sources
- [x] Replace universal metric cutoffs with industry, sector, peer, and historical benchmarks
- [ ] Add earnings-call transcript sources
- [ ] Exportable research briefs (PDF)
- [x] Add watchlists, saved research sessions, and deterministic change tracking
- [x] Add the Thesis Ledger with measurable assumptions, two-sided evidence, and change history
- [x] Add deterministic DCF, reverse DCF, peer multiples, scenarios, and sensitivity analysis
- [x] Add deterministic evidence auditing and block unsupported generated conclusions

## Contributing

The project is just getting started. Ideas, research, and implementation
suggestions are welcome through [GitHub issues](../../issues).

## Disclaimer

FinSight is an educational research tool and does not provide financial,
investment, legal, or tax advice. Its output may be incomplete or incorrect.
Always verify important information and consult a qualified professional when
appropriate.
