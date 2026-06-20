"""OpenAI summary generation and resilient JSON parsing."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Iterable

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_SUMMARY_BATCH_SIZE,
    OPENAI_SUMMARY_MAX_TOKENS,
)
from prompts import build_openai_messages
from rss import NewsItem, clean_text

logger = logging.getLogger(__name__)


class AISummaryError(RuntimeError):
    """Raised when AI summaries cannot be generated at all."""


@dataclass(frozen=True)
class AiNewsText:
    """Ukrainian title and short summary for one news item."""

    title: str
    summary: str


def summarize_news_items(
    items: Iterable[NewsItem],
    api_key: str = OPENAI_API_KEY,
    model: str = OPENAI_MODEL,
    batch_size: int = OPENAI_SUMMARY_BATCH_SIZE,
    max_tokens: int = OPENAI_SUMMARY_MAX_TOKENS,
) -> dict[str, AiNewsText]:
    """Generate Ukrainian titles and summaries for all selected important news."""
    if not api_key:
        raise AISummaryError("OPENAI_API_KEY is required for AI summaries.")

    item_list = list(items)
    if not item_list:
        raise AISummaryError("At least one news item is required for AI summaries.")
    if batch_size < 1:
        raise AISummaryError("OPENAI_SUMMARY_BATCH_SIZE must be at least 1.")
    if max_tokens < 1:
        raise AISummaryError("OPENAI_SUMMARY_MAX_TOKENS must be at least 1.")

    try:
        summaries: dict[str, AiNewsText] = {}
        for batch in _chunk_items(item_list, batch_size):
            summaries.update(
                _summarize_news_items_with_openai(
                    batch,
                    api_key=api_key,
                    model=model,
                    max_tokens=max_tokens,
                )
            )

        for item in _missing_summary_items(item_list, summaries):
            logger.warning("OpenAI did not summarize item; using fallback summary: %s", item.link)
            summaries[_link_key(item.link)] = _fallback_summary(item)

        return summaries
    except Exception as exc:  # pragma: no cover - external API resilience
        logger.warning("AI summary failed: %s", exc)
        if isinstance(exc, AISummaryError):
            raise
        raise AISummaryError("AI summary generation failed.") from exc


def _summarize_news_items_with_openai(
    items: list[NewsItem],
    api_key: str,
    model: str,
    max_tokens: int,
) -> dict[str, AiNewsText]:
    """Send one summary batch to OpenAI and parse JSON into a link-keyed dict."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, max_retries=0)
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=build_openai_messages(items),
    )
    choice = response.choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason == "length":
        raise AISummaryError("OpenAI response was truncated before valid JSON.")
    if finish_reason not in (None, "stop"):
        raise AISummaryError(f"OpenAI stopped with unexpected finish_reason={finish_reason!r}.")

    return _parse_ai_response(choice.message.content, items)


def _parse_ai_response(content: str | None, items: Iterable[NewsItem]) -> dict[str, AiNewsText]:
    """Parse OpenAI JSON into summaries, filling incomplete/missing items with fallback text."""
    item_list = list(items)
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

    items_by_id = {_item_id(index): item for index, item in enumerate(item_list)}
    summaries: dict[str, AiNewsText] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise AISummaryError("OpenAI returned a non-object item in the news list.")

        item = _match_item_from_entry(entry, items_by_id)
        link = item.link if item else str(entry.get("link", "")).strip()
        if not link:
            logger.warning("OpenAI returned a summary item without id or link; skipping it.")
            continue

        title = str(entry.get("title_uk", "")).strip()
        summary = str(entry.get("summary_uk", "")).strip()
        if not title or not summary:
            if item is None:
                logger.warning("OpenAI returned incomplete summary for unknown item; skipping it.")
                continue
            logger.warning("OpenAI returned incomplete summary; using fallback summary: %s", item.link)
            summaries[_link_key(link)] = _fallback_summary(item)
            continue

        summaries[_link_key(link)] = AiNewsText(title=title, summary=summary)

    for item in _missing_summary_items(item_list, summaries):
        logger.warning("OpenAI omitted summary; using fallback summary: %s", item.link)
        summaries[_link_key(item.link)] = _fallback_summary(item)

    return summaries


def _chunk_items(items: list[NewsItem], batch_size: int) -> Iterable[list[NewsItem]]:
    """Split news into smaller OpenAI batches."""
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


def _missing_summary_items(
    items: Iterable[NewsItem],
    summaries: dict[str, AiNewsText],
) -> list[NewsItem]:
    return [item for item in items if _link_key(item.link) not in summaries]


def _fallback_summary(item: NewsItem) -> AiNewsText:
    title = clean_text(item.title) or "Важлива новина"
    description = clean_text(item.description)
    if description:
        summary = _truncate_text(description, 260)
    else:
        summary = "OpenAI не повернув короткий опис, тому показано оригінальний заголовок новини."
    return AiNewsText(title=title, summary=summary)


def _match_item_from_entry(
    entry: dict[str, object],
    items_by_id: dict[str, NewsItem],
) -> NewsItem | None:
    raw_id = str(entry.get("id") or entry.get("item_id") or "").strip()
    if raw_id in items_by_id:
        return items_by_id[raw_id]

    if raw_id.isdigit():
        return items_by_id.get(_item_id(int(raw_id) - 1))

    link = str(entry.get("link", "")).strip()
    if link:
        link_key = _link_key(link)
        for item in items_by_id.values():
            if _link_key(item.link) == link_key:
                return item

    return None


def _truncate_text(value: str, max_chars: int) -> str:
    text = clean_text(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _item_id(index: int) -> str:
    return f"item_{index + 1}"


def _link_key(link: str) -> str:
    """Normalize links for stable summary lookup."""
    return link.strip().lower()
