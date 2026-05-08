"""
Endpoint API per gestione video.

Tutti gli endpoint sono nested sotto `/partite/{partita_id}/video`.

Note implementative:
- Upload via multipart, streaming per evitare di caricare in memoria GB di video.
- Download/playback con supporto HTTP Range per seek nel browser senza scaricare tutto.
- DELETE pulisce sia DB che filesystem.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db, impostazioni
from app.schemi import VideoLettura
from app.servizi import (
    PartitaInesistenteError,
    ServizioVideo,
    VideoInesistenteError,
)
from app.storage import (
    EstrattoreMetadataVideo,
    FileVideoTroppoGrandeError,
    StorageVideoError,
    crea_storage_di_default,
    get_estrattore_metadata,
)
from app.storage.estrattore_metadata import (
    EstrazioneMetadataError,
    VideoCorrottoError,
)

router = APIRouter(prefix="/partite/{partita_id}/video", tags=["video"])


# === Dependency: ServizioVideo configurato ===


def get_servizio_video(
    estrattore: EstrattoreMetadataVideo = Depends(get_estrattore_metadata),
) -> ServizioVideo:
    """Crea un ServizioVideo con storage e estrattore configurati."""
    storage = crea_storage_di_default(impostazioni.storage_video_path)
    return ServizioVideo(
        storage=storage,
        estrattore=estrattore,
        dimensione_max_byte=impostazioni.upload_max_size_mb * 1024 * 1024,
    )


# === Endpoints ===


@router.post(
    "",
    response_model=VideoLettura,
    status_code=status.HTTP_201_CREATED,
    summary="Carica un video",
)
async def carica_video(
    partita_id: str,
    file: UploadFile = File(..., description="File video (mp4, mov, ...)"),
    db: AsyncSession = Depends(get_sessione_db),
    servizio: ServizioVideo = Depends(get_servizio_video),
) -> VideoLettura:
    """
    Carica un file video associato a una partita esistente.

    Vincoli:
    - La partita deve esistere.
    - L'estensione deve essere tra quelle ammesse (mp4, mov, m4v, ...).
    - La dimensione non deve superare `RISIKO_UPLOAD_MAX_SIZE_MB`.

    L'endpoint estrae automaticamente i metadata (durata, codec, risoluzione,
    timestamp di creazione) tramite ffprobe.
    """
    try:
        video = await servizio.carica(db, partita_id, file)
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    except FileVideoTroppoGrandeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        ) from e
    except StorageVideoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except VideoCorrottoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Video non valido: {e}",
        ) from e
    except EstrazioneMetadataError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore estrazione metadata: {e}",
        ) from e

    return VideoLettura.model_validate(video)


@router.get(
    "",
    response_model=list[VideoLettura],
    summary="Lista video di una partita",
)
async def lista_video(
    partita_id: str,
    db: AsyncSession = Depends(get_sessione_db),
    servizio: ServizioVideo = Depends(get_servizio_video),
) -> list[VideoLettura]:
    """Ritorna i metadata dei video associati alla partita."""
    try:
        video_lista = await servizio.lista(db, partita_id)
    except PartitaInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    return [VideoLettura.model_validate(v) for v in video_lista]


@router.get(
    "/{video_id}",
    response_model=VideoLettura,
    summary="Metadata di un video",
)
async def get_video(
    partita_id: str,
    video_id: str,
    db: AsyncSession = Depends(get_sessione_db),
    servizio: ServizioVideo = Depends(get_servizio_video),
) -> VideoLettura:
    """Ritorna i metadata di un singolo video."""
    try:
        video = await servizio.trova_per_id(db, partita_id, video_id)
    except VideoInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e
    return VideoLettura.model_validate(video)


@router.get(
    "/{video_id}/stream",
    summary="Stream del file video",
    responses={
        200: {"content": {"video/*": {}}, "description": "Video completo"},
        206: {"content": {"video/*": {}}, "description": "Range parziale"},
        404: {"description": "Video non trovato"},
    },
)
async def stream_video(
    partita_id: str,
    video_id: str,
    request: Request,
    db: AsyncSession = Depends(get_sessione_db),
    servizio: ServizioVideo = Depends(get_servizio_video),
) -> StreamingResponse:
    """
    Stream del contenuto video con supporto **HTTP Range**.

    Permette al browser di fare seek (scrubbing) senza dover scaricare
    tutto il file. Il `<video>` tag HTML5 e i player JS usano Range
    automaticamente per posizionarsi a un timestamp arbitrario.
    """
    try:
        video = await servizio.trova_per_id(db, partita_id, video_id)
    except VideoInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e

    percorso = servizio.percorso_file(video)
    if not percorso.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File video presente in DB ma assente sul filesystem",
        )

    dimensione_totale = video.dimensione_byte
    range_header = request.headers.get("range")
    media_type = _determina_media_type(percorso)

    if range_header:
        offset, lunghezza = _parse_range_header(range_header, dimensione_totale)
        end_byte = offset + lunghezza - 1
        return StreamingResponse(
            servizio._storage.stream_lettura(
                percorso, offset=offset, lunghezza=lunghezza
            ),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {offset}-{end_byte}/{dimensione_totale}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(lunghezza),
            },
        )

    return StreamingResponse(
        servizio._storage.stream_lettura(percorso),
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(dimensione_totale),
        },
    )


@router.delete(
    "/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Elimina un video",
)
async def elimina_video(
    partita_id: str,
    video_id: str,
    db: AsyncSession = Depends(get_sessione_db),
    servizio: ServizioVideo = Depends(get_servizio_video),
) -> None:
    """Rimuove il record DB e il file dal filesystem."""
    try:
        await servizio.elimina(db, partita_id, video_id)
    except VideoInesistenteError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        ) from e


# === Helper interni ===


_PATTERN_RANGE = re.compile(r"^bytes=(\d+)-(\d*)$")


def _parse_range_header(range_header: str, dimensione_totale: int) -> tuple[int, int]:
    """
    Parsa l'header `Range: bytes=START-END` (RFC 7233).

    Ritorna (offset, lunghezza). END è inclusivo nella spec HTTP.
    """
    match = _PATTERN_RANGE.match(range_header.strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail=f"Header Range non valido: {range_header}",
        )

    inizio = int(match.group(1))
    fine_str = match.group(2)
    fine = int(fine_str) if fine_str else dimensione_totale - 1

    if inizio > fine or fine >= dimensione_totale:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail=f"Range fuori dai limiti: {range_header}",
        )

    return inizio, fine - inizio + 1


def _determina_media_type(percorso: Path) -> str:
    """Mappa estensione → media type per il Content-Type."""
    estensione = percorso.suffix.lower()
    return {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".m4v": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }.get(estensione, "application/octet-stream")
