"""
Endpoint per estrazione e download di frame da video di partita.

Servono:
- Pipeline CV (raddrizzamento + Roboflow): consuma i frame estratti
- Debug review umana: mostra il frame del video al momento di un evento
- Calibrazione raddrizzamento: estrai 1 frame iniziale per calcolare omografia
"""

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
from app.storage.estrattore_frame import (
    EstrazioneFrameError,
    FfmpegNonDisponibileError,
    TimestampFuoriRangeError,
    get_estrattore_frame,
)
from app.storage.storage_frame import StorageFrame

router = APIRouter(prefix="/partite/{partita_id}", tags=["frame"])


def _crea_servizio() -> ServizioEstrazioneFrame:
    """Costruisce il servizio con le dipendenze di default."""
    storage = StorageFrame(impostazioni.storage_frame_path)
    estrattore = get_estrattore_frame()
    return ServizioEstrazioneFrame(storage=storage, estrattore=estrattore)


@router.get(
    "/eventi/{evento_id}/frame",
    summary="Estrai e scarica frame video al momento di un evento",
    response_class=FileResponse,
)
async def frame_per_evento(
    partita_id: str,
    evento_id: str,
    forza: bool = Query(
        default=False,
        description="Se true, ignora la cache e ri-estrae il frame.",
    ),
    db: AsyncSession = Depends(get_sessione_db),
) -> FileResponse:
    """
    Restituisce il frame JPEG del video corrispondente al timestamp
    dell'evento specificato. Cache su disco: la prima chiamata estrae
    via ffmpeg (~50-200ms), le successive ritornano dal disco (~ms).
    """
    servizio = _crea_servizio()
    try:
        percorso = await servizio.estrai_per_evento(
            db, partita_id, evento_id, forza=forza
        )
    except EventoSenzaVideoError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except EventoFuoriDuratavideoError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except EstrazioneFrameServizioError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except FfmpegNonDisponibileError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"FFmpeg non disponibile sul server: {e}",
        ) from e
    except TimestampFuoriRangeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except EstrazioneFrameError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Estrazione frame fallita: {e}",
        ) from e

    return FileResponse(
        path=percorso,
        media_type="image/jpeg",
        filename=f"frame-{evento_id[:8]}.jpg",
    )


@router.get(
    "/frame",
    summary="Estrai e scarica frame video a un offset arbitrario",
    response_class=FileResponse,
)
async def frame_per_offset(
    partita_id: str,
    offset_sec: float = Query(
        ...,
        ge=0,
        description="Offset in secondi dall'inizio del video.",
    ),
    chiave: str = Query(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Identificatore di cache (alfanumerico + _ -)",
    ),
    forza: bool = Query(default=False),
    db: AsyncSession = Depends(get_sessione_db),
) -> FileResponse:
    """
    Estrai un frame a un offset libero, identificato da una `chiave`
    di cache custom. Utile per snapshot periodici o frame di calibrazione.

    Esempio: `?offset_sec=0&chiave=calibrazione` estrae il primissimo
    frame con chiave fissa, riusabile per calcolare l'omografia di
    raddrizzamento.
    """
    servizio = _crea_servizio()
    try:
        percorso = await servizio.estrai_per_offset(
            db, partita_id, offset_sec, chiave, forza=forza
        )
    except EventoSenzaVideoError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except (EventoFuoriDuratavideoError, TimestampFuoriRangeError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except FfmpegNonDisponibileError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"FFmpeg non disponibile sul server: {e}",
        ) from e
    except EstrazioneFrameError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Estrazione frame fallita: {e}",
        ) from e

    return FileResponse(
        path=percorso,
        media_type="image/jpeg",
        filename=f"frame-{chiave}.jpg",
    )


@router.delete(
    "/frame/cache",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancella la cache dei frame estratti per la partita",
)
async def cancella_cache_frame(partita_id: str) -> None:
    """
    Rimuove tutti i frame estratti in cache per questa partita.
    Utile dopo modifiche significative alla timeline degli eventi.
    """
    storage = StorageFrame(impostazioni.storage_frame_path)
    storage.cancella_partita(partita_id)
