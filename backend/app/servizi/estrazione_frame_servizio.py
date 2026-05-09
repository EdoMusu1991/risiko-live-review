"""
Servizio applicativo per l'estrazione di frame da video di partita.

Orchestra:
- DB (lookup di Video + EventoValidato per la partita)
- StorageFrame (cache su disco)
- EstrattoreFrame (ffmpeg)

Pattern d'uso tipico:

    servizio = ServizioEstrazioneFrame(...)
    percorso = await servizio.estrai_per_evento(db, partita_id, evento_id)
    # → ritorna il path del frame (estratto fresh o letto da cache)

Algoritmo:
1. Carica EventoValidato → ts_evento
2. Carica primo Video della partita → ts_inizio + percorso file
3. Calcola offset_sec = (ts_evento - ts_inizio).total_seconds()
4. Se già in cache → ritorna path cache
5. Altrimenti → ffmpeg estrai → salva in cache → ritorna path
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import EventoValidato, Video
from app.storage.estrattore_frame import (
    EstrattoreFrame,
    TimestampFuoriRangeError,
)
from app.storage.storage_frame import StorageFrame


class EstrazioneFrameServizioError(Exception):
    """Errore generico del servizio."""


class EventoSenzaVideoError(EstrazioneFrameServizioError):
    """Non è stato caricato alcun video per la partita di questo evento."""


class EventoFuoriDuratavideoError(EstrazioneFrameServizioError):
    """L'evento è temporalmente fuori dalla durata del video."""


class ServizioEstrazioneFrame:
    """
    Estrae frame da video al timestamp di un evento, con cache su disco.

    Args:
        storage: gestore filesystem dei frame.
        estrattore: implementazione di estrazione (ffmpeg in prod, mock in test).
    """

    def __init__(
        self,
        storage: StorageFrame,
        estrattore: EstrattoreFrame,
    ) -> None:
        self._storage = storage
        self._estrattore = estrattore

    async def estrai_per_evento(
        self,
        db: AsyncSession,
        partita_id: str,
        evento_id: str,
        *,
        forza: bool = False,
    ) -> Path:
        """
        Estrae il frame del video corrispondente a un evento validato.

        Args:
            db: sessione database.
            partita_id: UUID partita.
            evento_id: UUID dell'EventoValidato.
            forza: se True, ignora la cache e ri-estrae.

        Returns:
            Path al file JPEG del frame.

        Raises:
            EstrazioneFrameServizioError o sotto-classi per errori
            applicativi (evento/video mancanti, fuori range).
            EstrazioneFrameError (da estrattore_frame.py) per errori ffmpeg.
        """
        # 1. Carica evento
        evento = await self._carica_evento(db, partita_id, evento_id)

        # 2. Cache hit?
        if not forza and self._storage.esiste_in_cache(partita_id, evento_id):
            return self._storage.percorso_frame(partita_id, evento_id)

        # 3. Carica video della partita
        video = await self._carica_primo_video(db, partita_id)

        # 4. Calcola offset
        offset_sec = self._calcola_offset(evento.ts_evento, video.ts_inizio)
        if offset_sec > video.durata_sec:
            raise EventoFuoriDuratavideoError(
                f"Evento {evento_id} è a {offset_sec:.1f}s ma il video "
                f"dura solo {video.durata_sec:.1f}s."
            )

        # 5. Estrai
        percorso_output = self._storage.percorso_frame(partita_id, evento_id)
        await self._estrattore.estrai(
            percorso_video=Path(video.file_path),
            offset_sec=offset_sec,
            percorso_output=percorso_output,
        )
        return percorso_output

    async def estrai_per_offset(
        self,
        db: AsyncSession,
        partita_id: str,
        offset_sec: float,
        chiave_cache: str,
        *,
        forza: bool = False,
    ) -> Path:
        """
        Estrae un frame a un offset arbitrario, identificato da una chiave
        di cache custom (es. "snapshot-60s", "calibrazione").

        Utile per:
        - Snapshot periodici (1 ogni 60s) come fallback se mancano eventi
        - Frame di calibrazione del raddrizzamento
        - Test manuali

        Args:
            db: sessione database.
            partita_id: UUID partita.
            offset_sec: offset in secondi dall'inizio del video.
            chiave_cache: identificatore per il file in cache (no `/`, `\\`, `..`).
            forza: ignora cache.

        Returns:
            Path al file JPEG.
        """
        if not forza and self._storage.esiste_in_cache(partita_id, chiave_cache):
            return self._storage.percorso_frame(partita_id, chiave_cache)

        video = await self._carica_primo_video(db, partita_id)

        if offset_sec < 0:
            raise TimestampFuoriRangeError(f"Offset negativo: {offset_sec}")
        if offset_sec > video.durata_sec:
            raise EventoFuoriDuratavideoError(
                f"Offset {offset_sec:.1f}s > durata {video.durata_sec:.1f}s"
            )

        percorso_output = self._storage.percorso_frame(partita_id, chiave_cache)
        await self._estrattore.estrai(
            percorso_video=Path(video.file_path),
            offset_sec=offset_sec,
            percorso_output=percorso_output,
        )
        return percorso_output

    # === Helpers privati ===

    async def _carica_evento(
        self,
        db: AsyncSession,
        partita_id: str,
        evento_id: str,
    ) -> EventoValidato:
        stmt = select(EventoValidato).where(
            EventoValidato.id == evento_id,
            EventoValidato.partita_id == partita_id,
        )
        risultato = await db.execute(stmt)
        evento = risultato.scalar_one_or_none()
        if evento is None:
            raise EstrazioneFrameServizioError(
                f"Evento '{evento_id}' non trovato per partita '{partita_id}'"
            )
        return evento

    async def _carica_primo_video(
        self,
        db: AsyncSession,
        partita_id: str,
    ) -> Video:
        stmt = (
            select(Video)
            .where(Video.partita_id == partita_id)
            .order_by(Video.data_caricamento)
            .limit(1)
        )
        risultato = await db.execute(stmt)
        video = risultato.scalar_one_or_none()
        if video is None:
            raise EventoSenzaVideoError(
                f"Nessun video caricato per la partita '{partita_id}'"
            )
        return video

    @staticmethod
    def _calcola_offset(ts_evento: datetime, ts_inizio: datetime) -> float:
        """
        Differenza in secondi (ts_evento - ts_inizio_video).

        Idealmente entrambi sono timezone-aware. SQLite in dev locale
        rimuove la tz al re-read (`DateTime(timezone=True)` non è
        davvero supportato da SQLite). In quel caso tolleriamo: se uno
        dei due è naive, lo trattiamo come UTC. Questo NON crea
        ambiguità perché la nostra app è sempre in scrittura UTC.
        """
        from datetime import UTC

        if ts_evento.tzinfo is None:
            ts_evento = ts_evento.replace(tzinfo=UTC)
        if ts_inizio.tzinfo is None:
            ts_inizio = ts_inizio.replace(tzinfo=UTC)

        delta = (ts_evento - ts_inizio).total_seconds()
        if delta < 0:
            raise EstrazioneFrameServizioError(
                f"ts_evento ({ts_evento}) e' prima di "
                f"ts_inizio video ({ts_inizio})"
            )
        return delta
