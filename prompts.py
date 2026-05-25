"""Шаблони промптів для batch-обробки новин одним OpenAI-запитом."""

from __future__ import annotations

from rss import NewsItem

OPENAI_NEWS_SYSTEM_PROMPT = """
Ти редактор новинної стрічки.
Для кожної новини переклади заголовок українською та створи короткий summary українською в 1-2 речення.
Збережи порядок новин.
Не вигадуй фактів, не додавай emoji, нумерацію, посилання, дати, зображення чи додаткові коментарі.
Поверни тільки валідний JSON без markdown.
Формат відповіді:
{"items":[{"link":"...","title_uk":"...","summary_uk":"..."}]}
""".strip()

OPENAI_NEWS_USER_PROMPT_TEMPLATE = """
Потрібно опрацювати такі новини:
{items}

Поверни JSON у форматі: {{"items":[{{"link":"...","title_uk":"...","summary_uk":"..."}}]}}
""".strip()


def build_openai_messages(items: list[NewsItem]) -> list[dict[str, str]]:
    """Готує messages для одного OpenAI-запиту з усіма новинами запуску."""
    formatted_items = "\n".join(
        (
            f"- Source: {item.source}\n"
            f"  Title: {item.title}\n"
            f"  Link: {item.link}\n"
            f"  Text: {item.description}"
        )
        for item in items
    )
    return [
        {"role": "system", "content": OPENAI_NEWS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": OPENAI_NEWS_USER_PROMPT_TEMPLATE.format(items=formatted_items),
        },
    ]
