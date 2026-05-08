"""
Servizio per la generazione automatica degli eventi di setup di una partita.

Crea in transazione la sequenza di eventi validati che porta una partita
da appena creata a "pronta per giocare":

1. 42 eventi `TERRITORIO_ASSEGNATO_INIZIO` (distribuzione round-robin
   con armate iniziali secondo regole EG).
2. N eventi `OBIETTIVO_ASSEGNATO` (uno per giocatore, dal catalogo dei
   16 obiettivi EG, senza ripetizioni).
3. 1 evento `PARTITA_INIZIO` (con `primo_giocatore_id`).

Tutti gli eventi hanno timestamp incrementali a partire da `data_inizio`
della partita, distanziati di 1 millisecondo per mantenere ordine
deterministico.

Ottimizzazioni:
- Inserimento batch (un solo flush + commit).
- Riproducibile tramite seed: stessi giocatori + stesso seed → stessa
  distribuzione (utile per debug e test).
- Validazione preventiva: la partita non deve avere già eventi validati,
  per evitare sovrascritture accidentali.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import EventoValidato, GiocatorePartita, Partita, TipoEvento
from app.servizi.partita_servizio import PartitaInesistenteError
from risiko_engine.mappa import TERRITORI

# === Costanti regolamento ===

#: Armate iniziali totali per giocatore secondo numero di giocatori
#: (regola Risiko classico EG).
ARMATE_INIZIALI_PER_NUMERO_GIOCATORI: dict[int, int] = {
    2: 40,
    3: 35,
    4: 30,
    5: 25,
    6: 20,
}

#: Numero totale di obiettivi del catalogo EG.
N_OBIETTIVI_TOTALI = 16


# === Eccezioni ===


class SetupGiaPresenteError(Exception):
    """La partita ha già eventi validati: non posso fare setup automatico."""


class NumeroGiocatoriNonSupportatoError(Exception):
    """Numero giocatori fuori dall'intervallo 2-6."""


# === Risultato ===


@dataclass(frozen=True)
class RisultatoSetup:
    """Riepilogo dell'operazione di setup automatico."""

    n_territori_assegnati: int
    n_obiettivi_assegnati: int
    primo_giocatore_id: str
    armate_per_giocatore: int
    seed_usato: int


# === Servizio ===


