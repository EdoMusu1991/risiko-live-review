"""
Middleware FastAPI che assegna a ogni richiesta un `request_id` univoco
(UUID v4) e lo propaga via context var per essere incluso nei log
strutturati.

Se la richiesta arriva con header `X-Request-ID`, lo riusa (utile per
trace cross-service). Altrimenti ne genera uno nuovo.

Aggiunge anche `X-Request-ID` alla response per consentire al client di
riferirsi alla richiesta nei bug report.
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import ClassVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utili.logging_setup import (
    imposta_request_id,
    ottieni_logger,
    reset_request_id,
)

log = ottieni_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    HEADER: ClassVar[str] = "X-Request-ID"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get(self.HEADER) or str(uuid.uuid4())
        token = imposta_request_id(rid)
        # salva su request.state per consentire accesso da exception handlers
        # anche dopo che la context var è stata resettata
        request.state.request_id = rid
        try:
            log.info(
                "request inizio",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client": request.client.host if request.client else None,
                },
            )
            response = await call_next(request)
            response.headers[self.HEADER] = rid
            log.info(
                "request fine",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                },
            )
            return response
        except Exception:
            log.exception(
                "request errore",
                extra={"method": request.method, "path": request.url.path},
            )
            raise
        finally:
            reset_request_id(token)
