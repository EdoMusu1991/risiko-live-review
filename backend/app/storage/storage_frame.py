"""
Storage filesystem per frame estratti da video.

Pattern: cache su disco. La chiave è (partita_id, evento_id) — se
qualcuno richiede di nuovo il frame per lo stesso evento, ritorna dal
disco invece di ri-eseguire ffmpeg.

Layout:
    storage_frames/
    └── {partita_id}/
        ├── {evento_id_1}.jpg
        ├── {evento_id_2}.jpg
        └── ...

Pulizia: cancellazione di una partita rimuove la cartella intera. Niente
TTL automatico per ora — i frame raddrizzati sono piccoli (~50-200KB
ognuno) e il volume per club è prevedibile (max ~300 frame x 50 partite =
~3GB totali), gestibile manualmente.
"""

from __future__ import annotations

import shutil
from pathlib import Path


class StorageFrameError(Exception):
    """Errore generico durante operazioni di storage frame."""


class StorageFrame:
    """
    Gestore filesystem per frame estratti.

    Args:
        cartella_radice: directory base sotto cui creare le sotto-cartelle
            per partita.
    """

    #: Estensione di default per i frame estratti (JPEG = compressione efficiente).
    ESTENSIONE_DEFAULT: str = ".jpg"

    def __init__(self, cartella_radice: Path) -> None:
        self._cartella = cartella_radice
        self._cartella.mkdir(parents=True, exist_ok=True)

    def percorso_frame(
        self,
        partita_id: str,
        evento_id: str,
        estensione: str | None = None,
    ) -> Path:
        """
        Calcola il percorso filesystem dove andrà salvato (o è già
        salvato) il frame per un dato evento di una partita.

        Args:
            partita_id: UUID della partita (validato dal chiamante).
            evento_id: UUID dell'evento (validato dal chiamante).
            estensione: forzare un'estensione specifica (es. ".png").
                Default = ESTENSIONE_DEFAULT.

        Returns:
            Path assoluto. La cartella padre potrebbe NON esistere ancora;
            chiamare `assicura_cartella_partita()` se necessario.
        """
        ext = estensione or self.ESTENSIONE_DEFAULT
        if not ext.startswith("."):
            ext = "." + ext

        # Sanity check: niente path traversal via partita_id/evento_id
        # Gli ID sono UUID validati lato modelli, ma difesa in profondità.
        for ide in (partita_id, evento_id):
            if "/" in ide or "\\" in ide or ".." in ide:
                raise StorageFrameError(
                    f"ID con caratteri non ammessi: {ide!r}"
                )

        return self._cartella / partita_id / f"{evento_id}{ext}"

    def esiste_in_cache(self, partita_id: str, evento_id: str) -> bool:
        """True se esiste un frame in cache per questo (partita, evento)."""
        return self.percorso_frame(partita_id, evento_id).exists()

    def cancella_frame(self, partita_id: str, evento_id: str) -> bool:
        """
        Rimuove il frame in cache per un evento.

        Returns:
            True se il file esisteva ed è stato cancellato; False altrimenti.
        """
        percorso = self.percorso_frame(partita_id, evento_id)
        if percorso.exists():
            percorso.unlink()
            return True
        return False

    def cancella_partita(self, partita_id: str) -> int:
        """
        Rimuove tutti i frame in cache di una partita (intera cartella).

        Returns:
            Numero di file rimossi (0 se la cartella non esisteva).
        """
        cartella_partita = self._cartella / partita_id
        if not cartella_partita.exists():
            return 0
        n = sum(1 for _ in cartella_partita.glob("*"))
        shutil.rmtree(cartella_partita)
        return n

    def lista_frame(self, partita_id: str) -> list[Path]:
        """Lista tutti i frame in cache per una partita (ordinati per nome)."""
        cartella_partita = self._cartella / partita_id
        if not cartella_partita.exists():
            return []
        return sorted(cartella_partita.glob(f"*{self.ESTENSIONE_DEFAULT}"))

    # === Gestione omografia di raddrizzamento (cache della matrice 3x3) ===

    def percorso_omografia(self, partita_id: str) -> Path:
        """Path del file JSON che cachea la matrice di omografia per partita."""
        for ide in (partita_id,):
            if "/" in ide or "\\" in ide or ".." in ide:
                raise StorageFrameError(
                    f"ID con caratteri non ammessi: {ide!r}"
                )
        return self._cartella / partita_id / "omografia.json"

    def salva_omografia(
        self,
        partita_id: str,
        matrice: list[list[float]],
    ) -> None:
        """
        Salva la matrice 3x3 di omografia in cache (JSON su disco).

        Args:
            partita_id: UUID partita.
            matrice: lista di liste 3x3 di float.
        """
        import json

        if len(matrice) != 3 or any(len(r) != 3 for r in matrice):
            raise StorageFrameError("Matrice 3x3 attesa")
        percorso = self.percorso_omografia(partita_id)
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(json.dumps({"matrice": matrice}, indent=2))

    def carica_omografia(self, partita_id: str) -> list[list[float]] | None:
        """
        Carica la matrice di omografia se in cache, altrimenti None.
        """
        import json

        percorso = self.percorso_omografia(partita_id)
        if not percorso.exists():
            return None
        try:
            dati = json.loads(percorso.read_text())
            matrice = dati.get("matrice")
            if not isinstance(matrice, list) or len(matrice) != 3:
                return None
            return matrice
        except (json.JSONDecodeError, OSError):
            return None

    def esiste_omografia(self, partita_id: str) -> bool:
        """True se è già stata calcolata l'omografia per questa partita."""
        return self.percorso_omografia(partita_id).exists()

    def cancella_omografia(self, partita_id: str) -> bool:
        """Rimuove la matrice di omografia in cache. Ritorna True se c'era."""
        percorso = self.percorso_omografia(partita_id)
        if percorso.exists():
            percorso.unlink()
            return True
        return False

    # === Gestione frame raddrizzati ===

    def percorso_frame_raddrizzato(
        self,
        partita_id: str,
        evento_id: str,
    ) -> Path:
        """
        Path del frame raddrizzato per un evento. Diverso da quello del
        frame raw: i frame raw stanno in `{evento_id}.jpg`, i raddrizzati
        in `{evento_id}-raddrizzato.jpg`.
        """
        for ide in (partita_id, evento_id):
            if "/" in ide or "\\" in ide or ".." in ide:
                raise StorageFrameError(
                    f"ID con caratteri non ammessi: {ide!r}"
                )
        return self._cartella / partita_id / f"{evento_id}-raddrizzato.jpg"

    def esiste_raddrizzato(self, partita_id: str, evento_id: str) -> bool:
        """True se il frame raddrizzato è già in cache."""
        return self.percorso_frame_raddrizzato(partita_id, evento_id).exists()

    @property
    def cartella_radice(self) -> Path:
        """Espone la cartella radice per debug/test."""
        return self._cartella
