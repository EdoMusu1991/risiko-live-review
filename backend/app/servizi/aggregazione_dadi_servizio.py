"""
Servizio di aggregazione automatica eventi BLE → proposte di attacchi risolti.

Algoritmo:

1. Carica gli `EventoGrezzo` di una partita con:
   - `tipo == TipoEvento.DADI_LANCIATI`
   - `fonte == FonteEvento.DADO_BLE`
   - `validato == False` (non ancora promossi)

2. Ordina per `ts_evento` e applica clustering temporale:
   un nuovo cluster inizia quando il gap dall'evento precedente
   supera `soglia_gap_secondi` (default 3s).

3. Per ogni cluster, raggruppa per `dati["ruolo"]` (attaccante/difensore)
   e ordina per slot, costruendo le liste `dadi_attaccante` e `dadi_difensore`.

4. Calcola la confidenza del cluster e produce note di warning per
   configurazioni sospette (es. 0 dadi attaccante, troppi dadi).

Limiti consapevoli:

- Se due attacchi consecutivi hanno gap < 3s (lancio veloce), vengono
  fusi in un'unica proposta. L'utente può modificare la finestra dal
  frontend ri-chiamando con una soglia più stretta.
- Lo slot del dado non è usato per ordinare (è solo per identificare
  fisicamente il dado), però è incluso nei `dati` originali per debug.
- Eventi BLE con `dati` malformati vengono saltati, e la cosa è
  registrata in `note` della proposta più vicina.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import EventoGrezzo, EventoValidato, FonteEvento, TipoEvento
from app.schemi.aggregazione import (
    AccettaProposta,
    PropostaAggregazioneDadi,
    RisultatoAggregazione,
)
from app.schemi.dati_eventi import DatiAttaccoRisolto

# === Costanti default ===

#: Gap massimo (secondi) entro cui due eventi BLE sono considerati
#: parte dello stesso "lancio". 3 secondi è una stima ragionevole:
#: il tempo per lanciare 6 dadi e che si fermino tutti.
SOGLIA_GAP_DEFAULT_SECONDI = 3.0


# === Errori ===


class PartitaInesistenteError(Exception):
    """La partita richiesta non esiste."""


class EventoGrezzoInesistenteError(Exception):
    """Uno degli eventi grezzi citati nella proposta non esiste."""


class EventoGiaValidatoError(Exception):
    """Uno degli eventi grezzi è già stato promosso ad EventoValidato."""


class EventoNonAppartenentePartitaError(Exception):
    """Uno degli eventi grezzi non appartiene alla partita richiesta."""


class EventoNonAggregabileError(Exception):
    """L'evento grezzo non è di tipo DADI_LANCIATI con fonte BLE."""


class GiocatoreInesistentePartitaError(Exception):
    """Il giocatore citato non appartiene alla partita."""


# === Servizio ===


