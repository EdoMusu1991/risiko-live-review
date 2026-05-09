"""
Servizio Ricostruzione: applica gli eventi validati al motore regole
`risiko_engine` per ricostruire lo stato finale della partita.

Workflow:
1. Carica `Partita` con i suoi giocatori dal DB.
2. Costruisce `StatoPartita` vuoto con `ConfigurazioneGiocatore` (player_id =
   UUID DB, colore + nome dal `GiocatorePartita`).
3. Crea `MotorePartita`.
4. Itera gli `EventoValidato` ordinati per `ts_evento` crescente.
5. Per ogni evento, chiama l'applicatore corrispondente che:
   - Parsa il payload `dati` con lo schema Pydantic giusto.
   - Gestisce eventuali transizioni di fase implicite del motore.
   - Chiama il metodo del motore appropriato.
6. Eccezioni durante l'applicazione vengono catturate, registrate come
   errori, e la ricostruzione prosegue con gli eventi successivi.
7. Lo stato finale è serializzato e salvato in `StatoPartitaRicostruito`.

Pattern: classmethod statici, niente stato di istanza nel servizio.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modelli import (
    EventoValidato,
    Partita,
    StatoPartitaRicostruito,
    TipoEvento,
)
from app.schemi.dati_eventi import (
    DatiArmatePiazzate,
    DatiArmateSpostate,
    DatiAttaccoRisolto,
    DatiObiettivoAssegnato,
    DatiPartitaInizio,
    DatiTerritorioAssegnatoInizio,
    DatiTrisGiocato,
    DatiTurnoFinito,
)
from app.schemi.stato_snapshot import (
    ErroreRicostruzioneSchema,
    InfoGiocatoreSchema,
    InfoTerritorioSchema,
    StatoPartitaSnapshot,
)
from app.servizi.partita_servizio import PartitaInesistenteError
from risiko_engine.carte import Carta, Simbolo
from risiko_engine.obiettivi import obiettivo_per_id
from risiko_engine.state_machine import FaseTurno, MotorePartita
from risiko_engine.stato_partita import (
    ColoreGiocatore as MotoreColoreGiocatore,
)
from risiko_engine.stato_partita import (
    ConfigurazioneGiocatore,
    StatoPartita,
    StatoPartitaError,
)

# === Eccezioni dominio ===


class RicostruzioneError(Exception):
    """Errore generico durante la ricostruzione."""


class PayloadInvalidoError(RicostruzioneError):
    """Il payload `dati` di un evento non rispetta lo schema atteso."""


class TipoEventoNonSupportatoError(RicostruzioneError):
    """Il tipo di evento non è applicabile al motore (es. eventi grezzi CV)."""


# === Risultato interno ===


@dataclass
class _RisultatoApplicazione:
    """Esito dell'applicazione di un singolo evento."""

    applicato: bool
    """True se ha avuto effetto sul motore, False se è stato saltato."""

    errore: ErroreRicostruzioneSchema | None = None


# === Servizio principale ===


