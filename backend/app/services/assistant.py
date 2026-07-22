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
    r"cómo (?:uso|puedo)|comment (?:utiliser|puis-je)|wie (?:nutze|benutze|kann ich)|"
    r"como (?:uso|posso)|come (?:uso|posso)|使い方|どう使|사용 방법|어떻게 사용|"
    r"كيف أستخدم|كيفية استخدام|如何使用|怎么用)",
    re.I,
)
_REPORT_REFERENCE = re.compile(
    r"(?:this|current|open|above|its?|these) (?:report|company|stock|number|metric)|"
    r"(?:este|esta|actual) (?:informe|empresa|número)|"
    r"(?:ce|cette|actuel) (?:rapport|entreprise|chiffre)|"
    r"(?:dieser|diese|aktueller|aktuelle) (?:bericht|unternehmen|zahl)|"
    r"(?:este|esta|atual) (?:relatório|empresa|número)|"
    r"(?:questo|questa|attuale) (?:rapporto|azienda|numero)|"
    r"(?:この|現在の)(?:レポート|会社|数値)|(?:이|현재)(?: 보고서| 회사| 수치)|"
    r"(?:هذا|هذه|الحالي) (?:التقرير|الشركة|الرقم)|"
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
    r"soll ich (?:kaufen|verkaufen|investieren)|beste aktie|kursziel|kursprognose|"
    r"devo (?:comprar|vender|investir)|melhor ação|preço-alvo|previsão de preço|"
    r"dovrei (?:comprare|vendere|investire)|migliore azione|prezzo obiettivo|previsione del prezzo|"
    r"買うべき|売るべき|おすすめ.{0,8}(?:株|銘柄)|目標株価|株価予測|"
    r"사야|팔아야|추천.{0,8}(?:주식|종목)|목표주가|주가 예측|"
    r"هل أشتري|هل أبيع|أفضل سهم|سعر مستهدف|توقع سعر|"
    r"应该买|应该卖|买哪|最好的股票|值得买|推荐.{0,8}股票|目标价|股价预测|保证收益)",
    re.I,
)
_COMPARISON = re.compile(
    r"(?:compare|comparison|versus|\bvs\.?\b|comparar|comparación|contre|comparer|"
    r"vergleichen|vergleich|confrontare|confronto|comparação|比較|비교|مقارنة|قارن|比较|对比)",
    re.I,
)
_COMPANY_LOOKUP = re.compile(
    r"(?:find|lookup|what(?:'s| is)|which|give me|buscar|cuál es|trouver|quel est|"
    r"finden|wie lautet|qual é|encontre|trova|qual è|探す|何ですか|찾아|무엇|ابحث|ما هو|查找|是什么).{0,55}"
    r"(?:ticker|stock symbol|symbol|símbolo|symbole|aktiensymbol|símbolo de ação|"
    r"simbolo azionario|銘柄コード|종목 코드|رمز السهم|رمز سهم|代码|股票代码)",
    re.I,
)
_CONCEPT_QUESTION = re.compile(
    r"(?:what (?:does|is)|define|meaning|explain|qué (?:significa|es)|explica|"
    r"que signifie|qu'est-ce|explique|was bedeutet|was ist|erkläre|o que significa|"
    r"explique|che cosa significa|cos'è|spiega|とは|何ですか|무엇|뜻|설명|"
    r"ما معنى|ما هو|اشرح|什么是|是什么意思|解释)",
    re.I,
)

