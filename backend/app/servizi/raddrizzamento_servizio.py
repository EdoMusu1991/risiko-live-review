"""
Servizio applicativo di raddrizzamento prospettico dei frame video.

Orchestra:
- ServizioEstrazioneFrame (estrae il frame raw dal video)
- StorageFrame (cache matrice omografia + frame raddrizzati)
- Raddrizzatore (calcolo omografia + warp)

Workflow tipico:

    # 1. Calibrazione (una volta per partita, manuale o automatica)
    matrice = await servizio.calibra(db, partita_id, evento_id_calibrazione)

    # 2. Raddrizzamento di un frame specifico (può essere ripetuto N volte,
    #    ogni volta usa la matrice cached)
    percorso_jpg = await servizio.raddrizza_per_evento(db, partita_id, evento_id)

Razionale del caching:
- L'iPhone è fisso al soffitto, la plancia è ferma per gran parte della
  partita. La matrice di omografia è quindi (quasi) costante.
- Calcolare l'omografia con SIFT è 200-500ms; applicarla è ~10ms.
- Cachare la matrice e applicarla a tutti i frame della partita
  riduce il tempo totale da minuti a secondi.
- Se la plancia si muove davvero, l'utente può forzare la ricalibrazione
  via endpoint dedicato (POST .../calibra-raddrizzamento?forza=true).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.servizi.estrazione_frame_servizio import ServizioEstrazioneFrame
from app.storage.raddrizzatore import (
    Raddrizzatore,
)
from app.storage.storage_frame import StorageFrame


class RaddrizzamentoServizioError(Exception):
    """Errore generico del servizio di raddrizzamento."""


class OmografiaNonCalibrataError(RaddrizzamentoServizioError):
    """L'omografia non è ancora stata calcolata per questa partita."""


class ServizioRaddrizzamento:
    """
    Calibra una volta per partita, applica a N frame in cache.

    Args:
        servizio_estrazione: usato per ottenere i frame raw dal video.
        storage: cache della matrice + frame raddrizzati.
        raddrizzatore: implementazione (OpenCV in prod, mock nei test).
    """

    def __init__(
        self,
        servizio_estrazione: ServizioEstrazioneFrame,
        storage: StorageFrame,
        raddrizzatore: Raddrizzatore,
    ) -> None:
        self._estrazione = servizio_estrazione
        self._storage = storage
        self._raddrizzatore = raddrizzatore

    async def calibra(
        self,
        db: AsyncSession,
        partita_id: str,
        *,
        evento_id_calibrazione: str | None = None,
        offset_sec_calibrazione: float = 0.0,
        forza: bool = False,
    ) -> list[list[float]]:
        """
        Calcola la matrice di omografia per una partita e la salva in cache.

        Sorgente del frame di calibrazione (in ordine di priorità):
        1. Se `evento_id_calibrazione` è specificato → usa il frame di
           quell'evento.
        2. Altrimenti → estrae un frame al `offset_sec_calibrazione`
           (default 0 = primo frame del video).

        Args:
            db: sessione database.
            partita_id: UUID partita.
            evento_id_calibrazione: UUID di un EventoValidato della partita.
            offset_sec_calibrazione: usato se evento_id non specificato.
            forza: se True, ricalibra anche se la cache esiste.

        Returns:
            La matrice 3x3 calcolata (e cachata).

        Raises:
            CalibrazioneFallitaError: feature matching fallito.
            RaddrizzamentoError: altri errori.
        """
        if not forza and self._storage.esiste_omografia(partita_id):
            cached = self._storage.carica_omografia(partita_id)
            if cached is not None:
                return cached

        # Estrai il frame di calibrazione
        if evento_id_calibrazione is not None:
            frame_path = await self._estrazione.estrai_per_evento(
                db, partita_id, evento_id_calibrazione
            )
        else:
            frame_path = await self._estrazione.estrai_per_offset(
                db,
                partita_id,
                offset_sec_calibrazione,
                "calibrazione-raddrizzamento",
            )

        # Calibra (può sollevare CalibrazioneFallitaError)
        matrice = self._raddrizzatore.calibra(frame_path)

        # Salva in cache
        self._storage.salva_omografia(partita_id, matrice)
        return matrice

    async def raddrizza_per_evento(
        self,
        db: AsyncSession,
        partita_id: str,
        evento_id: str,
        *,
        forza: bool = False,
    ) -> Path:
        """
        Restituisce il path del frame raddrizzato per un evento.

        Cache: se già esiste, lo restituisce direttamente. Altrimenti:
        1. Estrae il frame raw via ServizioEstrazioneFrame
        2. Carica la matrice di omografia (deve già essere calibrata)
        3. Applica il warp e salva in cache

        Args:
            db: sessione database.
            partita_id: UUID partita.
            evento_id: UUID dell'evento.
            forza: se True, ignora la cache e ri-applica il warp.

        Returns:
            Path al JPEG raddrizzato.

        Raises:
            OmografiaNonCalibrataError: chiamato senza prima `calibra()`.
            (e tutti gli errori di estrazione frame e di raddrizzamento)
        """
        # Cache hit?
        if not forza and self._storage.esiste_raddrizzato(partita_id, evento_id):
            return self._storage.percorso_frame_raddrizzato(partita_id, evento_id)

        # Carica matrice (deve esistere)
        matrice = self._storage.carica_omografia(partita_id)
        if matrice is None:
            raise OmografiaNonCalibrataError(
                f"La partita {partita_id} non è stata calibrata. "
                f"Chiamare prima ServizioRaddrizzamento.calibra()."
            )

        # Estrai frame raw (con la sua cache interna)
        frame_raw = await self._estrazione.estrai_per_evento(
            db, partita_id, evento_id
        )

        # Applica warp e salva
        percorso_output = self._storage.percorso_frame_raddrizzato(
            partita_id, evento_id
        )
        self._raddrizzatore.applica(frame_raw, matrice, percorso_output)
        return percorso_output

    async def raddrizza_per_offset(
        self,
        db: AsyncSession,
        partita_id: str,
        offset_sec: float,
        chiave_cache: str,
        *,
        forza: bool = False,
    ) -> Path:
        """
        Versione con offset arbitrario (per snapshot/calibrazione test).
        Stessa logica di raddrizza_per_evento ma usa estrai_per_offset.
        """
        chiave_raddrizzata = f"{chiave_cache}-raddrizzato"
        if not forza and self._storage.esiste_in_cache(partita_id, chiave_raddrizzata):
            return self._storage.percorso_frame(partita_id, chiave_raddrizzata)

        matrice = self._storage.carica_omografia(partita_id)
        if matrice is None:
            raise OmografiaNonCalibrataError(
                f"La partita {partita_id} non è calibrata."
            )

        frame_raw = await self._estrazione.estrai_per_offset(
            db, partita_id, offset_sec, chiave_cache
        )
        percorso_output = self._storage.percorso_frame(
            partita_id, chiave_raddrizzata
        )
        self._raddrizzatore.applica(frame_raw, matrice, percorso_output)
        return percorso_output

    def stato_calibrazione(self, partita_id: str) -> dict[str, object]:
        """
        Ritorna info di stato sulla calibrazione di una partita
        (utile per UI di debug).
        """
        omografia = self._storage.carica_omografia(partita_id)
        return {
            "calibrata": omografia is not None,
            "matrice": omografia,
        }
