"""
Endpoint diagnostici: health check e info versione.

`GET /api/health` — readiness/liveness probe per Railway/uptime monitoring.
`GET /api/version` — info versione + commit hash se disponibile via env var.

Il prefix `/api` viene aggiunto in `app/main.py` tramite `impostazioni.api_prefix`
(coerentemente con gli altri router del backend).
"""
from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["diag"])

_AVVIATO_TIMESTAMP = time.monotonic()


class RispostaHealth(BaseModel):
    status: str
    timestamp: str
    uptime_sec: float


class RispostaVersion(BaseModel):
    version: str
    commit: str | None
    python: str
    fastapi: str


@router.get("/health", response_model=RispostaHealth)
def health() -> RispostaHealth:
    """Probe leggero: ritorna sempre 200 se il processo gira."""
    return RispostaHealth(
        status="ok",
        timestamp=datetime.now(UTC).isoformat(),
        uptime_sec=round(time.monotonic() - _AVVIATO_TIMESTAMP, 2),
    )


@router.get("/version", response_model=RispostaVersion)
def version() -> RispostaVersion:
    import sys

    import fastapi as fastapi_mod

    return RispostaVersion(
        version=os.environ.get("APP_VERSION", "dev"),
        commit=os.environ.get("APP_COMMIT") or None,
        python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        fastapi=fastapi_mod.__version__,
    )
