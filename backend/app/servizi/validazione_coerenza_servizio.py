"""
Validatore di coerenza degli `EventoValidato` di una partita.

A differenza della ricostruzione (che si ferma al primo errore del
motore), questo validatore scorre tutti gli eventi raccogliendo
**tutti** i problemi in un'unica passata. È l'opposto del motore:
non simula la partita, controlla solo regole locali.

Uso tipico:
1. Utente importa bundle / aggiunge eventi manuali
2. Click "Verifica coerenza" prima di "Ricostruisci"
3. UI mostra lista problemi → utente correzione iterativa

Il validatore usa il motore in modalità "shadow" per derivare lo stato
del territorio (chi possiede cosa) ma cattura le eccezioni e continua,
così segnala TUTTI i problemi anche se il motore esploderebbe a metà.
"""

from __future__ import annotations

from typing import Any

from app.modelli import EventoValidato, GiocatorePartita, Partita, TipoEvento
from app.schemi.validazione import (
    CodiceProblema,
    ProblemaCoerenza,
    RisultatoValidazioneCoerenza,
    SeveritaProblema,
)


def valida_coerenza(
    partita: Partita,
    giocatori: list[GiocatorePartita],
    eventi_validati: list[EventoValidato],
) -> RisultatoValidazioneCoerenza:
    """
    Scorre gli eventi raccogliendo tutti i problemi di coerenza.

    Eventi malformati (`dati` non un dict) sono ignorati silenziosamente
    perché generano già errori di validazione Pydantic a monte; non è
    compito di questo validatore segnalarli.
    """
    problemi: list[ProblemaCoerenza] = []

    # Validazioni globali (no motore necessario)
    problemi.extend(_valida_ordine_temporale(eventi_validati))
    problemi.extend(_valida_turni_consecutivi(eventi_validati))

    # Validazioni che richiedono lo stato del motore
    problemi.extend(
        _valida_con_motore(partita, giocatori, eventi_validati)
    )

    n_errori = sum(1 for p in problemi if p.severita == "errore")
    n_avvisi = sum(1 for p in problemi if p.severita == "avviso")

    # Ordina per posizione cronologica (None alla fine)
    problemi.sort(key=lambda p: (p.posizione if p.posizione is not None else 1e9))

    return RisultatoValidazioneCoerenza(
        n_eventi_analizzati=len(eventi_validati),
        n_errori=n_errori,
        n_avvisi=n_avvisi,
        problemi=problemi,
    )


# === Validazioni globali (senza motore) ===


def _valida_ordine_temporale(
    eventi: list[EventoValidato],
) -> list[ProblemaCoerenza]:
    """Segnala eventi cronologicamente fuori ordine rispetto al precedente."""
    risultato: list[ProblemaCoerenza] = []
    for i in range(1, len(eventi)):
        if eventi[i].ts_evento < eventi[i - 1].ts_evento:
            risultato.append(
                _problema(
                    severita="avviso",
                    codice="evento_fuori_ordine_temporale",
                    messaggio=(
                        f"L'evento alla posizione {i} ha timestamp "
                        f"({eventi[i].ts_evento.isoformat()}) precedente "
                        f"a quello della posizione {i - 1}"
                    ),
                    evento_id=eventi[i].id,
                    posizione=i,
                )
            )
    return risultato


def _valida_turni_consecutivi(
    eventi: list[EventoValidato],
) -> list[ProblemaCoerenza]:
    """Segnala due TURNO_INIZIATO consecutivi senza eventi in mezzo."""
    risultato: list[ProblemaCoerenza] = []
    ultimo_turno_pos: int | None = None
    eventi_dal_turno: int = 0

    for i, ev in enumerate(eventi):
        if ev.tipo == TipoEvento.TURNO_INIZIATO:
            if ultimo_turno_pos is not None and eventi_dal_turno == 0:
                risultato.append(
                    _problema(
                        severita="avviso",
                        codice="doppio_turno_iniziato",
                        messaggio=(
                            f"Due TURNO_INIZIATO consecutivi alle posizioni "
                            f"{ultimo_turno_pos} e {i} senza eventi in mezzo "
                            "(rinforzi/attacchi mancanti?)"
                        ),
                        evento_id=ev.id,
                        posizione=i,
                    )
                )
            ultimo_turno_pos = i
            eventi_dal_turno = 0
        else:
            eventi_dal_turno += 1
    return risultato


# === Validazioni con motore (best-effort) ===


