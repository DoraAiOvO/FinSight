"""Safety-first orchestration for the multilingual FinSight Assistant."""
from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from typing import Iterable

from sqlalchemy.orm import Session

from ..models.schemas import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantCitation,
    AssistantIntent,
    AssistantReportContext,
    AssistantReportEvidence,
    ExplanationDepth,
    ResearchSnapshot,
)
from . import ai, assistant_kb, company_search, research_workspace
from .assistant_controls import moderation_reason
from .assistant_language import LanguageDetection, detect_language
from .presentation import _explanation_depth


logger = logging.getLogger("finsight.assistant.usage")
MAX_CONTEXT_MESSAGES = 8

_SITE_HELP = re.compile(
    r"(?:how (?:do|can) i|how to|where (?:do|can) i|use (?:this|the) (?:site|website)|"
    r"cómo (?:uso|puedo)|comment (?:utiliser|puis-je)|如何使用|怎么用)",
    re.I,
)
_REPORT_REFERENCE = re.compile(
    r"(?:this|current|open|above|its?|these) (?:report|company|stock|number|metric)|"
    r"(?:este|esta|actual) (?:informe|empresa|número)|"
    r"(?:ce|cette|actuel) (?:rapport|entreprise|chiffre)|"
    r"(?:这份|当前|上面的?)(?:报告|公司|数据|指标)",
    re.I,
)
_RECOMMENDATION = re.compile(
    r"(?:should i (?:buy|sell|invest)|best stock|(?:which|what) stock|target price|price target|"
    r"price (?:next|in|by)|forecast .{0,20}price|will .{0,30} (?:rise|fall|go up|go down)|"
    r"guarantee(?:d)? .{0,20}(?:return|profit|gain|outcome|money)|(?:return|profit|gain).{0,15}guaranteed|"
    r"good investment|worth buying|recommend .{0,20}(?:stock|share|investment)|"
    r"debo (?:comprar|vender|invertir)|mejor acción|precio objetivo|predice|pronóstico|buena inversión|"
    r"devrais-je (?:acheter|vendre|investir)|meilleure action|objectif de cours|prédis|prévision|bon investissement|"
    r"应该买|应该卖|买哪|最好的股票|值得买|推荐.{0,8}股票|目标价|股价预测|保证收益)",
    re.I,
)
_COMPARISON = re.compile(
    r"(?:compare|comparison|versus|\bvs\.?\b|comparar|comparación|contre|comparer|比较|对比)",
    re.I,
)
_COMPANY_LOOKUP = re.compile(
    r"(?:find|lookup|what(?:'s| is)|which|give me|buscar|cuál es|trouver|quel est|查找|是什么).{0,45}"
    r"(?:ticker|symbol|símbolo|symbole|代码)",
    re.I,
)
_CONCEPT_QUESTION = re.compile(
    r"(?:what (?:does|is)|define|meaning|explain|qué (?:significa|es)|explica|"
    r"que signifie|qu'est-ce|explique|什么是|是什么意思|解释)",
    re.I,
)

_REPORT_LABEL_ALIASES = {
    "p/e": ("p/e", "pe", "price earnings", "precio beneficio", "cours bénéfice", "市盈率"),
    "revenue": ("revenue", "sales", "ingresos", "chiffre d'affaires", "营收", "收入"),
    "price": ("price", "share price", "precio", "cours", "股价"),
    "market cap": ("market cap", "capitalización", "capitalisation", "市值"),
    "free cash flow": ("free cash flow", "fcf", "flujo de caja", "flux de trésorerie", "自由现金流"),
    "profit margin": ("profit margin", "margen", "marge", "利润率"),
    "debt": ("debt", "leverage", "deuda", "dette", "债务", "负债"),
    "growth": ("growth", "crecimiento", "croissance", "增长"),
}