class ServizioRicostruzione:
    """Applica eventi validati al motore e salva lo snapshot finale."""

    @staticmethod
    async def ricostruisci(
        db: AsyncSession, partita_id: str
    ) -> StatoPartitaRicostruito:
        """
        Esegue una ricostruzione completa della partita.

        Idempotente: ogni chiamata sostituisce lo snapshot precedente.
        """
        partita = await ServizioRicostruzione._carica_partita(db, partita_id)
        eventi = list(partita.eventi_validati)

        # Costruisci motore con i giocatori della partita.
        motore = ServizioRicostruzione._crea_motore(partita)

        errori: list[ErroreRicostruzioneSchema] = []
        n_applicati = 0

        for indice, evento in enumerate(eventi):
            esito = ServizioRicostruzione._applica_evento(
                motore, evento, posizione=indice
            )
            if esito.applicato:
                n_applicati += 1
            if esito.errore is not None:
                errori.append(esito.errore)

        # Serializza stato finale (None se la partita non è nemmeno partita).
        stato_finale: StatoPartitaSnapshot | None
        if motore.fase_corrente == FaseTurno.PRE_PARTITA:
            stato_finale = None
        else:
            stato_finale = ServizioRicostruzione._serializza_stato(motore)

        # Upsert dello snapshot.
        snapshot = await ServizioRicostruzione._upsert_snapshot(
            db,
            partita_id=partita_id,
            successo=(len(errori) == 0 and n_applicati > 0),
            n_eventi_totali=len(eventi),
            n_eventi_applicati=n_applicati,
            stato_finale=stato_finale,
            errori=errori,
        )
        return snapshot

    @staticmethod
    async def trova_snapshot(
        db: AsyncSession, partita_id: str
    ) -> StatoPartitaRicostruito | None:
        """Ritorna lo snapshot corrente di una partita, se esiste."""
        # Prima verifica esistenza partita per dare 404 chiaro.
        await ServizioRicostruzione._carica_partita(db, partita_id)

        stmt = select(StatoPartitaRicostruito).where(
            StatoPartitaRicostruito.partita_id == partita_id
        )
        risultato = await db.execute(stmt)
        return risultato.scalar_one_or_none()

    @staticmethod
    async def ricostruisci_fino_a_evento(
        db: AsyncSession, partita_id: str, evento_id: str,
    ) -> StatoPartitaSnapshot | None:
        """
        Ricostruisce lo stato motore applicando gli eventi DALL'INIZIO
        FINO ALL'evento specificato (incluso).

        Returns:
            StatoPartitaSnapshot al momento subito DOPO l'evento, oppure
            None se la partita non e' partita (fase = PRE_PARTITA).

        Raises:
            HTTPException equivalent: l'evento non appartiene alla partita.

        Note:
            Non persiste lo snapshot, e' solo per query temporanea.
            Costo: O(N_eventi_fino_a_target). Per partite < 500 eventi
            e' istantaneo (~50ms).
        """
        partita = await ServizioRicostruzione._carica_partita(db, partita_id)
        eventi = list(partita.eventi_validati)

        # Verifica che l'evento target appartenga alla partita
        evento_trovato = False
        for ev in eventi:
            if ev.id == evento_id:
                evento_trovato = True
                break
        if not evento_trovato:
            raise ValueError(
                f"Evento '{evento_id}' non trovato nella partita '{partita_id}'"
            )

        motore = ServizioRicostruzione._crea_motore(partita)

        for indice, evento in enumerate(eventi):
            ServizioRicostruzione._applica_evento(
                motore, evento, posizione=indice
            )
            if evento.id == evento_id:
                # Stop dopo aver applicato l'evento target
                break

        if motore.fase_corrente == FaseTurno.PRE_PARTITA:
            return None
        return ServizioRicostruzione._serializza_stato(motore)

    # === Private: caricamento dati ===

    @staticmethod
    async def _carica_partita(db: AsyncSession, partita_id: str) -> Partita:
        stmt = (
            select(Partita)
            .where(Partita.id == partita_id)
            .options(
                selectinload(Partita.giocatori),
                selectinload(Partita.eventi_validati),
            )
        )
        risultato = await db.execute(stmt)
        partita = risultato.scalar_one_or_none()
        if partita is None:
            raise PartitaInesistenteError(
                f"Partita '{partita_id}' non trovata"
            )
        return partita

    # === Private: setup motore ===

    @staticmethod
    def _crea_motore(partita: Partita) -> MotorePartita:
        """Crea un motore vuoto coi giocatori della partita."""
        configurazioni = [
            ConfigurazioneGiocatore(
                player_id=g.id,
                # `g.colore` può essere str (letto da DB) o ColoreGiocatore enum
                colore=MotoreColoreGiocatore(
                    g.colore.value if hasattr(g.colore, "value") else g.colore
                ),
                nome=g.nome,
            )
            for g in partita.giocatori
        ]
        stato = StatoPartita(configurazioni)
        return MotorePartita(stato)

    # === Private: applicazione di un singolo evento ===

    @staticmethod
    def _applica_evento(
        motore: MotorePartita,
        evento: EventoValidato,
        posizione: int,
    ) -> _RisultatoApplicazione:
        """
        Dispatch su `evento.tipo` verso l'applicatore corrispondente.
        Cattura ogni eccezione, traducendola in `ErroreRicostruzioneSchema`.
        """
        applicatore = _APPLICATORI.get(evento.tipo)
        if applicatore is None:
            return _RisultatoApplicazione(
                applicato=False,
                errore=_costruisci_errore(
                    evento,
                    posizione,
                    "TipoEventoNonSupportatoError",
                    f"Tipo evento '{evento.tipo}' non applicabile al motore "
                    f"(probabilmente è un evento grezzo CV o informativo)",
                ),
            )

        try:
            applicatore(motore, evento.dati)
            return _RisultatoApplicazione(applicato=True)
        except ValidationError as e:
            return _RisultatoApplicazione(
                applicato=False,
                errore=_costruisci_errore(
                    evento,
                    posizione,
                    "PayloadInvalidoError",
                    f"Payload dati non valido: {e.errors(include_url=False)}",
                ),
            )
        except StatoPartitaError as e:
            return _RisultatoApplicazione(
                applicato=False,
                errore=_costruisci_errore(
                    evento, posizione, type(e).__name__, str(e)
                ),
            )
        except Exception as e:
            # Eccezione inattesa: la registriamo ma non blocchiamo
            return _RisultatoApplicazione(
                applicato=False,
                errore=_costruisci_errore(
                    evento, posizione, type(e).__name__, str(e)
                ),
            )

    # === Private: serializzazione stato ===

    @staticmethod
    def _serializza_stato(motore: MotorePartita) -> StatoPartitaSnapshot:
        """Converte la `vista_arbitro` in StatoPartitaSnapshot Pydantic."""
        vista = motore.stato.vista_arbitro()

        giocatori = [
            InfoGiocatoreSchema(
                player_id=g.player_id,
                colore=g.colore.value,
                nome=g.nome,
                eliminato=g.eliminato,
            )
            for g in vista.giocatori
        ]

        territori = {
            nome: InfoTerritorioSchema(
                nome=info.nome,
                controllore_id=info.controllore_id,
                armate=info.armate,
            )
            for nome, info in vista.territori.items()
        }

        return StatoPartitaSnapshot(
            fase_corrente=motore.fase_corrente.value,
            turno=vista.turno,
            giocatore_attivo_id=vista.giocatore_attivo_id,
            vincitore_id=vista.vincitore_id,
            armate_da_piazzare=motore.armate_da_piazzare,
            tris_giocato_questo_turno=motore.tris_giocato_questo_turno,
            spostamento_effettuato=motore.spostamento_effettuato,
            territori_conquistati_nel_turno=sorted(
                motore.territori_conquistati_nel_turno
            ),
            giocatori=giocatori,
            territori=territori,
            conteggio_mani=dict(vista.conteggio_mani),
            snapshot_mazzo=dict(vista.snapshot_mazzo),
        )

    # === Private: persistence dello snapshot ===

    @staticmethod
    async def _upsert_snapshot(
        db: AsyncSession,
        *,
        partita_id: str,
        successo: bool,
        n_eventi_totali: int,
        n_eventi_applicati: int,
        stato_finale: StatoPartitaSnapshot | None,
        errori: list[ErroreRicostruzioneSchema],
    ) -> StatoPartitaRicostruito:
        """Inserisce o sostituisce lo snapshot della partita."""
        stmt = select(StatoPartitaRicostruito).where(
            StatoPartitaRicostruito.partita_id == partita_id
        )
        esistente = (await db.execute(stmt)).scalar_one_or_none()

        stato_json: dict[str, object] | None = (
            stato_finale.model_dump(mode="json") if stato_finale else None
        )
        errori_json: list[dict[str, object]] = [
            e.model_dump(mode="json") for e in errori
        ]

        if esistente is not None:
            esistente.successo = successo
            esistente.n_eventi_totali = n_eventi_totali
            esistente.n_eventi_applicati = n_eventi_applicati
            esistente.stato_serializzato = stato_json
            esistente.errori = errori_json
            esistente.data_ricostruzione = _dt.datetime.now(_dt.UTC)
            snapshot = esistente
        else:
            snapshot = StatoPartitaRicostruito(
                partita_id=partita_id,
                successo=successo,
                n_eventi_totali=n_eventi_totali,
                n_eventi_applicati=n_eventi_applicati,
                stato_serializzato=stato_json,
                errori=errori_json,
            )
            db.add(snapshot)

        await db.commit()
        await db.refresh(snapshot)
        return snapshot


