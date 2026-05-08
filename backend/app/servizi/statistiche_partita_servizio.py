"""
Servizio di calcolo statistiche di una partita.

Pure function: prende lista di `EventoValidato` + lista di
`GiocatorePartita`, ritorna `StatistichePartita`. Nessun DB, nessun
motore, niente I/O.

Algoritmo di confronto dadi (regola Risiko):
- Si ordinano i dadi attaccante e difensore in ordine decrescente.
- Per ogni coppia (i-esimo att, i-esimo dif) finché entrambe le liste
  hanno valore: se att > dif l'attaccante vince (difensore -1 armata),
  altrimenti vince il difensore (attaccante -1 armata, anche in parità).
- I dadi non confrontati (eccedenti di una delle parti) non danno
  perdite a nessuno.

Esempio:
- att=[6,4,2], dif=[5,3] → confronti: 6>5 (dif-1), 4>3 (dif-1), 2 non
  confrontato. Risultato: att perde 0, dif perde 2.
- att=[3,2], dif=[3,2] → 3=3 (att-1), 2=2 (att-1). Att perde 2, dif 0.
"""

from __future__ import annotations

from typing import Any

from app.modelli import EventoValidato, GiocatorePartita, Partita, TipoEvento
from app.schemi.statistiche import (
    StatisticheGiocatore,
    StatistichePartita,
)


def calcola_statistiche(
    partita: Partita,
    giocatori: list[GiocatorePartita],
    eventi_validati: list[EventoValidato],
    difensori_per_evento: dict[str, str] | None = None,
) -> StatistichePartita:
    """
    Calcola le statistiche complete della partita.

    Tutti gli eventi malformati (es. `dati` non un dict, campi mancanti)
    vengono saltati silenziosamente — la priorità è non crashare se la
    partita ha qualche dato anomalo, non garantire purezza assoluta.

    Se `difensori_per_evento` è fornito (mappa evento_id → giocatore_id
    del difensore al momento dell'attacco), vengono calcolate anche le
    statistiche di difesa. Tipicamente popolato da
    `derivare_difensori_per_evento` che usa il motore di gioco.
    """
    # Inizializza accumulatori per giocatore
    accumulatori: dict[str, _AccumulatoreGiocatore] = {
        g.id: _AccumulatoreGiocatore() for g in giocatori
    }

    n_turni = 0
    n_attacchi_totali = 0

    for evento in eventi_validati:
        dati = evento.dati
        if not isinstance(dati, dict):
            continue

        tipo = evento.tipo

        if tipo == TipoEvento.TURNO_INIZIATO:
            n_turni += 1

        elif tipo == TipoEvento.ATTACCO_RISOLTO:
            n_attacchi_totali += 1
            _aggrega_attacco(accumulatori, dati)
            # Statistiche di difesa (solo se la mappa è disponibile)
            if difensori_per_evento is not None:
                difensore_id = difensori_per_evento.get(evento.id)
                if difensore_id is not None:
                    _aggrega_difesa(accumulatori, dati, difensore_id)

        elif tipo == TipoEvento.TERRITORIO_CONQUISTATO:
            gid = _str_o_none(dati.get("giocatore_id"))
            if gid and gid in accumulatori:
                accumulatori[gid].n_territori_conquistati += 1

        elif tipo == TipoEvento.ARMATE_PIAZZATE:
            gid = _str_o_none(dati.get("giocatore_id"))
            n = _int_o_none(dati.get("n"))
            if gid and gid in accumulatori and n is not None and n > 0:
                accumulatori[gid].n_armate_piazzate_totali += n

        elif tipo == TipoEvento.TRIS_GIOCATO:
            gid = _str_o_none(dati.get("giocatore_id"))
            if gid and gid in accumulatori:
                accumulatori[gid].n_tris_giocati += 1

        elif tipo == TipoEvento.CARTA_PESCATA:
            gid = _str_o_none(dati.get("giocatore_id"))
            if gid and gid in accumulatori:
                accumulatori[gid].n_carte_pescate += 1

    # Costruisci output ordinato per ordine_seduta
    giocatori_ordinati = sorted(giocatori, key=lambda g: g.ordine_seduta)
    statistiche_giocatori = [
        accumulatori[g.id].materializza(g) for g in giocatori_ordinati
    ]

    return StatistichePartita(
        partita_id=partita.id,
        n_eventi_validati=len(eventi_validati),
        durata_sec=_calcola_durata(partita),
        n_turni=n_turni,
        n_attacchi_totali=n_attacchi_totali,
        statistiche_giocatori=statistiche_giocatori,
    )