def route_intent(message: str, has_report: bool = False) -> AssistantIntent:
    """Route locally before any optional model call."""
    if _RECOMMENDATION.search(message):
        return AssistantIntent.RECOMMENDATION_OR_PREDICTION
    if _SITE_HELP.search(message):
        return AssistantIntent.SITE_HELP
    if _COMPANY_LOOKUP.search(message):
        return AssistantIntent.COMPANY_LOOKUP
    if _COMPARISON.search(message):
        return AssistantIntent.COMPARISON_REQUEST
    if _REPORT_REFERENCE.search(message):
        return AssistantIntent.CURRENT_REPORT_QUESTION
    if (
        has_report
        and _requested_report_label(message)
        and re.search(
            r"\b(?:current|its?|company['’]s|report['’]s)\b|"
            r"(?:当前|该公司|这家公司|此报告)",
            message,
            re.I,
        )
    ):
        return AssistantIntent.CURRENT_REPORT_QUESTION
    if assistant_kb.concept_key(message) or _CONCEPT_QUESTION.search(message):
        return AssistantIntent.FINANCIAL_CONCEPT
    if has_report and re.search(r"\b(?:it|its|those|these)\b|(?:它|这些)", message, re.I):
        return AssistantIntent.CURRENT_REPORT_QUESTION
    return AssistantIntent.GENERAL_EDUCATION


def _depth_for_profile(profile) -> ExplanationDepth:
    return _explanation_depth(profile)


def _localized(language: str, key: str, **values) -> str:
    messages = {
        "en": {
            "advice": "I can't choose a stock for you, give a buy/sell instruction, guarantee an outcome, or predict a future price. I can compare the companies using current, cited evidence—for example valuation, growth, cash flow, leverage, and key uncertainties. Those comparisons are descriptive, not a forecast.",
            "comparison": "I can help compare 2–5 companies using the same evidence-backed metrics. Tell me the company names or tickers and what dimension matters—such as growth, profitability, leverage, or valuation. The result will show uncertainty and will not rank a stock as the one you should buy.",
            "lookup": "{name}'s ticker is {ticker} on {exchange}. [1]",
            "lookup_missing": "I couldn't verify a ticker from that company name, so I won't guess. Try the full legal name and, if known, its exchange or country.",
            "report_missing": "I don't have sufficient evidence in the open FinSight report to answer that. I won't fill the gap with an estimated or invented number. Open or refresh the relevant report section and ask again.",
            "report_intro": "Based only on the open FinSight report for {company}:",
            "moderated": "I can't help with market manipulation, account theft, prompt extraction, or other abusive activity. I can help with lawful financial education and evidence-based company research.",
            "general": "I can help explain a financial concept, find a ticker, explain evidence in the open FinSight report, compare companies, or show you how to use the site. Ask one specific question and I'll keep the answer at your preferred explanation level.",
        },
        "es": {
            "advice": "No puedo elegir una acción por ti, dar una orden de compra o venta, garantizar un resultado ni predecir un precio futuro. Sí puedo comparar empresas con evidencia actual y citada—por ejemplo valoración, crecimiento, flujo de caja, deuda e incertidumbres. La comparación será descriptiva, no un pronóstico.",
            "comparison": "Puedo comparar entre 2 y 5 empresas con las mismas métricas respaldadas por evidencia. Dime nombres o tickers y el aspecto relevante, como crecimiento, rentabilidad, deuda o valoración. No clasificaré una acción como la que deberías comprar.",
            "lookup": "El ticker de {name} es {ticker} en {exchange}. [1]",
            "lookup_missing": "No pude verificar un ticker con ese nombre, así que no voy a adivinar. Prueba con la razón social completa y, si la conoces, la bolsa o el país.",
            "report_missing": "El informe abierto no contiene evidencia suficiente para responder. No completaré el dato con una cifra estimada o inventada. Abre o actualiza la sección relevante y vuelve a preguntar.",
            "report_intro": "Basándome solo en el informe FinSight abierto de {company}:",
            "moderated": "No puedo ayudar con manipulación de mercado, robo de cuentas, extracción de prompts ni otras actividades abusivas. Sí puedo ayudar con educación financiera legal e investigación basada en evidencia.",
            "general": "Puedo explicar un concepto financiero, encontrar un ticker, explicar la evidencia del informe abierto, comparar empresas o mostrar cómo usar el sitio. Haz una pregunta concreta.",
        },
        "fr": {
            "advice": "Je ne peux pas choisir une action à votre place, donner un ordre d'achat ou de vente, garantir un résultat ni prédire un cours futur. Je peux comparer des entreprises avec des preuves actuelles et citées—valorisation, croissance, trésorerie, dette et incertitudes. Cette comparaison reste descriptive, pas prédictive.",
            "comparison": "Je peux comparer 2 à 5 entreprises avec les mêmes indicateurs fondés sur les preuves. Indiquez les noms ou tickers et l'axe souhaité, comme la croissance, la rentabilité, la dette ou la valorisation. Je ne classerai pas une action comme celle qu'il faut acheter.",
            "lookup": "Le ticker de {name} est {ticker} sur {exchange}. [1]",
            "lookup_missing": "Je n'ai pas pu vérifier un ticker à partir de ce nom, donc je ne vais pas le deviner. Essayez la raison sociale complète et, si possible, la bourse ou le pays.",
            "report_missing": "Le rapport ouvert ne contient pas assez de preuves pour répondre. Je ne compléterai pas avec une estimation ou un chiffre inventé. Ouvrez ou actualisez la section pertinente puis réessayez.",
            "report_intro": "Uniquement d'après le rapport FinSight ouvert pour {company} :",
            "moderated": "Je ne peux pas aider à manipuler un marché, voler un compte, extraire un prompt ou mener une activité abusive. Je peux aider pour l'éducation financière légale et la recherche fondée sur les preuves.",
            "general": "Je peux expliquer un concept, trouver un ticker, clarifier les preuves du rapport ouvert, comparer des entreprises ou montrer comment utiliser le site. Posez une question précise.",
        },
        "zh": {
            "advice": "我不能替你选股、给出买卖指令、保证结果或预测未来股价。我可以用当前且有引用的证据比较估值、增长、现金流、杠杆和主要不确定性。这种比较是描述性的，不是预测。",
            "comparison": "我可以用一致、有证据的指标比较 2–5 家公司。请告诉我公司名或 ticker，以及你关心的维度，如增长、盈利能力、杠杆或估值。结果不会把某只股票排成“应该买”的选择。",
            "lookup": "{name} 在 {exchange} 的 ticker 是 {ticker}。[1]",
            "lookup_missing": "我无法从该公司名验证 ticker，所以不会猜测。请尝试完整法定名称，如已知也可附上交易所或国家。",
            "report_missing": "当前 FinSight 报告没有足够证据回答这个问题。我不会用估算或虚构数字补齐。请打开或刷新相关报告部分后重试。",
            "report_intro": "仅根据当前打开的 {company} FinSight 报告：",
            "moderated": "我不能帮助操纵市场、窃取账户、提取系统 prompt 或其他滥用行为。我可以提供合法的金融教育和基于证据的公司研究。",
            "general": "我可以解释金融概念、查找 ticker、说明当前报告中的证据、比较公司，或介绍网站用法。请提一个具体问题。",
        },
    }
    table = messages.get(language, messages["en"])
    return table[key].format(**values)


