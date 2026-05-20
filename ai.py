from __future__ import annotations

import logging
import re
import time
from typing import Iterable

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_RATE_LIMIT_RETRIES, OPENAI_REQUEST_DELAY_SECONDS
from rss import NewsItem, clean_text

logger = logging.getLogger(__name__)


class AISummaryError(RuntimeError):
    pass


def summarize_news_items(
    items: Iterable[NewsItem],
    api_key: str = OPENAI_API_KEY,
    model: str = OPENAI_MODEL,
    use_ai: bool = True,
    require_ai: bool = False,
    request_delay_seconds: float = OPENAI_REQUEST_DELAY_SECONDS,
    rate_limit_retries: int = OPENAI_RATE_LIMIT_RETRIES,
) -> dict[str, str]:
    summaries: dict[str, str] = {}
    ai_disabled = not use_ai or not api_key
    last_ai_request_at: float | None = None

    for item in items:
        if ai_disabled:
            if require_ai:
                raise AISummaryError("AI summaries are required, but OPENAI_API_KEY is missing or AI is disabled.")
            summaries[item.link] = fallback_summary(item.description or item.title)
            continue

        try:
            if last_ai_request_at is not None and request_delay_seconds > 0:
                elapsed = time.monotonic() - last_ai_request_at
                if elapsed < request_delay_seconds:
                    time.sleep(request_delay_seconds - elapsed)
            summaries[item.link] = _summarize_with_openai_with_rate_limit_retry(
                item,
                api_key=api_key,
                model=model,
                rate_limit_retries=rate_limit_retries,
            )
            last_ai_request_at = time.monotonic()
        except Exception as exc:  # pragma: no cover - external API resilience
            logger.warning("AI summary failed for %s: %s", item.link, exc)
            if require_ai:
                raise AISummaryError(f"AI summary failed for {item.link}") from exc
            if _is_quota_error(exc):
                logger.warning("OpenAI quota is unavailable; using fallback summaries for the rest of this run.")
                ai_disabled = True
            summaries[item.link] = fallback_summary(item.description or item.title)

    return summaries


def summarize_news_item(
    item: NewsItem,
    api_key: str = OPENAI_API_KEY,
    model: str = OPENAI_MODEL,
) -> str:
    if not api_key:
        return fallback_summary(item.description or item.title)

    try:
        return _summarize_with_openai(item, api_key=api_key, model=model)
    except Exception as exc:  # pragma: no cover - external API resilience
        logger.warning("AI summary failed for %s: %s", item.link, exc)
        return fallback_summary(item.description or item.title)


def fallback_summary(text: str, max_chars: int = 280) -> str:
    text = clean_text(text)
    if not text:
        return "Короткий опис недоступний."

    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary = " ".join(sentence for sentence in sentences[:2] if sentence).strip()
    if not summary:
        summary = text

    if len(summary) <= max_chars:
        return summary

    trimmed = summary[: max_chars - 1].rsplit(" ", 1)[0].strip()
    return f"{trimmed}..." if trimmed else f"{summary[: max_chars - 3]}..."


def _summarize_with_openai(item: NewsItem, api_key: str, model: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, max_retries=0)
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=180,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ти редактор ранкової стрічки новин. Підсумовуй українською у 1-2 реченнях. "
                    "Не вигадуй фактів, не додавай посилань, не згадуй і не створюй зображень."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Source: {item.source}\n"
                    f"Title: {item.title}\n"
                    f"Text: {item.description}\n\n"
                    "Поверни тільки короткий summary українською."
                ),
            },
        ],
    )
    summary = (response.choices[0].message.content or "").strip()
    return summary or fallback_summary(item.description or item.title)


def _summarize_with_openai_with_rate_limit_retry(
    item: NewsItem,
    api_key: str,
    model: str,
    rate_limit_retries: int,
) -> str:
    for attempt in range(rate_limit_retries + 1):
        try:
            return _summarize_with_openai(item, api_key=api_key, model=model)
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt >= rate_limit_retries:
                raise
            wait_seconds = _retry_wait_seconds(exc)
            logger.warning("OpenAI rate limit reached; waiting %.0fs before retrying.", wait_seconds)
            time.sleep(wait_seconds)

    raise AISummaryError("Unreachable rate-limit retry state.")


def _is_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "insufficient_quota" in text or "exceeded your current quota" in text


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "rate_limit_exceeded" in text or "rate limit reached" in text


def _retry_wait_seconds(exc: Exception) -> float:
    match = re.search(r"try again in ([0-9.]+)s", str(exc), flags=re.IGNORECASE)
    if match:
        return max(1.0, float(match.group(1)) + 1.0)
    return 21.0
