"""
Estrazione di singoli frame da un video, a un timestamp dato.

Workflow tipico:
1. App mobile carica un video di partita lungo (es. 90 minuti).
2. Backend riceve eventi BLE con timestamp ISO 8601.
3. Per analisi CV (Roboflow), per ogni evento di interesse estraiamo
   UN frame del video al timestamp corrispondente.
4. Il frame estratto va in cache (storage_frame.py); se richiesto di
   nuovo con stesso input, ritorna dalla cache invece di ri-estrarre.

Astrazione vs implementazione:
- `EstrattoreFrame`: protocollo astratto.
- `EstrattoreFrameFfmpeg`: implementazione concreta che invoca ffmpeg.
- `EstrattoreFrameMock`: per i test (genera un PNG 1x1 deterministico).

Cross-platform: usiamo `asyncio.to_thread(subprocess.run, ...)` invece di
`asyncio.create_subprocess_exec` perché su Windows con uvicorn --reload
quest'ultimo non funziona (WindowsSelectorEventLoopPolicy). Stesso pattern
di estrattore_metadata.py.
"""

from __future__ import annotations

import asyncio
import struct
import subprocess
import zlib
from abc import ABC, abstractmethod
from pathlib import Path


class EstrazioneFrameError(Exception):
    """Errore generico durante l'estrazione di un frame."""


class FfmpegNonDisponibileError(EstrazioneFrameError):
    """ffmpeg non è installato o non è raggiungibile nel PATH."""


class TimestampFuoriRangeError(EstrazioneFrameError):
    """L'offset richiesto è negativo o supera la durata del video."""


class VideoNonLeggibileError(EstrazioneFrameError):
    """ffmpeg non riesce a leggere il video al timestamp richiesto."""


class EstrattoreFrame(ABC):
    """
    Protocollo astratto: estrae UN frame da un video a un offset dato
    e lo scrive su file. Idempotente: chiamato due volte con stessi
    input produce lo stesso output (modulo determinismo del codec).
    """

    @abstractmethod
    async def estrai(
        self,
        percorso_video: Path,
        offset_sec: float,
        percorso_output: Path,
    ) -> None:
        """
        Estrae il frame del video al `offset_sec` e lo salva in
        `percorso_output` (formato dedotto dall'estensione: .jpg/.png).

        Raises:
            FfmpegNonDisponibileError: ffmpeg non installato.
            TimestampFuoriRangeError: offset_sec < 0.
            VideoNonLeggibileError: video corrotto o offset oltre durata.
            EstrazioneFrameError: altri errori generici.
        """


# === Implementazione ffmpeg ===


class EstrattoreFrameFfmpeg(EstrattoreFrame):
    """
    Estrattore concreto basato su ffmpeg.

    Usa seek "veloce" (`-ss` prima di `-i`): non è frame-accurate al
    millisecondo ma è ~100x più veloce del seek frame-accurate. Per il
    nostro caso (analisi CV post-partita su eventi BLE con tolleranza
    di ~100ms) la precisione è sufficiente.
    """

    def __init__(self, comando_ffmpeg: str = "ffmpeg") -> None:
        self._comando = comando_ffmpeg

    async def estrai(
        self,
        percorso_video: Path,
        offset_sec: float,
        percorso_output: Path,
    ) -> None:
        if offset_sec < 0:
            raise TimestampFuoriRangeError(
                f"Offset negativo: {offset_sec}s"
            )
        if not percorso_video.exists():
            raise EstrazioneFrameError(
                f"Video non esistente: {percorso_video}"
            )

        # Crea cartella di output se non esiste
        percorso_output.parent.mkdir(parents=True, exist_ok=True)

        # ffmpeg -ss OFFSET -i VIDEO -frames:v 1 -q:v 2 -y OUTPUT
        # -ss prima di -i: seek veloce
        # -frames:v 1: estrai un solo frame
        # -q:v 2: qualità JPEG alta (scala 1-31, 2 è quasi-lossless)
        # -y: sovrascrivi senza chiedere
        argomenti = [
            self._comando,
            "-ss", f"{offset_sec:.3f}",
            "-i", str(percorso_video),
            "-frames:v", "1",
            "-q:v", "2",
            "-y",
            str(percorso_output),
        ]

        try:
            risultato = await asyncio.to_thread(
                subprocess.run,
                argomenti,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as e:
            raise FfmpegNonDisponibileError(
                f"Comando '{self._comando}' non trovato. Installa FFmpeg."
            ) from e

        if risultato.returncode != 0:
            stderr = risultato.stderr.decode("utf-8", errors="replace")
            raise VideoNonLeggibileError(
                f"ffmpeg ha rifiutato l'estrazione "
                f"(offset={offset_sec}s): {stderr[:500]}"
            )

        # Sanity check: il file di output deve esistere e avere dimensione > 0
        if not percorso_output.exists() or percorso_output.stat().st_size == 0:
            raise VideoNonLeggibileError(
                f"ffmpeg ha terminato con successo ma il frame di output "
                f"è mancante o vuoto: {percorso_output}"
            )


# === Implementazione mock per test ===


class EstrattoreFrameMock(EstrattoreFrame):
    """
    Estrattore mock: genera un PNG 1x1 deterministico al posto del frame.
    Il colore del pixel dipende dall'offset (per distinguere visivamente
    frame estratti a timestamp diversi nei test).

    Non richiede ffmpeg installato.
    """

    def __init__(self, *, simula_errore_ffmpeg: bool = False) -> None:
        self._simula_errore = simula_errore_ffmpeg

    async def estrai(
        self,
        percorso_video: Path,
        offset_sec: float,
        percorso_output: Path,
    ) -> None:
        if self._simula_errore:
            raise FfmpegNonDisponibileError("Mock: simulo ffmpeg mancante")

        if offset_sec < 0:
            raise TimestampFuoriRangeError(f"Offset negativo: {offset_sec}s")

        if not percorso_video.exists():
            raise EstrazioneFrameError(f"Video non esistente: {percorso_video}")

        percorso_output.parent.mkdir(parents=True, exist_ok=True)

        # Genera un PNG 1x1 valido con colore derivato dall'offset
        rosso = int(offset_sec) % 256
        verde = int(offset_sec * 10) % 256
        blu = int(offset_sec * 100) % 256

        png_bytes = _png_1x1(rosso, verde, blu)
        percorso_output.write_bytes(png_bytes)


def _png_1x1(r: int, g: int, b: int) -> bytes:
    """Genera i bytes di un PNG 1x1 con il colore RGB specificato."""

    def chunk(tipo: bytes, dati: bytes) -> bytes:
        crc = zlib.crc32(tipo + dati)
        return struct.pack(">I", len(dati)) + tipo + dati + struct.pack(">I", crc)

    firma = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    raw = bytes([0, r, g, b])  # filter byte + RGB pixel
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return firma + ihdr + idat + iend


# === Singleton ===


estrattore_frame_default: EstrattoreFrame = EstrattoreFrameFfmpeg()
"""
Singleton di default per produzione. I test possono iniettare un
`EstrattoreFrameMock` tramite override delle dipendenze FastAPI.
"""


def get_estrattore_frame() -> EstrattoreFrame:
    """Dipendenza FastAPI: ritorna l'estrattore di default."""
    return estrattore_frame_default
