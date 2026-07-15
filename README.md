# FinSight

> See beyond the numbers.

FinSight is an AI-powered stock research agent that helps people make more
informed investment decisions. It brings financial data, market news, company
comparisons, and risk analysis into one research workflow, then explains the
evidence behind its conclusions.

FinSight is designed to support a user's judgment—not to tell them what to buy
or sell.

## Why FinSight?

Investment research is often scattered across financial statements, news
articles, market data, and company reports. FinSight aims to turn that fragmented
information into a clear, explainable view of a company so users can understand
both the opportunity and the uncertainty.

## Capabilities

- **Financial analysis** — organize important company data and surface meaningful trends.
- **Market news summaries** — condense relevant news and explain why it may matter.
- **Company comparisons** — compare businesses side by side using consistent criteria.
- **Risk and opportunity analysis** — identify possible strengths, catalysts, uncertainties, and warning signs.
- **Evidence-based explanations** — show the reasoning and supporting information behind each analysis.

## Getting started

The MVP is a FastAPI backend (market data via Yahoo Finance) plus a React/Vite
frontend. An optional Anthropic API key adds AI news summaries and analysis
narratives; without it, insights come from the transparent rules engine alone.

Backend (Python 3.10+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (Node 18+):

```bash
cd frontend
pnpm install
pnpm dev           # http://localhost:5173 (proxies /api to :8000)
```

Optional AI layer: `cp .env.example .env` and set `ANTHROPIC_API_KEY`.

Tests: `cd backend && pytest`

## Architecture

```
├── backend/            FastAPI + yfinance
│   ├── app/
│   │   ├── main.py             API routes
│   │   ├── config.py           env-based settings
│   │   ├── models/schemas.py   Pydantic response models
│   │   └── services/
│   │       ├── market_data.py  Yahoo Finance access + cache
│   │       ├── analysis.py     transparent risk/opportunity rules
│   │       └── ai.py           optional Anthropic layer
│   └── tests/          unit tests (no network needed)
└── frontend/           React + Vite single-page app
```

| Endpoint | Description |
|---|---|
| `GET /api/stocks/{ticker}` | Normalized fundamentals overview |
| `GET /api/stocks/{ticker}/history?period=6mo` | Daily closes (1mo–5y) |
| `GET /api/news/{ticker}` | Recent headlines + optional AI theme summary |
| `GET /api/analysis/{ticker}` | Evidence-backed risks & opportunities |
| `GET /api/compare?tickers=AAPL,MSFT` | Side-by-side comparison (2–5 tickers) |
| `GET /api/health` | Status + whether the AI layer is enabled |

Every insight the analysis engine produces cites its evidence: the metric, the
observed value, and the benchmark it was judged against. The AI layer narrates
those findings; it never generates conclusions of its own and never recommends
buying or selling.

## Intended workflow

1. Choose a stock or a group of companies to research.
2. Collect relevant financial data and market news.
3. Analyze the company and compare it with peers.
4. Review potential risks, opportunities, and the evidence behind them.
5. Use the research to make an independent decision.

## Product principles

- **Evidence first:** conclusions should be supported by relevant data and sources.
- **Explainable by default:** users should be able to understand how an insight was reached.
- **Balanced analysis:** opportunities and risks should be presented together.
- **User agency:** FinSight assists with research; the user makes the final decision.
- **Responsible communication:** the product should never imply guaranteed returns.

## Project status

The MVP is implemented: it can research a company, summarize its financial
picture and recent news, compare it with peers, and produce a transparent
risk-and-opportunity brief.

### Roadmap

- [x] Define the MVP user journey and research report format
- [x] Select reliable financial-data and news sources (Yahoo Finance via yfinance)
- [x] Build stock search and company overview
- [x] Add financial and news analysis
- [x] Add company comparison
- [x] Add risk and opportunity reporting with source references
- [ ] Test the quality, clarity, and consistency of generated research
- [ ] Add SEC filings and earnings-call sources
- [ ] Exportable research briefs (PDF)
- [ ] Watchlists and saved research sessions

## Contributing

The project is just getting started. Ideas, research, and implementation
suggestions are welcome through GitHub issues.

## Disclaimer

FinSight is an educational research tool and does not provide financial,
investment, legal, or tax advice. Its output may be incomplete or incorrect.
Always verify important information and consult a qualified professional when
appropriate.
