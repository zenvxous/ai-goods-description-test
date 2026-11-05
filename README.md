# AI helper for preparing product descriptions

A service that takes data about a measuring instrument and, through an LLM (any OpenAI-compatible API), builds a draft product card for a B2B online store: SEO title, SEO description, key specs, search queries and a commercial block.

> 🚧 The project is in progress: so far only the infrastructure is set up, generation is not implemented yet.

## Stack

- Python 3.14, [uv](https://docs.astral.sh/uv/)
- FastAPI + Uvicorn
- `openai` SDK (OpenAI, OpenRouter, Ollama `/v1`, vLLM and other compatible APIs)
- pydantic-settings, structlog

## Quick start

```bash
cp .env.example .env   # fill in LLM_API_KEY (and, if needed, LLM_BASE_URL / LLM_MODEL)
uv sync
uv run uvicorn app.main:app --reload
```

Swagger UI: http://localhost:8000/docs

### Docker

```bash
cp .env.example .env
docker compose up --build
```

The host port is set with `APP_PORT` (default `8000`).

## Configuration

All settings are read from environment variables / `.env` (see `.env.example`). The API key is **not** stored in the code, and `.env` is listed in `.gitignore`.

| Variable | Description |
|---|---|
| `LLM_BASE_URL` | Base URL of an OpenAI-compatible API |
| `LLM_API_KEY` | API key |
| `LLM_MODEL` | Model name |
| `LLM_TEMPERATURE` | Generation temperature |
| `LLM_TIMEOUT`, `LLM_MAX_RETRIES` | Request timeout and number of retries |

## Endpoints

- `GET /api/v1/health/live` — the service is running
- `GET /api/v1/health/ready` — the LLM is reachable and the model exists

## Project structure

```
app/
├── api/v1/routes/   # HTTP endpoints (health, products)
├── core/            # settings and DI
├── exceptions/      # domain exceptions
├── middlewares/     # access log
├── prompts/         # LLM prompts
├── schemas/         # Pydantic models
├── services/        # business logic
├── logging_config.py
└── main.py
examples/            # sample input data and results
tests/
```

## Development

```bash
uv run ruff check .
uv run mypy app
uv run pytest
```
