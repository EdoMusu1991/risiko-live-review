"""
Exception handler globale per catturare eccezioni non gestite e ritornare
una response 500 JSON con request_id.

Si registra con `registra_exception_handlers(app)`.

Implementato come `@app.exception_handler(Exception)` (FastAPI/Starlette
nativo) invece che middleware perché `BaseHTTPMiddleware` ha problemi
noti con la propagazione di eccezioni dentro `call_next`.

Per l'ordering: questo handler cattura solo eccezioni che bubble fuori
dalle route. RequestIdMiddleware è ancora attivo a quel punto (la sua
context var resta settata fino al `finally`), quindi `ottieni_request_id`
ritorna il valore corretto.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.utili.logging_setup import ottieni_logger, ottieni_request_id

log = ottieni_logger(__name__)


async def gestore_eccezione_generica(request: Request, exc: Exception) -> JSONResponse:
    log.exception(
        "errore non gestito",
        extra={"path": request.url.path, "method": request.method},
    )
    # context var potrebbe essere già stata resettata dal middleware finally;
    # fallback su request.state.request_id che persiste
    rid = ottieni_request_id() or getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=500,
        content={
            "errore": "errore interno del server",
            "request_id": rid,
            "tipo": type(exc).__name__,
        },
        headers={"X-Request-ID": rid} if rid else {},
    )


def registra_exception_handlers(app: FastAPI) -> None:
    """Registra il gestore globale sull'app FastAPI."""
    app.add_exception_handler(Exception, gestore_eccezione_generica)
