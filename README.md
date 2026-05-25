# AI Telegram News Bot

Автоматизований Telegram-бот, який читає RSS-джерела, збирає нові статті за заданий проміжок часу, робить один batch-запит до OpenAI для перекладу заголовків і коротких summary, а потім надсилає **окрему картку для кожної новини**. Поточні джерела: The Verge, Engadget, 9to5Mac, AppleInsider News і TechCrunch.

## Що робить проєкт

- читає кілька RSS-джерел за один запуск;
- зберігає вже надіслані посилання в `data/sent_news.json` і не дублює їх;
- бере `title`, `description`, `link`, `image`, `source` і час публікації;
- використовує один OpenAI batch-запит для всіх новин запуску;
- формує окрему Telegram-картку для кожної новини;
- якщо картинка для новини не підходить, автоматично падає назад на текст;
- запускається без сервера через GitHub Actions.

## Структура проєкту

```text
.
├── main.py
├── rss.py
├── ai.py
├── prompts.py
├── telegram.py
├── config.py
├── sent_news.py
├── data/
│   └── sent_news.json
├── tests/
├── requirements.txt
├── .env.example
└── .github/
    └── workflows/
        └── news.yml
```

## Налаштування

Встанови залежності:

```bash
pip install -r requirements.txt
```

Створи локальний `.env` на основі `.env.example` і заповни змінні:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
OPENAI_API_KEY=...
```

`OPENAI_API_KEY` обов’язковий. Без нього бот завершується з помилкою.

## Запуск локально

Щоб надіслати картки новин вручну:

```bash
python main.py
```

Якщо хочеш подивитися ширший період новин, можна змінити lookback:

```bash
python main.py --lookback-hours 48
```

Окремого зведеного повідомлення більше немає. Кожна новина йде окремою карткою.

## GitHub Actions

Додай секрети в репозиторій:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENAI_API_KEY`

Додай змінні репозиторію:

- `OPENAI_MODEL`
- `OPENAI_RATE_LIMIT_RETRIES`
- `NEWS_LOOKBACK_HOURS`

Workflow запускається щогодини:

```text
7,22,37,52 * * * *
```

Щоб не втрачати новини через затримки RSS або GitHub schedule, залишай `NEWS_LOOKBACK_HOURS=24`, а історія відправок у `data/sent_news.json` прибирає дублікати.

Після успішної відправки workflow комітить оновлений `data/sent_news.json` назад у репозиторій. Це дозволяє наступному запуску пропускати вже надіслані лінки.

`workflow_dispatch` теж увімкнений, тож картки можна запускати вручну.

## Додавання нового RSS

Відкрий `config.py` і додай нове джерело в `RSS_SOURCES`:

```python
RSS_SOURCES = [
    RSSSource(name="The Verge", url="https://www.theverge.com/rss/index.xml"),
    RSSSource(name="Engadget", url="https://www.engadget.com/rss.xml"),
    RSSSource(name="9to5Mac", url="https://9to5mac.com/feed/"),
    RSSSource(name="AppleInsider News", url="https://appleinsider.com/rss/news/"),
    RSSSource(name="TechCrunch", url="https://techcrunch.com/feed/"),
    RSSSource(name="New Source", url="https://example.com/rss.xml"),
]
```

Після цього логіка AI та Telegram не потребує змін.