class ServizioSetupAutomatico:
    """Generazione automatica eventi di setup di una partita."""

    @staticmethod
    async def genera(
        db: AsyncSession,
        partita_id: str,
        primo_giocatore_id: str | None = None,
        seed: int | None = None,
    ) -> RisultatoSetup:
        """
        Genera e inserisce gli eventi di setup di una partita.

        Args:
            partita_id: la partita da cui generare il setup.
            primo_giocatore_id: chi inizia. Default: giocatore con
                ordine_seduta=1.
            seed: per riproducibilità della distribuzione casuale.
                Default: random.

        Returns:
            Riepilogo dell'operazione.

        Raises:
            PartitaInesistenteError: partita non trovata.
            SetupGiaPresenteError: ci sono già eventi validati.
            NumeroGiocatoriNonSupportatoError: numero giocatori invalido.
        """
        partita = await ServizioSetupAutomatico._carica_partita(db, partita_id)

        # Verifica nessun evento validato già presente
        n_eventi_esistenti = await ServizioSetupAutomatico._conta_eventi_validati(
            db, partita_id
        )
        if n_eventi_esistenti > 0:
            raise SetupGiaPresenteError(
                f"La partita ha già {n_eventi_esistenti} eventi validati. "
                f"Eliminali prima di rigenerare il setup."
            )

        n_giocatori = len(partita.giocatori)
        if n_giocatori not in ARMATE_INIZIALI_PER_NUMERO_GIOCATORI:
            raise NumeroGiocatoriNonSupportatoError(
                f"Numero giocatori non supportato: {n_giocatori}. "
                f"Valori accettati: 2-6."
            )

        # Seed deterministico se richiesto
        seed_usato = seed if seed is not None else random.randint(0, 2**31 - 1)
        rng = random.Random(seed_usato)

        # Calcoli setup
        armate_per_giocatore = ARMATE_INIZIALI_PER_NUMERO_GIOCATORI[n_giocatori]
        primo_id = (
            primo_giocatore_id
            or _giocatore_per_ordine_seduta(partita.giocatori, 1).id
        )
        if not _giocatore_esiste(partita.giocatori, primo_id):
            raise NumeroGiocatoriNonSupportatoError(
                f"primo_giocatore_id '{primo_id}' non appartiene alla partita"
            )

        # Genera eventi
        eventi = ServizioSetupAutomatico._costruisci_eventi(
            partita=partita,
            armate_per_giocatore=armate_per_giocatore,
            primo_giocatore_id=primo_id,
            rng=rng,
        )

        # Inserimento batch
        db.add_all(eventi)
        await db.commit()

        # Conteggi per la risposta
        territori = sum(
            1 for e in eventi if e.tipo == TipoEvento.TERRITORIO_ASSEGNATO_INIZIO
        )
        obiettivi = sum(
            1 for e in eventi if e.tipo == TipoEvento.OBIETTIVO_ASSEGNATO
        )

        return RisultatoSetup(
            n_territori_assegnati=territori,
            n_obiettivi_assegnati=obiettivi,
            primo_giocatore_id=primo_id,
            armate_per_giocatore=armate_per_giocatore,
            seed_usato=seed_usato,
        )

    # === Private: caricamento ===

    @staticmethod
    async def _carica_partita(db: AsyncSession, partita_id: str) -> Partita:
        from sqlalchemy.orm import selectinload

        stmt = (
            select(Partita)
            .where(Partita.id == partita_id)
            .options(selectinload(Partita.giocatori))
        )
        risultato = await db.execute(stmt)
        partita = risultato.scalar_one_or_none()
        if partita is None:
            raise PartitaInesistenteError(
                f"Partita '{partita_id}' non trovata"
            )
        return partita

    @staticmethod
    async def _conta_eventi_validati(db: AsyncSession, partita_id: str) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(EventoValidato)
            .where(EventoValidato.partita_id == partita_id)
        )
        risultato = await db.execute(stmt)
        return int(risultato.scalar() or 0)

    # === Private: costruzione eventi ===

    @staticmethod
    def _costruisci_eventi(
        partita: Partita,
        armate_per_giocatore: int,
        primo_giocatore_id: str,
        rng: random.Random,
    ) -> list[EventoValidato]:
        """Costruisce gli oggetti EventoValidato (non ancora persisti)."""
        ts_base = partita.data_inizio
        contatore_offset = 0

        def prossimo_ts() -> object:
            nonlocal contatore_offset
            ts = ts_base + timedelta(milliseconds=contatore_offset)
            contatore_offset += 1
            return ts

        eventi: list[EventoValidato] = []

        # 1. Distribuzione territori round-robin (con shuffle)
        territori_mescolati = list(TERRITORI)
        rng.shuffle(territori_mescolati)

        # Assegnazione round-robin (giocatore i riceve territori i, i+N, i+2N...)
        giocatori_ordinati = sorted(partita.giocatori, key=lambda g: g.ordine_seduta)
        n_giocatori = len(giocatori_ordinati)
        assegnazioni: dict[str, list[str]] = {g.id: [] for g in giocatori_ordinati}

        for i, terr in enumerate(territori_mescolati):
            giocatore = giocatori_ordinati[i % n_giocatori]
            assegnazioni[giocatore.id].append(terr)

        # Distribuisci armate iniziali per ogni giocatore
        for giocatore in giocatori_ordinati:
            terr_giocatore = assegnazioni[giocatore.id]
            armate_per_terr = _distribuisci_armate(
                len(terr_giocatore), armate_per_giocatore
            )
            for terr, n_armate in zip(terr_giocatore, armate_per_terr, strict=True):
                eventi.append(
                    EventoValidato(
                        partita_id=partita.id,
                        ts_evento=prossimo_ts(),
                        tipo=TipoEvento.TERRITORIO_ASSEGNATO_INIZIO,
                        dati={
                            "giocatore_id": giocatore.id,
                            "territorio": terr,
                            "n_armate": n_armate,
                        },
                        validato_da="setup_automatico",
                    )
                )

        # 2. Obiettivi: uno random distinto per giocatore
        obiettivi_disponibili = list(range(1, N_OBIETTIVI_TOTALI + 1))
        rng.shuffle(obiettivi_disponibili)
        for i, giocatore in enumerate(giocatori_ordinati):
            eventi.append(
                EventoValidato(
                    partita_id=partita.id,
                    ts_evento=prossimo_ts(),
                    tipo=TipoEvento.OBIETTIVO_ASSEGNATO,
                    dati={
                        "giocatore_id": giocatore.id,
                        "obiettivo_id": obiettivi_disponibili[i],
                    },
                    validato_da="setup_automatico",
                )
            )

        # 3. Partita inizio
        eventi.append(
            EventoValidato(
                partita_id=partita.id,
                ts_evento=prossimo_ts(),
                tipo=TipoEvento.PARTITA_INIZIO,
                dati={"primo_giocatore_id": primo_giocatore_id},
                validato_da="setup_automatico",
            )
        )

        return eventi


# === Helper ===


def _distribuisci_armate(n_territori: int, armate_totali: int) -> list[int]:
    """
    Distribuisce `armate_totali` su `n_territori` con vincolo: ogni
    territorio almeno 1 armata, eccedenze divise il più uniformemente
    possibile.

    Esempio: (21 terr, 40 armate) → 19 territori con 2, 2 territori con 1.
    """
    if n_territori == 0:
        return []
    if armate_totali < n_territori:
        raise ValueError(
            f"Armate totali ({armate_totali}) < n_territori ({n_territori}): "
            f"non posso garantire almeno 1 armata per territorio."
        )

    base, resto = divmod(armate_totali, n_territori)
    # I primi `resto` territori ricevono base+1, gli altri base.
    return [base + 1 if i < resto else base for i in range(n_territori)]


def _giocatore_per_ordine_seduta(
    giocatori: list[GiocatorePartita], ordine: int
) -> GiocatorePartita:
    for g in giocatori:
        if g.ordine_seduta == ordine:
            return g
    raise NumeroGiocatoriNonSupportatoError(
        f"Nessun giocatore con ordine_seduta={ordine}"
    )


def _giocatore_esiste(
    giocatori: list[GiocatorePartita], giocatore_id: str
) -> bool:
    return any(g.id == giocatore_id for g in giocatori)


__all__ = [
    "ARMATE_INIZIALI_PER_NUMERO_GIOCATORI",
    "NumeroGiocatoriNonSupportatoError",
    "RisultatoSetup",
    "ServizioSetupAutomatico",
    "SetupGiaPresenteError",
]
