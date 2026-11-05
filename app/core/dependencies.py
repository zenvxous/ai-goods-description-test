from functools import lru_cache
from typing import Annotated, cast

from fastapi import Depends, Request
from openai import AsyncOpenAI

from app.core.config import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def get_llm_client(request: Request) -> AsyncOpenAI:
    return cast(AsyncOpenAI, request.app.state.llm_client)


LLMClientDep = Annotated[AsyncOpenAI, Depends(get_llm_client)]
