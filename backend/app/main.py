"""
Entry point dell'applicazione FastAPI.

Avvio:
    uvicorn app.main:app --reload

Documentazione interattiva:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.configurazione import Base, engine, impostazioni
from app.middleware.error_handler import registra_exception_handlers
from app.middleware.request_id import RequestIdMiddleware
from app.routers import (
    aggregazione,
    classifica_club,
    diagnostica,
    esportazione,
    eventi,
    frame,
    health,
    import_bundle,
    import_bundle_mobile,
    inferenze_cv,
    partite,
    raddrizzamento,
    ricostruzione,
    risorse,
    statistiche,
    validazione,
    video,
)
from app.utili.logging_setup import configura_logging


@asynccontextmanager
async def ciclo_vita(_: FastAPI) -> AsyncIterator[None]:
    """
    Lifespan manager: setup all'avvio e teardown allo shutdown.

    Le tabelle sono gestite da Alembic (`alembic upgrade head`).
    In dev, se `auto_create_schema=True`, crea le tabelle automaticamente
    per facilitare i test. In produzione (`auto_create_schema=False`)
    nessun create_all viene eseguito; il deploy deve aver applicato
    le migrazioni prima.
    """
    # Logging strutturato JSON line-per-line (Loki/Datadog/CloudWatch friendly)
    configura_logging(level="INFO")

    # Crea cartella storage video se manca
    impostazioni.storage_video_path.mkdir(parents=True, exist_ok=True)
    impostazioni.storage_frame_path.mkdir(parents=True, exist_ok=True)
    impostazioni.storage_partite_path.mkdir(parents=True, exist_ok=True)

    if impostazioni.auto_create_schema:
        # Modalità dev/test: crea le tabelle se non esistono.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


app = FastAPI(
    title="Risiko Live Review API",
    description=(
        "Backend per la review e validazione di partite Risiko registrate "
        "al club. Riceve eventi dal tablet osservatore e video dall'iPhone, "
        "li allinea via timestamp, e applica il motore regole risiko_engine "
        "per ricostruire la partita ufficiale."
    ),
    version="0.1.0",
    lifespan=ciclo_vita,
)

# CORS per il frontend dev server (Vite su :5173 di default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=impostazioni.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# Request ID middleware: assegna UUID v4 a ogni richiesta, lo propaga via
# context var, lo logga in JSON, lo aggiunge come header sulla response.
app.add_middleware(RequestIdMiddleware)

# Exception handler globale: cattura eccezioni non-HTTPException → 500 JSON
# con `{errore, request_id, tipo}` e header X-Request-ID.
registra_exception_handlers(app)

# Registrazione router
app.include_router(partite.router, prefix=impostazioni.api_prefix)
app.include_router(eventi.router, prefix=impostazioni.api_prefix)
app.include_router(video.router, prefix=impostazioni.api_prefix)
app.include_router(ricostruzione.router, prefix=impostazioni.api_prefix)
app.include_router(risorse.router, prefix=impostazioni.api_prefix)
app.include_router(esportazione.router, prefix=impostazioni.api_prefix)
app.include_router(import_bundle.router, prefix=impostazioni.api_prefix)
app.include_router(import_bundle_mobile.router, prefix=impostazioni.api_prefix)
app.include_router(aggregazione.router, prefix=impostazioni.api_prefix)
app.include_router(statistiche.router, prefix=impostazioni.api_prefix)
app.include_router(validazione.router, prefix=impostazioni.api_prefix)
app.include_router(classifica_club.router, prefix=impostazioni.api_prefix)
app.include_router(frame.router, prefix=impostazioni.api_prefix)
app.include_router(raddrizzamento.router, prefix=impostazioni.api_prefix)
app.include_router(inferenze_cv.router, prefix=impostazioni.api_prefix)
app.include_router(diagnostica.router, prefix=impostazioni.api_prefix)
app.include_router(health.router, prefix=impostazioni.api_prefix)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    """Info base sull'API. Utile per healthcheck."""
    return {
        "nome": "risiko-live-review-api",
        "versione": "0.1.0",
        "docs": "/docs",
    }


@app.get("/healthz", tags=["root"])
async def healthcheck() -> dict[str, str]:
    """Health check semplice. Da estendere con check DB in futuro."""
    return {"status": "ok"}
