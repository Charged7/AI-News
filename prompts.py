from __future__ import annotations

from rss import NewsItem

OPENAI_NEWS_DIGEST_SYSTEM_PROMPT = """
Ти редактор новинного дайджесту.
Стисни список новин у короткий структурований дайджест українською.
Не вигадуй фактів, не додавай посилань, дат або зображень.
Поверни тільки валідний JSON без markdown.
""".strip()

OPENAI_NEWS_DIGEST_USER_PROMPT_TEMPLATE = """
Потрібно підсумувати такі новини:
{items}

Поверни JSON у форматі: {{"digest_uk": "..."}}
""".strip()


def build_openai_digest_messages(items: list[NewsItem]) -> list[dict[str, str]]:
    formatted_items = "\n".join(
        f"- {item.source}: {item.title}\n  {item.description}" for item in items
    )
    return [
        {"role": "system", "content": OPENAI_NEWS_DIGEST_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": OPENAI_NEWS_DIGEST_USER_PROMPT_TEMPLATE.format(items=formatted_items),
        },
    ]