_REPORT_LABEL_ALIASES = {
    "p/e": ("p/e", "pe", "price earnings", "precio beneficio", "cours bénéfice", "kgv", "p/l", "株価収益率", "주가수익비율", "مكرر الربحية", "市盈率"),
    "revenue": ("revenue", "sales", "ingresos", "chiffre d'affaires", "umsatz", "receita", "ricavi", "売上", "매출", "الإيرادات", "营收", "收入"),
    "price": ("price", "share price", "precio", "cours", "kurs", "preço", "prezzo", "株価", "주가", "سعر السهم", "股价"),
    "market cap": ("market cap", "capitalización", "capitalisation", "marktkapitalisierung", "capitalização", "capitalizzazione", "時価総額", "시가총액", "القيمة السوقية", "市值"),
    "free cash flow": ("free cash flow", "fcf", "flujo de caja", "flux de trésorerie", "freier cashflow", "fluxo de caixa", "flusso di cassa", "フリーキャッシュフロー", "잉여현금흐름", "التدفق النقدي الحر", "自由现金流"),
    "profit margin": ("profit margin", "margen", "marge", "gewinnmarge", "margem", "margine", "利益率", "이익률", "هامش الربح", "利润率"),
    "debt": ("debt", "leverage", "deuda", "dette", "schulden", "dívida", "debito", "負債", "부채", "الدين", "债务", "负债"),
    "growth": ("growth", "crecimiento", "croissance", "wachstum", "crescimento", "crescita", "成長", "성장", "نمو", "增长"),
}
_REPORT_EVIDENCE_KEYS = {
    "p/e": ("trailing_pe", "forward_pe"),
    "revenue": ("revenue", "revenue_growth"),
    "price": ("price",),
    "market cap": ("market_cap",),
    "free cash flow": ("free_cash_flow",),
    "profit margin": ("profit_margin",),
    "debt": ("debt", "debt_to_equity"),
    "growth": ("growth",),
}
_REPORT_METRIC_LABELS = {
    "en": {"price": "Share price", "market_cap": "Market cap", "trailing_pe": "Trailing P/E", "forward_pe": "Forward P/E", "price_to_sales": "Price / Sales", "revenue_growth": "Revenue growth", "profit_margin": "Profit margin", "free_cash_flow": "Free cash flow", "debt_to_equity": "Debt / Equity", "beta": "Beta", "dividend_yield": "Dividend yield"},
    "es": {"price": "Precio de la acción", "market_cap": "Capitalización bursátil", "trailing_pe": "P/E histórico", "forward_pe": "P/E futuro", "price_to_sales": "Precio / Ventas", "revenue_growth": "Crecimiento de ingresos", "profit_margin": "Margen de beneficio", "free_cash_flow": "Flujo de caja libre", "debt_to_equity": "Deuda / Patrimonio", "beta": "Beta", "dividend_yield": "Rentabilidad por dividendo"},
    "fr": {"price": "Cours de l’action", "market_cap": "Capitalisation boursière", "trailing_pe": "P/E historique", "forward_pe": "P/E prévisionnel", "price_to_sales": "Cours / Chiffre d’affaires", "revenue_growth": "Croissance du chiffre d’affaires", "profit_margin": "Marge bénéficiaire", "free_cash_flow": "Flux de trésorerie disponible", "debt_to_equity": "Dette / Capitaux propres", "beta": "Beta", "dividend_yield": "Rendement du dividende"},
    "zh": {"price": "股价", "market_cap": "市值", "trailing_pe": "历史市盈率", "forward_pe": "预期市盈率", "price_to_sales": "市销率", "revenue_growth": "营收增长", "profit_margin": "利润率", "free_cash_flow": "自由现金流", "debt_to_equity": "负债权益比", "beta": "贝塔系数", "dividend_yield": "股息率"},
    "ja": {"price": "株価", "market_cap": "時価総額", "trailing_pe": "実績P/E", "forward_pe": "予想P/E", "price_to_sales": "株価売上高倍率", "revenue_growth": "売上高成長率", "profit_margin": "利益率", "free_cash_flow": "フリーキャッシュフロー", "debt_to_equity": "負債資本倍率", "beta": "ベータ", "dividend_yield": "配当利回り"},
    "ko": {"price": "주가", "market_cap": "시가총액", "trailing_pe": "과거 P/E", "forward_pe": "예상 P/E", "price_to_sales": "주가매출비율", "revenue_growth": "매출 성장률", "profit_margin": "이익률", "free_cash_flow": "잉여현금흐름", "debt_to_equity": "부채비율", "beta": "베타", "dividend_yield": "배당수익률"},
    "de": {"price": "Aktienkurs", "market_cap": "Marktkapitalisierung", "trailing_pe": "Historisches KGV", "forward_pe": "Erwartetes KGV", "price_to_sales": "Kurs-Umsatz-Verhältnis", "revenue_growth": "Umsatzwachstum", "profit_margin": "Gewinnmarge", "free_cash_flow": "Freier Cashflow", "debt_to_equity": "Verschuldungsgrad", "beta": "Beta", "dividend_yield": "Dividendenrendite"},
    "pt": {"price": "Preço da ação", "market_cap": "Capitalização de mercado", "trailing_pe": "P/L histórico", "forward_pe": "P/L futuro", "price_to_sales": "Preço / Vendas", "revenue_growth": "Crescimento da receita", "profit_margin": "Margem de lucro", "free_cash_flow": "Fluxo de caixa livre", "debt_to_equity": "Dívida / Patrimônio", "beta": "Beta", "dividend_yield": "Rendimento de dividendos"},
    "it": {"price": "Prezzo dell’azione", "market_cap": "Capitalizzazione di mercato", "trailing_pe": "P/E storico", "forward_pe": "P/E atteso", "price_to_sales": "Prezzo / Ricavi", "revenue_growth": "Crescita dei ricavi", "profit_margin": "Margine di profitto", "free_cash_flow": "Flusso di cassa libero", "debt_to_equity": "Debito / Patrimonio", "beta": "Beta", "dividend_yield": "Rendimento da dividendo"},
    "ar": {"price": "سعر السهم", "market_cap": "القيمة السوقية", "trailing_pe": "مكرر الربحية التاريخي", "forward_pe": "مكرر الربحية المتوقع", "price_to_sales": "السعر إلى المبيعات", "revenue_growth": "نمو الإيرادات", "profit_margin": "هامش الربح", "free_cash_flow": "التدفق النقدي الحر", "debt_to_equity": "الدين إلى حقوق الملكية", "beta": "بيتا", "dividend_yield": "عائد التوزيعات"},
}


