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


@router.get("/scheduler")
def scheduler() -> dict[str, object]:
    """
    Stato dello scheduler in-process per il cleanup bundle vecchi.
    Utile per verificare via curl/UI che lo scheduler stia funzionando.
    """
    from app.utili.scheduler import stato_scheduler

    return stato_scheduler()


@router.post("/scheduler/run-now")
def scheduler_run_now() -> dict[str, object]:
    """
    Esegue subito il job di cleanup bundle vecchi, senza aspettare il
    trigger schedulato. Utile per testare manualmente la configurazione,
    o per liberare spazio on-demand.

    Funziona anche se `SCHEDULER_ABILITATO=false`: il job e' una funzione
    pura, lo scheduler ne controlla solo lo schedule.

    Ritorna `{n_cancellati, ids_cancellati[]}` come l'endpoint batch
    `DELETE /api/partite/bundle`.
    """
    from app.configurazione import impostazioni
    from app.servizi.promozione_bundle_servizio import cancella_bundle_vecchi

    risultato = cancella_bundle_vecchi(impostazioni.bundle_cleanup_giorni)
    return {
        "n_cancellati": risultato["n_cancellati"],
        "ids_cancellati": risultato["ids_cancellati"],
        "giorni_soglia": impostazioni.bundle_cleanup_giorni,
    }
