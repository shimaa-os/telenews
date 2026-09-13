# AI Morning Brief

AI Morning Brief is a Python 3.12 FastAPI automation that collects AI news from RSS feeds, filters the last 24 hours, removes duplicates, ranks the most important stories, asks OpenAI for structured Arabic summaries, and sends the final brief to Telegram every day at 08:00 Africa/Cairo.

The manual API endpoints are useful for health checks, testing Telegram delivery, and triggering a run on demand.

## Architecture

```mermaid
flowchart TD
    A[APScheduler 08:00 Africa/Cairo] --> B[BriefWorkflow]
    C[POST /run-news-brief] --> B
    B --> D[Concurrent RSS collection]
    D --> E[Last 24h filter]
    E --> F[URL and fuzzy title dedupe]
    F --> G[Deterministic ranking 0-10]
    G --> H[Top 5 selection]
    H --> I[OpenAI Responses API structured Arabic summaries]
    I --> J[Telegram message formatter]
    J --> K[Telegram Bot API with 4096 char splitting]
    G --> L[GET /news latest ranked cache]
    M[GET /health] --> N[Scheduler and config status]
```

## What It Does

- Reads multiple RSS feeds from AI labs, technology companies, and technology news sources.
- Keeps only dated articles published inside the configured lookback window, defaulting to 24 hours.
- Deduplicates exact URL matches after removing tracking parameters and near-duplicate titles with fuzzy matching.
- Scores articles from 0 to 10 using deterministic signals: source reliability, major AI entities, model releases, agents, developer impact, safety, regulation, research, recency, and low-quality penalties.
- Selects the top 5 stories by default.
- Sends only the selected article records to OpenAI and requires a Pydantic structured response.
- Formats the brief in Arabic for a Computer Science student focused on AI Engineering and Agentic AI.
- Sends Telegram-safe plain text, splitting messages before Telegram's 4096 character limit.
- Runs daily at 08:00 in `Africa/Cairo` and also supports manual API runs.

## Prompt-Injection Defenses

RSS content is treated as untrusted data. The system prompt explicitly instructs the model to ignore instructions embedded in article titles, descriptions, sources, and URLs. The summarizer sends article data as JSON inside a quoted data block, does not browse, and validates that the model returns exactly one item per selected article index.

The deterministic collection, filtering, deduplication, and ranking happen before any LLM call.

The OpenAI integration uses the Responses API structured-output parser with a Pydantic response model. Reference: https://developers.openai.com/api/docs/guides/structured-outputs

## Project Structure

```text
ai-morning-brief/
  app/
    config/settings.py
    main.py
    models/news.py
    scheduler/daily_job.py
    services/
      ai_summarizer.py
      brief_formatter.py
      news_collector.py
      news_filter.py
      news_ranker.py
      telegram_service.py
    utils/
      deduplication.py
      logging.py
      text_utils.py
  tests/
  Dockerfile
  docker-compose.yml
  requirements.txt
  requirements-dev.txt
  .env.example
```

## Environment Variables

Copy `.env.example` to `.env` and fill in real secrets:

```bash
OPENAI_API_KEY=sk-your-openai-api-key
TELEGRAM_BOT_TOKEN=123456789:telegram-bot-token
TELEGRAM_CHAT_ID=123456789
API_BEARER_TOKEN=change-me-for-manual-endpoints
TIMEZONE=Africa/Cairo
NEWS_LOOKBACK_HOURS=24
MAX_NEWS_ITEMS=5
OPENAI_MODEL=gpt-5-mini
REQUEST_TIMEOUT_SECONDS=20
LOG_LEVEL=INFO
```

`API_BEARER_TOKEN` is optional. If set, `POST /run-news-brief` and `POST /telegram/test` require:

```bash
Authorization: Bearer your-token
```

## Local Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

On macOS/Linux, activate with:

```bash
source .venv/bin/activate
```

## Docker Run

```bash
cp .env.example .env
docker compose up --build
```

The service listens on `http://localhost:8000`.

## API Endpoints

### `GET /health`

Returns scheduler state, next run time, timezone, whether OpenAI and Telegram are configured, and the last workflow result.

```bash
curl http://localhost:8000/health
```

### `POST /run-news-brief`

Runs the complete workflow immediately and sends the brief to Telegram.

```bash
curl -X POST http://localhost:8000/run-news-brief \
  -H "Authorization: Bearer change-me-for-manual-endpoints"
```

### `GET /news`

Returns the latest ranked article cache from the most recent run.

```bash
curl http://localhost:8000/news
```

### `POST /telegram/test`

Sends a short Telegram connectivity test message.

```bash
curl -X POST http://localhost:8000/telegram/test \
  -H "Authorization: Bearer change-me-for-manual-endpoints"
```

## Testing

The test suite avoids real OpenAI, Telegram, and RSS network calls. It uses local fake clients and `httpx.MockTransport`.

```bash
pytest
```

Coverage includes:

- Last-24-hour filtering and missing-date rejection.
- URL tracking removal and fuzzy duplicate matching.
- RSS entry normalization and malformed item rejection.
- Deterministic ranking.
- Telegram message splitting and Bot API payloads.
- OpenAI structured-output integration using a fake client.

## Logging

Logs are emitted as JSON objects with an `event` field so production systems can filter by workflow stage:

- `scheduler_started`
- `news_source_collected`
- `workflow_articles_selected`
- `openai_call_started`
- `telegram_send_succeeded`
- `workflow_finished`

Secrets are never logged.

## Scheduler Behavior

The scheduler uses APScheduler's async scheduler and a Cairo timezone cron trigger:

```text
08:00 every day, Africa/Cairo
```

Only one workflow instance may run at a time. If a manual request overlaps an active scheduled run, the API returns HTTP 409.

## RSS Sources

Default feeds are configured in `app/services/news_collector.py` and include OpenAI, Hugging Face, Google DeepMind, Google AI, Microsoft AI, NVIDIA, TechCrunch AI, The Verge AI, Ars Technica, and MIT Technology Review.

If one source fails or returns malformed XML, the collector logs that source and continues with the remaining feeds.

## Important Limitations

- RSS feed URLs and schemas can change over time; the app is fault tolerant, but source maintenance is normal.
- The app only summarizes the feed title and description, not the full article body.
- Articles without usable publication dates are excluded from the last-24-hour brief.
- Ranking is deterministic and explainable, but still heuristic.
- OpenAI and Telegram secrets are required for a full delivery run.
- The service stores only in-memory latest-news state; restarting the process clears `/news` and `last_result`.