def _valida_con_motore(
    partita: Partita,
    giocatori: list[GiocatorePartita],
    eventi: list[EventoValidato],
) -> list[ProblemaCoerenza]:
    """
    Per ogni evento applicabile, controlla pre-condizioni che il motore
    valuterebbe (territori adiacenti, possesso, ecc.).

    Strategia: rigioca gli eventi al motore in shadow. Prima di applicare
    ATTACCO/SPOSTAMENTO/ARMATE_PIAZZATE controlla pre-condizioni e
    segnala problemi senza bloccare. In caso di errore di applicazione
    (motore solleva), continua sul prossimo evento — lo stato shadow
    sarà incompleto ma il validatore continua a fare il suo dovere.
    """
    from app.servizi.ricostruzione_servizio import _APPLICATORI
    from risiko_engine.mappa import TERRITORI, adiacenti_a
    from risiko_engine.state_machine import MotorePartita
    from risiko_engine.stato_partita import (
        ColoreGiocatore as MotoreColoreGiocatore,
    )
    from risiko_engine.stato_partita import (
        ConfigurazioneGiocatore,
        StatoPartita,
    )

    risultato: list[ProblemaCoerenza] = []
    giocatori_id = {g.id for g in giocatori}

    # Crea motore shadow inline (evita di dipendere da partita.giocatori
    # che su oggetti detached non è popolato).
    try:
        configurazioni = [
            ConfigurazioneGiocatore(
                player_id=g.id,
                colore=MotoreColoreGiocatore(
                    g.colore.value if hasattr(g.colore, "value") else g.colore
                ),
                nome=g.nome,
            )
            for g in giocatori
        ]
        motore = MotorePartita(StatoPartita(configurazioni))
    except Exception:
        return risultato  # senza motore non possiamo validare nulla qui

    for i, ev in enumerate(eventi):
        if not isinstance(ev.dati, dict):
            continue
        dati = ev.dati

        # Pre-controlli specifici per tipo
        if ev.tipo == TipoEvento.ATTACCO_RISOLTO:
            risultato.extend(
                _controlla_attacco(
                    motore=motore,
                    dati=dati,
                    evento_id=ev.id,
                    posizione=i,
                    giocatori_id=giocatori_id,
                    territori_validi=TERRITORI,
                    adiacenze=adiacenti_a,
                )
            )

        elif ev.tipo == TipoEvento.ARMATE_PIAZZATE:
            risultato.extend(
                _controlla_armate_piazzate(
                    motore=motore,
                    dati=dati,
                    evento_id=ev.id,
                    posizione=i,
                    giocatori_id=giocatori_id,
                    territori_validi=TERRITORI,
                )
            )

        elif ev.tipo == TipoEvento.ARMATE_SPOSTATE:
            risultato.extend(
                _controlla_spostamento(
                    dati=dati,
                    evento_id=ev.id,
                    posizione=i,
                    territori_validi=TERRITORI,
                    adiacenze=adiacenti_a,
                )
            )

        # Applica al motore (best effort)
        applicatore = _APPLICATORI.get(ev.tipo)
        if applicatore is None:
            continue
        try:
            applicatore(motore, dati)
        except Exception:
            continue

    return risultato