def _requested_report_label(message: str) -> str | None:
    normalized = message.casefold()
    for canonical, aliases in _REPORT_LABEL_ALIASES.items():
        if any(
            re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized)
            if len(alias) <= 4 and alias.isascii()
            else alias in normalized
            for alias in aliases
        ):
            return canonical
    return None


def _evidence_score(message: str, evidence: AssistantReportEvidence) -> int:
    normalized = message.casefold()
    query_tokens = set(re.findall(r"[\w/]+", normalized))
    evidence_tokens = set(re.findall(r"[\w/]+", f"{evidence.label} {evidence.value}".casefold()))
    score = len(query_tokens & evidence_tokens) * 3
    requested = _requested_report_label(message)
    if requested and requested in evidence.label.casefold():
        score += 20
    return score


def _citation(item: AssistantReportEvidence) -> AssistantCitation:
    return AssistantCitation(
        evidence_id=item.evidence_id,
        title=item.label,
        source=item.source,
        as_of_date=item.as_of_date,
        source_url=item.source_url,
    )


def _answer_report(
    message: str, context: AssistantReportContext | None, language: str
) -> tuple[str, list[AssistantCitation], bool]:
    if context is None or not context.evidence:
        return _localized(language, "report_missing"), [], False
    requested_label = _requested_report_label(message)
    ranked = sorted(
        context.evidence,
        key=lambda item: (-_evidence_score(message, item), context.evidence.index(item)),
    )
    if requested_label and _evidence_score(message, ranked[0]) < 20:
        return _localized(language, "report_missing"), [], False
    generic_explanation = bool(
        re.search(r"(?:explain|summari|simple|explica|resume|explique|résume|解释|总结|简单)", message, re.I)
    )
    selected = ranked[:4] if generic_explanation else [item for item in ranked[:3] if _evidence_score(message, item) > 0]
    if not selected:
        return _localized(language, "report_missing"), [], False
    company = context.company_name or context.ticker
    lines = [_localized(language, "report_intro", company=company)]
    citations = []
    for index, item in enumerate(selected, start=1):
        lines.append(f"- {item.label}: {item.value} [{index}]")
        citations.append(_citation(item))
    return "\n".join(lines), citations, True


