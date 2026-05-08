"""
Endpoint API per la gestione partite.

Pattern:
- Router per dominio (uno per Partita).
- Dependency injection della sessione DB tramite `get_sessione_db`.
- Eccezioni di dominio mappate a HTTPException con status code appropriato.
- Schemi Pydantic per request/response (validazione automatica).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db
from app.modelli import StatoReview
from app.routers.video import get_servizio_video
from app.schemi import (
    PartitaAggiornamento,
    PartitaCreazione,
    PartitaLetturaDettaglio,
    PartitaLetturaSommario,
    SetupAutomaticoRichiesta,
    SetupAutomaticoRisposta,
)
from app.servizi import (
    ColoriDuplicatiError,
    NumeroGiocatoriNonSupportatoError,
    OrdineSedutaInvalidoError,
    PartitaInesistenteError,
    ServizioPartita,
    ServizioSetupAutomatico,
    ServizioVideo,
    SetupGiaPresenteError,
)

router = APIRouter(prefix="/partite", tags=["partite"])


@router.post(
    "",
    response_model=PartitaLetturaDettaglio,
    status_code=status.HTTP_201_CREATED,
    summary="Crea una nuova partita",
)
async def crea_partita(
    dati: PartitaCreazione,
    db: AsyncSession = Depends(get_sessione_db),
) -> PartitaLetturaDettaglio:
    """
    Crea una nuova partita Risiko con i suoi giocatori.

    La partita parte in stato `GREZZA`. Eventi e video possono essere
    aggiunti tramite gli endpoint dedicati.
    """
    try:
        partita = await ServizioPartita.crea(db, dati)
    except (ColoriDuplicatiError, OrdineSedutaInvalidoError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return PartitaLetturaDettaglio.model_validate(partita)


@router.get(
    "",
    response_model=list[PartitaLetturaSommario],
    summary="Lista partite",
)
async def lista_partite(
    offset: int = Query(default=0, ge=0),
    limite: int = Query(default=50, ge=1, le=200),
    stato: StatoReview | None = Query(default=None),
    db: AsyncSession = Depends(get_sessione_db),
) -> list[PartitaLetturaSommario]:
    """
    Ritorna l'elenco delle partite, paginato e ordinato per data_inizio
    decrescente. Filtrabile per stato di review.
    """
    partite = await ServizioPartita.lista(db, offset=offset, limite=limite, stato=stato)
    return [PartitaLetturaSommario.model_validate(p) for p in partite]


@router.get(
    "/{partita_id}",
    response_model=PartitaLetturaDettaglio,
    summary="Dettaglio partita",
)
async def get_partita(
    partita_id: str,
    db: AsyncSession = Depends(get_sessione_db),
) -> PartitaLetturaDettaglio:
    """Ritorna una partita con giocatori e video."""
    try:
        partita = await ServizioPartita.trova_per_id(db, partita_id)
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return PartitaLetturaDettaglio.model_validate(partita)


@router.patch(
    "/{partita_id}",
    response_model=PartitaLetturaDettaglio,
    summary="Aggiorna metadata partita",
)
async def aggiorna_partita(
    partita_id: str,
    dati: PartitaAggiornamento,
    db: AsyncSession = Depends(get_sessione_db),
) -> PartitaLetturaDettaglio:
    """
    Aggiorna i metadati di una partita.

    Solo i campi presenti nel body verranno modificati. Per cambiare
    i giocatori serve un endpoint dedicato (TBD).
    """
    try:
        partita = await ServizioPartita.aggiorna(db, partita_id, dati)
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return PartitaLetturaDettaglio.model_validate(partita)


@router.delete(
    "/{partita_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina partita",
)
async def elimina_partita(
    partita_id: str,
    db: AsyncSession = Depends(get_sessione_db),
    servizio_video: ServizioVideo = Depends(get_servizio_video),
) -> None:
    """
    Elimina una partita e tutti gli eventi associati.

    Pulisce anche i file video sul filesystem (oltre ai record DB
    eliminati via CASCADE).
    """
    try:
        await ServizioPartita.elimina(db, partita_id, servizio_video=servizio_video)
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/{partita_id}/setup-automatico",
    response_model=SetupAutomaticoRisposta,
    status_code=status.HTTP_201_CREATED,
    summary="Setup automatico della partita",
)
async def setup_automatico(
    partita_id: str,
    richiesta: SetupAutomaticoRichiesta | None = None,
    db: AsyncSession = Depends(get_sessione_db),
) -> SetupAutomaticoRisposta:
    """
    Genera automaticamente gli eventi di setup (territori + obiettivi +
    partita_inizio) applicando le regole Risiko EG:

    - 42 territori distribuiti round-robin tra i giocatori
    - Armate iniziali: 40/35/30/25/20 a giocatore secondo numero giocatori (2/3/4/5/6)
    - Un obiettivo random distinto per giocatore
    - Partita iniziata con `primo_giocatore_id` (default: ordine_seduta=1)

    L'operazione è atomica e fallisce se la partita ha già eventi
    validati. Per rigenerare il setup, eliminare prima gli eventi esistenti.
    """
    parametri = richiesta or SetupAutomaticoRichiesta()
    try:
        risultato = await ServizioSetupAutomatico.genera(
            db,
            partita_id,
            primo_giocatore_id=parametri.primo_giocatore_id,
            seed=parametri.seed,
        )
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except SetupGiaPresenteError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from e
    except NumeroGiocatoriNonSupportatoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    return SetupAutomaticoRisposta(
        n_territori_assegnati=risultato.n_territori_assegnati,
        n_obiettivi_assegnati=risultato.n_obiettivi_assegnati,
        primo_giocatore_id=risultato.primo_giocatore_id,
        armate_per_giocatore=risultato.armate_per_giocatore,
        seed_usato=risultato.seed_usato,
    )
