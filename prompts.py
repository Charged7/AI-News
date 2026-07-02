"""Prompt templates for OpenAI news summaries."""

import re

from rss import NewsItem

SUMMARY_TEXT_MAX_CHARS = 900

# OPENAI_NEWS_SYSTEM_PROMPT = """
# Ти редактор новинної стрічки.
# Для кожної новини переклади заголовок українською та створи короткий summary українською в 1-4 речення.
# Збережи порядок новин.
# Не вигадуй фактів. Не додавай жодних emoji, нумерацію, посилання, дати, зображення чи додаткові коментарі.
# Поверни тільки валідний JSON без markdown.
# Формат відповіді:
# {"items":[{"id":"item_1","link":"...","title_uk":"...","summary_uk":"...", "event_key": "earthquake venezuela caracas"}]}
# """.strip()

OPENAI_NEWS_SYSTEM_PROMPT = """
Ти редактор новинної стрічки.

Для кожної новини:
1. Переклади заголовок українською.
2. Створи короткий summary українською в 1-4 речення.
3. Створи event_key — короткий канонічний опис події англійською мовою, 3-10 слів, без розділових знаків.

Приклади event_key:
- earthquake venezuela caracas
- trump iran talks
- wildfire california
- plane crash india

Поверни тільки валідний JSON.

Формат:
{
  "items":[
    {
      "id":"item_1",
      "link":"...",
      "title_uk":"...",
      "summary_uk":"...",
      "event_key":"..."
    }
  ]
}
"""

OPENAI_NEWS_USER_PROMPT_TEMPLATE = """
Потрібно опрацювати такі новини:

{items}

Для кожного input ID поверни рівно один JSON object.

Поверни JSON у форматі:
{
  "items":[
    {
      "id":"item_1",
      "link":"...",
      "title_uk":"...",
      "summary_uk":"...",
      "event_key":"..."
    }
  ]
}
""".strip()

def build_openai_messages(items: list[NewsItem]) -> list[dict[str, str]]:
    """Build messages for one OpenAI summary request."""
    formatted_items = "\n".join(
        (
            f"- ID: item_{index + 1}\n"
            f"  Source: {item.source}\n"
            f"  Title: {_truncate_text(item.title, 220)}\n"
            f"  Link: {item.link}\n"
            f"  Text: {_truncate_text(item.description, SUMMARY_TEXT_MAX_CHARS)}"
        )
        for index, item in enumerate(items)
    )
    return [
        {"role": "system", "content": OPENAI_NEWS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": OPENAI_NEWS_USER_PROMPT_TEMPLATE.format(items=formatted_items),
        },
    ]


def _truncate_text(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
