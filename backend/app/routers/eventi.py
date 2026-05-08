"""
Endpoint API per gestione eventi (grezzi e validati).

Gli eventi sono sempre legati a una partita: tutti gli endpoint sono
nested sotto `/partite/{partita_id}/eventi-...`.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db
from app.schemi import (
    EventoGrezzoAggiornamento,
    EventoGrezzoBatch,
    EventoGrezzoCreazione,
    EventoGrezzoLettura,
    EventoValidatoAggiornamento,
    EventoValidatoBatch,
    EventoValidatoCreazione,
    EventoValidatoLettura,
)
from app.servizi import (
    EventoInesistenteError,
    PartitaInesistenteError,
    ServizioEventiGrezzi,
    ServizioEventiValidati,
)

router = APIRouter(prefix="/partite/{partita_id}", tags=["eventi"])


# === Eventi grezzi ===


@router.post(
    "/eventi-grezzi",
    response_model=EventoGrezzoLettura,
    status_code=status.HTTP_201_CREATED,
    summary="Aggiungi evento grezzo",
)
async def aggiungi_evento_grezzo(
    partita_id: str,
    dati: EventoGrezzoCreazione,
    db: AsyncSession = Depends(get_sessione_db),
) -> EventoGrezzoLettura:
    """
    Inserisce un evento grezzo (osservazione non ancora validata) in una
    partita esistente.

    Usato sia per inserimento manuale via UI di review, sia come endpoint
    di sync per il tablet osservatore (che invia un evento alla volta o
    in batch tramite `/eventi-grezzi/batch`).
    """
    try:
        evento = await ServizioEventiGrezzi.aggiungi(db, partita_id, dati)
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return EventoGrezzoLettura.model_validate(evento)


@router.post(
    "/eventi-grezzi/batch",
    response_model=list[EventoGrezzoLettura],
    status_code=status.HTTP_201_CREATED,
    summary="Carica eventi grezzi in batch",
)
async def aggiungi_eventi_grezzi_batch(
    partita_id: str,
    batch: EventoGrezzoBatch,
    db: AsyncSession = Depends(get_sessione_db),
) -> list[EventoGrezzoLettura]:
    """
    Carica più eventi grezzi in un'unica chiamata.

    Tipico utilizzo: l'app osservatore Android, a fine partita, fa upload
    di tutti gli eventi catturati durante la serata in un colpo solo.
    """
    try:
        eventi = await ServizioEventiGrezzi.aggiungi_batch(
            db, partita_id, batch.eventi
        )
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return [EventoGrezzoLettura.model_validate(e) for e in eventi]


@router.get(
    "/eventi-grezzi",
    response_model=list[EventoGrezzoLettura],
    summary="Lista eventi grezzi",
)
async def lista_eventi_grezzi(
    partita_id: str,
    solo_non_validati: bool = Query(default=False),
    db: AsyncSession = Depends(get_sessione_db),
) -> list[EventoGrezzoLettura]:
    """Ritorna gli eventi grezzi di una partita, ordinati per timestamp."""
    try:
        eventi = await ServizioEventiGrezzi.lista(
            db, partita_id, solo_non_validati=solo_non_validati
        )
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return [EventoGrezzoLettura.model_validate(e) for e in eventi]


@router.patch(
    "/eventi-grezzi/{evento_id}",
    response_model=EventoGrezzoLettura,
    summary="Aggiorna evento grezzo",
)
async def aggiorna_evento_grezzo(
    partita_id: str,
    evento_id: str,
    dati: EventoGrezzoAggiornamento,
    db: AsyncSession = Depends(get_sessione_db),
) -> EventoGrezzoLettura:
    """
    Aggiornamento parziale di un evento grezzo. Solo i campi presenti nel
    body vengono modificati. Utile per correggere il timestamp di un evento
    rilevato dal CV con drift, o riclassificarne il tipo dopo verifica
    manuale del video.
    """
    try:
        evento = await ServizioEventiGrezzi.aggiorna(
            db, partita_id, evento_id, dati
        )
    except EventoInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return EventoGrezzoLettura.model_validate(evento)


@router.delete(
    "/eventi-grezzi/{evento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina evento grezzo",
)
async def elimina_evento_grezzo(
    partita_id: str,
    evento_id: str,
    db: AsyncSession = Depends(get_sessione_db),
) -> None:
    """Rimuove un evento grezzo (es. falso positivo CV)."""
    try:
        await ServizioEventiGrezzi.elimina(db, partita_id, evento_id)
    except EventoInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/eventi-grezzi/elimina-batch",
    summary="Elimina più eventi grezzi atomicamente",
)
async def elimina_eventi_grezzi_batch(
    partita_id: str,
    body: dict[str, Any],
    db: AsyncSession = Depends(get_sessione_db),
) -> dict[str, int]:
    """
    Elimina N eventi grezzi in un'unica transazione.

    Body: `{"evento_ids": ["uuid1", "uuid2", ...]}`. ID che non esistono
    o non appartengono alla partita sono ignorati silenziosamente.

    Risposta: `{"n_eliminati": <int>}`. Utile per il flusso "rifiuta
    proposta" dove l'utente scarta tutti gli eventi BLE di un cluster
    in un colpo solo invece di N round-trip.
    """
    evento_ids = body.get("evento_ids", [])
    if not isinstance(evento_ids, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campo 'evento_ids' deve essere una lista di stringhe",
        )
    if not all(isinstance(i, str) for i in evento_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ogni elemento di 'evento_ids' deve essere una stringa",
        )

    n_eliminati = await ServizioEventiGrezzi.elimina_batch(
        db, partita_id, evento_ids
    )
    return {"n_eliminati": n_eliminati}


# === Eventi validati ===


@router.post(
    "/eventi-validati",
    response_model=EventoValidatoLettura,
    status_code=status.HTTP_201_CREATED,
    summary="Crea evento validato",
)
async def crea_evento_validato(
    partita_id: str,
    dati: EventoValidatoCreazione,
    db: AsyncSession = Depends(get_sessione_db),
) -> EventoValidatoLettura:
    """
    Crea un evento validato (pronto per il motore regole).

    Se `evento_grezzo_id` è specificato, il grezzo corrispondente viene
    marcato come validato (riferimento bidirezionale).
    """
    try:
        evento = await ServizioEventiValidati.crea(db, partita_id, dati)
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except EventoInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return EventoValidatoLettura.model_validate(evento)


@router.post(
    "/eventi-validati/batch",
    response_model=list[EventoValidatoLettura],
    status_code=status.HTTP_201_CREATED,
    summary="Crea eventi validati in batch",
)
async def crea_eventi_validati_batch(
    partita_id: str,
    batch: EventoValidatoBatch,
    db: AsyncSession = Depends(get_sessione_db),
) -> list[EventoValidatoLettura]:
    """
    Inserisce più eventi validati in un'unica transazione.

    Caso d'uso principale: setup automatico di una partita (42 territori
    distribuiti + N obiettivi assegnati + partita_inizio) — ~45 eventi
    inseriti atomicamente con una sola chiamata.

    Se uno qualsiasi degli `evento_grezzo_id` referenziati non esiste,
    l'intera operazione fallisce con 400 (rollback completo).
    """
    try:
        eventi = await ServizioEventiValidati.crea_batch(
            db, partita_id, batch.eventi
        )
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except EventoInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    return [EventoValidatoLettura.model_validate(e) for e in eventi]


@router.get(
    "/eventi-validati",
    response_model=list[EventoValidatoLettura],
    summary="Lista eventi validati",
)
async def lista_eventi_validati(
    partita_id: str,
    db: AsyncSession = Depends(get_sessione_db),
) -> list[EventoValidatoLettura]:
    """Ritorna gli eventi validati di una partita, ordinati per timestamp."""
    try:
        eventi = await ServizioEventiValidati.lista(db, partita_id)
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    return [EventoValidatoLettura.model_validate(e) for e in eventi]


@router.patch(
    "/eventi-validati/{evento_id}",
    response_model=EventoValidatoLettura,
    summary="Aggiorna evento validato",
)
async def aggiorna_evento_validato(
    partita_id: str,
    evento_id: str,
    dati: EventoValidatoAggiornamento,
    db: AsyncSession = Depends(get_sessione_db),
) -> EventoValidatoLettura:
    """
    Aggiorna campi di un evento validato esistente.

    Solo i campi presenti nel body vengono modificati. Dopo un aggiornamento
    è consigliato richiamare `POST /ricostruisci` per rigenerare lo snapshot.
    """
    try:
        evento = await ServizioEventiValidati.aggiorna(
            db, partita_id, evento_id, dati
        )
    except EventoInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    return EventoValidatoLettura.model_validate(evento)


@router.delete(
    "/eventi-validati/{evento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina evento validato",
)
async def elimina_evento_validato(
    partita_id: str,
    evento_id: str,
    db: AsyncSession = Depends(get_sessione_db),
) -> None:
    """
    Rimuove un evento validato.

    Se l'evento era stato promosso da un grezzo, il grezzo NON viene
    automaticamente "de-validato": resta marcato come tale e l'utente potrà
    decidere se promuoverlo nuovamente o eliminarlo a sua volta.
    """
    try:
        await ServizioEventiValidati.elimina(db, partita_id, evento_id)
    except EventoInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
