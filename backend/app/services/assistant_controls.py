"""In-process assistant quotas and deterministic abuse moderation."""
from __future__ import annotations

import hashlib
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from ..config import settings


@dataclass(frozen=True)
class QuotaResult:
    allowed: bool
    retry_after: int
    user_remaining: int
    ip_remaining: int


class AssistantRateLimiter:
    def __init__(self):
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _consume(self, key: str, limit: int, now: float, window: int) -> tuple[bool, int, int]:
        events = self._events[key]
        cutoff = now - window
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= limit:
            retry_after = max(1, int(window - (now - events[0])) + 1)
            return False, retry_after, 0
        events.append(now)
        return True, 0, max(0, limit - len(events))

    def check(self, ip_address: str, customer_id: str | None) -> QuotaResult:
        now = time.monotonic()
        window = settings.ASSISTANT_QUOTA_WINDOW_SECONDS
        ip_hash = hashlib.sha256(ip_address.encode("utf-8")).hexdigest()[:20]
        with self._lock:
            ip_allowed, ip_retry, ip_remaining = self._consume(
                f"ip:{ip_hash}", settings.ASSISTANT_IP_QUOTA, now, window
            )
            if customer_id:
                user_allowed, user_retry, user_remaining = self._consume(
                    f"user:{customer_id}", settings.ASSISTANT_USER_QUOTA, now, window
                )
            else:
                user_allowed, user_retry, user_remaining = True, 0, settings.ASSISTANT_USER_QUOTA
        return QuotaResult(
            allowed=ip_allowed and user_allowed,
            retry_after=max(ip_retry, user_retry),
            user_remaining=user_remaining,
            ip_remaining=ip_remaining,
        )

    def reset(self):
        """Test helper; production quotas naturally expire."""
        with self._lock:
            self._events.clear()


rate_limiter = AssistantRateLimiter()

_BLOCKED_PATTERNS = (
    re.compile(r"\b(?:insider trading|pump and dump|manipulate (?:a |the )?market)\b", re.I),
    re.compile(r"\b(?:phish|steal|launder)\b.{0,30}\b(?:account|money|credentials?)\b", re.I),
    re.compile(r"\b(?:ignore|reveal)\b.{0,40}\b(?:system prompt|developer instructions?)\b", re.I),
    re.compile(r"(?:内幕交易|操纵市场|窃取账户)"),
)


def moderation_reason(message: str) -> str | None:
    if any(pattern.search(message) for pattern in _BLOCKED_PATTERNS):
        return "unsafe_or_abusive_request"
    # Reject low-effort flooding without storing the original text.
    compact = re.sub(r"\s+", "", message)
    if len(compact) >= 80 and len(set(compact.casefold())) <= 3:
        return "spam"
    return None