def route_intent(message: str, has_report: bool = False) -> AssistantIntent:
    """Route locally before any optional model call."""
    if _RECOMMENDATION.search(message):
        return AssistantIntent.RECOMMENDATION_OR_PREDICTION
    if _SITE_HELP.search(message):
        return AssistantIntent.SITE_HELP
    if _COMPANY_LOOKUP.search(message) or (
        company_search.search_companies(message, limit=1, include_provider=False)
        and re.search(
            r"ticker|stock symbol|símbolo|symbole|aktiensymbol|simbolo|銘柄コード|"
            r"종목\s*코드|رمز\s*(?:السهم|سهم)|股票代码|代码",
            message,
            re.I,
        )
    ):
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
            r"(?:aktuell|dessen|unternehmen|bericht|atual|empresa|relatório|attuale|azienda|rapporto|"
            r"現在|この会社|このレポート|현재|이 회사|이 보고서|الحالي|هذه الشركة|هذا التقرير|"
            r"当前|该公司|这家公司|此报告)",
            message,
            re.I,
        )
    ):
        return AssistantIntent.CURRENT_REPORT_QUESTION
    if assistant_kb.concept_key(message) or _CONCEPT_QUESTION.search(message):
        return AssistantIntent.FINANCIAL_CONCEPT
    if has_report and re.search(
        r"\b(?:it|its|those|these|dessen|diese|ele|ela|esso|quello)\b|"
        r"(?:それ|その|이것|그것|هو|هي|它|这些)",
        message,
        re.I,
    ):
        return AssistantIntent.CURRENT_REPORT_QUESTION
    return AssistantIntent.GENERAL_EDUCATION


def _depth_for_profile(profile) -> ExplanationDepth:
    return _explanation_depth(profile)


