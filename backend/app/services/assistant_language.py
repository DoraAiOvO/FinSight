"""Small, deterministic language detector for FinSight Assistant languages.

The detector intentionally returns every material language in a message. That
lets the response layer preserve code-switching instead of forcing the whole
conversation into the website language.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_WORD_RE = re.compile(r"[A-Za-zÀ-ɏ']+")
_HAN_RE = re.compile(r"[\u3400-\u9fff]")
_JA_RE = re.compile(r"[\u3040-\u30ff]")
_KO_RE = re.compile(r"[\uac00-\ud7af]")
_AR_RE = re.compile(r"[\u0600-\u06ff]")

SUPPORTED_ASSISTANT_LANGUAGES = (
    "en", "es", "fr", "zh", "ja", "ko", "de", "pt", "it", "ar",
)

_WORDS = {
    "en": {
        "a", "about", "and", "can", "company", "compare", "does", "explain",
        "find", "how", "in", "is", "mean", "me", "of", "report", "should",
        "simple", "simply", "stock", "the", "this", "to", "what", "which",
        "with", "you",
    },
    "es": {
        "a", "acciones", "compañía", "comparar", "comprar", "cómo", "de",
        "el", "en", "esta", "este", "explica", "explicar", "informe", "la",
        "las", "los", "me", "qué", "significa", "simple", "vender", "y",
    },
    "fr": {
        "acheter", "actions", "ce", "cette", "comment", "comparer", "de", "des",
        "entreprise", "est", "expliquer", "explique", "le", "les", "me", "que",
        "quel", "quelle", "rapport", "signifie", "simplement", "un", "une", "vendre",
    },
    "de": {
        "aktie", "bericht", "bedeutet", "bitte", "das", "diese", "dieser", "erkläre",
        "erklären", "ist", "kaufen", "mir", "soll", "unternehmen", "und", "vergleichen",
        "verkaufen", "was", "welche", "wie",
    },
    "pt": {
        "ação", "ações", "a", "como", "comparar", "comprar", "de", "devo", "empresa",
        "esta", "este", "explica", "explicar", "o", "qual", "que", "relatório",
        "significa", "uma", "vender",
    },
    "it": {
        "azione", "azioni", "azienda", "che", "come", "comprare", "confrontare", "devo",
        "il", "la", "questo", "questa", "rapporto", "significa", "spiega", "spiegare",
        "una", "vendere", "vorrei",
    },
}

_FINANCE_WORDS = {
    "en": {"earnings", "market", "margin", "revenue", "share", "symbol", "valuation"},
    "es": {"bursátil", "capitalización", "deuda", "ingresos", "margen", "patrimonio", "símbolo", "valoración"},
    "fr": {"boursier", "boursière", "capitalisation", "capitaux", "dette", "marge", "symbole", "valorisation"},
    "de": {"aktiensymbol", "gewinnmarge", "kgv", "marktkapitalisierung", "umsatzwachstum", "verschuldungsgrad"},
    "pt": {"ação", "capitalização", "dívida", "margem", "patrimônio", "receita", "símbolo"},
    "it": {"azionario", "capitalizzazione", "debito", "margine", "patrimonio", "ricavi", "simbolo"},
}


@dataclass(frozen=True)
class LanguageDetection:
    primary: str
    languages: tuple[str, ...]
    code_switched: bool


def detect_language(message: str, fallback: str = "en") -> LanguageDetection:
    """Detect ten assistant languages without changing the site's four locales."""
    fallback = fallback if fallback in {"en", "es", "fr", "zh"} else "en"
    scores = {language: 0.0 for language in SUPPORTED_ASSISTANT_LANGUAGES}
    tokens = [token.casefold() for token in _WORD_RE.findall(message)]

    ja_count = len(_JA_RE.findall(message))
    ko_count = len(_KO_RE.findall(message))
    ar_count = len(_AR_RE.findall(message))
    han_count = len(_HAN_RE.findall(message))
    if ja_count:
        scores["ja"] = min(10.0, 2.0 + (ja_count + han_count) / 3)
    elif han_count:
        scores["zh"] = min(10.0, 1.0 + han_count / 2)
    if ko_count:
        scores["ko"] = min(10.0, 1.5 + ko_count / 2)
    if ar_count:
        scores["ar"] = min(10.0, 1.5 + ar_count / 3)

    for token in tokens:
        for language, words in _WORDS.items():
            if token in words:
                scores[language] += 1.0
        for language, words in _FINANCE_WORDS.items():
            if token in words:
                scores[language] += 1.5
        if any(character in token for character in "ñ¿¡"):
            scores["es"] += 1.5
        if any(character in token for character in "çœëîû"):
            scores["fr"] += 1.5
        if token in {"qué", "cómo", "está", "más", "también"}:
            scores["es"] += 1.5
        if token in {"où", "très", "société", "marché", "prévision"}:
            scores["fr"] += 1.5
        if token in {"für", "über", "möchte", "erklären", "börse"}:
            scores["de"] += 1.5
        if token in {"ação", "ações", "você", "previsão", "cotação"}:
            scores["pt"] += 1.5
        if token in {"perché", "società", "previsione", "più", "cos'è"}:
            scores["it"] += 1.5

    positive = [language for language, score in scores.items() if score >= 1.5]
    if not positive:
        # ASCII prose is most often English; isolated ticker symbols and financial
        # acronyms should follow the website language rather than count as English.
        ascii_words = [token for token in tokens if len(token) > 2]
        primary = "en" if len(ascii_words) >= 2 and fallback == "en" else fallback
        return LanguageDetection(primary, (primary,), False)

    ranked = sorted(
        positive,
        key=lambda language: (-scores[language], 0 if language == fallback else 1, language),
    )
    primary = ranked[0]
    material = tuple(
        language
        for language in ranked
        if scores[language] >= max(1.5, scores[primary] * 0.45)
    )
    return LanguageDetection(primary, material, len(material) > 1)