def report_context_from_snapshot(snapshot: ResearchSnapshot, report_id=None) -> AssistantReportContext:
    """Reduce a saved report to its exact, sourced display evidence."""
    overview = snapshot.overview
    evidence: list[AssistantReportEvidence] = []
    labels = {
        "price": "Share price",
        "market_cap": "Market cap",
        "trailing_pe": "Trailing P/E",
        "forward_pe": "Forward P/E",
        "price_to_sales": "Price / Sales",
        "revenue_growth": "Revenue growth",
        "profit_margin": "Profit margin",
        "free_cash_flow": "Free cash flow",
        "debt_to_equity": "Debt / Equity",
        "beta": "Beta",
        "dividend_yield": "Dividend yield",
    }
    for key, label in labels.items():
        point = getattr(overview, key, None)
        if point is None or point.value is None:
            continue
        value = point.display_value or str(point.value)
        evidence.append(
            AssistantReportEvidence(
                evidence_id=f"overview.{key}",
                label=label,
                value=value,
                source=f"{point.provider} · {point.source}",
                as_of_date=point.as_of_date,
                source_url=point.source_url,
            )
        )
    if snapshot.analysis:
        for index, insight in enumerate(snapshot.analysis.insights[:8]):
            evidence.append(
                AssistantReportEvidence(
                    evidence_id=f"analysis.insights.{index}",
                    label=insight.title.claim,
                    value=insight.explanation.claim,
                    source=f"{insight.explanation.provider} · {insight.explanation.source}",
                    as_of_date=insight.explanation.as_of_date,
                    source_url=insight.explanation.source_url,
                )
            )
    return AssistantReportContext(
        ticker=overview.ticker,
        company_name=overview.name,
        report_id=report_id,
        evidence=evidence,
    )


def load_saved_report_context(
    db: Session, customer_id, report_id
) -> AssistantReportContext:
    research = research_workspace.get_research_session(db, customer_id, report_id)
    response = research_workspace.serialize_research_session(research)
    return report_context_from_snapshot(response.snapshot, report_id=report_id)


def _trim_history(history: Iterable) -> tuple[list[dict[str, str]], bool]:
    history = list(history)
    if len(history) <= MAX_CONTEXT_MESSAGES:
        return [item.model_dump(mode="json") for item in history], False
    recent = history[-(MAX_CONTEXT_MESSAGES - 1):]
    older = history[:-(MAX_CONTEXT_MESSAGES - 1)]
    topic_counts = Counter(
        route_intent(item.content).value
        for item in older
        if item.role.value == "user"
    )
    language_counts = Counter(
        detect_language(item.content).primary
        for item in older
        if item.role.value == "user"
    )
    topics = ", ".join(
        f"{topic} ({count})" for topic, count in topic_counts.most_common(4)
    ) or "no user topics"
    languages = ", ".join(language_counts) or "unknown"
    summary = {
        "role": "assistant",
        "content": (
            f"Earlier conversation summary: {len(older)} messages; "
            f"topics: {topics}; languages: {languages}. "
            "No company facts or numbers were retained in this summary."
        ),
    }
    return [summary, *[item.model_dump(mode="json") for item in recent]], True


def _log_usage(
    *, customer_id, ip_address: str, intent: AssistantIntent, used_llm: bool,
    input_tokens: int = 0, output_tokens: int = 0,
):
    ip_hash = hashlib.sha256(ip_address.encode("utf-8")).hexdigest()[:12]
    logger.info(
        "assistant_usage user=%s ip_hash=%s intent=%s used_llm=%s input_tokens=%d output_tokens=%d",
        str(customer_id) if customer_id else "anonymous",
        ip_hash,
        intent.value,
        used_llm,
        input_tokens,
        output_tokens,
    )


