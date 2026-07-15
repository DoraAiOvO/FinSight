"""Optional AI layer (Anthropic). Degrades gracefully when no API key is set."""
from ..config import settings

_SYSTEM = (
    "You are FinSight, an evidence-first stock analysis assistant. Never tell the "
    "user to buy or sell. Explain what the data shows, cite the specific numbers "
    "you rely on, and note uncertainty. Be concise and plain-spoken."
)

SUPPORTED_LANGUAGES = ("en", "es", "fr", "zh")

_LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "zh": "Chinese (Simplified)",
}


def _language_instruction(lang: str) -> str:
    """Mirror RoboPrompt's language policy: respond in the UI-selected language."""
    if lang == "en" or lang not in _LANGUAGE_NAMES:
        return ""
    return (
        f"\n\nWrite your entire response in {_LANGUAGE_NAMES[lang]}. Keep ticker "
        "symbols and standard financial terms (P/E, FCF, beta) in their usual "
        "form when natural."
    )


def _client():
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic

        return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    except Exception:
        return None


def _ask(prompt: str, max_tokens: int = 600, lang: str = "en") -> str | None:
    client = _client()
    if client is None:
        return None
    try:
        msg = client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=max_tokens,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt + _language_instruction(lang)}],
        )
        return "".join(b.text for b in msg.content if b.type == "text").strip()
    except Exception:
        return None


def summarize_news(ticker: str, items: list[dict], lang: str = "en") -> str | None:
    """Summarize recent headlines into key themes. None if AI unavailable."""
    if not items:
        return None
    headlines = "\n".join(f"- {i['title']} ({i.get('publisher') or 'unknown'})" for i in items[:10])
    return _ask(
        f"Recent headlines for {ticker}:\n{headlines}\n\n"
        "Summarize the 2-4 main themes in these headlines and what each could mean "
        "for the company. Reference the headlines as your evidence.",
        lang=lang,
    )


def narrate_analysis(ticker: str, metrics: dict, insights: list[dict], lang: str = "en") -> str | None:
    """Turn rule-based insights into a short plain-English narrative."""
    if not insights:
        return None
    bullet = "\n".join(
        f"- [{i['kind']}/{i['severity']}] {i['title']}: "
        + "; ".join(f"{e['metric']}={e['value']}" for e in i["evidence"])
        for i in insights
    )
    return _ask(
        f"Company: {metrics.get('name')} ({ticker}), sector {metrics.get('sector')}.\n"
        f"Rule-based findings with evidence:\n{bullet}\n\n"
        "Write a short narrative (under 200 words) weaving these findings together. "
        "Explain the evidence; do not recommend buying or selling.",
        lang=lang,
    )
