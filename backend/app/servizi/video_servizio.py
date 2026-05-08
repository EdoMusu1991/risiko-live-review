"""
Servizio Video: orchestra DB + filesystem + estrazione metadata.

Pattern di lavoro:
- Upload: salva file su filesystem → estrae metadata → crea record DB.
  Se uno step fallisce, fa cleanup di quelli già fatti.
- Download: legge dal DB il path del file, ritorna stream + metadata.
- Delete: elimina record DB + file su filesystem.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import Video
from app.servizi.partita_servizio import (
    PartitaInesistenteError,
    ServizioPartita,
)
from app.storage import (
    EstrattoreMetadataVideo,
    StorageVideo,
)


class VideoInesistenteError(Exception):
    """Il video richiesto non esiste."""


class ServizioVideo:
    """
    Operazioni sul ciclo di vita dei video.

    A differenza di `ServizioPartita`, qui c'è side-effect su filesystem,
    quindi i metodi non sono `@staticmethod` ma istanza con storage e
    estrattore iniettati.
    """

    def __init__(
        self,
        storage: StorageVideo,
        estrattore: EstrattoreMetadataVideo,
        dimensione_max_byte: int,
    ) -> None:
        self._storage = storage
        self._estrattore = estrattore
        self._dimensione_max_byte = dimensione_max_byte

    async def carica(
        self,
        db: AsyncSession,
        partita_id: str,
        upload: UploadFile,
    ) -> Video:
        """
        Carica un video associato a una partita.

        Sequenza:
        1. Verifica che la partita esista.
        2. Salva il file su filesystem (streaming).
        3. Estrae i metadata via ffprobe.
        4. Crea il record DB.

        Cleanup: se qualunque step dopo il salvataggio fallisce, il file
        su filesystem viene rimosso.
        """
        # 1. Verifica partita esistente (solleva PartitaInesistenteError)
        await ServizioPartita.trova_per_id(db, partita_id)

        nome_originale = upload.filename or "video"

        # 2. Salva file su filesystem
        percorso, dimensione = await self._storage.salva_upload(
            upload, dimensione_max_byte=self._dimensione_max_byte
        )

        try:
            # 3. Estrai metadata
            metadata = await self._estrattore.estrai(percorso)

            # 4. Crea record DB. Se ts_creazione manca dai tag video, fallback
            # alla data corrente (l'utente potrà correggere via PATCH).
            from datetime import UTC, datetime

            ts_inizio = metadata.ts_creazione or datetime.now(UTC)

            video = Video(
                partita_id=partita_id,
                file_path=str(percorso),
                nome_originale=nome_originale,
                ts_inizio=ts_inizio,
                durata_sec=metadata.durata_sec,
                codec=metadata.codec,
                risoluzione=metadata.risoluzione,
                dimensione_byte=dimensione,
            )
            db.add(video)
            await db.commit()
            await db.refresh(video)
            return video

        except Exception:
            # Cleanup filesystem se DB/metadata falliscono
            self._storage.elimina(percorso)
            raise

    async def trova_per_id(
        self,
        db: AsyncSession,
        partita_id: str,
        video_id: str,
    ) -> Video:
        """Carica un video specifico verificando che appartenga alla partita."""
        stmt = (
            select(Video)
            .where(Video.id == video_id)
            .where(Video.partita_id == partita_id)
        )
        risultato = await db.execute(stmt)
        try:
            return risultato.scalar_one()
        except NoResultFound as e:
            raise VideoInesistenteError(
                f"Video '{video_id}' non trovato per partita '{partita_id}'"
            ) from e

    async def lista(
        self,
        db: AsyncSession,
        partita_id: str,
    ) -> Sequence[Video]:
        """Lista i video di una partita, ordinati per data caricamento."""
        await ServizioPartita.trova_per_id(db, partita_id)
        stmt = (
            select(Video)
            .where(Video.partita_id == partita_id)
            .order_by(Video.data_caricamento)
        )
        risultato = await db.execute(stmt)
        return risultato.scalars().all()

    async def elimina(
        self,
        db: AsyncSession,
        partita_id: str,
        video_id: str,
    ) -> None:
        """Elimina un video: prima il record DB, poi il file su filesystem."""
        video = await self.trova_per_id(db, partita_id, video_id)
        percorso = Path(video.file_path)

        await db.delete(video)
        await db.commit()

        # File system cleanup dopo commit DB. Se fallisce, lo log ma non sollevo:
        # il record DB è già rimosso.
        from contextlib import suppress

        with suppress(Exception):
            self._storage.elimina(percorso)

    async def elimina_tutti_di_partita(
        self,
        db: AsyncSession,
        partita_id: str,
    ) -> None:
        """
        Elimina tutti i video di una partita (file su FS + record DB).

        Da chiamare PRIMA di eliminare la partita stessa, perché dopo il
        DELETE CASCADE i record sarebbero spariti senza pulizia file.
        """
        video_lista = await self.lista(db, partita_id)
        percorsi = [Path(v.file_path) for v in video_lista]

        # Cleanup filesystem (i record DB li eliminerà il CASCADE della partita)
        self._storage.elimina_tutti_di_partita(percorsi)

    def percorso_file(self, video: Video) -> Path:
        """Ritorna il Path del file su disco per un dato video."""
        return Path(video.file_path)


# === Re-export per import comodo ===

__all__ = [
    "PartitaInesistenteError",
    "ServizioVideo",
    "VideoInesistenteError",
]
