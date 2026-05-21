# AI Telegram News Bot

Automated Telegram news feed that reads RSS sources, summarizes each article, and sends one Telegram message per news item. The current sources are The Verge and Engadget, and RSS handling is multi-source ready.

## What It Does

- Fetches all articles from the last 24 hours.
- Extracts `title`, `description`, `link`, `image`, `source`, and publication time.
- Uses OpenAI for Ukrainian summaries when `OPENAI_API_KEY` is configured.
- Falls back to a simple local summary when AI is not configured or fails.
- Sends each article individually:
  - `sendPhoto` when an image URL exists.
  - `sendMessage` when no image is available.
- Runs daily through GitHub Actions without a server.

## Project Structure

```text
.
├── main.py
├── rss.py
├── ai.py
├── telegram.py
├── config.py
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

`OPENAI_API_KEY` is optional. Without it, the bot still works with fallback summaries based on the RSS text. OpenAI summaries are generated in Ukrainian; fallback summaries keep the source text language.

## Run Locally

Preview the feed without sending Telegram messages:

```bash
python main.py --dry-run
```

Preview without OpenAI API calls:

```bash
python main.py --dry-run --no-ai
```

Preview with AI required for every article:

```bash
python main.py --dry-run --require-ai
```

If your OpenAI limit is 3 RPM, keep `OPENAI_REQUEST_DELAY_SECONDS=21` in `.env` so the bot waits between article summaries instead of falling back.

Send messages for real:

```bash
python main.py
```

Run in scheduled mode locally:

```bash
python main.py --scheduled
```

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

The workflow uses a simple UTC schedule:

- `0 6 * * *`
- `0 18 * * *`

In Kyiv summer time, that is 09:00 and 21:00. In Kyiv winter time, it runs one hour earlier.

For a 12-hour feed cadence, set this GitHub variable:

```text
NEWS_LOOKBACK_HOURS=12
```

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
