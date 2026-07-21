"""Benchmark-aware company context built from transparent Yahoo Finance samples."""

import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import median

import yfinance as yf

from . import market_data
from .provenance import data_point, data_value, evidence, inherited_provenance


METRICS = (
    ("trailing_pe", "Trailing P/E"),
    ("forward_pe", "Forward P/E"),
    ("price_to_sales", "Price / Sales"),
    ("revenue_growth", "Revenue growth (YoY)"),
    ("profit_margin", "Net profit margin"),
    ("operating_margin", "Operating margin"),
    ("debt_to_equity", "Debt / Equity"),
    ("current_ratio", "Current ratio"),
    ("free_cash_flow_margin", "Free cash flow margin"),
    ("beta", "Beta (5y)"),
    ("dividend_yield", "Dividend yield"),
)

POSITIVE_ONLY_METRICS = {"trailing_pe", "forward_pe", "price_to_sales"}
INDUSTRY_PEER_LIMIT = 4
SECTOR_EXTRA_LIMIT = 5
INDUSTRY_CANDIDATE_LIMIT = 6
SECTOR_CANDIDATE_LIMIT = 8
SCREEN_LIMIT = 100
PRIMARY_MIN_SAMPLE = 3


def _label_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _company_key(value: str | None) -> str:
    key = _label_key(value)
    for suffix in (
        "corporation",
        "company",
        "holdings",
        "holding",
        "limited",
        "incorporated",
        "corp",
        "inc",
        "ltd",
        "plc",
    ):
        if key.endswith(suffix):
            key = key[: -len(suffix)]
    return key


def _query_values() -> dict:
    return yf.EquityQuery("eq", ["region", "us"]).valid_values


def normalize_screener_label(scope: str, value: str | None) -> str | None:
    """Map Ticker.info labels (often hyphenated) to Yahoo screener labels."""
    if not value or scope not in {"industry", "sector"}:
        return None
    valid = _query_values().get(scope)
    if scope == "industry" and isinstance(valid, dict):
        candidates = [item for group in valid.values() for item in group]
    else:
        candidates = list(valid or [])
    target = _label_key(value)
    return next((candidate for candidate in candidates if _label_key(candidate) == target), None)


def exchange_region(exchange: str | None) -> str | None:
    if not exchange:
        return None
    exchange = exchange.upper()
    mapping = _query_values().get("exchange") or {}
    return next(
        (region for region, exchanges in mapping.items() if exchange in exchanges),
        None,
    )


def _finite_number(value, *, metric_key: str | None = None) -> float | None:
    value = data_value(value)
    if not isinstance(value, (int, float)):
        return None
    value = float(value)
    if not math.isfinite(value):
        return None
    if metric_key in POSITIVE_ONLY_METRICS and value <= 0:
        return None
    return value


def _market_cap(value) -> float | None:
    return _finite_number(value)


def _rank_candidates(quotes: list[dict], overview: dict, raw_info: dict) -> list[str]:
    company_cap = _market_cap(overview.get("market_cap"))
    company_name = _company_key(overview.get("name"))
    ticker = overview["ticker"].upper()
    exchange = str(raw_info.get("exchange") or "").upper()
    ranked = []
    seen = set()
    for quote in quotes:
        symbol = str(quote.get("symbol") or "").upper()
        if not symbol or symbol == ticker or symbol in seen:
            continue
        if quote.get("quoteType") not in {None, "EQUITY"}:
            continue
        candidate_name = _company_key(quote.get("shortName") or quote.get("longName"))
        if company_name and candidate_name and company_name == candidate_name:
            continue
        cap = _market_cap(quote.get("marketCap"))
        if company_cap and cap:
            distance = abs(math.log(cap / company_cap))
        elif cap:
            distance = 2.0
        else:
            distance = 5.0
        candidate_exchange = str(quote.get("exchange") or "").upper()
        exchange_penalty = 0 if candidate_exchange == exchange else 0.15
        if candidate_exchange in {"PNK", "OQX", "OQB", "OEM"} and exchange not in {
            "PNK",
            "OQX",
            "OQB",
            "OEM",
        }:
            exchange_penalty += 0.8
        ranked.append((distance + exchange_penalty, -1 * (cap or 0), symbol))
        seen.add(symbol)
    ranked.sort()
    return [symbol for _, _, symbol in ranked]