# === Helper costruzione errore ===


def _costruisci_errore(
    evento: EventoValidato,
    posizione: int,
    classe: str,
    messaggio: str,
) -> ErroreRicostruzioneSchema:
    tipo_str = (
        evento.tipo.value if hasattr(evento.tipo, "value") else str(evento.tipo)
    )
    return ErroreRicostruzioneSchema(
        evento_validato_id=evento.id,
        posizione_nella_sequenza=posizione,
        tipo_evento=tipo_str,
        ts_evento=evento.ts_evento,
        classe_errore=classe,
        messaggio=messaggio,
    )


# === Applicatori (mapping TipoEvento → metodo motore) ===
#
# Ogni applicatore prende `(motore, dati_dict)` e:
# 1. Valida `dati_dict` con uno schema Pydantic.
# 2. Esegue eventuali transizioni di fase implicite necessarie.
# 3. Chiama il metodo appropriato del motore.
#
# Eventuali eccezioni si propagano e vengono catturate dal dispatcher.


def _applica_territorio_assegnato(motore: MotorePartita, dati: dict[str, Any]) -> None:
    """Setup pre-partita: assegna un territorio a un giocatore con N armate."""
    parsato = DatiTerritorioAssegnatoInizio.model_validate(dati)
    motore.stato.assegna_territorio(
        parsato.territorio, parsato.giocatore_id, parsato.n_armate
    )


