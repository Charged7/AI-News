"""OpenAI-based high-impact news classification."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Iterable

from config import (
    NEWS_MAX_ITEMS_PER_RUN,
    NEWS_MIN_IMPACT_SCORE,
    OPENAI_API_KEY,
    OPENAI_IMPACT_BATCH_SIZE,
    OPENAI_IMPACT_MAX_TOKENS,
    OPENAI_IMPACT_RETRY_MISSING_LIMIT,
    OPENAI_MODEL,
)
from rss import NewsItem

logger = logging.getLogger(__name__)
IMPACT_TEXT_MAX_CHARS = 700


class ImpactClassificationError(RuntimeError):
    """Raised when OpenAI cannot return trustworthy impact classifications."""


@dataclass(frozen=True)
class ImpactDecision:
    """AI decision for one candidate news item."""

    link: str
    is_important: bool
    impact_score: int
    impact_level: str
    category: str
    event_type: str
    scope: str
    reason_uk: str


IMPACT_SYSTEM_PROMPT = """
Ти редактор важливих світових новин для Telegram-alerts.
Твоє завдання: визначити, чи варто надсилати кожну RSS-новину користувачу негайно.

Надсилай тільки події з реальною вагою:
- війни, ескалації, санкції, дипломатичні кризи, вибори, перевороти;
- рішення США, ЄС, НАТО, Китаю, РФ, України або великих міжнародних організацій;
- глобальна економіка, ринки, ставки центробанків, великі банкрутства;
- великі технологічні події: AI, чипи, регуляції, кібератаки, антимонопольні справи;
- катастрофи, теракти, масштабні аварії;
- спорт тільки якщо це фінал, титульний бій, Олімпіада, ЧС/Євро/ЛЧ, світовий скандал або подія, яку знає масова аудиторія.

Відхиляй:
- lifestyle, поради, how-to, reviews, deals, evergreen-контент;
- звичайні матчі, трансферні чутки, локальні спортивні новини;
- дрібні продуктові апдейти, локальні пости, opinion без нової події;
- матеріали, які не є конкретною новинною подією.

Оцінюй impact_score від 0 до 100:
- 90-100: критична світова подія;
- 75-89: важлива подія, яку варто надіслати;
- 60-74: помітна, але не обов'язкова;
- 0-59: не надсилати.

Поверни тільки валідний JSON без markdown.
Формат:
{"items":[{"id":"item_1","link":"...","is_important":true,"impact_score":85,"impact_level":"high","category":"politics","event_type":"geopolitical_escalation","scope":"global","reason_uk":"..."}]}
""".strip()

IMPACT_USER_PROMPT_TEMPLATE = """
Оціни важливість цих RSS-новин:
{items}

Для кожного input ID поверни рівно один JSON object, навіть якщо новина неважлива.
Не пропускай rejected/low-impact items. Використовуй точне значення ID з input.

