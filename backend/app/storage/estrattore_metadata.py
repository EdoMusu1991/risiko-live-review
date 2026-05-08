"""
Estrazione metadati da file video.

Definisce un'interfaccia astratta + implementazione concreta basata su
`ffprobe` (parte di FFmpeg). L'astrazione permette di iniettare un mock
nei test senza dover invocare ffprobe.

ffprobe deve essere installato e raggiungibile nel PATH:
- Linux:    apt install ffmpeg
- macOS:    brew install ffmpeg
- Windows:  winget install ffmpeg / scoop install ffmpeg
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# === Eccezioni ===


class EstrazioneMetadataError(Exception):
    """Errore generico durante l'estrazione metadata."""


class FfprobeNonDisponibileError(EstrazioneMetadataError):
    """ffprobe non è installato o non è raggiungibile nel PATH."""


class VideoCorrottoError(EstrazioneMetadataError):
    """Il file non è un video valido o è corrotto."""


# === Modello dati ===


@dataclass(frozen=True, slots=True)
class MetadataVideo:
    """Metadati estratti da un file video."""

    durata_sec: float
    """Durata in secondi (float per precisione frame)."""

    larghezza: int
    """Larghezza del video in pixel."""

    altezza: int
    """Altezza del video in pixel."""

    codec: str | None
    """Nome del codec video (es. 'h264', 'hevc'). None se non determinabile."""

    ts_creazione: datetime | None
    """
    Timestamp di creazione del video, estratto dai metadata del container
    (es. tag `creation_time` MOV/MP4). None se non presente nei metadata.
    Nel caso di iPhone, questo è il momento esatto di start della
    registrazione, fondamentale per la sincronizzazione con gli eventi.
    """

    @property
    def risoluzione(self) -> str:
        """Stringa formato 'WxH' (es. '1920x1080')."""
        return f"{self.larghezza}x{self.altezza}"


# === Interfaccia astratta ===


class EstrattoreMetadataVideo(ABC):
    """
    Strategia astratta per estrazione metadata da file video.

    Implementazioni:
    - `EstrattoreFfprobe`: usa il binario ffprobe (produzione).
    - `EstrattoreMockVideo`: ritorna metadata fissi (test).
    """

    @abstractmethod
    async def estrai(self, percorso_file: Path) -> MetadataVideo:
        """
        Estrae i metadati dal file specificato.

        Raises:
            VideoCorrottoError: se il file non è leggibile come video.
            EstrazioneMetadataError: per altri errori di estrazione.
        """


# === Implementazione ffprobe ===


class EstrattoreFfprobe(EstrattoreMetadataVideo):
    """Estrattore concreto basato su ffprobe."""

    def __init__(self, comando_ffprobe: str = "ffprobe") -> None:
        self._comando = comando_ffprobe

    async def estrai(self, percorso_file: Path) -> MetadataVideo:
        if not percorso_file.exists():
            raise EstrazioneMetadataError(
                f"File video non esistente: {percorso_file}"
            )

        # Invoco ffprobe con output JSON per parsing affidabile
        argomenti = [
            self._comando,
            "-v", "error",  # solo errori, no info
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(percorso_file),
        ]

        try:
            processo = await asyncio.create_subprocess_exec(
                *argomenti,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await processo.communicate()
        except FileNotFoundError as e:
            raise FfprobeNonDisponibileError(
                f"Comando '{self._comando}' non trovato. Installa FFmpeg."
            ) from e

        if processo.returncode != 0:
            raise VideoCorrottoError(
                f"ffprobe ha rifiutato il file {percorso_file.name}: "
                f"{stderr.decode('utf-8', errors='replace')}"
            )

        try:
            dati = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise EstrazioneMetadataError(
                f"Output ffprobe non parsabile: {e}"
            ) from e

        return self._parse_metadata(dati, percorso_file)

    @staticmethod
    def _parse_metadata(dati: dict, percorso_file: Path) -> MetadataVideo:  # type: ignore[type-arg]
        """Estrae i campi rilevanti dall'output JSON di ffprobe."""
        formato = dati.get("format", {})
        streams = dati.get("streams", [])

        # Trova il primo stream video (esclude eventuale audio)
        stream_video = next(
            (s for s in streams if s.get("codec_type") == "video"),
            None,
        )
        if stream_video is None:
            raise VideoCorrottoError(
                f"Nessuno stream video trovato in {percorso_file.name}"
            )

        # Durata: dal format (più affidabile) o dallo stream
        durata_str = formato.get("duration") or stream_video.get("duration")
        if durata_str is None:
            raise VideoCorrottoError(
                f"Durata non determinabile per {percorso_file.name}"
            )
        durata_sec = float(durata_str)

        larghezza = int(stream_video.get("width", 0))
        altezza = int(stream_video.get("height", 0))
        if larghezza == 0 or altezza == 0:
            raise VideoCorrottoError(
                f"Risoluzione non valida per {percorso_file.name}"
            )

        codec = stream_video.get("codec_name")

        # ts_creazione: cerca nei tag del format e dello stream.
        # iPhone/iOS scrive `creation_time` in formato ISO 8601 UTC.
        ts_creazione = (
            EstrattoreFfprobe._estrai_ts_creazione(formato.get("tags", {}))
            or EstrattoreFfprobe._estrai_ts_creazione(
                stream_video.get("tags", {})
            )
        )

        return MetadataVideo(
            durata_sec=durata_sec,
            larghezza=larghezza,
            altezza=altezza,
            codec=codec,
            ts_creazione=ts_creazione,
        )

    @staticmethod
    def _estrai_ts_creazione(tags: dict) -> datetime | None:  # type: ignore[type-arg]
        """Estrae creation_time da un dict di tag, restituendo datetime UTC."""
        valore = tags.get("creation_time")
        if not valore:
            return None
        try:
            # Format tipico iPhone: "2026-05-07T15:30:42.000000Z"
            ts = datetime.fromisoformat(valore.replace("Z", "+00:00"))
            return ts.astimezone(UTC) if ts.tzinfo else ts.replace(tzinfo=UTC)
        except ValueError:
            return None


# === Implementazione mock per test ===


class EstrattoreMockVideo(EstrattoreMetadataVideo):
    """
    Estrattore fittizio per test: ritorna sempre metadata predefiniti.

    Permette di testare logica di upload/storage senza richiedere ffprobe
    né file video reali.
    """

    def __init__(self, metadata: MetadataVideo | None = None) -> None:
        self._metadata = metadata or MetadataVideo(
            durata_sec=600.0,  # 10 minuti
            larghezza=1920,
            altezza=1080,
            codec="h264",
            ts_creazione=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        )

    async def estrai(self, percorso_file: Path) -> MetadataVideo:
        if not percorso_file.exists():
            raise EstrazioneMetadataError(
                f"File video non esistente: {percorso_file}"
            )
        return self._metadata


# === Singleton produzione ===

#: Istanza di default usata in produzione (override-abile via dependency).
estrattore_default: EstrattoreMetadataVideo = EstrattoreFfprobe()


def get_estrattore_metadata() -> EstrattoreMetadataVideo:
    """
    Dependency FastAPI che fornisce l'estrattore metadata.

    Override-abile nei test per usare `EstrattoreMockVideo`.
    """
    return estrattore_default
