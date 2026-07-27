# GitHub Actions production

Проєкт повністю запускається у GitHub Actions. Production-конфігурація,
розклад, secrets, logs і runtime state зосереджені в GitHub.

## Secrets

GitHub repository:

`Settings -> Secrets and variables -> Actions -> Secrets`

Обов'язкові repository secrets:

- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_CHAT_ID`;
- `OPENAI_API_KEY`.

Workflow перевіряє кожен secret перед запуском і завершується з чіткою помилкою,
якщо значення відсутнє.

## Variables

Необов'язкові repository variables:

- `OPENAI_MODEL`, default `gpt-4o-mini`;
- `OPENAI_SUMMARY_BATCH_SIZE`, default `4`;
- `OPENAI_SUMMARY_MAX_TOKENS`, default `4000`;
- `OPENAI_RELEVANCE_BATCH_SIZE`, default `6`;
- `OPENAI_RELEVANCE_MAX_TOKENS`, default `5000`;
- `OPENAI_RELEVANCE_RETRY_MISSING_LIMIT`, default `0`;
- `NEWS_LOOKBACK_HOURS`, default `6`;
- `NEWS_MIN_RELEVANCE_SCORE`, default `70`;
- `NEWS_MAX_CANDIDATES_PER_RUN`, default `36`;
- `NEWS_MAX_ITEMS_PER_RUN`, default `5`;
- `SENT_NEWS_RETENTION_DAYS`, default `30`.

## Автоматичний запуск

Workflow `.github/workflows/news.yml` працює щогодини:

```text
23 * * * *
```

Cron використовує UTC. Scheduled run завжди бере останній commit із default
branch `main`.

## Ручний запуск

1. Відкрити GitHub repository.
2. Перейти в `Actions`.
3. Вибрати `Hourly Personalized News`.
4. Натиснути `Run workflow`.
5. Вибрати branch `main`.

Успішний job `send-news` містить кроки:

1. `Checkout`;
2. `Set up Python`;
3. `Restore news state`;
4. `Install dependencies`;
5. `Validate required secrets`;
6. `Send personalized news`;
7. `Save news state`.

## SQLite state

`data/newsbot.db` не комітиться в repository. Перед cron-циклом workflow
відновлює останній `newsbot-state-*` із GitHub Actions Cache, після циклу
зберігає новий immutable cache.

Якщо cache відсутній або був видалений:

- база створюється автоматично;
- імпортується доступний `data/sent_news.json`;
- RSS-вікно тимчасово обмежується двома годинами;
- за перший цикл надсилається максимум три новини.

Це зменшує ризик повторної масової відправки після втрати cache.

## Push у main

Push не надсилає новини. Він запускає job `test`, який:

1. встановлює Python 3.12;
2. встановлює `requirements.txt`;
3. запускає всі `unittest`.

Якщо push-тести пройшли, наступний scheduled run автоматично використовує
оновлений код із `main`.

## Типові помилки

`Repository secret ... is not configured.`

- Додати відсутній secret у repository settings.

`No cached SQLite state found; using safe first-run limits.`

- Це notice, а не помилка. Workflow створить нову базу.

`AI relevance classification failed.`

- Перевірити `OPENAI_API_KEY`, quota, model access і логи OpenAI request.

`Telegram sending failed.`

- Перевірити `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` і доступ бота до чату.

Scheduled workflow не з'являється:

- workflow має бути в `main`;
- GitHub Actions мають бути enabled;
- public repository може автоматично вимкнути schedule після тривалої
  відсутності activity.