Поверни JSON у форматі:
{{"items":[{{"id":"item_1","link":"...","is_important":true,"impact_score":85,"impact_level":"high","category":"politics","event_type":"geopolitical_escalation","scope":"global","reason_uk":"..."}}]}}
""".strip()


def select_important_news(
    items: Iterable[NewsItem],
    api_key: str = OPENAI_API_KEY,
    model: str = OPENAI_MODEL,
    min_score: int = NEWS_MIN_IMPACT_SCORE,
    max_items: int = NEWS_MAX_ITEMS_PER_RUN,
    batch_size: int = OPENAI_IMPACT_BATCH_SIZE,
    max_tokens: int = OPENAI_IMPACT_MAX_TOKENS,
) -> list[NewsItem]:
    """Classify news with OpenAI and return items worth sending."""
    item_list = list(items)
    decisions = classify_news_importance(
        item_list,
        api_key=api_key,
        model=model,
        batch_size=batch_size,
        max_tokens=max_tokens,
    )

    selected = [
        item
        for item in item_list
        if _accepted(decisions[_link_key(item.link)], min_score=min_score)
    ]
    selected.sort(
        key=lambda item: (
            decisions[_link_key(item.link)].impact_score,
            item.published_at is not None,
            item.published_at,
        ),
        reverse=True,
    )

    for item in item_list:
        decision = decisions[_link_key(item.link)]
        if _accepted(decision, min_score=min_score):
            logger.info(
                "AI impact accepted (%s, %s, %s): %s",
                decision.impact_score,
                decision.category,
                decision.event_type,
                item.title,
            )
        else:
            logger.info(
                "AI impact rejected (%s, %s): %s",
                decision.impact_score,
                decision.reason_uk,
                item.title,
            )

    return selected[:max_items] if max_items > 0 else selected


def classify_news_importance(
    items: Iterable[NewsItem],
    api_key: str = OPENAI_API_KEY,
    model: str = OPENAI_MODEL,
    batch_size: int = OPENAI_IMPACT_BATCH_SIZE,
    max_tokens: int = OPENAI_IMPACT_MAX_TOKENS,
    retry_missing_limit: int = OPENAI_IMPACT_RETRY_MISSING_LIMIT,
) -> dict[str, ImpactDecision]:
    """Classify all candidate items using OpenAI JSON mode."""
    if not api_key:
        raise ImpactClassificationError("OPENAI_API_KEY is required for impact classification.")

    item_list = list(items)
    if not item_list:
        return {}
    if batch_size < 1:
        raise ImpactClassificationError("OPENAI_IMPACT_BATCH_SIZE must be at least 1.")
    if max_tokens < 1:
        raise ImpactClassificationError("OPENAI_IMPACT_MAX_TOKENS must be at least 1.")
    if retry_missing_limit < 0:
        raise ImpactClassificationError("OPENAI_IMPACT_RETRY_MISSING_LIMIT must be at least 0.")

    try:
        decisions: dict[str, ImpactDecision] = {}
        for batch in _chunk_items(item_list, batch_size):
            batch_decisions = _classify_news_items_with_openai(
                batch,
                api_key=api_key,
                model=model,
                max_tokens=max_tokens,
                require_complete=False,
            )
            decisions.update(batch_decisions)

            missing_items = _missing_decision_items(batch, decisions)
            if missing_items:
                retry_items = missing_items[:retry_missing_limit]
                if retry_items:
                    logger.warning(
                        "OpenAI omitted %s impact decision(s); retrying %s individually.",
                        len(missing_items),
                        len(retry_items),
                    )
                else:
                    logger.warning(
                        "OpenAI omitted %s impact decision(s); retry is disabled for this cycle.",
                        len(missing_items),
                    )
                for item in retry_items:
                    decisions.update(
                        _classify_news_items_with_openai(
                            [item],
                            api_key=api_key,
                            model=model,
                            max_tokens=max_tokens,
                            require_complete=False,
                        )
                    )

        for item in _missing_decision_items(item_list, decisions):
            logger.warning("OpenAI did not classify item; rejecting conservatively: %s", item.link)
            decisions[_link_key(item.link)] = _fallback_rejected_decision(item)

        return decisions
    except Exception as exc:  # pragma: no cover - external API resilience
        logger.warning("AI impact classification failed: %s", exc)
        if isinstance(exc, ImpactClassificationError):
            raise
        raise ImpactClassificationError("AI impact classification failed.") from exc


def _classify_news_items_with_openai(
    items: list[NewsItem],
    api_key: str,
    model: str,
    max_tokens: int,
    require_complete: bool = True,
) -> dict[str, ImpactDecision]:
    """Send one batch of candidate news to OpenAI and parse impact decisions."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, max_retries=0)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=build_impact_messages(items),
    )
    choice = response.choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason == "length":
        raise ImpactClassificationError("OpenAI impact response was truncated before valid JSON.")
    if finish_reason not in (None, "stop"):
        raise ImpactClassificationError(f"OpenAI stopped with unexpected finish_reason={finish_reason!r}.")

    return _parse_impact_response(choice.message.content, items, require_complete=require_complete)