def _controlla_attacco(
    *,
    motore: Any,
    dati: dict[str, Any],
    evento_id: str,
    posizione: int,
    giocatori_id: set[str],
    territori_validi: tuple[str, ...],
    adiacenze: Any,  # callable[[str], frozenset[str]]
) -> list[ProblemaCoerenza]:
    risultato: list[ProblemaCoerenza] = []
    gid = _str(dati.get("giocatore_id"))
    da = _str(dati.get("da"))
    a = _str(dati.get("a"))
    dadi_dif = dati.get("dadi_difensore")

    # Giocatore
    if gid is not None and gid not in giocatori_id:
        risultato.append(
            _problema(
                "errore",
                "giocatore_id_inesistente",
                f"L'attacco cita giocatore_id '{gid}' che non appartiene "
                "alla partita",
                evento_id,
                posizione,
            )
        )

    # Territori esistenti
    for terr, ruolo in [(da, "da"), (a, "a")]:
        if terr is not None and terr not in territori_validi:
            risultato.append(
                _problema(
                    "errore",
                    "territorio_inesistente",
                    f"Territorio '{ruolo}'='{terr}' non esiste sulla mappa",
                    evento_id,
                    posizione,
                )
            )

    # Adiacenza
    if (
        da in territori_validi
        and a in territori_validi
        and a not in adiacenze(da)
    ):
        risultato.append(
            _problema(
                "errore",
                "attacco_territori_non_adiacenti",
                f"Attacco da '{da}' a '{a}': i territori non sono adiacenti",
                evento_id,
                posizione,
            )
        )

    # Possesso (richiede stato motore)
    if da in territori_validi:
        controllore = motore.stato.controllore_di(da)
        if controllore is not None and gid is not None and controllore != gid:
            risultato.append(
                _problema(
                    "errore",
                    "attacco_da_territorio_non_posseduto",
                    f"Il giocatore '{gid}' attacca da '{da}' che è "
                    f"controllato da '{controllore}'",
                    evento_id,
                    posizione,
                )
            )

    if a in territori_validi:
        controllore_dif = motore.stato.controllore_di(a)
        if controllore_dif is not None and gid is not None and controllore_dif == gid:
            risultato.append(
                _problema(
                    "errore",
                    "attacco_su_territorio_proprio",
                    f"Il giocatore '{gid}' attacca '{a}' che è già suo",
                    evento_id,
                    posizione,
                )
            )
        elif controllore_dif is None and a in territori_validi:
            risultato.append(
                _problema(
                    "avviso",
                    "attacco_difensore_inesistente",
                    f"Attacco a '{a}' che non risulta controllato da nessuno "
                    "(possibile setup incompleto)",
                    evento_id,
                    posizione,
                )
            )

    # Dadi difensore vuoti = avviso
    if isinstance(dadi_dif, list) and len(dadi_dif) == 0:
        risultato.append(
            _problema(
                "avviso",
                "attacco_difensore_inesistente",
                "L'attacco non ha dadi difensore (territorio sgombro o "
                "errore di registrazione BLE?)",
                evento_id,
                posizione,
            )
        )

    return risultato


def _controlla_armate_piazzate(
    *,
    motore: Any,
    dati: dict[str, Any],
    evento_id: str,
    posizione: int,
    giocatori_id: set[str],
    territori_validi: tuple[str, ...],
) -> list[ProblemaCoerenza]:
    risultato: list[ProblemaCoerenza] = []
    gid = _str(dati.get("giocatore_id"))
    terr = _str(dati.get("territorio"))

    if gid is not None and gid not in giocatori_id:
        risultato.append(
            _problema(
                "errore",
                "giocatore_id_inesistente",
                f"ARMATE_PIAZZATE cita giocatore '{gid}' inesistente",
                evento_id,
                posizione,
            )
        )

    if terr is not None and terr not in territori_validi:
        risultato.append(
            _problema(
                "errore",
                "territorio_inesistente",
                f"ARMATE_PIAZZATE su territorio inesistente '{terr}'",
                evento_id,
                posizione,
            )
        )
    elif terr in territori_validi:
        controllore = motore.stato.controllore_di(terr)
        if controllore is not None and gid is not None and controllore != gid:
            risultato.append(
                _problema(
                    "errore",
                    "armate_piazzate_su_territorio_altrui",
                    f"Il giocatore '{gid}' piazza armate su '{terr}' "
                    f"controllato da '{controllore}'",
                    evento_id,
                    posizione,
                )
            )

    return risultato


def _controlla_spostamento(
    *,
    dati: dict[str, Any],
    evento_id: str,
    posizione: int,
    territori_validi: tuple[str, ...],
    adiacenze: Any,
) -> list[ProblemaCoerenza]:
    risultato: list[ProblemaCoerenza] = []
    da = _str(dati.get("da"))
    a = _str(dati.get("a"))

    for terr, ruolo in [(da, "da"), (a, "a")]:
        if terr is not None and terr not in territori_validi:
            risultato.append(
                _problema(
                    "errore",
                    "territorio_inesistente",
                    f"Spostamento '{ruolo}'='{terr}' non esiste sulla mappa",
                    evento_id,
                    posizione,
                )
            )

    if (
        da in territori_validi
        and a in territori_validi
        and a not in adiacenze(da)
    ):
        risultato.append(
            _problema(
                "errore",
                "spostamento_territori_non_adiacenti",
                f"Spostamento da '{da}' a '{a}': non adiacenti",
                evento_id,
                posizione,
            )
        )

    return risultato


# === Helper ===


def _str(v: object) -> str | None:
    return v if isinstance(v, str) and v else None


def _problema(
    severita: SeveritaProblema,
    codice: CodiceProblema,
    messaggio: str,
    evento_id: str | None = None,
    posizione: int | None = None,
) -> ProblemaCoerenza:
    return ProblemaCoerenza(
        severita=severita,
        codice=codice,
        messaggio=messaggio,
        evento_id=evento_id,
        posizione=posizione,
    )
