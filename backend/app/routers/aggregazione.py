"""
Endpoint per generare proposte di aggregazione di eventi BLE.

L'utente, dopo aver caricato un bundle dall'app mobile, chiama questo
endpoint per ottenere proposte di `attacco_risolto` candidati che
raggruppano i singoli eventi `dado_lanciato` BLE.

Le proposte vengono mostrate nel frontend di review: l'utente le
accetta (con territori e giocatore aggiunti) o le rifiuta.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db
from app.modelli import EventoValidato, Partita
from app.schemi.aggregazione import (
    AccettaProposta,
    RisultatoAggregazione,
)
from app.schemi.partita import EventoValidatoLettura
from app.servizi.aggregazione_dadi_servizio import (
    SOGLIA_GAP_DEFAULT_SECONDI,
    EventoGiaValidatoError,
    EventoGrezzoInesistenteError,
    EventoNonAggregabileError,
    EventoNonAppartenentePartitaError,
    GiocatoreInesistentePartitaError,
    PartitaInesistenteError,
    ServizioAggregazioneDadi,
)

router = APIRouter(prefix="/partite", tags=["aggregazione"])


@router.post(
    "/{partita_id}/proponi-aggregazioni-dadi",
    response_model=RisultatoAggregazione,
    summary="Proponi aggregazioni di eventi BLE → attacchi risolti",
)
async def proponi_aggregazioni_dadi(
    partita_id: str,
    soglia_gap_secondi: float = Query(
        default=SOGLIA_GAP_DEFAULT_SECONDI,
        gt=0.0,
        le=60.0,
        description=(
            "Gap massimo (secondi) tra eventi BLE consecutivi perché "
            "siano considerati parte dello stesso lancio. Default 3s. "
            "Aumenta se i lanci sono lenti, riduci se attacchi rapidi "
            "vengono fusi a torto."
        ),
    ),
    db: AsyncSession = Depends(get_sessione_db),
) -> RisultatoAggregazione:
    """
    Ritorna la lista di proposte di `attacco_risolto` candidati,
    raggruppando gli eventi grezzi `DADI_LANCIATI` con `fonte=DADO_BLE`
    non ancora validati per finestra temporale.

    Le proposte includono solo i dadi (estratti dal BLE). I campi
    mancanti per creare un evento validato finale (`giocatore_id`,
    `da`, `a`) devono essere forniti dal frontend in fase di accettazione.

    L'endpoint è **idempotente**: ricalcolare le proposte sugli stessi
    eventi grezzi produce lo stesso risultato. Una volta validati
    (creando un `EventoValidato` collegato), gli eventi grezzi smettono
    di apparire nelle proposte successive.
    """
    # Verifica che la partita esista (errore esplicito invece di
    # ritornare un risultato vuoto silenzioso).
    partita = await db.get(Partita, partita_id)
    if partita is None:
        # Doppio check via query in caso di session caching anomalo
        result = await db.execute(
            select(Partita).where(Partita.id == partita_id)
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Partita {partita_id} non trovata",
            )

    servizio = ServizioAggregazioneDadi(soglia_gap_secondi=soglia_gap_secondi)
    return await servizio.proponi_aggregazioni(db, partita_id)


@router.post(
    "/{partita_id}/accetta-aggregazione-dadi",
    response_model=EventoValidatoLettura,
    status_code=status.HTTP_201_CREATED,
    summary="Accetta una proposta di aggregazione → crea EventoValidato",
)
async def accetta_aggregazione_dadi(
    partita_id: str,
    proposta: AccettaProposta,
    db: AsyncSession = Depends(get_sessione_db),
) -> EventoValidato:
    """
    Promuove una proposta di aggregazione a `EventoValidato` di tipo
    `ATTACCO_RISOLTO`.

    Effetti collaterali:
    - Crea un nuovo `EventoValidato` con i dati validati.
    - Marca tutti gli `EventoGrezzo` citati come `validato=True` (così
      non riappaiono nelle proposte successive).
    - Lega l'`EventoValidato` al primo evento grezzo del cluster come
      "rappresentante" (per audit). Gli altri eventi sono solo marcati
      consumati senza FK.

    Errori:
    - **404**: partita o evento grezzo non trovato
    - **400**: evento già validato, evento di altro tipo/fonte, evento
      di un'altra partita, giocatore non appartenente alla partita
    """
    servizio = ServizioAggregazioneDadi()
    try:
        evento_validato = await servizio.accetta_proposta(
            db, partita_id, proposta
        )
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except EventoGrezzoInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except (
        EventoGiaValidatoError,
        EventoNonAggregabileError,
        EventoNonAppartenentePartitaError,
        GiocatoreInesistentePartitaError,
    ) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    await db.commit()
    return evento_validato