def build_impact_messages(items: list[NewsItem]) -> list[dict[str, str]]:
    """Build OpenAI messages for impact classification."""
    formatted_items = "\n".join(
        (
            f"- ID: {_item_id(index)}\n"
            f"  Source: {item.source}\n"
            f"  Source category: {item.source_category}\n"
            f"  Source priority: {item.source_priority}\n"
            f"  Title: {_truncate_text(item.title, 220)}\n"
            f"  Link: {item.link}\n"
            f"  Text: {_truncate_text(item.description, IMPACT_TEXT_MAX_CHARS)}"
        )
        for index, item in enumerate(items)
    )
    return [
        {"role": "system", "content": IMPACT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": IMPACT_USER_PROMPT_TEMPLATE.format(items=formatted_items),
        },
    ]


def _parse_impact_response(
    content: str | None,
    items: Iterable[NewsItem],
    require_complete: bool = True,
) -> dict[str, ImpactDecision]:
    """Parse OpenAI impact JSON into decisions keyed by normalized link."""
    item_list = list(items)
    text = (content or "").strip()
    if not text:
        raise ImpactClassificationError("OpenAI returned an empty impact response.")

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImpactClassificationError("OpenAI returned invalid impact JSON.") from exc

    entries = data.get("items") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        raise ImpactClassificationError("OpenAI returned impact JSON in an unexpected format.")

    items_by_id = {_item_id(index): item for index, item in enumerate(item_list)}
    decisions: dict[str, ImpactDecision] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ImpactClassificationError("OpenAI returned a non-object impact item.")

        item = _match_item_from_entry(entry, items_by_id)
        link = item.link if item else str(entry.get("link", "")).strip()
        score = _coerce_score(entry.get("impact_score"))
        if not link:
            logger.warning("OpenAI returned an impact item without id or link; skipping it.")
            continue

        decisions[_link_key(link)] = ImpactDecision(
            link=link,
            is_important=bool(entry.get("is_important", False)),
            impact_score=score,
            impact_level=str(entry.get("impact_level", "")).strip() or _impact_level(score),
            category=str(entry.get("category", "")).strip() or "general",
            event_type=str(entry.get("event_type", "")).strip() or "unknown",
            scope=str(entry.get("scope", "")).strip() or "unknown",
            reason_uk=str(entry.get("reason_uk", "")).strip() or "Без пояснення.",
        )

    expected_links = {_link_key(item.link) for item in item_list}
    missing_links = sorted(expected_links - set(decisions))
    if require_complete and missing_links:
        raise ImpactClassificationError(
            "OpenAI returned incomplete impact decisions for: " + ", ".join(missing_links)
        )

    return decisions


def _accepted(decision: ImpactDecision, min_score: int) -> bool:
    return decision.is_important and decision.impact_score >= min_score


def _coerce_score(value: object) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError) as exc:
        raise ImpactClassificationError("OpenAI returned invalid impact_score.") from exc
    return max(0, min(100, score))


def _impact_level(score: int) -> str:
    if score >= 90:
        return "critical"
    if score >= 75:
        return "high"
    if score >= 60:
        return "notable"
    return "low"


def _missing_decision_items(
    items: Iterable[NewsItem],
    decisions: dict[str, ImpactDecision],
) -> list[NewsItem]:
    return [item for item in items if _link_key(item.link) not in decisions]


def _fallback_rejected_decision(item: NewsItem) -> ImpactDecision:
    return ImpactDecision(
        link=item.link,
        is_important=False,
        impact_score=0,
        impact_level="low",
        category=item.source_category or "general",
        event_type="unclassified",
        scope="unknown",
        reason_uk="OpenAI не повернув класифікацію після повторної спроби.",
    )


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


def _chunk_items(items: list[NewsItem], batch_size: int) -> Iterable[list[NewsItem]]:
    for index in range(0, len(items), batch_size):
        yield items[index : index + batch_size]


def _truncate_text(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _item_id(index: int) -> str:
    return f"item_{index + 1}"


def _link_key(link: str) -> str:
    return link.strip().lower()
