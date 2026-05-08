"""
Endpoint per la classifica del club: aggregazione cross-partita di
tutte le statistiche dei giocatori.

A differenza di `/partite/{id}/statistiche` (singola partita), questo
endpoint scorre TUTTE le partite del DB e produce una vista
"stagionale" del club.

Costo computazionale: O(N_partite x N_eventi). Per club con poche
centinaia di partite è OK (sotto il secondo). Quando crescerà andrà
introdotto caching/pre-aggregazione.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db
from app.schemi.classifica_club import ClassificaClub
from app.servizi.classifica_club_servizio import calcola_classifica_club

router = APIRouter(prefix="/club", tags=["club"])


@router.get(
    "/classifica",
    response_model=ClassificaClub,
    summary="Classifica club aggregata cross-partita",
)
async def classifica_club(
    db: AsyncSession = Depends(get_sessione_db),
) -> ClassificaClub:
    """
    Aggrega le statistiche di TUTTE le partite del DB per nome
    giocatore (case-insensitive). Ritorna la lista giocatori ordinata
    per bilancio armate decrescente, più totali aggregati del club.
    """
    return await calcola_classifica_club(db)
