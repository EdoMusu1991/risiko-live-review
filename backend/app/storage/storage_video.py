"""
Gestione del filesystem per i file video.

Responsabilità:
- Salvataggio streaming di file caricati (no caricamento in memoria di file da GB).
- Generazione path sicuri (UUID-based, no path traversal).
- Rimozione file alla cancellazione di una partita o di un video.

Il modulo è isolato dall'ORM: lavora solo con percorsi e bytes. Le
correlazioni con le tabelle (`Video`, `Partita`) sono compito dei servizi
applicativi che orchestrano DB + filesystem.
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import aiofiles
from fastapi import UploadFile


class StorageVideoError(Exception):
    """Errore generico durante operazioni di storage video."""


class FileVideoTroppoGrandeError(StorageVideoError):
    """File caricato eccede la dimensione massima consentita."""


class StorageVideo:
    """
    Gestore filesystem per file video.

    Tutti i file vengono salvati in una cartella radice (configurabile),
    con nomi generati come UUID per garantire unicità e prevenire
    path traversal attacks.
    """

    #: Estensioni accettate per video (filtro lato server, oltre al MIME type).
    ESTENSIONI_AMMESSE: frozenset[str] = frozenset({
        ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm",
    })

    #: Dimensione del chunk per lo streaming I/O (bytes).
    CHUNK_SIZE: int = 1024 * 1024  # 1 MB

    def __init__(self, cartella_radice: Path) -> None:
        self._cartella = cartella_radice
        self._cartella.mkdir(parents=True, exist_ok=True)

    async def salva_upload(
        self,
        upload: UploadFile,
        dimensione_max_byte: int,
    ) -> tuple[Path, int]:
        """
        Salva un file caricato in modo streaming.

        Args:
            upload: il file ricevuto dall'endpoint FastAPI.
            dimensione_max_byte: limite massimo, oltre il quale solleva.

        Returns:
            (percorso_file, dimensione_byte) — il file salvato e la sua size.

        Raises:
            StorageVideoError: estensione non ammessa.
            FileVideoTroppoGrandeError: superata la dimensione massima.
        """
        nome_originale = upload.filename or "upload"
        estensione = Path(nome_originale).suffix.lower()

        if estensione not in self.ESTENSIONI_AMMESSE:
            raise StorageVideoError(
                f"Estensione '{estensione}' non ammessa. "
                f"Ammesse: {sorted(self.ESTENSIONI_AMMESSE)}"
            )

        # Genero nome univoco. NON uso il nome originale per evitare:
        # 1) collisioni
        # 2) path traversal (..\..\..)
        # 3) caratteri non validi del filesystem
        nome_file = f"{uuid.uuid4()}{estensione}"
        percorso = self._cartella / nome_file

        dimensione_totale = 0
        try:
            async with aiofiles.open(percorso, "wb") as file_destinazione:
                while True:
                    chunk = await upload.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    dimensione_totale += len(chunk)
                    if dimensione_totale > dimensione_max_byte:
                        raise FileVideoTroppoGrandeError(
                            f"File supera la dimensione massima "
                            f"({dimensione_max_byte} byte)"
                        )
                    await file_destinazione.write(chunk)
        except Exception:
            # Cleanup file parziale in caso di errore
            if percorso.exists():
                percorso.unlink(missing_ok=True)
            raise

        return percorso, dimensione_totale

    async def salva_da_path(
        self,
        sorgente: Path,
        nome_originale: str,
        dimensione_max_byte: int,
    ) -> tuple[Path, int]:
        """
        Salva un file video copiandolo da un path esistente.

        Usato per import di bundle (file già estratto da uno ZIP) dove
        non si dispone di un `UploadFile`.

        Applica gli stessi controlli di sicurezza di `salva_upload`
        (estensione, dimensione massima, nome univoco).
        """
        estensione = Path(nome_originale).suffix.lower()
        if estensione not in self.ESTENSIONI_AMMESSE:
            raise StorageVideoError(
                f"Estensione '{estensione}' non ammessa. "
                f"Ammesse: {sorted(self.ESTENSIONI_AMMESSE)}"
            )

        if not sorgente.exists():
            raise StorageVideoError(f"File sorgente non esiste: {sorgente}")

        dimensione = sorgente.stat().st_size
        if dimensione > dimensione_max_byte:
            raise FileVideoTroppoGrandeError(
                f"File supera la dimensione massima ({dimensione_max_byte} byte)"
            )

        nome_file = f"{uuid.uuid4()}{estensione}"
        percorso = self._cartella / nome_file

        try:
            async with (
                aiofiles.open(sorgente, "rb") as src,
                aiofiles.open(percorso, "wb") as dst,
            ):
                while True:
                    chunk = await src.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    await dst.write(chunk)
        except Exception:
            if percorso.exists():
                percorso.unlink(missing_ok=True)
            raise

        return percorso, dimensione

    def elimina(self, percorso: Path) -> None:
        """
        Elimina un file video. Non solleva se il file non esiste già.

        Per sicurezza, verifica che il path sia dentro la cartella radice
        (anti path traversal).
        """
        try:
            percorso_assoluto = percorso.resolve()
            cartella_assoluta = self._cartella.resolve()
            percorso_assoluto.relative_to(cartella_assoluta)
        except ValueError as e:
            raise StorageVideoError(
                f"Tentativo di eliminare file fuori dalla cartella storage: "
                f"{percorso}"
            ) from e

        percorso.unlink(missing_ok=True)

    def elimina_tutti_di_partita(self, percorsi: list[Path]) -> None:
        """Elimina più file in batch (usato a cancellazione partita)."""
        from contextlib import suppress

        for p in percorsi:
            with suppress(StorageVideoError):
                self.elimina(p)

    async def stream_lettura(
        self, percorso: Path, *, offset: int = 0, lunghezza: int | None = None
    ) -> AsyncIterator[bytes]:
        """
        Streaming async dei byte di un file, per servirlo in HTTP response.

        Args:
            percorso: file da leggere.
            offset: byte di partenza (per Range requests).
            lunghezza: byte massimi da leggere. Se None, fino a EOF.

        Yields:
            Chunk di bytes di dimensione `CHUNK_SIZE` (l'ultimo può essere minore).
        """
        if not percorso.exists():
            raise StorageVideoError(f"File non esistente: {percorso}")

        async with aiofiles.open(percorso, "rb") as file_sorgente:
            if offset > 0:
                await file_sorgente.seek(offset)

            byte_letti = 0
            while True:
                if lunghezza is not None:
                    rimanenti = lunghezza - byte_letti
                    if rimanenti <= 0:
                        break
                    chunk_size = min(self.CHUNK_SIZE, rimanenti)
                else:
                    chunk_size = self.CHUNK_SIZE

                chunk = await file_sorgente.read(chunk_size)
                if not chunk:
                    break
                byte_letti += len(chunk)
                yield chunk

    @property
    def cartella_radice(self) -> Path:
        return self._cartella


def crea_storage_di_default(cartella: Path) -> StorageVideo:
    """Factory function per creare uno StorageVideo (utile nei test e DI)."""
    return StorageVideo(cartella)


# Pulisce un'intera cartella di storage (uso interno, es. nei test)
def pulisci_cartella_storage(cartella: Path) -> None:
    """Rimuove ricorsivamente la cartella e ricrea vuota. ATTENZIONE: distruttivo."""
    if cartella.exists():
        shutil.rmtree(cartella)
    cartella.mkdir(parents=True, exist_ok=True)
