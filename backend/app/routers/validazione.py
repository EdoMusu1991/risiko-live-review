"""
Endpoint per validare la coerenza degli eventi di una partita.

Diverso da `/ricostruisci`: non applica gli eventi al motore
(non genera lo snapshot), si limita a riportare tutti i problemi
di coerenza in un colpo solo.

Tipico uso UI: l'utente clicca "Verifica" prima di "Ricostruisci"
per vedere se ci sono incoerenze da correggere.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.configurazione import get_sessione_db
from app.modelli import EventoValidato, Partita
from app.schemi.validazione import RisultatoValidazioneCoerenza
from app.servizi.validazione_coerenza_servizio import valida_coerenza

router = APIRouter(prefix="/partite", tags=["validazione"])


@router.get(
    "/{partita_id}/valida-coerenza",
    response_model=RisultatoValidazioneCoerenza,
    summary="Verifica problemi di coerenza degli eventi validati",
)
async def valida_coerenza_partita(
    partita_id: str,
    db: AsyncSession = Depends(get_sessione_db),
) -> RisultatoValidazioneCoerenza:
    """
    Scorre gli `EventoValidato` della partita e ritorna tutti i
    problemi di coerenza rilevati (errori bloccanti + avvisi).

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

    return valida_coerenza(partita, list(partita.giocatori), eventi)
