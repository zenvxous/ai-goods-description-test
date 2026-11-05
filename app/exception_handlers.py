from http import HTTPStatus

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions.llm import LLMError, LLMResponseError, LLMTimeoutError, LLMUnavailableError
from app.exceptions.products import InsufficientProductDataError

log = structlog.get_logger(__name__)

_LLM_STATUS: dict[type[LLMError], HTTPStatus] = {
    LLMTimeoutError: HTTPStatus.GATEWAY_TIMEOUT,
    LLMUnavailableError: HTTPStatus.BAD_GATEWAY,
    LLMResponseError: HTTPStatus.BAD_GATEWAY,
}


async def _insufficient_data_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, InsufficientProductDataError)
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"detail": str(exc), "missing_fields": exc.missing_fields},
    )


async def _llm_error_handler(request: Request, exc: Exception) -> JSONResponse:
    status = next(
        (code for cls, code in _LLM_STATUS.items() if isinstance(exc, cls)),
        HTTPStatus.BAD_GATEWAY,
    )
    log.warning("llm_error_response", error=type(exc).__name__, detail=str(exc))
    return JSONResponse(status_code=status, content={"detail": str(exc)})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(InsufficientProductDataError, _insufficient_data_handler)
    app.add_exception_handler(LLMError, _llm_error_handler)
