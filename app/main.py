from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI

from app.api.v1.router import router
from app.core.dependencies import settings
from app.logging_config import configure_logging
from app.middlewares.logging import AccessLogMiddleware

configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if not settings.llm_api_key.get_secret_value():
        log.warning("llm_api_key_missing", hint="set LLM_API_KEY in .env")

    app.state.llm_client = AsyncOpenAI(
        base_url=settings.llm_base_url,
        # Local OpenAI-compatible servers (e.g. Ollama) accept any non-empty key
        api_key=settings.llm_api_key.get_secret_value() or "not-set",
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
    )
    log.debug("llm_client_initialized", base_url=settings.llm_base_url, model=settings.llm_model)
    log.info("app_startup_completed", app_name=settings.app_name)

    yield

    log.info("app_shutdown_started")
    await app.state.llm_client.close()
    log.info("app_shutdown_completed")


app = FastAPI(title=settings.app_name, lifespan=lifespan, debug=settings.debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AccessLogMiddleware)

app.include_router(router)
