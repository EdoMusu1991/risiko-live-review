"""
Endpoint API per la ricostruzione partita.

Due endpoint:
- `POST /api/partite/{id}/ricostruisci`: rigenera lo snapshot dello stato.
- `GET  /api/partite/{id}/stato-finale`: ritorna lo snapshot corrente.

La ricostruzione è idempotente: ogni `POST` sovrascrive lo snapshot
precedente. Errori di applicazione di singoli eventi NON fanno fallire
l'endpoint — vengono raccolti nella lista `errori` della risposta.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db
from app.modelli import StatoPartitaRicostruito
from app.schemi import (
    ErroreRicostruzioneSchema,
    RisultatoRicostruzione,
    StatoPartitaSnapshot,
)
from app.servizi import (
    PartitaInesistenteError,
    ServizioRicostruzione,
)

router = APIRouter(prefix="/partite/{partita_id}", tags=["ricostruzione"])


@router.post(
    "/ricostruisci",
    response_model=RisultatoRicostruzione,
    summary="Ricostruisce lo stato partita applicando gli eventi validati",
)
async def ricostruisci_partita(
    partita_id: str,
    db: AsyncSession = Depends(get_sessione_db),
) -> RisultatoRicostruzione:
    """
    Carica tutti gli eventi validati della partita, li applica al motore
    `risiko_engine` in ordine cronologico, e salva uno snapshot dello
    stato finale.

    Se uno o più eventi falliscono (es. azione illegale, payload malformato),
    vengono saltati e segnalati nella lista `errori`. La ricostruzione
    prosegue con gli eventi successivi.

    L'endpoint è idempotente: ogni chiamata sostituisce lo snapshot
    precedente. Chiamare ripetutamente senza modificare gli eventi produce
    sempre lo stesso risultato.
    """
    try:
        snapshot = await ServizioRicostruzione.ricostruisci(db, partita_id)
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e

    return _serializza_snapshot(snapshot)


@router.get(
    "/stato-finale",
    response_model=RisultatoRicostruzione,
    summary="Ritorna lo stato corrente ricostruito della partita",
    responses={
        404: {"description": "Partita inesistente o nessuna ricostruzione fatta"},
    },
)
async def get_stato_finale(
    partita_id: str,
    db: AsyncSession = Depends(get_sessione_db),
) -> RisultatoRicostruzione:
    """
    Ritorna l'ultimo snapshot ricostruito della partita.

    Se la partita non è mai stata ricostruita, ritorna 404 con messaggio
    chiaro. In quel caso il client deve prima chiamare
    `POST /partite/{id}/ricostruisci`.
    """
    try:
        snapshot = await ServizioRicostruzione.trova_snapshot(db, partita_id)
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e

    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Nessuna ricostruzione disponibile per la partita "
                f"'{partita_id}'. Esegui prima POST /partite/{partita_id}/ricostruisci"
            ),
        )

    return _serializza_snapshot(snapshot)


# === Helper ===


def _serializza_snapshot(
    snapshot: StatoPartitaRicostruito,
) -> RisultatoRicostruzione:
    """Converte un `StatoPartitaRicostruito` ORM in `RisultatoRicostruzione`."""
    stato_finale: StatoPartitaSnapshot | None
    if snapshot.stato_serializzato is not None:
        stato_finale = StatoPartitaSnapshot.model_validate(
            snapshot.stato_serializzato
        )
    else:
        stato_finale = None

    errori = [ErroreRicostruzioneSchema.model_validate(e) for e in snapshot.errori]

    return RisultatoRicostruzione(
        partita_id=snapshot.partita_id,
        successo=snapshot.successo,
        n_eventi_totali=snapshot.n_eventi_totali,
        n_eventi_applicati=snapshot.n_eventi_applicati,
        n_errori=len(errori),
        errori=errori,
        stato_finale=stato_finale,
        data_ricostruzione=snapshot.data_ricostruzione,
    )