def _applica_obiettivo_assegnato(motore: MotorePartita, dati: dict[str, Any]) -> None:
    """Setup pre-partita: assegna un obiettivo a un giocatore."""
    parsato = DatiObiettivoAssegnato.model_validate(dati)
    obiettivo = obiettivo_per_id(parsato.obiettivo_id)
    motore.stato.assegna_obiettivo(parsato.giocatore_id, obiettivo)


def _applica_partita_inizio(motore: MotorePartita, dati: dict[str, Any]) -> None:
    """Avvia la partita."""
    parsato = DatiPartitaInizio.model_validate(dati)
    motore.inizia_partita(parsato.primo_giocatore_id)


def _applica_armate_piazzate(motore: MotorePartita, dati: dict[str, Any]) -> None:
    """Piazza armate in fase RINFORZO."""
    parsato = DatiArmatePiazzate.model_validate(dati)
    motore.piazza_armate(parsato.territorio, parsato.n)


def _applica_tris_giocato(motore: MotorePartita, dati: dict[str, Any]) -> None:
    """Gioca un tris in fase RINFORZO."""
    parsato = DatiTrisGiocato.model_validate(dati)
    carte = [
        Carta(territorio=c.territorio, simbolo=Simbolo(c.simbolo))
        for c in parsato.carte
    ]
    motore.gioca_tris(carte)


def _applica_attacco_risolto(motore: MotorePartita, dati: dict[str, Any]) -> None:
    """
    Esegue un attacco. Gestisce transizione implicita RINFORZO → ATTACCO se
    non ci sono più armate da piazzare.
    """
    parsato = DatiAttaccoRisolto.model_validate(dati)

    # Transizione implicita: se siamo ancora in RINFORZO ma il giocatore ha
    # piazzato tutte le armate, passa automaticamente ad ATTACCO.
    if (
        motore.fase_corrente == FaseTurno.RINFORZO
        and motore.armate_da_piazzare == 0
    ):
        motore.passa_a_attacco()

    motore.attacca(
        parsato.da, parsato.a, parsato.dadi_attaccante, parsato.dadi_difensore
    )


def _applica_armate_spostate(motore: MotorePartita, dati: dict[str, Any]) -> None:
    """
    Spostamento finale di armate. Gestisce transizione ATTACCO → SPOSTAMENTO.
    """
    parsato = DatiArmateSpostate.model_validate(dati)

    if motore.fase_corrente == FaseTurno.ATTACCO:
        motore.passa_a_spostamento()

    motore.sposta(parsato.da, parsato.a, parsato.n)


def _applica_turno_finito(motore: MotorePartita, dati: dict[str, Any]) -> None:
    """
    Termina il turno corrente. Se siamo in fasi precedenti (es. ATTACCO senza
    spostamento), gestisce le transizioni implicite necessarie.
    """
    DatiTurnoFinito.model_validate(dati)  # validazione minima

    if motore.fase_corrente == FaseTurno.RINFORZO and motore.armate_da_piazzare == 0:
        motore.passa_a_attacco()
    if motore.fase_corrente == FaseTurno.ATTACCO:
        motore.passa_a_spostamento()

    motore.fine_turno()


# Tipo della funzione applicatore.
_TipoApplicatore = Callable[[MotorePartita, dict[str, Any]], None]


#: Tabella di dispatch: `TipoEvento` → applicatore.
#: I tipi non presenti qui (eventi CV grezzi, note, partita_fine info-only)
#: vengono saltati durante la ricostruzione con un'errore informativo.
_APPLICATORI: dict[TipoEvento, _TipoApplicatore] = {
    TipoEvento.TERRITORIO_ASSEGNATO_INIZIO: _applica_territorio_assegnato,
    TipoEvento.OBIETTIVO_ASSEGNATO: _applica_obiettivo_assegnato,
    TipoEvento.PARTITA_INIZIO: _applica_partita_inizio,
    TipoEvento.ARMATE_PIAZZATE: _applica_armate_piazzate,
    TipoEvento.TRIS_GIOCATO: _applica_tris_giocato,
    TipoEvento.ATTACCO_RISOLTO: _applica_attacco_risolto,
    TipoEvento.ARMATE_SPOSTATE: _applica_armate_spostate,
    TipoEvento.TURNO_FINITO: _applica_turno_finito,
}


__all__ = [
    "PartitaInesistenteError",
    "PayloadInvalidoError",
    "RicostruzioneError",
    "ServizioRicostruzione",
    "TipoEventoNonSupportatoError",
]