def answer_chat(
    request: AssistantChatRequest,
    *,
    profile=None,
    report_context: AssistantReportContext | None = None,
    ip_address: str = "unknown",
) -> AssistantChatResponse:
    detection: LanguageDetection = detect_language(
        request.message, fallback=request.website_language.value
    )
    language = detection.primary
    depth = _depth_for_profile(profile)
    report_context = report_context or request.current_report
    intent = route_intent(request.message, has_report=report_context is not None)
    citations: list[AssistantCitation] = []
    used_llm = False
    grounded = False
    context, context_truncated = _trim_history(request.history)
    input_tokens = output_tokens = 0

    if moderation_reason(request.message):
        reply = _localized(language, "moderated")
    elif intent == AssistantIntent.RECOMMENDATION_OR_PREDICTION:
        reply = _localized(language, "advice")
    elif intent == AssistantIntent.SITE_HELP:
        reply = assistant_kb.site_help_response(
            assistant_kb.site_topic(request.message), language
        )
    elif intent == AssistantIntent.FINANCIAL_CONCEPT:
        concept = assistant_kb.concept_key(request.message)
        reply = assistant_kb.concept_response(concept, language, depth.value) if concept else None
        if reply is None:
            reply = _localized(language, "general")
    elif intent == AssistantIntent.COMPANY_LOOKUP:
        results = company_search.search_companies(request.message, limit=1)
        if not results:
            reply = _localized(language, "lookup_missing")
        else:
            company = results[0]
            reply = _localized(
                language, "lookup", name=company.name,
                ticker=company.ticker, exchange=company.exchange,
            )
            citations = [
                AssistantCitation(
                    evidence_id=f"company_directory.{company.ticker}",
                    title=f"{company.name} ({company.ticker})",
                    source="FinSight company-search directory",
                    source_url="https://www.nasdaq.com/market-activity/stocks/screener",
                )
            ]
            grounded = True
    elif intent == AssistantIntent.CURRENT_REPORT_QUESTION:
        reply, citations, grounded = _answer_report(
            request.message, report_context, language
        )
    elif intent == AssistantIntent.COMPARISON_REQUEST:
        if report_context and _REPORT_REFERENCE.search(request.message):
            reply, citations, grounded = _answer_report(
                request.message, report_context, language
            )
        else:
            reply = _localized(language, "comparison")
    else:
        ticker_candidates = set(re.findall(r"\b[A-Z]{2,5}(?:\.[A-Z])?\b", request.message))
        ticker_candidates -= {"SEC", "EPS", "FCF", "ETF", "IPO", "DCF", "GAAP", "EBIT", "P", "E"}
        possessives = re.findall(r"\b([A-Z][A-Za-z&.-]+)['’]s\b", request.message)
        named_possessive = any(
            value.casefold() not in {"what", "who", "where", "how", "it", "that", "there"}
            for value in possessives
        )
        named_company = named_possessive or bool(re.search(
            r"\b[A-Z][A-Za-z&.-]+(?:\s+[A-Z][A-Za-z&.-]+){0,3}\s+"
            r"(?:Corp(?:oration)?|Inc|PLC|Ltd|Company)\b",
            request.message,
        ))
        company_specific = (
            bool(company_search.search_companies(request.message, limit=1))
            or bool(ticker_candidates)
            or named_company
        )
        generation = None if company_specific else ai.answer_assistant_question(
            request.message, history=context, lang=language,
            detected_languages=list(detection.languages), explanation_depth=depth.value,
        )
        if generation:
            candidate = generation["text"]
            # A final deterministic guard prevents uncited model output from
            # introducing a financial figure despite the system instruction.
            if re.search(r"(?:[$€£]\s*\d|\d+(?:\.\d+)?\s*(?:%|x\b))", candidate, re.I):
                reply = _localized(language, "general")
            else:
                reply = candidate
                input_tokens = generation["input_tokens"]
                output_tokens = generation["output_tokens"]
                used_llm = True
        elif company_specific:
            reply = _localized(language, "report_missing")
        else:
            reply = _localized(language, "general")

    if detection.code_switched and not used_llm:
        reply = assistant_kb.preserve_mix(reply, language, detection.languages)

    _log_usage(
        customer_id=request.customer_id,
        ip_address=ip_address,
        intent=intent,
        used_llm=used_llm,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    return AssistantChatResponse(
        reply=reply,
        intent=intent,
        detected_language="mixed" if detection.code_switched else language,
        detected_languages=list(detection.languages),
        code_switched=detection.code_switched,
        explanation_depth=depth,
        citations=citations,
        used_llm=used_llm,
        grounded=grounded,
        context_truncated=context_truncated,
    )