# === Helper di aggregazione ===


class _AccumulatoreGiocatore:
    """Accumulatore mutabile per le metriche di un singolo giocatore."""

    __slots__ = (
        "armate_inflitte_attaccando",
        "armate_inflitte_difendendo",
        "armate_perse_attaccando",
        "armate_perse_difendendo",
        "n_armate_piazzate_totali",
        "n_attacchi",
        "n_carte_pescate",
        "n_difese",
        "n_territori_conquistati",
        "n_tris_giocati",
        "valori_dadi",
    )

    def __init__(self) -> None:
        self.n_attacchi: int = 0
        self.armate_perse_attaccando: int = 0
        self.armate_inflitte_attaccando: int = 0
        self.valori_dadi: list[int] = []
        self.n_difese: int = 0
        self.armate_perse_difendendo: int = 0
        self.armate_inflitte_difendendo: int = 0
        self.n_territori_conquistati: int = 0
        self.n_armate_piazzate_totali: int = 0
        self.n_tris_giocati: int = 0
        self.n_carte_pescate: int = 0

    def materializza(self, giocatore: GiocatorePartita) -> StatisticheGiocatore:
        media = (
            sum(self.valori_dadi) / len(self.valori_dadi)
            if self.valori_dadi
            else None
        )
        return StatisticheGiocatore(
            giocatore_id=giocatore.id,
            nome=giocatore.nome,
            colore=giocatore.colore,
            n_attacchi=self.n_attacchi,
            armate_perse_attaccando=self.armate_perse_attaccando,
            armate_inflitte_attaccando=self.armate_inflitte_attaccando,
            n_dadi_lanciati=len(self.valori_dadi),
            media_dadi_lanciati=(
                round(media, 2) if media is not None else None
            ),
            n_difese=self.n_difese,
            armate_perse_difendendo=self.armate_perse_difendendo,
            armate_inflitte_difendendo=self.armate_inflitte_difendendo,
            n_territori_conquistati=self.n_territori_conquistati,
            n_armate_piazzate_totali=self.n_armate_piazzate_totali,
            n_tris_giocati=self.n_tris_giocati,
            n_carte_pescate=self.n_carte_pescate,
        )


def _aggrega_attacco(
    accumulatori: dict[str, _AccumulatoreGiocatore],
    dati: dict[str, Any],
) -> None:
    """Aggrega un singolo evento ATTACCO_RISOLTO sull'accumulatore attaccante."""
    gid = _str_o_none(dati.get("giocatore_id"))
    if gid is None or gid not in accumulatori:
        return

    dadi_att = _list_int(dati.get("dadi_attaccante"))
    dadi_dif = _list_int(dati.get("dadi_difensore"))
    if not dadi_att:
        # Senza dadi attaccante non possiamo calcolare nulla; ignoriamo
        # per coerenza con la regola Risiko (DatiAttaccoRisolto richiede
        # min 1 dado per ruolo, ma qui siamo difensivi).
        return

    acc = accumulatori[gid]
    acc.n_attacchi += 1
    acc.valori_dadi.extend(dadi_att)

    perdite_att, perdite_dif = _confronta_dadi(dadi_att, dadi_dif)
    acc.armate_perse_attaccando += perdite_att
    acc.armate_inflitte_attaccando += perdite_dif


def _aggrega_difesa(
    accumulatori: dict[str, _AccumulatoreGiocatore],
    dati: dict[str, Any],
    difensore_id: str,
) -> None:
    """Aggrega le metriche di difesa per il giocatore_id che possedeva
    il territorio attaccato al momento dell'attacco."""
    if difensore_id not in accumulatori:
        return

    dadi_att = _list_int(dati.get("dadi_attaccante"))
    dadi_dif = _list_int(dati.get("dadi_difensore"))
    if not dadi_att or not dadi_dif:
        return

    acc = accumulatori[difensore_id]
    acc.n_difese += 1
    perdite_att, perdite_dif = _confronta_dadi(dadi_att, dadi_dif)
    acc.armate_perse_difendendo += perdite_dif
    # "Inflitte difendendo" = perdite_att (l'attaccante ha perso)
    acc.armate_inflitte_difendendo += perdite_att


