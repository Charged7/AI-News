"""OpenAI-логіка: готує batch summaries для новин і парсить JSON-відповідь."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Iterable

from config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_RATE_LIMIT_RETRIES
from prompts import build_openai_messages
from rss import NewsItem

logger = logging.getLogger(__name__)


class AISummaryError(RuntimeError):
    """Помилка, яка означає, що AI-результат для новин не вдалося зібрати."""


@dataclass(frozen=True)
class AiNewsText:
    """Український заголовок і summary для однієї новини."""

    title: str
    summary: str


def summarize_news_items(
    items: Iterable[NewsItem],
    api_key: str = OPENAI_API_KEY,
    model: str = OPENAI_MODEL,
    rate_limit_retries: int = OPENAI_RATE_LIMIT_RETRIES,
) -> dict[str, AiNewsText]:
    """Генерує перекладені заголовки та summaries для всіх новин одним запитом."""
    if not api_key:
        raise AISummaryError("OPENAI_API_KEY is required for AI summaries.")

    item_list = list(items)
    if not item_list:
        raise AISummaryError("At least one news item is required for AI summaries.")

    try:
        return _summarize_news_items_with_openai_with_rate_limit_retry(
            item_list,
            api_key=api_key,
            model=model,
            rate_limit_retries=rate_limit_retries,
        )
    except Exception as exc:  # pragma: no cover - external API resilience
        logger.warning("AI summary failed: %s", exc)
        raise AISummaryError("AI summary generation failed.") from exc


def _summarize_news_items_with_openai(
    items: list[NewsItem],
    api_key: str,
    model: str,
) -> dict[str, AiNewsText]:
    """Відправляє batch-запит до OpenAI й парсить JSON у словник по link."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, max_retries=0)
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=2200,
        messages=build_openai_messages(items),
    )
    return _parse_ai_response(response.choices[0].message.content, items)


def _summarize_news_items_with_openai_with_rate_limit_retry(
    items: list[NewsItem],
    api_key: str,
    model: str,
    rate_limit_retries: int,
) -> dict[str, AiNewsText]:
    """Повторює batch-запит, якщо OpenAI відповів rate limit помилкою."""
    for attempt in range(rate_limit_retries + 1):
        try:
            return _summarize_news_items_with_openai(items, api_key=api_key, model=model)
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt >= rate_limit_retries:
                raise
            wait_seconds = _retry_wait_seconds(exc)
            logger.warning("OpenAI rate limit reached; waiting %.0fs before retrying.", wait_seconds)
            time.sleep(wait_seconds)

    raise AISummaryError("Unreachable rate-limit retry state.")


def _parse_ai_response(content: str | None, items: Iterable[NewsItem]) -> dict[str, AiNewsText]:
    """Перетворює JSON-відповідь моделі на словник summary по link."""
    text = (content or "").strip()
    if not text:
        raise AISummaryError("OpenAI returned an empty response.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AISummaryError("OpenAI returned invalid JSON.") from exc

    if isinstance(data, dict):
        entries = data.get("items", data.get("news", data))
    else:
        entries = data

    if not isinstance(entries, list):
        raise AISummaryError("OpenAI returned JSON in an unexpected format.")

    summaries: dict[str, AiNewsText] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise AISummaryError("OpenAI returned a non-object item in the news list.")

        link = str(entry.get("link", "")).strip()
        title = str(entry.get("title_uk", "")).strip()
        summary = str(entry.get("summary_uk", "")).strip()
        if not link or not title or not summary:
            raise AISummaryError("OpenAI returned incomplete news item data.")

        summaries[_link_key(link)] = AiNewsText(title=title, summary=summary)

    expected_links = {_link_key(item.link) for item in items}
    missing_links = sorted(expected_links - set(summaries))
    if missing_links:
        raise AISummaryError(
            "OpenAI returned incomplete summaries for: " + ", ".join(missing_links)
        )

    return summaries


def _link_key(link: str) -> str:
    """Нормалізує link для стабільного доступу до summary."""
    return link.strip().lower()


def _is_rate_limit_error(exc: Exception) -> bool:
    """Перевіряє, чи схожа помилка на rate limit від OpenAI."""
    text = str(exc).lower()
    return "rate_limit_exceeded" in text or "rate limit reached" in text


def _retry_wait_seconds(exc: Exception) -> float:
    """Дістає час очікування з тексту помилки або повертає запасне значення."""
    match = re.search(r"try again in ([0-9.]+)s", str(exc), flags=re.IGNORECASE)
    if match:
        return max(1.0, float(match.group(1)) + 1.0)
    return 21.0
