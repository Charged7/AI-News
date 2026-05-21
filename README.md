# AI Telegram News Bot

Automated Telegram news feed that reads RSS sources, summarizes each article with OpenAI, and sends one Telegram message per news item. The current sources are The Verge and Engadget, and RSS handling is multi-source ready.

## What It Does

- Fetches recent articles from RSS sources.
- Remembers sent article links in `data/sent_news.json` and sends only new articles.
- Extracts `title`, `description`, `link`, `image`, `source`, and publication time.
- Uses OpenAI for Ukrainian summaries.
- Fails fast when OpenAI is not configured or summary generation fails.
- Requires an image URL for every article and sends each article through Telegram `sendPhoto`.
- Runs hourly through GitHub Actions without a server.

## Project Structure

```text
.
├── main.py
├── rss.py
├── ai.py
├── telegram.py
├── config.py
├── data/
│   └── sent_news.json
├── requirements.txt
├── .env.example
└── .github/
    └── workflows/
        └── news.yml
```

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a local `.env` from `.env.example` and set:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
OPENAI_API_KEY=...
```

`OPENAI_API_KEY` is required. Without it, the bot exits with an error instead of sending lower-quality local summaries.

## Run Locally

Preview the feed without sending Telegram messages:

```bash
python main.py --dry-run
```

If your OpenAI limit is 3 RPM, keep `OPENAI_REQUEST_DELAY_SECONDS=21` in `.env` so the bot waits between article summaries instead of hitting rate limits.

Send messages for real:

```bash
python main.py
```

Scheduling is controlled by `.github/workflows/news.yml`; the Python script itself sends whenever it is executed.

## GitHub Actions

Add these repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENAI_API_KEY`

Add these repository variables:

- `OPENAI_MODEL`
- `OPENAI_REQUEST_DELAY_SECONDS`
- `OPENAI_RATE_LIMIT_RETRIES`
- `NEWS_LOOKBACK_HOURS`

The workflow runs hourly:

- `0 * * * *`

Use a wider RSS lookback than the hourly schedule so delayed GitHub runs do not miss articles. The sent-news history prevents duplicates:

```text
NEWS_LOOKBACK_HOURS=6
```

After every successful send, the workflow commits `data/sent_news.json` back to the repository. This lets the next hourly run skip links that were already sent.

Manual `workflow_dispatch` runs send immediately.

## Add Another RSS Source

Edit `RSS_SOURCES` in `config.py`:

```python
RSS_SOURCES = [
    RSSSource(name="The Verge", url="https://www.theverge.com/rss/index.xml"),
    RSSSource(name="Engadget", url="https://www.engadget.com/rss.xml"),
    RSSSource(name="Another Source", url="https://example.com/rss.xml"),
]
```

No AI or Telegram logic changes are needed.