def _confronta_dadi(
    dadi_att: list[int], dadi_dif: list[int]
) -> tuple[int, int]:
    """
    Applica la regola Risiko: ordina decrescente, confronta a coppie
    finché entrambi hanno valori, parità → vince difensore.

    Ritorna (perdite_attaccante, perdite_difensore).
    """
    a = sorted(dadi_att, reverse=True)
    d = sorted(dadi_dif, reverse=True)
    perdite_att = 0
    perdite_dif = 0
    for i in range(min(len(a), len(d))):
        if a[i] > d[i]:
            perdite_dif += 1
        else:  # parità inclusa: vince il difensore
            perdite_att += 1
    return perdite_att, perdite_dif


def _calcola_durata(partita: Partita) -> float | None:
    if partita.data_inizio is None or partita.data_fine is None:
        return None
    delta = partita.data_fine - partita.data_inizio
    return delta.total_seconds()


# === Helper integrazione motore (per statistiche di difesa) ===


def derivare_difensori_per_evento(
    partita: Partita,
    eventi_validati: list[EventoValidato],
) -> dict[str, str]:
    """
    Per ogni evento ATTACCO_RISOLTO, deriva quale giocatore possedeva
    il territorio attaccato al momento dell'attacco.

    Ritorna mappa `evento_id -> giocatore_id_difensore`. Eventi non
    attacco, eventi malformati, attacchi su territori non assegnati o
    eventi che il motore non riesce ad applicare vengono saltati
    silenziosamente.

    Implementazione: rigioca tutti gli eventi al motore in ordine
    cronologico. Per ogni attacco, prima di applicarlo legge
    `motore.controllore_di(territorio_a)`. Costo O(N) per partita.

    Limite noto: se il motore va in errore su un evento intermedio,
    gli attacchi successivi sono basati su uno stato incompleto. È
    una best-effort, accettabile per statistiche aggregate.
    """
    # Import lazy per evitare import circolari (ricostruzione importa
    # questo modulo? No, ma è comunque buona prassi)
    from app.servizi.ricostruzione_servizio import (
        _APPLICATORI,
        ServizioRicostruzione,
    )

    # Se la partita non è in stato compatibile con il motore (es. <2
    # giocatori), non possiamo calcolare i difensori. Ritorna vuoto.
    try:
        motore = ServizioRicostruzione._crea_motore(partita)
    except Exception:
        return {}

    difensori: dict[str, str] = {}

    for evento in eventi_validati:
        if not isinstance(evento.dati, dict):
            continue

        # PRIMA di applicare l'attacco, registra il difensore corrente
        if evento.tipo == TipoEvento.ATTACCO_RISOLTO:
            territorio_a = _str_o_none(evento.dati.get("a"))
            if territorio_a is not None:
                difensore_id = motore.stato.controllore_di(territorio_a)
                if difensore_id is not None:
                    difensori[evento.id] = difensore_id

        # Poi applica l'evento (best effort, ignora errori)
        applicatore = _APPLICATORI.get(evento.tipo)
        if applicatore is None:
            continue
        try:
            applicatore(motore, evento.dati)
        except Exception:
            # Lo stato del motore può essere ora parziale, ma ci proviamo
            # comunque per gli eventi successivi
            continue

    return difensori


# === Helper di parsing difensivo ===


def _str_o_none(v: object) -> str | None:
    return v if isinstance(v, str) and v else None


def _int_o_none(v: object) -> int | None:
    if isinstance(v, bool):  # bool è sottoclasse di int, non lo voglio
        return None
    return v if isinstance(v, int) else None


def _list_int(v: object) -> list[int]:
    if not isinstance(v, list):
        return []
    risultato: list[int] = []
    for item in v:
        if isinstance(item, bool):
            continue
        if isinstance(item, int) and 1 <= item <= 6:
            risultato.append(item)
    return risultato
