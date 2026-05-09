"""
Endpoint per il raddrizzamento prospettico dei frame video.

Workflow tipico per il client (frontend RL o pipeline CV):

1. POST `/calibra-raddrizzamento` (una volta per partita): calcola
   l'omografia e la salva in cache lato server.

2. GET `/eventi/{evento_id}/frame-raddrizzato`: per ogni evento di
   interesse, ottieni il JPEG raddrizzato. La prima richiesta calcola
   il warp; le successive ritornano dalla cache.

3. (opzionale) DELETE per re-calibrare se la plancia si è mossa.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db, impostazioni
from app.servizi.estrazione_frame_servizio import (
    EstrazioneFrameServizioError,
    EventoFuoriDuratavideoError,
    EventoSenzaVideoError,
    ServizioEstrazioneFrame,
)
from app.servizi.raddrizzamento_servizio import (
    OmografiaNonCalibrataError,
    ServizioRaddrizzamento,
)
from app.storage.estrattore_frame import (
    EstrazioneFrameError,
    FfmpegNonDisponibileError,
    TimestampFuoriRangeError,
    get_estrattore_frame,
)
from app.storage.raddrizzatore import (
    CalibrazioneFallitaError,
    OpencvNonDisponibileError,
    RaddrizzamentoError,
    RaddrizzatoreOpencv,
    RiferimentoNonTrovatoError,
)
from app.storage.storage_frame import StorageFrame

router = APIRouter(prefix="/partite/{partita_id}", tags=["raddrizzamento"])


def _crea_servizio() -> ServizioRaddrizzamento:
    """
    Costruisce il servizio con dipendenze di default.

    Per ora il path del riferimento è hardcoded come
    `<storage_frame>/img_riferimento.jpg`. In futuro si potrebbe rendere
    configurabile per partita (es. plance diverse: classico, rinascimento).
    """
    storage = StorageFrame(impostazioni.storage_frame_path)
    estrazione = ServizioEstrazioneFrame(
        storage=storage,
        estrattore=get_estrattore_frame(),
    )

    percorso_riferimento = impostazioni.storage_frame_path / "img_riferimento.jpg"
    try:
        raddrizzatore = RaddrizzatoreOpencv(percorso_riferimento)
    except OpencvNonDisponibileError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "OpenCV non installato sul server. "
                "Esegui: pip install -e \".[cv]\""
            ),
        ) from e
    except RiferimentoNonTrovatoError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Immagine di riferimento mancante: {percorso_riferimento}. "
                f"Caricala nella cartella storage_frame del server."
            ),
        ) from e

    return ServizioRaddrizzamento(
        servizio_estrazione=estrazione,
        storage=storage,
        raddrizzatore=raddrizzatore,
    )


@router.post(
    "/calibra-raddrizzamento",
    summary="Calcola e salva la matrice di omografia per la partita",
)
async def calibra_raddrizzamento(
    partita_id: str,
    evento_id_calibrazione: str | None = Query(
        default=None,
        description=(
            "UUID di un evento da usare come frame di calibrazione. "
            "Se omesso, usa il primo frame del video (offset 0s)."
        ),
    ),
    offset_sec_calibrazione: float = Query(
        default=0.0,
        ge=0,
        description="Offset alternativo se evento_id non specificato.",
    ),
    forza: bool = Query(
        default=False,
        description="Se true, ricalibra anche se già esiste cache.",
    ),
    db: AsyncSession = Depends(get_sessione_db),
) -> dict[str, Any]:
    """
    Calcola la matrice di omografia 3x3 per raddrizzare i frame della
    plancia di questa partita.

    L'iPhone è fisso al soffitto, la plancia è (quasi) ferma: una
    calibrazione vale per tutti i frame della partita. Se la plancia si
    muove, l'utente può forzare ricalibrazione con `?forza=true`.
    """
    servizio = _crea_servizio()
    try:
        matrice = await servizio.calibra(
            db,
            partita_id,
            evento_id_calibrazione=evento_id_calibrazione,
            offset_sec_calibrazione=offset_sec_calibrazione,
            forza=forza,
        )
    except EventoSenzaVideoError as e:
        raise HTTPException(404, detail=str(e)) from e
    except EventoFuoriDuratavideoError as e:
        raise HTTPException(422, detail=str(e)) from e
    except EstrazioneFrameServizioError as e:
        raise HTTPException(404, detail=str(e)) from e
    except (FfmpegNonDisponibileError, OpencvNonDisponibileError) as e:
        raise HTTPException(503, detail=str(e)) from e
    except CalibrazioneFallitaError as e:
        raise HTTPException(
            422,
            detail=(
                f"Calibrazione fallita ({e}). Suggerimenti: prova un "
                f"frame con plancia ben visibile e poche pedine, o un "
                f"frame con illuminazione migliore."
            ),
        ) from e
    except (TimestampFuoriRangeError, EstrazioneFrameError, RaddrizzamentoError) as e:
        raise HTTPException(500, detail=str(e)) from e

    return {
        "calibrata": True,
        "matrice": matrice,
    }


@router.get(
    "/stato-raddrizzamento",
    summary="Stato della calibrazione di raddrizzamento per la partita",
)
async def stato_raddrizzamento(partita_id: str) -> dict[str, object]:
    """
    Ritorna info di stato:
    - `calibrata`: bool
    - `matrice`: lista 3x3 di float, o null
    """
    storage = StorageFrame(impostazioni.storage_frame_path)
    omografia = storage.carica_omografia(partita_id)
    return {
        "calibrata": omografia is not None,
        "matrice": omografia,
    }


@router.delete(
    "/calibrazione-raddrizzamento",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancella la calibrazione (forza ricalibrazione alla prossima)",
)
async def cancella_calibrazione(partita_id: str) -> None:
    storage = StorageFrame(impostazioni.storage_frame_path)
    storage.cancella_omografia(partita_id)


@router.get(
    "/eventi/{evento_id}/frame-raddrizzato",
    summary="Frame raddrizzato del video al momento di un evento",
    response_class=FileResponse,
)
async def frame_raddrizzato_per_evento(
    partita_id: str,
    evento_id: str,
    forza: bool = Query(default=False),
    db: AsyncSession = Depends(get_sessione_db),
) -> FileResponse:
    """
    Restituisce il JPEG raddrizzato del frame video corrispondente a
    un evento. Richiede calibrazione preventiva.
    """
    servizio = _crea_servizio()
    try:
        percorso = await servizio.raddrizza_per_evento(
            db, partita_id, evento_id, forza=forza
        )
    except OmografiaNonCalibrataError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{e} Chiama prima POST /api/partite/{partita_id}/calibra-raddrizzamento."
            ),
        ) from e
    except EventoSenzaVideoError as e:
        raise HTTPException(404, detail=str(e)) from e
    except EventoFuoriDuratavideoError as e:
        raise HTTPException(422, detail=str(e)) from e
    except EstrazioneFrameServizioError as e:
        raise HTTPException(404, detail=str(e)) from e
    except (FfmpegNonDisponibileError, OpencvNonDisponibileError) as e:
        raise HTTPException(503, detail=str(e)) from e
    except (EstrazioneFrameError, RaddrizzamentoError) as e:
        raise HTTPException(500, detail=str(e)) from e

    return FileResponse(
        path=percorso,
        media_type="image/jpeg",
        filename=f"frame-raddrizzato-{evento_id[:8]}.jpg",
    )


@router.post(
    "/raddrizza-tutti-eventi-validati",
    summary="Raddrizza in batch i frame di tutti gli eventi validati",
)
async def raddrizza_tutti_eventi_validati(
    partita_id: str,
    forza: bool = Query(
        default=False,
        description="Se true, ignora la cache e ri-applica il warp.",
    ),
    db: AsyncSession = Depends(get_sessione_db),
) -> dict[str, Any]:
    """
    Pre-calcola in batch tutti i frame raddrizzati della partita.

    Use case: dopo upload video + calibrazione, l'utente può lanciare
    questo endpoint per pre-popolare la cache. La pipeline CV (Roboflow)
    troverà tutto pronto e potrà processare i frame senza latenza.

    Costo per partita ~200 eventi: ~3-5 secondi se la matrice è cached
    (solo applicazione del warp, niente nuovi calcoli SIFT).

    Restituisce un riepilogo: n_riusciti, n_falliti, lista evento_id
    dei falliti.
    """
    from sqlalchemy import select

    from app.modelli import EventoValidato

    servizio = _crea_servizio()

    # Verifica calibrazione preventiva (errore esplicito se manca)
    storage_check = StorageFrame(impostazioni.storage_frame_path)
    if not storage_check.esiste_omografia(partita_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Partita non calibrata. Chiama prima "
                f"POST /api/partite/{partita_id}/calibra-raddrizzamento."
            ),
        )

    # Carica eventi validati ordinati cronologicamente
    stmt = (
        select(EventoValidato)
        .where(EventoValidato.partita_id == partita_id)
        .order_by(EventoValidato.ts_evento)
    )
    risultato = await db.execute(stmt)
    eventi = list(risultato.scalars().all())

    n_riusciti = 0
    falliti: list[dict[str, str]] = []

    for ev in eventi:
        try:
            await servizio.raddrizza_per_evento(
                db, partita_id, ev.id, forza=forza
            )
            n_riusciti += 1
        except (
            EventoFuoriDuratavideoError,
            EstrazioneFrameError,
            RaddrizzamentoError,
        ) as e:
            falliti.append({"evento_id": ev.id, "errore": str(e)})

    return {
        "n_eventi_totali": len(eventi),
        "n_riusciti": n_riusciti,
        "n_falliti": len(falliti),
        "falliti": falliti,
    }
