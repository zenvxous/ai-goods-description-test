import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger("access")

REQUEST_ID_HEADER = "X-Request-ID"


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round((time.perf_counter() - start) * 1000, 2),
            )
            raise
        finally:
            structlog.contextvars.unbind_contextvars("request_id")

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        status = response.status_code

        log_method = log.info
        if 400 <= status < 500:
            log_method = log.warning
        elif status >= 500:
            log_method = log.error

        log_method(
            "request_finished",
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
            status_code=status,
            duration_ms=duration_ms,
            client=request.client.host if request.client else None,
        )

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