def _localized(language: str, key: str, **values) -> str:
    messages = {
        "en": {
            "advice": "I can't choose a stock for you, give a buy/sell instruction, guarantee an outcome, or predict a future price. I can compare the companies using current, cited evidence—for example valuation, growth, cash flow, leverage, and key uncertainties. Those comparisons are descriptive, not a forecast.",
            "comparison": "I can help compare 2–5 companies using the same evidence-backed metrics. Tell me the company names or stock symbols and what dimension matters—such as growth, profitability, leverage, or valuation. The result will show uncertainty and will not rank a stock as the one you should buy.",
            "lookup": "{name}'s stock symbol is {ticker} on {exchange}. [1]",
            "lookup_missing": "I couldn't verify a stock symbol from that company name, so I won't guess. Try the full legal name and, if known, its exchange or country.",
            "report_missing": "I don't have sufficient evidence in the open FinSight report to answer that. I won't fill the gap with an estimated or invented number. Open or refresh the relevant report section and ask again.",
            "report_intro": "Based only on the open FinSight report for {company}:",
            "moderated": "I can't help with market manipulation, account theft, prompt extraction, or other abusive activity. I can help with lawful financial education and evidence-based company research.",
            "general": "I can help explain a financial concept, find a stock symbol, explain evidence in the open FinSight report, compare companies, or show you how to use the site. Ask one specific question and I'll keep the answer at your preferred explanation level.",
            "company_directory": "FinSight company and stock-symbol directory",
        },
        "es": {
            "advice": "No puedo elegir una acción por ti, dar una orden de compra o venta, garantizar un resultado ni predecir un precio futuro. Sí puedo comparar empresas con evidencia actual y citada—por ejemplo valoración, crecimiento, flujo de caja, deuda e incertidumbres. La comparación será descriptiva, no un pronóstico.",
            "comparison": "Puedo comparar entre 2 y 5 empresas con las mismas métricas respaldadas por evidencia. Dime nombres o símbolos bursátiles y el aspecto relevante, como crecimiento, rentabilidad, deuda o valoración. No clasificaré una acción como la que deberías comprar.",
            "lookup": "El símbolo bursátil de {name} es {ticker} en {exchange}. [1]",
            "lookup_missing": "No pude verificar un símbolo bursátil con ese nombre, así que no voy a adivinar. Prueba con la razón social completa y, si la conoces, la bolsa o el país.",
            "report_missing": "El informe abierto no contiene evidencia suficiente para responder. No completaré el dato con una cifra estimada o inventada. Abre o actualiza la sección relevante y vuelve a preguntar.",
            "report_intro": "Basándome solo en el informe FinSight abierto de {company}:",
            "moderated": "No puedo ayudar con manipulación de mercado, robo de cuentas, extracción de prompts ni otras actividades abusivas. Sí puedo ayudar con educación financiera legal e investigación basada en evidencia.",
            "general": "Puedo explicar un concepto financiero, encontrar un símbolo bursátil, explicar la evidencia del informe abierto, comparar empresas o mostrar cómo usar el sitio. Haz una pregunta concreta.",
            "company_directory": "Directorio de empresas y símbolos bursátiles de FinSight",
        },
        "fr": {
            "advice": "Je ne peux pas choisir une action à votre place, donner un ordre d'achat ou de vente, garantir un résultat ni prédire un cours futur. Je peux comparer des entreprises avec des preuves actuelles et citées—valorisation, croissance, trésorerie, dette et incertitudes. Cette comparaison reste descriptive, pas prédictive.",
            "comparison": "Je peux comparer 2 à 5 entreprises avec les mêmes indicateurs fondés sur les preuves. Indiquez les noms ou symboles boursiers et l'axe souhaité, comme la croissance, la rentabilité, la dette ou la valorisation. Je ne classerai pas une action comme celle qu'il faut acheter.",
            "lookup": "Le symbole boursier de {name} est {ticker} sur {exchange}. [1]",
            "lookup_missing": "Je n'ai pas pu vérifier un symbole boursier à partir de ce nom, donc je ne vais pas le deviner. Essayez la raison sociale complète et, si possible, la bourse ou le pays.",
            "report_missing": "Le rapport ouvert ne contient pas assez de preuves pour répondre. Je ne compléterai pas avec une estimation ou un chiffre inventé. Ouvrez ou actualisez la section pertinente puis réessayez.",
            "report_intro": "Uniquement d'après le rapport FinSight ouvert pour {company} :",
            "moderated": "Je ne peux pas aider à manipuler un marché, voler un compte, extraire un prompt ou mener une activité abusive. Je peux aider pour l'éducation financière légale et la recherche fondée sur les preuves.",
            "general": "Je peux expliquer un concept, trouver un symbole boursier, clarifier les preuves du rapport ouvert, comparer des entreprises ou montrer comment utiliser le site. Posez une question précise.",
            "company_directory": "Répertoire FinSight des entreprises et symboles boursiers",
        },
        "zh": {
            "advice": "我不能替你选股、给出买卖指令、保证结果或预测未来股价。我可以用当前且有引用的证据比较估值、增长、现金流、杠杆和主要不确定性。这种比较是描述性的，不是预测。",
            "comparison": "我可以用一致、有证据的指标比较 2–5 家公司。请告诉我公司名或股票代码，以及你关心的维度，如增长、盈利能力、杠杆或估值。结果不会把某只股票排成“应该买”的选择。",
            "lookup": "{name} 在 {exchange} 的股票代码是 {ticker}。[1]",
            "lookup_missing": "我无法从该公司名验证股票代码，所以不会猜测。请尝试完整法定名称，如已知也可附上交易所或国家。",
            "report_missing": "当前 FinSight 报告没有足够证据回答这个问题。我不会用估算或虚构数字补齐。请打开或刷新相关报告部分后重试。",
            "report_intro": "仅根据当前打开的 {company} FinSight 报告：",
            "moderated": "我不能帮助操纵市场、窃取账户、提取系统提示词或其他滥用行为。我可以提供合法的金融教育和基于证据的公司研究。",
            "general": "我可以解释金融概念、查找股票代码、说明当前报告中的证据、比较公司，或介绍网站用法。请提一个具体问题。",
            "company_directory": "FinSight 公司与股票代码目录",
        },
        "ja": {
            "advice": "あなたに代わって銘柄を選んだり、売買を指示したり、結果を保証したり、将来の株価を予測したりすることはできません。現在の出典付きデータを使って、評価、成長、キャッシュフロー、負債、不確実性を比較できます。比較は予測ではありません。",
            "comparison": "同じ根拠付き指標で2～5社を比較できます。会社名または銘柄コードと、成長性、収益性、負債、評価など比較したい観点を教えてください。購入すべき銘柄として順位付けはしません。",
            "lookup": "{name} の {exchange} における銘柄コードは {ticker} です。[1]",
            "lookup_missing": "その会社名から銘柄コードを確認できなかったため、推測はしません。正式な会社名と、分かれば取引所または国を入力してください。",
            "report_missing": "開いている FinSight レポートには、この質問に答える十分な根拠がありません。推定値や架空の数値では補いません。関連セクションを開くか更新して、もう一度質問してください。",
            "report_intro": "開いている {company} の FinSight レポートだけに基づくと：",
            "moderated": "市場操作、アカウント窃取、システム指示の抽出などの不正行為には協力できません。合法的な金融教育と根拠に基づく企業調査には対応できます。",
            "general": "金融概念の説明、銘柄コードの検索、開いているレポートの根拠の説明、企業比較、サイトの使い方を支援できます。具体的な質問を1つ入力してください。",
            "company_directory": "FinSight 企業・銘柄コード一覧",
        },
        "ko": {
            "advice": "사용자를 대신해 종목을 고르거나 매수·매도 지시를 내리거나 결과를 보장하거나 미래 주가를 예측할 수 없습니다. 현재의 출처가 있는 근거로 가치평가, 성장, 현금흐름, 부채와 불확실성을 비교할 수 있습니다. 비교는 예측이 아닙니다.",
            "comparison": "동일한 근거 기반 지표로 2~5개 회사를 비교할 수 있습니다. 회사명이나 종목 코드와 성장성, 수익성, 부채, 가치평가 등 비교할 항목을 알려 주세요. 매수해야 할 종목으로 순위를 매기지 않습니다.",
            "lookup": "{name}의 {exchange} 종목 코드는 {ticker}입니다. [1]",
            "lookup_missing": "해당 회사명으로 종목 코드를 확인할 수 없어 추측하지 않겠습니다. 정식 회사명과 가능하면 거래소 또는 국가를 입력해 주세요.",
            "report_missing": "열려 있는 FinSight 보고서에 이 질문에 답할 충분한 근거가 없습니다. 추정값이나 임의의 숫자로 채우지 않습니다. 관련 보고서 섹션을 열거나 새로 고친 뒤 다시 질문해 주세요.",
            "report_intro": "열려 있는 {company} FinSight 보고서만을 기준으로 보면:",
            "moderated": "시장 조작, 계정 탈취, 시스템 지시 추출 또는 기타 악용을 도울 수 없습니다. 합법적인 금융 교육과 근거 기반 기업 조사는 도울 수 있습니다.",
            "general": "금융 개념 설명, 종목 코드 검색, 열린 보고서의 근거 설명, 기업 비교, 사이트 사용 안내를 도울 수 있습니다. 구체적인 질문 하나를 입력해 주세요.",
            "company_directory": "FinSight 기업·종목 코드 목록",
        },
        "de": {
            "advice": "Ich kann keine Aktie für Sie auswählen, keine Kauf- oder Verkaufsanweisung geben, kein Ergebnis garantieren und keinen künftigen Kurs vorhersagen. Ich kann Unternehmen anhand aktueller, belegter Daten zu Bewertung, Wachstum, Cashflow, Verschuldung und Unsicherheiten vergleichen. Der Vergleich ist keine Prognose.",
            "comparison": "Ich kann 2–5 Unternehmen anhand derselben belegten Kennzahlen vergleichen. Nennen Sie Namen oder Aktiensymbole und den gewünschten Schwerpunkt, etwa Wachstum, Rentabilität, Verschuldung oder Bewertung. Ich erstelle keine Rangliste, welche Aktie Sie kaufen sollten.",
            "lookup": "Das Aktiensymbol von {name} an der {exchange} lautet {ticker}. [1]",
            "lookup_missing": "Ich konnte zu diesem Firmennamen kein Aktiensymbol verifizieren und werde nicht raten. Versuchen Sie den vollständigen rechtlichen Namen und, falls bekannt, Börse oder Land.",
            "report_missing": "Der geöffnete FinSight-Bericht enthält nicht genügend Belege für diese Antwort. Ich ergänze keine geschätzte oder erfundene Zahl. Öffnen oder aktualisieren Sie den passenden Berichtsabschnitt und fragen Sie erneut.",
            "report_intro": "Ausschließlich auf Grundlage des geöffneten FinSight-Berichts zu {company}:",
            "moderated": "Bei Marktmanipulation, Kontodiebstahl, dem Auslesen von Systemanweisungen oder anderem Missbrauch kann ich nicht helfen. Rechtmäßige Finanzbildung und belegte Unternehmensrecherche unterstütze ich gern.",
            "general": "Ich kann Finanzbegriffe erklären, Aktiensymbole finden, Belege im geöffneten Bericht erläutern, Unternehmen vergleichen oder die Nutzung der Website zeigen. Stellen Sie eine konkrete Frage.",
            "company_directory": "FinSight-Verzeichnis für Unternehmen und Aktiensymbole",
        },
        "pt": {
            "advice": "Não posso escolher uma ação por você, dar ordem de compra ou venda, garantir resultados nem prever um preço futuro. Posso comparar empresas com evidências atuais e citadas sobre avaliação, crescimento, caixa, dívida e incertezas. A comparação é descritiva, não uma previsão.",
            "comparison": "Posso comparar de 2 a 5 empresas com as mesmas métricas baseadas em evidências. Informe nomes ou símbolos de ações e o aspecto desejado, como crescimento, rentabilidade, dívida ou avaliação. Não classificarei uma ação como a que você deveria comprar.",
            "lookup": "O símbolo de ação de {name} na {exchange} é {ticker}. [1]",
            "lookup_missing": "Não consegui verificar um símbolo de ação com esse nome e não vou adivinhar. Tente o nome jurídico completo e, se souber, a bolsa ou o país.",
            "report_missing": "O relatório FinSight aberto não contém evidências suficientes para responder. Não preencherei a lacuna com um número estimado ou inventado. Abra ou atualize a seção relevante e pergunte novamente.",
            "report_intro": "Com base apenas no relatório FinSight aberto de {company}:",
            "moderated": "Não posso ajudar com manipulação de mercado, roubo de contas, extração de instruções do sistema ou outros abusos. Posso ajudar com educação financeira legal e pesquisa empresarial baseada em evidências.",
            "general": "Posso explicar um conceito financeiro, encontrar um símbolo de ação, explicar as evidências do relatório aberto, comparar empresas ou mostrar como usar o site. Faça uma pergunta específica.",
            "company_directory": "Diretório FinSight de empresas e símbolos de ações",
        },
        "it": {
            "advice": "Non posso scegliere un’azione per te, dare istruzioni di acquisto o vendita, garantire risultati o prevedere un prezzo futuro. Posso confrontare aziende con prove attuali e citate su valutazione, crescita, flussi di cassa, debito e incertezze. Il confronto è descrittivo, non una previsione.",
            "comparison": "Posso confrontare da 2 a 5 aziende con le stesse metriche basate su prove. Indica nomi o simboli azionari e l’aspetto desiderato, come crescita, redditività, debito o valutazione. Non classificherò un’azione come quella da acquistare.",
            "lookup": "Il simbolo azionario di {name} sul mercato {exchange} è {ticker}. [1]",
            "lookup_missing": "Non ho potuto verificare un simbolo azionario da questo nome e non farò ipotesi. Prova il nome legale completo e, se noto, il mercato o il paese.",
            "report_missing": "Il rapporto FinSight aperto non contiene prove sufficienti per rispondere. Non colmerò la lacuna con un numero stimato o inventato. Apri o aggiorna la sezione pertinente e riprova.",
            "report_intro": "Basandomi esclusivamente sul rapporto FinSight aperto di {company}:",
            "moderated": "Non posso aiutare con manipolazione del mercato, furto di account, estrazione delle istruzioni di sistema o altri abusi. Posso aiutare con educazione finanziaria lecita e ricerca aziendale basata su prove.",
            "general": "Posso spiegare un concetto finanziario, trovare un simbolo azionario, chiarire le prove del rapporto aperto, confrontare aziende o mostrare come usare il sito. Fai una domanda specifica.",
            "company_directory": "Elenco FinSight di aziende e simboli azionari",
        },
        "ar": {
            "advice": "لا يمكنني اختيار سهم لك أو إصدار تعليمات شراء أو بيع أو ضمان نتيجة أو توقع سعر مستقبلي. يمكنني مقارنة الشركات باستخدام أدلة حالية وموثقة حول التقييم والنمو والتدفق النقدي والدين وأوجه عدم اليقين. المقارنة وصفية وليست توقعًا.",
            "comparison": "يمكنني مقارنة شركتين إلى خمس شركات بالمقاييس الموثقة نفسها. اذكر أسماء الشركات أو رموز الأسهم والجانب المطلوب مثل النمو أو الربحية أو الدين أو التقييم. لن أرتب سهمًا على أنه السهم الذي ينبغي لك شراؤه.",
            "lookup": "رمز سهم {name} في {exchange} هو {ticker}. [1]",
            "lookup_missing": "لم أتمكن من التحقق من رمز سهم بهذا الاسم، لذلك لن أخمّن. جرّب الاسم القانوني الكامل، وإن أمكن، البورصة أو البلد.",
            "report_missing": "لا يحتوي تقرير FinSight المفتوح على أدلة كافية للإجابة. لن أملأ النقص برقم تقديري أو مختلق. افتح قسم التقرير ذي الصلة أو حدّثه ثم اسأل مرة أخرى.",
            "report_intro": "استنادًا فقط إلى تقرير FinSight المفتوح عن {company}:",
            "moderated": "لا يمكنني المساعدة في التلاعب بالسوق أو سرقة الحسابات أو استخراج تعليمات النظام أو أي إساءة أخرى. يمكنني المساعدة في التعليم المالي القانوني والبحث المؤسسي القائم على الأدلة.",
            "general": "يمكنني شرح مفهوم مالي، والعثور على رمز سهم، وشرح أدلة التقرير المفتوح، ومقارنة الشركات، أو توضيح استخدام الموقع. اطرح سؤالًا محددًا.",
            "company_directory": "دليل FinSight للشركات ورموز الأسهم",
        },
    }
    table = messages.get(language, messages["en"])
    return table[key].format(**values)


