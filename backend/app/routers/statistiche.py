"""
Endpoint per le statistiche aggregate di una partita.

Ritorna metriche derivate dagli `EventoValidato`:
- Per giocatore: attacchi, conquiste, carte, tris, perdite/vincite armate
- Globali: durata, numero turni, numero attacchi totali

Le statistiche sono calcolate al volo (non persistite). Performance:
con 1000 eventi il calcolo è in millisecondi (è solo iterazione +
aggregazione).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.configurazione import get_sessione_db
from app.modelli import EventoValidato, Partita
from app.schemi.statistiche import StatistichePartita
from app.servizi.statistiche_partita_servizio import (
    calcola_statistiche,
    derivare_difensori_per_evento,
)

router = APIRouter(prefix="/partite", tags=["statistiche"])


@router.get(
    "/{partita_id}/statistiche",
    response_model=StatistichePartita,
    summary="Statistiche aggregate della partita",
)
async def statistiche_partita(
    partita_id: str,
    db: AsyncSession = Depends(get_sessione_db),
) -> StatistichePartita:
    """
    Calcola e ritorna le statistiche della partita basate sugli
    `EventoValidato` esistenti.

    Errori:
    - **404**: partita non trovata
    """
    partita = await db.get(
        Partita,
        partita_id,
        options=[selectinload(Partita.giocatori)],
    )
    if partita is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partita {partita_id} non trovata",
        )

    risultato = await db.execute(
        select(EventoValidato)
        .where(EventoValidato.partita_id == partita_id)
        .order_by(EventoValidato.ts_evento)
    )
    eventi = list(risultato.scalars())

    # Deriva i difensori (giocatore che possedeva il territorio
    # attaccato al momento dell'attacco) usando il motore di gioco.
    # Best-effort: se la partita ha errori, le difese saranno parziali.
    difensori = derivare_difensori_per_evento(partita, eventi)

    return calcola_statistiche(
        partita,
        list(partita.giocatori),
        eventi,
        difensori_per_evento=difensori,
    )
