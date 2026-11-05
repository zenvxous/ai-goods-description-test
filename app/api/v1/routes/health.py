import time
from http import HTTPStatus
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from openai import AsyncOpenAI

from app.core.dependencies import LLMClientDep, settings

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


async def check_llm(llm_client: AsyncOpenAI) -> dict[str, Any]:
    # GET /models/{id} is not supported by every OpenAI-compatible provider (e.g. OpenRouter),
    # so the model is looked up in the list instead
    started = time.perf_counter()
    try:
        page = await llm_client.models.list(timeout=5.0)
        detail = None
        if settings.llm_model not in {model.id for model in page.data}:
            detail = f"Model '{settings.llm_model}' not found"
    except Exception as e:
        detail = str(e)

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    if detail is not None:
        log.error("health_check_failed", check="llm", latency_ms=latency_ms, detail=detail)
        return {"status": "error", "latency_ms": latency_ms, "detail": detail}

    return {"status": "ok", "latency_ms": latency_ms, "model": settings.llm_model}


@router.get("/ready")
async def readiness_check(llm_client: LLMClientDep) -> dict[str, Any]:
    checks = {"llm": await check_llm(llm_client)}

    payload: dict[str, Any] = {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "checks": checks,
    }

    failed_checks = [name for name, result in checks.items() if result["status"] != "ok"]
    if failed_checks:
        payload["status"] = "error"
        log.warning("readiness_check_degraded", failed_checks=failed_checks)
        raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE, detail=payload)

    return payload