def _requested_report_label(message: str) -> str | None:
    normalized = message.casefold()
    for canonical, aliases in _REPORT_LABEL_ALIASES.items():
        if any(
            re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized)
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
    evidence_id = evidence.evidence_id.casefold()
    if requested and (
        requested in evidence.label.casefold()
        or any(key in evidence_id for key in _REPORT_EVIDENCE_KEYS.get(requested, ()))
    ):
        score += 20
    return score


def _localized_evidence_label(item: AssistantReportEvidence, language: str) -> str:
    labels = _REPORT_METRIC_LABELS.get(language, _REPORT_METRIC_LABELS["en"])
    for metric_key, label in labels.items():
        if item.evidence_id.casefold().endswith(f".{metric_key}"):
            return label
    return item.label


def _citation(item: AssistantReportEvidence, language: str) -> AssistantCitation:
    return AssistantCitation(
        evidence_id=item.evidence_id,
        title=_localized_evidence_label(item, language),
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
        lines.append(f"- {_localized_evidence_label(item, language)}: {item.value} [{index}]")
        citations.append(_citation(item, language))
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
        results = company_search.search_companies(
            request.message, limit=1, include_provider=False
        )
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
                    source=_localized(language, "company_directory"),
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
            bool(company_search.search_companies(
                request.message, limit=1, include_provider=False
            ))
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
