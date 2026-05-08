"""
Servizio di calcolo della classifica club (aggregazione cross-partita).

Riusa `calcola_statistiche` per ogni partita, poi aggrega per nome
giocatore normalizzato. Costo: O(N_partite x N_eventi_per_partita).
Per club con poche centinaia di partite e qualche centinaia di eventi
ognuna è OK; per scale maggiori andrà introdotto caching delle
statistiche per partita.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modelli import EventoValidato, Partita
from app.schemi.classifica_club import ClassificaClub, GiocatoreClub
from app.servizi.statistiche_partita_servizio import (
    calcola_statistiche,
    derivare_difensori_per_evento,
)


async def calcola_classifica_club(db: AsyncSession) -> ClassificaClub:
    """
    Carica tutte le partite con i loro giocatori ed eventi, calcola
    le statistiche per partita e aggrega per nome giocatore.

    Le partite senza giocatori (es. create ma mai popolate) vengono
    saltate. Gli eventi malformati vengono saltati silenziosamente da
    `calcola_statistiche`.
    """
    stmt_partite = select(Partita).options(selectinload(Partita.giocatori))
    risultato = await db.execute(stmt_partite)
    partite = list(risultato.scalars().all())

    if not partite:
        return ClassificaClub(
            n_partite_totali=0,
            n_partite_con_eventi=0,
            n_giocatori_distinti=0,
            durata_totale_sec=0.0,
            n_attacchi_totali=0,
            giocatori=[],
        )

    # Accumulatori per nome normalizzato
    accumulatori: dict[str, _AccumulatoreNome] = {}

    n_partite_con_eventi = 0
    durata_totale_sec = 0.0
    n_attacchi_totali_globale = 0

    for partita in partite:
        giocatori_partita = list(partita.giocatori)
        if not giocatori_partita:
            continue

        # Carica eventi della partita
        stmt_eventi = (
            select(EventoValidato)
            .where(EventoValidato.partita_id == partita.id)
            .order_by(EventoValidato.ts_evento)
        )
        risultato_eventi = await db.execute(stmt_eventi)
        eventi = list(risultato_eventi.scalars().all())

        if eventi:
            n_partite_con_eventi += 1
            # Difensori derivati dal motore (best-effort)
            difensori = derivare_difensori_per_evento(partita, eventi)
        else:
            difensori = {}

        statistiche = calcola_statistiche(
            partita,
            giocatori_partita,
            eventi,
            difensori_per_evento=difensori,
        )

        n_attacchi_totali_globale += statistiche.n_attacchi_totali
        if statistiche.durata_sec is not None:
            durata_totale_sec += statistiche.durata_sec

        # Mappa giocatore_id (di questa partita) → statistiche per giocatore
        for sg in statistiche.statistiche_giocatori:
            chiave = _normalizza_nome(sg.nome)
            if not chiave:
                continue
            acc = accumulatori.setdefault(
                chiave, _AccumulatoreNome(nome=sg.nome)
            )
            acc.aggrega(sg)

    giocatori_aggregati = [
        acc.materializza() for acc in accumulatori.values()
    ]

    # Ordina per bilancio armate decrescente (default che sembra il più
    # significativo per "chi è il più forte"). Il client può re-ordinare.
    giocatori_aggregati.sort(key=lambda g: g.bilancio_armate, reverse=True)

    return ClassificaClub(
        n_partite_totali=len(partite),
        n_partite_con_eventi=n_partite_con_eventi,
        n_giocatori_distinti=len(giocatori_aggregati),
        durata_totale_sec=durata_totale_sec,
        n_attacchi_totali=n_attacchi_totali_globale,
        giocatori=giocatori_aggregati,
    )


def _normalizza_nome(nome: str) -> str:
    """Lowercase + trim. Stringa vuota se il nome è vuoto/whitespace-only."""
    return nome.strip().lower()


# === Accumulatore interno ===


class _AccumulatoreNome:
    """Mutevole, raccoglie metriche per un giocatore identificato per nome."""

    __slots__ = (
        "armate_inflitte_attaccando_tot",
        "armate_inflitte_difendendo_tot",
        "armate_perse_attaccando_tot",
        "armate_perse_difendendo_tot",
        "n_attacchi_totali",
        "n_carte_pescate_tot",
        "n_dadi_lanciati_tot",
        "n_difese_totali",
        "n_partite",
        "n_territori_conquistati_tot",
        "n_tris_giocati_tot",
        "nome",
        "somma_dadi_lanciati",
    )

    def __init__(self, nome: str) -> None:
        self.nome: str = nome  # primo nome incontrato (case originale)
        self.n_partite: int = 0
        self.n_attacchi_totali: int = 0
        self.n_difese_totali: int = 0
        self.armate_inflitte_attaccando_tot: int = 0
        self.armate_perse_attaccando_tot: int = 0
        self.armate_inflitte_difendendo_tot: int = 0
        self.armate_perse_difendendo_tot: int = 0
        self.n_territori_conquistati_tot: int = 0
        self.n_carte_pescate_tot: int = 0
        self.n_tris_giocati_tot: int = 0
        self.n_dadi_lanciati_tot: int = 0
        self.somma_dadi_lanciati: int = 0  # per calcolare media globale

    def aggrega(self, sg: object) -> None:
        """Aggiunge le metriche di una `StatisticheGiocatore` di una partita."""
        # Type-narrowing: sg è StatisticheGiocatore ma evitiamo l'import
        # circolare. Accediamo agli attributi direttamente.
        self.n_partite += 1
        self.n_attacchi_totali += sg.n_attacchi  # type: ignore[attr-defined]
        self.n_difese_totali += sg.n_difese  # type: ignore[attr-defined]
        self.armate_inflitte_attaccando_tot += (
            sg.armate_inflitte_attaccando  # type: ignore[attr-defined]
        )
        self.armate_perse_attaccando_tot += (
            sg.armate_perse_attaccando  # type: ignore[attr-defined]
        )
        self.armate_inflitte_difendendo_tot += (
            sg.armate_inflitte_difendendo  # type: ignore[attr-defined]
        )
        self.armate_perse_difendendo_tot += (
            sg.armate_perse_difendendo  # type: ignore[attr-defined]
        )
        self.n_territori_conquistati_tot += (
            sg.n_territori_conquistati  # type: ignore[attr-defined]
        )
        self.n_carte_pescate_tot += sg.n_carte_pescate  # type: ignore[attr-defined]
        self.n_tris_giocati_tot += sg.n_tris_giocati  # type: ignore[attr-defined]
        self.n_dadi_lanciati_tot += sg.n_dadi_lanciati  # type: ignore[attr-defined]
        if (
            sg.media_dadi_lanciati is not None  # type: ignore[attr-defined]
            and sg.n_dadi_lanciati > 0  # type: ignore[attr-defined]
        ):
            self.somma_dadi_lanciati += round(
                sg.media_dadi_lanciati  # type: ignore[attr-defined]
                * sg.n_dadi_lanciati  # type: ignore[attr-defined]
            )

    def materializza(self) -> GiocatoreClub:
        media_globale: float | None = None
        if self.n_dadi_lanciati_tot > 0:
            media_globale = round(
                self.somma_dadi_lanciati / self.n_dadi_lanciati_tot, 2
            )

        return GiocatoreClub(
            nome=self.nome,
            nome_normalizzato=_normalizza_nome(self.nome),
            n_partite=self.n_partite,
            n_attacchi_totali=self.n_attacchi_totali,
            n_difese_totali=self.n_difese_totali,
            armate_inflitte_attaccando_tot=self.armate_inflitte_attaccando_tot,
            armate_perse_attaccando_tot=self.armate_perse_attaccando_tot,
            armate_inflitte_difendendo_tot=self.armate_inflitte_difendendo_tot,
            armate_perse_difendendo_tot=self.armate_perse_difendendo_tot,
            n_territori_conquistati_tot=self.n_territori_conquistati_tot,
            n_carte_pescate_tot=self.n_carte_pescate_tot,
            n_tris_giocati_tot=self.n_tris_giocati_tot,
            n_dadi_lanciati_tot=self.n_dadi_lanciati_tot,
            media_dadi_globale=media_globale,
        )
