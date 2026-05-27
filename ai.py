"""OpenAI-логіка: готує batch summaries для новин і парсить JSON-відповідь."""

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
    batch_size: int = OPENAI_SUMMARY_BATCH_SIZE,
    max_tokens: int = OPENAI_SUMMARY_MAX_TOKENS,
) -> dict[str, AiNewsText]:
    """Генерує перекладені заголовки та summaries для всіх новин одним запитом."""
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
        return summaries
    except Exception as exc:  # pragma: no cover - external API resilience
        logger.warning("AI summary failed: %s", exc)
        raise AISummaryError("AI summary generation failed.") from exc


def _summarize_news_items_with_openai(
    items: list[NewsItem],
    api_key: str,
    model: str,
    max_tokens: int,
) -> dict[str, AiNewsText]:
    """Відправляє batch-запит до OpenAI й парсить JSON у словник по link."""
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


def _chunk_items(items: list[NewsItem], batch_size: int) -> Iterable[list[NewsItem]]:
    """Ділить новини на менші AI batches, щоб відповідь не обрізалась по max_tokens."""
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


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
