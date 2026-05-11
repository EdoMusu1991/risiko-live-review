"""
Endpoint dashboard: metriche aggregate dell'intero sistema.

Pensato per una schermata "Status" frontend che mostra in colpo d'occhio
lo stato del backend Railway: quante partite, quanti eventi, spazio
occupato, bundle in attesa, ecc.

Tutto in un singolo endpoint per minimizzare round-trip. Risposta typed
con Pydantic, sicura per typecheck frontend.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db, impostazioni
from app.modelli import EventoGrezzo, Partita, Video

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class StatisticheBundle(BaseModel):
    """Statistiche sui bundle in attesa (non ancora promossi)."""

    n_bundle_in_attesa: int
    dimensione_totale_byte: int
    bundle_piu_vecchio_giorni: int | None
    """Eta' in giorni del bundle in attesa piu' vecchio. None se vuoto."""


class StatisticheSpazio(BaseModel):
    """Statistiche occupazione disco del backend."""

    storage_video_byte: int
    storage_frame_byte: int
    storage_partite_byte: int  # bundle non promossi
    totale_byte: int


class StatistichePartite(BaseModel):
    """Statistiche aggregate delle partite SQL (promosse)."""

    n_partite_totali: int
    n_partite_ultimo_mese: int
    n_partite_ultima_settimana: int
    n_eventi_totali: int
    n_video_totali: int
    durata_video_totale_sec: int
    """Somma di tutte le durate dei video (proxy per ore di partita registrate)."""


class StatoServizi(BaseModel):
    """Stato dei servizi interni del backend."""

    scheduler_abilitato: bool
    scheduler_in_esecuzione: bool
    roboflow_configurato: bool
    """True se ROBOFLOW_API_KEY e ROBOFLOW_ENDPOINT sono settati."""


class RispostaDashboard(BaseModel):
    """Risposta completa dell'endpoint /dashboard/sommario."""

    partite: StatistichePartite
    bundle: StatisticheBundle
    spazio: StatisticheSpazio
    servizi: StatoServizi
    timestamp: str


def _calcola_dimensione_directory(path: Path) -> int:
    """Somma ricorsiva delle dimensioni di tutti i file in una directory."""
    if not path.exists():
        return 0
    totale = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                with contextlib.suppress(OSError, FileNotFoundError):
                    totale += f.stat().st_size
    except (OSError, PermissionError):
        pass
    return totale


def _bundle_in_attesa_stats(base: Path) -> StatisticheBundle:
    """Calcola statistiche sui bundle non promossi in storage_partite_path."""
    if not base.exists():
        return StatisticheBundle(
            n_bundle_in_attesa=0,
            dimensione_totale_byte=0,
            bundle_piu_vecchio_giorni=None,
        )

    n = 0
    dim_totale = 0
    ts_piu_vecchio: datetime | None = None

    for sub in base.iterdir():
        if not sub.is_dir():
            continue
        manifest = sub / "manifest.json"
        if not manifest.exists():
            continue
        n += 1
        dim_totale += _calcola_dimensione_directory(sub)
        # Usa mtime del manifest come proxy per la data di creazione
        try:
            mtime = datetime.fromtimestamp(manifest.stat().st_mtime, tz=UTC)
            if ts_piu_vecchio is None or mtime < ts_piu_vecchio:
                ts_piu_vecchio = mtime
        except OSError:
            pass

    eta_giorni: int | None = None
    if ts_piu_vecchio is not None:
        eta_giorni = (datetime.now(UTC) - ts_piu_vecchio).days

    return StatisticheBundle(
        n_bundle_in_attesa=n,
        dimensione_totale_byte=dim_totale,
        bundle_piu_vecchio_giorni=eta_giorni,
    )


@router.get(
    "/sommario",
    response_model=RispostaDashboard,
    summary="Sommario globale del sistema (per dashboard)",
)
async def sommario_dashboard(
    db: AsyncSession = Depends(get_sessione_db),
) -> RispostaDashboard:
    """
    Ritorna un sommario aggregato di tutte le metriche utili per una
    dashboard di stato:

    - **partite**: counts e durata totale dalle Partite SQL promosse
    - **bundle**: statistiche sui bundle non promossi (`storage_partite/`)
    - **spazio**: occupazione disco delle 3 cartelle storage
    - **servizi**: stato scheduler e configurazione Roboflow
    """
    # === Partite SQL ===
    ora = datetime.now(UTC)
    settimana_fa = ora - timedelta(days=7)
    mese_fa = ora - timedelta(days=30)

    n_partite = (
        await db.execute(select(func.count()).select_from(Partita))
    ).scalar_one()

    n_partite_mese = (
        await db.execute(
            select(func.count())
            .select_from(Partita)
            .where(Partita.data_creazione >= mese_fa)
        )
    ).scalar_one()

    n_partite_settimana = (
        await db.execute(
            select(func.count())
            .select_from(Partita)
            .where(Partita.data_creazione >= settimana_fa)
        )
    ).scalar_one()

    n_eventi = (
        await db.execute(select(func.count()).select_from(EventoGrezzo))
    ).scalar_one()

    n_video = (
        await db.execute(select(func.count()).select_from(Video))
    ).scalar_one()

    durata_totale = (
        await db.execute(select(func.coalesce(func.sum(Video.durata_sec), 0)))
    ).scalar_one()

    stats_partite = StatistichePartite(
        n_partite_totali=int(n_partite or 0),
        n_partite_ultimo_mese=int(n_partite_mese or 0),
        n_partite_ultima_settimana=int(n_partite_settimana or 0),
        n_eventi_totali=int(n_eventi or 0),
        n_video_totali=int(n_video or 0),
        durata_video_totale_sec=int(durata_totale or 0),
    )

    # === Bundle non promossi ===
    stats_bundle = _bundle_in_attesa_stats(impostazioni.storage_partite_path)

    # === Spazio disco ===
    dim_video = _calcola_dimensione_directory(impostazioni.storage_video_path)
    dim_frame = _calcola_dimensione_directory(impostazioni.storage_frame_path)
    dim_partite = stats_bundle.dimensione_totale_byte
    stats_spazio = StatisticheSpazio(
        storage_video_byte=dim_video,
        storage_frame_byte=dim_frame,
        storage_partite_byte=dim_partite,
        totale_byte=dim_video + dim_frame + dim_partite,
    )

    # === Stato servizi ===
    from app.utili.scheduler import stato_scheduler

    sched_info = stato_scheduler()
    stato_servizi = StatoServizi(
        scheduler_abilitato=bool(sched_info.get("abilitato")),
        scheduler_in_esecuzione=bool(sched_info.get("in_esecuzione")),
        roboflow_configurato=bool(
            impostazioni.roboflow_api_key and impostazioni.roboflow_endpoint
        ),
    )

    return RispostaDashboard(
        partite=stats_partite,
        bundle=stats_bundle,
        spazio=stats_spazio,
        servizi=stato_servizi,
        timestamp=ora.isoformat(),
    )