def _fetch_overviews(symbols: list[str]) -> dict[str, dict]:
    if not symbols:
        return {}
    results = {}
    with ThreadPoolExecutor(max_workers=min(5, len(symbols))) as executor:
        futures = {
            executor.submit(market_data.get_overview, symbol): symbol for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                results[symbol] = future.result()
            except Exception:
                continue
    return results


def _deduplicate_companies(
    overviews: list[dict], *, excluded: list[dict] | None = None
) -> list[dict]:
    """Keep one listing per company after detailed names become available."""
    seen = {
        _company_key(overview.get("name")) or overview["ticker"].upper()
        for overview in (excluded or [])
    }
    unique = []
    for overview in overviews:
        key = _company_key(overview.get("name")) or overview["ticker"].upper()
        if key in seen:
            continue
        seen.add(key)
        unique.append(overview)
    return unique


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered[lower_index]
    weight = position - lower_index
    return ordered[lower_index] * (1 - weight) + ordered[upper_index] * weight


def _display(metric_key: str, value: float) -> str:
    if metric_key in {
        "revenue_growth",
        "profit_margin",
        "operating_margin",
        "free_cash_flow_margin",
        "dividend_yield",
    }:
        return f"{value * 100:.1f}%"
    if metric_key == "debt_to_equity":
        return f"{value:.0f}%"
    return f"{value:.2f}"


def _derived_point(metric_key: str, value: float, inputs: list[dict], source: str) -> dict:
    return data_point(
        value,
        display_value=_display(metric_key, value),
        **inherited_provenance(inputs, source=source, confidence=0.8),
    )


def _reference(
    *,
    scope: str,
    name: str,
    metric_key: str,
    points_by_ticker: list[tuple[str, dict]],
    range_kind: str = "middle_50_percent",
    period: str | None = None,
) -> dict | None:
    usable = [
        (ticker, point, _finite_number(point, metric_key=metric_key))
        for ticker, point in points_by_ticker
    ]
    usable = [(ticker, point, value) for ticker, point, value in usable if value is not None]
    if len(usable) < 2:
        return None
    values = [value for _, _, value in usable]
    points = [point for _, point, _ in usable]
    if range_kind == "observed_range":
        lower, upper = min(values), max(values)
    else:
        lower, upper = _percentile(values, 0.25), _percentile(values, 0.75)
    middle = median(values)
    tickers = [ticker for ticker, _, _ in usable if ticker]
    sample_size = len(usable)
    rationale_key = {
        "industry": "benchmarkIndustryReason",
        "sector": "benchmarkSectorReason",
        "peers": "benchmarkPeersReason",
        "historical": "benchmarkHistoricalReason",
    }[scope]
    rationale_params = {
        "name": name,
        "sampleSize": str(sample_size),
        "period": period or "",
    }
    claims = {
        "industry": (
            f"Uses the median of {sample_size} companies classified in {name}; "
            "industry economics are the closest operating comparison."
        ),
        "sector": (
            f"Uses the median of {sample_size} {name} companies to provide a broader "
            "reference when individual industries differ."
        ),
        "peers": (
            f"Uses {sample_size} automatically selected peers that prioritize the same "
            "industry and similar market capitalization."
        ),
        "historical": (
            f"Uses {sample_size} annual company observations from {period} so the current "
            "value is compared with the company's own reported range."
        ),
    }
    return {
        "scope": scope,
        "name": name,
        "median": _derived_point(
            metric_key, middle, points, f"{scope} benchmark median: {metric_key}"
        ),
        "lower_bound": _derived_point(
            metric_key, lower, points, f"{scope} benchmark lower bound: {metric_key}"
        ),
        "upper_bound": _derived_point(
            metric_key, upper, points, f"{scope} benchmark upper bound: {metric_key}"
        ),
        "range_kind": range_kind,
        "sample_size": sample_size,
        "sample_tickers": tickers,
        "period": period,
        "rationale": evidence(
            claims[scope],
            **inherited_provenance(
                points,
                source=f"benchmark selection rationale: {scope}",
                confidence=0.75,
            ),
        ),
        "rationale_key": rationale_key,
        "rationale_params": rationale_params,
    }


def _cohort_points(overviews: list[dict], metric_key: str) -> list[tuple[str, dict]]:
    return [
        (overview["ticker"], overview[metric_key])
        for overview in overviews
        if isinstance(overview.get(metric_key), dict)
    ]


def _historical_points(observations: list[dict], metric_key: str) -> list[tuple[str, dict]]:
    return [
        (str(observation["period_end"].year), observation["metrics"][metric_key])
        for observation in observations
        if isinstance(observation.get("metrics", {}).get(metric_key), dict)
    ]


def _same_label(left: str | None, right: str | None) -> bool:
    return bool(left and right and _label_key(left) == _label_key(right))


def _peer_payload(peer: dict, overview: dict, company_cap: dict | None) -> dict:
    same_industry = _same_label(peer.get("industry"), overview.get("industry"))
    reason_key = "peerSameIndustryReason" if same_industry else "peerSectorFallbackReason"
    reason_params = {
        "industry": peer.get("industry") or overview.get("industry") or "—",
        "sector": peer.get("sector") or overview.get("sector") or "—",
    }
    inputs = [point for point in (company_cap, peer.get("market_cap")) if isinstance(point, dict)]
    if same_industry:
        claim = (
            f"Selected because it shares the {peer.get('industry')} industry and is among "
            "the closest available companies by market capitalization."
        )
    else:
        claim = (
            f"Selected as a {peer.get('sector')} sector fallback because too few same-industry "
            "companies were available, with market-cap proximity used next."
        )
    return {
        "ticker": peer["ticker"],
        "name": peer.get("name"),
        "sector": peer.get("sector"),
        "industry": peer.get("industry"),
        "market_cap": peer.get("market_cap"),
        "selection_reason": evidence(
            claim,
            **inherited_provenance(
                inputs,
                source="automatic peer selection: classification and market cap",
                confidence=0.75,
            ),
        ),
        "selection_reason_key": reason_key,
        "selection_reason_params": reason_params,
    }


def _limitation(claim: str, inputs: list[dict]) -> dict:
    return evidence(
        claim,
        **inherited_provenance(
            inputs,
            source="benchmark coverage limitation",
            confidence=0.9,
        ),
    )


def build_benchmark_context(ticker: str, overview: dict) -> dict:
    """Compare a company with industry, sector, selected peers, and itself."""
    raw_info = {"exchange": overview.get("exchange")}
    region = exchange_region(raw_info.get("exchange"))
    industry_label = normalize_screener_label("industry", overview.get("industry"))
    sector_label = normalize_screener_label("sector", overview.get("sector"))
    limitations = []
    base_inputs = [
        point
        for point in (overview.get("market_cap"), overview.get("price"))
        if isinstance(point, dict)
    ]

    industry_symbols = []
    if industry_label:
        try:
            industry_quotes = market_data.get_benchmark_candidates(
                "industry", industry_label, region=region, limit=SCREEN_LIMIT
            )
            industry_symbols = _rank_candidates(industry_quotes, overview, raw_info)[
                :INDUSTRY_CANDIDATE_LIMIT
            ]
        except Exception:
            limitations.append(
                _limitation("The industry cohort is temporarily unavailable.", base_inputs)
            )
    else:
        limitations.append(
            _limitation("Yahoo Finance did not provide a recognized industry classification.", base_inputs)
        )

    sector_symbols = []
    if sector_label:
        try:
            sector_quotes = market_data.get_benchmark_candidates(
                "sector", sector_label, region=region, limit=SCREEN_LIMIT
            )
            sector_ranked = _rank_candidates(sector_quotes, overview, raw_info)
            sector_symbols = [
                symbol for symbol in sector_ranked if symbol not in set(industry_symbols)
            ][:SECTOR_CANDIDATE_LIMIT]
        except Exception:
            limitations.append(
                _limitation("The sector cohort is temporarily unavailable.", base_inputs)
            )
    else:
        limitations.append(
            _limitation("Yahoo Finance did not provide a recognized sector classification.", base_inputs)
        )

    requested_symbols = list(dict.fromkeys([*industry_symbols, *sector_symbols]))
    peer_map = _fetch_overviews(requested_symbols)
    industry_cohort = _deduplicate_companies(
        [
            peer_map[symbol]
            for symbol in industry_symbols
            if symbol in peer_map
            and _same_label(peer_map[symbol].get("industry"), overview.get("industry"))
        ]
    )[:INDUSTRY_PEER_LIMIT]
    sector_extras = _deduplicate_companies(
        [
            peer_map[symbol]
            for symbol in sector_symbols
            if symbol in peer_map
            and _same_label(peer_map[symbol].get("sector"), overview.get("sector"))
        ],
        excluded=industry_cohort,
    )[:SECTOR_EXTRA_LIMIT]
    sector_cohort = [*industry_cohort, *sector_extras]
    selected_peer_overviews = [*industry_cohort]
    for peer in sector_extras:
        if len(selected_peer_overviews) >= INDUSTRY_PEER_LIMIT:
            break
        selected_peer_overviews.append(peer)

    try:
        history = market_data.get_historical_financial_metrics(ticker)
    except Exception:
        history = []
        limitations.append(
            _limitation("The company's annual historical range is temporarily unavailable.", base_inputs)
        )

    if not selected_peer_overviews:
        limitations.append(
            _limitation("No sufficiently comparable peer listings were available.", base_inputs)
        )

    history_years = [observation["period_end"].year for observation in history]
    history_period = (
        f"{min(history_years)}–{max(history_years)}" if history_years else None
    )
    metric_benchmarks = []
    all_reference_points = []
    for metric_key, label in METRICS:
        company_point = overview.get(metric_key)
        if not isinstance(company_point, dict) or _finite_number(
            company_point, metric_key=metric_key
        ) is None:
            continue
        references = []
        reference_specs = (
            (
                "industry",
                overview.get("industry") or industry_label or "Industry",
                _cohort_points(industry_cohort, metric_key),
                "middle_50_percent",
                None,
            ),
            (
                "sector",
                overview.get("sector") or sector_label or "Sector",
                _cohort_points(sector_cohort, metric_key),
                "middle_50_percent",
                None,
            ),
            (
                "peers",
                "Selected peers",
                _cohort_points(selected_peer_overviews, metric_key),
                "middle_50_percent",
                None,
            ),
            (
                "historical",
                f"{ticker.upper()} history",
                _historical_points(history, metric_key),
                "observed_range",
                history_period,
            ),
        )
        for scope, name, points, range_kind, period in reference_specs:
            reference = _reference(
                scope=scope,
                name=name,
                metric_key=metric_key,
                points_by_ticker=points,
                range_kind=range_kind,
                period=period,
            )
            if reference:
                references.append(reference)
                all_reference_points.append(reference["median"])
        primary = next(
            (
                reference
                for scope in ("industry", "peers", "sector", "historical")
                for reference in references
                if reference["scope"] == scope
                and reference["sample_size"] >= PRIMARY_MIN_SAMPLE
            ),
            None,
        )
        if primary is None and references:
            primary = references[0]
        metric_benchmarks.append(
            {
                "metric_key": metric_key,
                "label": label,
                "company_value": company_point,
                "references": references,
                "primary_scope": primary["scope"] if primary else None,
                "primary_rationale": primary["rationale"] if primary else None,
            }
        )

    if not any(
        reference["scope"] == "historical"
        for metric in metric_benchmarks
        for reference in metric["references"]
    ) and history:
        limitations.append(
            _limitation("Historical statements did not contain enough comparable annual observations.", base_inputs)
        )

    methodology_inputs = [*base_inputs, *all_reference_points]
    methodology = evidence(
        "Benchmarks use Yahoo Finance classifications and a transparent sample: same-industry "
        "companies first, then same-sector companies, ranked by market-cap proximity. Industry, "
        "sector, and peer ranges show the middle 50%; company history shows the observed annual range.",
        **inherited_provenance(
            methodology_inputs,
            source="FinSight benchmark methodology v1",
            confidence=0.75,
        ),
    )
    limitations.append(
        _limitation(
            "The benchmark cohort is a selected Yahoo Finance sample, not every company in the market; classifications and reported metrics may be incomplete.",
            methodology_inputs,
        )
    )
    return {
        "industry": overview.get("industry"),
        "sector": overview.get("sector"),
        "selected_peers": [
            _peer_payload(peer, overview, overview.get("market_cap"))
            for peer in selected_peer_overviews
        ],
        "metrics": metric_benchmarks,
        "methodology": methodology,
        "limitations": limitations,
    }