class ServizioAggregazioneDadi:
    """
    Genera proposte di `attacco_risolto` aggregando eventi BLE per
    finestra temporale. La supervisione umana resta sempre richiesta
    per accettare le proposte.
    """

    def __init__(
        self,
        soglia_gap_secondi: float = SOGLIA_GAP_DEFAULT_SECONDI,
    ) -> None:
        if soglia_gap_secondi <= 0:
            raise ValueError("soglia_gap_secondi deve essere > 0")
        self._gap = timedelta(seconds=soglia_gap_secondi)

    async def proponi_aggregazioni(
        self,
        db: AsyncSession,
        partita_id: str,
    ) -> RisultatoAggregazione:
        """Calcola le proposte di aggregazione per una partita."""
        eventi = await self._carica_eventi_ble(db, partita_id)

        if not eventi:
            return RisultatoAggregazione(
                n_eventi_grezzi_analizzati=0, n_proposte=0, proposte=[]
            )

        proposte: list[PropostaAggregazioneDadi] = []
        for cluster in self._clusterizza_per_finestra(eventi):
            proposta = self._costruisci_proposta(cluster)
            if proposta is not None:
                proposte.append(proposta)

        return RisultatoAggregazione(
            n_eventi_grezzi_analizzati=len(eventi),
            n_proposte=len(proposte),
            proposte=proposte,
        )

    async def accetta_proposta(
        self,
        db: AsyncSession,
        partita_id: str,
        proposta: AccettaProposta,
    ) -> EventoValidato:
        """
        Promuove una proposta a `EventoValidato` di tipo ATTACCO_RISOLTO.

        Effetti:
        1. Verifica esistenza/consistenza degli eventi grezzi citati.
        2. Verifica che il giocatore appartenga alla partita.
        3. Crea un `EventoValidato` con `dati` validato come
           `DatiAttaccoRisolto`.
        4. Marca tutti gli eventi grezzi come `validato=True`.
        5. Lega l'EventoValidato al primo evento grezzo del cluster
           (il più "vecchio" cronologicamente) come rappresentante,
           lasciando gli altri solo marcati come consumati.

        L'operazione fa flush ma NON commit: il chiamante (router) decide
        quando committare per consentire eventuali rollback in test.
        """
        from sqlalchemy.orm import selectinload

        from app.modelli import Partita

        # 1. Verifica partita
        partita = await db.get(
            Partita, partita_id, options=[selectinload(Partita.giocatori)]
        )
        if partita is None:
            raise PartitaInesistenteError(
                f"Partita {partita_id} non trovata"
            )

        # 2. Verifica giocatore (cerco tra i giocatori della partita)
        giocatore = next(
            (g for g in partita.giocatori if g.id == proposta.giocatore_id),
            None,
        )
        if giocatore is None:
            raise GiocatoreInesistentePartitaError(
                f"Giocatore {proposta.giocatore_id} non appartiene "
                f"alla partita {partita_id}"
            )

        # 3. Carica gli eventi grezzi (in un'unica query)
        eventi = await self._carica_eventi_per_id(
            db, proposta.eventi_grezzi_id
        )

        # Mappa per lookup veloce e per detect mancanti
        eventi_by_id = {e.id: e for e in eventi}
        mancanti = [
            eid for eid in proposta.eventi_grezzi_id if eid not in eventi_by_id
        ]
        if mancanti:
            raise EventoGrezzoInesistenteError(
                f"Eventi grezzi non trovati: {mancanti}"
            )

        # 4. Validazione di ciascun evento grezzo
        for evento in eventi:
            if evento.partita_id != partita_id:
                raise EventoNonAppartenentePartitaError(
                    f"Evento {evento.id} appartiene a partita "
                    f"{evento.partita_id}, non a {partita_id}"
                )
            if evento.validato:
                raise EventoGiaValidatoError(
                    f"Evento {evento.id} è già stato validato"
                )
            if (
                evento.tipo != TipoEvento.DADI_LANCIATI
                or evento.fonte != FonteEvento.DADO_BLE
            ):
                raise EventoNonAggregabileError(
                    f"Evento {evento.id} non è DADI_LANCIATI/DADO_BLE "
                    f"(tipo={evento.tipo}, fonte={evento.fonte})"
                )

        # 5. Costruisci payload validato (Pydantic = ulteriore validazione)
        dati = DatiAttaccoRisolto(
            giocatore_id=proposta.giocatore_id,
            da=proposta.da,
            a=proposta.a,
            dadi_attaccante=proposta.dadi_attaccante,
            dadi_difensore=proposta.dadi_difensore,
        )

        # 6. Trova il "rappresentante" (evento grezzo più vecchio del cluster)
        eventi_ordinati = sorted(eventi, key=lambda e: e.ts_evento)
        rappresentante = eventi_ordinati[0]

        # 7. Crea EventoValidato
        ts_evento = proposta.ts_evento or rappresentante.ts_evento
        evento_validato = EventoValidato(
            partita_id=partita_id,
            ts_evento=ts_evento,
            tipo=TipoEvento.ATTACCO_RISOLTO,
            dati=dati.model_dump(mode="json"),
            evento_grezzo_id=rappresentante.id,
            validato_da=proposta.validato_da,
        )
        db.add(evento_validato)

        # 8. Marca TUTTI gli eventi grezzi del cluster come validati
        for evento in eventi:
            evento.validato = True

        await db.flush()
        await db.refresh(evento_validato)
        return evento_validato

    # === Helper ===

    async def _carica_eventi_ble(
        self, db: AsyncSession, partita_id: str
    ) -> list[EventoGrezzo]:
        stmt = (
            select(EventoGrezzo)
            .where(
                EventoGrezzo.partita_id == partita_id,
                EventoGrezzo.tipo == TipoEvento.DADI_LANCIATI,
                EventoGrezzo.fonte == FonteEvento.DADO_BLE,
                EventoGrezzo.validato.is_(False),
            )
            .order_by(EventoGrezzo.ts_evento)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _carica_eventi_per_id(
        self, db: AsyncSession, ids: list[str]
    ) -> list[EventoGrezzo]:
        """Carica eventi grezzi per ID, in qualsiasi stato (validato o no)."""
        if not ids:
            return []
        stmt = select(EventoGrezzo).where(EventoGrezzo.id.in_(ids))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def _clusterizza_per_finestra(
        self, eventi: Iterable[EventoGrezzo]
    ) -> list[list[EventoGrezzo]]:
        """
        Raggruppa eventi consecutivi in cluster basandosi sul gap.

        Gli eventi devono già essere ordinati per ts_evento crescente.
        """
        cluster_corrente: list[EventoGrezzo] = []
        cluster: list[list[EventoGrezzo]] = []
        ultimo_ts: datetime | None = None

        for evento in eventi:
            if ultimo_ts is None or (evento.ts_evento - ultimo_ts) <= self._gap:
                cluster_corrente.append(evento)
            else:
                if cluster_corrente:
                    cluster.append(cluster_corrente)
                cluster_corrente = [evento]
            ultimo_ts = evento.ts_evento

        if cluster_corrente:
            cluster.append(cluster_corrente)

        return cluster

    def _costruisci_proposta(
        self, cluster: list[EventoGrezzo]
    ) -> PropostaAggregazioneDadi | None:
        """
        Costruisce una proposta da un cluster di eventi grezzi.

        Restituisce None solo se nessun evento del cluster ha dati
        utilizzabili — evento totalmente degenere.
        """
        dadi_att: list[tuple[int, int]] = []  # (slot, valore)
        dadi_dif: list[tuple[int, int]] = []
        eventi_id: list[str] = []
        note: list[str] = []

        for evento in cluster:
            eventi_id.append(evento.id)
            dati = evento.dati
            try:
                ruolo = cast(str, dati["ruolo"])
                slot = cast(int, dati["slot"])
                valore = cast(int, dati["valore"])
            except (KeyError, TypeError):
                note.append(
                    f"Evento {evento.id[:8]}… ha dati malformati e non è "
                    "stato incluso nei dadi"
                )
                continue

            if not isinstance(valore, int) or not (1 <= valore <= 6):
                note.append(
                    f"Evento {evento.id[:8]}… ha valore fuori range ({valore})"
                )
                continue

            if ruolo == "attaccante":
                dadi_att.append((slot, valore))
            elif ruolo == "difensore":
                dadi_dif.append((slot, valore))
            else:
                note.append(
                    f"Evento {evento.id[:8]}… ha ruolo sconosciuto: {ruolo!r}"
                )

        # Ordino per slot per stabilità (slot 1 prima di slot 2 ecc.)
        dadi_att.sort()
        dadi_dif.sort()
        valori_att = [v for _, v in dadi_att]
        valori_dif = [v for _, v in dadi_dif]

        # Avvertimenti su configurazione del cluster
        if len(valori_att) == 0 and len(valori_dif) == 0:
            # Cluster degenere
            return None

        if len(valori_att) == 0:
            note.append("Nessun dado attaccante nel cluster")
        elif len(valori_att) > 3:
            note.append(
                f"Troppi dadi attaccante ({len(valori_att)}, max 3) — "
                "il cluster potrebbe contenere due attacchi consecutivi"
            )

        if len(valori_dif) == 0:
            note.append("Nessun dado difensore nel cluster")
        elif len(valori_dif) > 3:
            note.append(
                f"Troppi dadi difensore ({len(valori_dif)}, max 3) — "
                "il cluster potrebbe contenere due attacchi consecutivi"
            )

        confidenza = self._calcola_confidenza(valori_att, valori_dif)

        return PropostaAggregazioneDadi(
            ts_inizio=cluster[0].ts_evento,
            ts_fine=cluster[-1].ts_evento,
            dadi_attaccante=valori_att,
            dadi_difensore=valori_dif,
            eventi_grezzi_id=eventi_id,
            confidenza=confidenza,
            note=note,
        )

    @staticmethod
    def _calcola_confidenza(
        dadi_att: list[int], dadi_dif: list[int]
    ) -> float:
        """
        Confidenza che il cluster sia un singolo attacco plausibile.

        Regole (calibrabili in futuro):
        - 1.0 se entrambi i ruoli hanno 1-3 dadi (config canonica)
        - 0.5 se uno dei ruoli è vuoto (raro: tipico di dado che non
          si è registrato, oppure attacco su territorio neutrale che
          non c'è nel Risiko ma può essere errore di clustering)
        - 0.3 se uno dei ruoli ha più di 3 dadi (cluster troppo largo)
        - 0.0 se entrambi i ruoli hanno più di 3 dadi (impossibile come
          singolo attacco)
        """
        n_att, n_dif = len(dadi_att), len(dadi_dif)

        sforamenti = (1 if n_att > 3 else 0) + (1 if n_dif > 3 else 0)
        if sforamenti == 2:
            return 0.0
        if sforamenti == 1:
            return 0.3

        if n_att == 0 or n_dif == 0:
            return 0.5

        return 1.0
