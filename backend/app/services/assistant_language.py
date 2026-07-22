"""Small, deterministic language detector for FinSight's supported languages.

The detector intentionally returns every material language in a message. That
lets the response layer preserve code-switching instead of forcing the whole
conversation into the website language.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_WORD_RE = re.compile(r"[A-Za-zÀ-ɏ']+")
_ZH_RE = re.compile(r"[\u3400-\u9fff]")

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
}


@dataclass(frozen=True)
class LanguageDetection:
    primary: str
    languages: tuple[str, ...]
    code_switched: bool


def detect_language(message: str, fallback: str = "en") -> LanguageDetection:
    """Detect English, Spanish, French, and Simplified Chinese without a network call."""
    fallback = fallback if fallback in {"en", "es", "fr", "zh"} else "en"
    scores = {language: 0.0 for language in ("en", "es", "fr", "zh")}
    tokens = [token.casefold() for token in _WORD_RE.findall(message)]

    zh_count = len(_ZH_RE.findall(message))
    if zh_count:
        scores["zh"] = min(10.0, 1.0 + zh_count / 2)

    for token in tokens:
        for language, words in _WORDS.items():
            if token in words:
                scores[language] += 1.0
        if any(character in token for character in "ñ¿¡"):
            scores["es"] += 1.5
        if any(character in token for character in "çœëîû"):
            scores["fr"] += 1.5
        if token in {"qué", "cómo", "está", "más", "también"}:
            scores["es"] += 1.5
        if token in {"où", "très", "société", "marché", "prévision"}:
            scores["fr"] += 1.5

    positive = [language for language, score in scores.items() if score >= 1.5]
    if not positive:
        # ASCII prose is most often English; isolated ticker symbols and financial
        # acronyms should follow the website language rather than count as English.
        ascii_words = [token for token in tokens if len(token) > 2]
        primary = "en" if len(ascii_words) >= 2 and fallback == "en" else fallback
        return LanguageDetection(primary, (primary,), False)

    ranked = sorted(positive, key=lambda language: (-scores[language], language))
    primary = ranked[0]
    material = tuple(
        language
        for language in ranked
        if scores[language] >= max(1.5, scores[primary] * 0.34)
    )
    return LanguageDetection(primary, material, len(material) > 1)

