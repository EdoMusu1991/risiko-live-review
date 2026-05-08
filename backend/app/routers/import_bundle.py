"""
Endpoint per l'import del bundle prodotto dall'app mobile.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db
from app.servizi.import_bundle_servizio import (
    BundleImportError,
    BundleNonValidoError,
    HashVideoMismatchError,
    ManifestNonValidoError,
    SchemaVersionNonSupportataError,
    ServizioImportBundle,
    get_servizio_import,
)

router = APIRouter(prefix="/import", tags=["import"])


class RispostaImportBundle(BaseModel):
    """Riepilogo dell'import esposto al client."""

    partita_id: str
    n_giocatori: int
    n_eventi_grezzi_creati: int
    n_eventi_scartati: int
    durata_video_sec: float
    dimensione_video_byte: int
    note: list[str]


@router.post(
    "/bundle-mobile",
    response_model=RispostaImportBundle,
    status_code=status.HTTP_201_CREATED,
    summary="Importa bundle ZIP prodotto dall'app mobile",
)
async def importa_bundle_mobile(
    file: UploadFile = File(
        ...,
        description="File ZIP con manifest.json + video.mp4 + eventi.jsonl",
    ),
    db: AsyncSession = Depends(get_sessione_db),
    servizio: ServizioImportBundle = Depends(get_servizio_import),
) -> RispostaImportBundle:
    """
    Riceve uno ZIP prodotto dall'app mobile, lo elabora e crea una nuova
    Partita con relativo video e eventi grezzi.

    Lo ZIP deve contenere:
    - `manifest.json` (schema_version 1.0)
    - file video (default `video.mp4`)
    - file eventi (default `eventi.jsonl`)

    Eventi malformati vengono scartati con una nota nella risposta;
    non bloccano l'import.

    La partita creata ha stato `GREZZA`. L'utente userà l'editor di review
    per validare gli eventi (spostando i `dadi_lanciati` grezzi in
    `attacco_risolto` validati, ecc.).
    """
    if file.filename and not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il file deve essere uno ZIP",
        )

    contenuto = await file.read()
    if not contenuto:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bundle vuoto",
        )

    try:
        risultato = await servizio.importa(db, contenuto)
    except BundleNonValidoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bundle non valido: {e}",
        ) from e
    except ManifestNonValidoError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Manifest non valido: {e}",
        ) from e
    except SchemaVersionNonSupportataError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except HashVideoMismatchError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hash video non corrisponde: {e}",
        ) from e
    except BundleImportError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante l'import: {e}",
        ) from e

    return RispostaImportBundle(
        partita_id=risultato.partita_id,
        n_giocatori=risultato.n_giocatori,
        n_eventi_grezzi_creati=risultato.n_eventi_grezzi_creati,
        n_eventi_scartati=risultato.n_eventi_scartati,
        durata_video_sec=risultato.durata_video_sec,
        dimensione_video_byte=risultato.dimensione_video_byte,
        note=risultato.note,
    )
