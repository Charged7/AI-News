from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Iterable

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_RATE_LIMIT_RETRIES
from prompts import build_openai_digest_messages
from rss import NewsItem

logger = logging.getLogger(__name__)


class AISummaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class AiNewsDigest:
    digest: str


def summarize_news_digest(
    items: Iterable[NewsItem],
    api_key: str = OPENAI_API_KEY,
    model: str = OPENAI_MODEL,
    rate_limit_retries: int = OPENAI_RATE_LIMIT_RETRIES,
) -> AiNewsDigest:
    if not api_key:
        raise AISummaryError("OPENAI_API_KEY is required for AI summaries.")

    item_list = list(items)
    if not item_list:
        raise AISummaryError("At least one news item is required for a digest.")

    try:
        return _summarize_digest_with_openai_with_rate_limit_retry(
            item_list,
            api_key=api_key,
            model=model,
            rate_limit_retries=rate_limit_retries,
        )
    except Exception as exc:  # pragma: no cover - external API resilience
        logger.warning("AI digest failed: %s", exc)
        raise AISummaryError("AI digest generation failed.") from exc


def _summarize_digest_with_openai(items: list[NewsItem], api_key: str, model: str) -> AiNewsDigest:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, max_retries=0)
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=320,
        messages=build_openai_digest_messages(items),
    )
    return _parse_digest_response(response.choices[0].message.content)


def _summarize_digest_with_openai_with_rate_limit_retry(
    items: list[NewsItem],
    api_key: str,
    model: str,
    rate_limit_retries: int,
) -> AiNewsDigest:
    for attempt in range(rate_limit_retries + 1):
        try:
            return _summarize_digest_with_openai(items, api_key=api_key, model=model)
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt >= rate_limit_retries:
                raise
            wait_seconds = _retry_wait_seconds(exc)
            logger.warning("OpenAI rate limit reached; waiting %.0fs before retrying.", wait_seconds)
            time.sleep(wait_seconds)

    raise AISummaryError("Unreachable rate-limit retry state.")


def _parse_digest_response(content: str | None) -> AiNewsDigest:
    text = (content or "").strip()
    if not text:
        raise AISummaryError("OpenAI returned an empty digest response.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AISummaryError("OpenAI returned invalid digest JSON.") from exc

    digest = str(data.get("digest_uk", "")).strip()
    if not digest:
        raise AISummaryError("OpenAI returned an empty digest.")

    return AiNewsDigest(digest=digest)


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "rate_limit_exceeded" in text or "rate limit reached" in text


def _retry_wait_seconds(exc: Exception) -> float:
    match = re.search(r"try again in ([0-9.]+)s", str(exc), flags=re.IGNORECASE)
    if match:
        return max(1.0, float(match.group(1)) + 1.0)
    return 21.0
