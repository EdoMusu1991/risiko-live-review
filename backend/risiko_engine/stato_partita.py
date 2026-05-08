"""
Stato di una partita Risiko in corso, con knowledge segregation.

Modulo architetturale chiave: mantiene lo stato COMPLETO della partita
internamente e lo espone tramite **viste filtrate** a seconda di chi sta
osservando.

Le 4 viste:

1. `vista_arbitro()` — l'arbitro vede tutto tranne il **contenuto delle
   mani** e gli **obiettivi dei giocatori**. Vede solo i conteggi mani.
2. `vista_giocatore(player_id)` — un giocatore vede la vista arbitro **più**
   la propria mano e il proprio obiettivo. Mai mani o obiettivi altrui.
3. `vista_pubblica()` — gli spettatori vedono lo stesso dell'arbitro: niente
   mani, niente obiettivi, e senza dettagli del mazzo.
4. `vista_post_partita()` — a partita finita, tutto viene rivelato (replay).

**Invariante critico**: nessuna vista (eccetto post-partita) deve mai
contenere il contenuto della mano di un giocatore o l'obiettivo di un altro
giocatore. Verificato da test di regressione esaustivi.

Il modulo si occupa di **stato dei dati**: territori, armate, mani,
obiettivi, mazzo. La gestione delle **fasi di turno** (rinforzo, attacco,
spostamento) è responsabilità separata di `state_machine.py`.
"""

import random
from dataclasses import dataclass, field
from enum import StrEnum

from risiko_engine.carte import Carta
from risiko_engine.gestore_mazzo import GestoreMazzo
from risiko_engine.mappa import TERRITORI
from risiko_engine.obiettivi import (
    Obiettivo,
    verifica_vittoria,
)

# === Colore giocatore ===


class ColoreGiocatore(StrEnum):
    """I 6 colori canonici delle armate del Risiko classico EG."""

    ROSSO = "rosso"
    BLU = "blu"
    VERDE = "verde"
    GIALLO = "giallo"
    NERO = "nero"
    VIOLA = "viola"


# === Eccezioni dominio ===


class StatoPartitaError(Exception):
    """Errore generico sul dominio della partita."""


class TerritorioInesistenteError(StatoPartitaError):
    """Riferimento a un territorio non presente nella mappa."""


class GiocatoreInesistenteError(StatoPartitaError):
    """Riferimento a un player_id non presente nella partita."""


class ColoreDuplicatoError(StatoPartitaError):
    """Due giocatori configurati con lo stesso colore."""


class PlayerIdDuplicatoError(StatoPartitaError):
    """Due giocatori configurati con lo stesso player_id."""


class NumeroGiocatoriError(StatoPartitaError):
    """Numero di giocatori fuori range supportato."""


class ArmateInsufficientiError(StatoPartitaError):
    """Tentativo di rimuovere più armate di quelle presenti su un territorio."""


class CarteInsufficientiError(StatoPartitaError):
    """Tentativo di giocare carte non presenti nella mano del giocatore."""


class TerritorioNonAssegnatoError(StatoPartitaError):
    """Operazione richiede un territorio già assegnato a qualcuno, ma non lo è."""


class GiocatoreEliminatoError(StatoPartitaError):
    """Operazione su un giocatore già eliminato dalla partita."""


# === Soglie configurazione ===

NUMERO_MIN_GIOCATORI = 2
NUMERO_MAX_GIOCATORI = 6


# === Configurazione iniziale giocatori ===


@dataclass(frozen=True, slots=True)
class ConfigurazioneGiocatore:
    """Configurazione di un giocatore al setup della partita."""

    player_id: str
    colore: ColoreGiocatore
    nome: str

    def __post_init__(self) -> None:
        if not self.player_id:
            raise ValueError("player_id non può essere vuoto")
        if not self.nome:
            raise ValueError("nome non può essere vuoto")


# === Stato interno (privato, mai esposto direttamente) ===


@dataclass(slots=True)
class _StatoGiocatoreInterno:
    """
    Stato COMPLETO di un giocatore, comprensivo di informazioni segrete
    (mano e obiettivo). Mai esposto al di fuori del modulo.
    """

    player_id: str
    colore: ColoreGiocatore
    nome: str
    mano_carte: list[Carta] = field(default_factory=list)
    obiettivo: Obiettivo | None = None
    eliminato: bool = False


# === Strutture per le viste (immutabili, sicure da serializzare) ===


@dataclass(frozen=True, slots=True)
class InfoGiocatorePubblica:
    """Info di un giocatore visibili a chiunque (no mano, no obiettivo)."""

    player_id: str
    colore: ColoreGiocatore
    nome: str
    eliminato: bool


@dataclass(frozen=True, slots=True)
class InfoGiocatoreCompleta:
    """Info complete con mano e obiettivo: usata SOLO in vista post-partita."""

    player_id: str
    colore: ColoreGiocatore
    nome: str
    eliminato: bool
    mano_carte: tuple[Carta, ...]
    obiettivo: Obiettivo | None


@dataclass(frozen=True, slots=True)
class InfoTerritorio:
    """Info su un territorio: chi lo controlla e con quante armate."""

    nome: str
    controllore_id: str | None  # None se non ancora assegnato
    armate: int


@dataclass(frozen=True, slots=True)
class VistaArbitro:
    """
    Vista dell'arbitro: tutto tranne contenuto mani e obiettivi.

    L'arbitro è una persona fisica con tablet che conferma le azioni e
    gestisce eccezioni. Vede chi ha quanti carri ovunque, di chi è ogni
    territorio, i conteggi delle mani, lo stato del mazzo. Non vede MAI il
    contenuto delle mani né gli obiettivi.
    """

    turno: int
    giocatore_attivo_id: str | None
    vincitore_id: str | None
    giocatori: tuple[InfoGiocatorePubblica, ...]
    territori: dict[str, InfoTerritorio]
    conteggio_mani: dict[str, int]
    snapshot_mazzo: dict[str, int]


@dataclass(frozen=True, slots=True)
class VistaGiocatore:
    """
    Vista personale di un giocatore.

    Contiene la `VistaArbitro` (info pubbliche) PIÙ la propria mano e il
    proprio obiettivo. Mai mani o obiettivi altrui.
    """

    arbitro: VistaArbitro
    player_id: str
    mia_mano: tuple[Carta, ...]
    mio_obiettivo: Obiettivo | None


@dataclass(frozen=True, slots=True)
class VistaPubblica:
    """
    Vista per gli spettatori (web pubblico).

    Identica all'arbitro per quanto riguarda territori, giocatori e
    conteggi mani, ma senza dettagli del mazzo.
    """

    turno: int
    giocatore_attivo_id: str | None
    vincitore_id: str | None
    giocatori: tuple[InfoGiocatorePubblica, ...]
    territori: dict[str, InfoTerritorio]
    conteggio_mani: dict[str, int]


@dataclass(frozen=True, slots=True)
class VistaPostPartita:
    """
    Vista a partita finita: rivelazione completa per il replay.

    Mani finali, obiettivi di tutti, territori finali. Da invocare SOLO
    dopo che la partita è terminata.
    """

    vincitore_id: str
    turno_finale: int
    giocatori: tuple[InfoGiocatoreCompleta, ...]
    territori_finali: dict[str, InfoTerritorio]


# === Classe principale ===


class StatoPartita:
    """
    Stato completo di una partita Risiko.

    L'API è divisa in tre gruppi:
    - **Mutazioni**: cambiano lo stato (assegna_territorio, cambia_controllore, ...)
    - **Query**: leggono lo stato senza modificarlo (territori_di, armate_su, ...)
    - **Viste**: ritornano snapshot immutabili filtrati per audience.
    """

    def __init__(
        self,
        giocatori: list[ConfigurazioneGiocatore],
        *,
        gestore_mazzo: GestoreMazzo | None = None,
        rng: random.Random | None = None,
    ) -> None:
        """
        Inizializza una partita VUOTA: nessun territorio assegnato, nessuna
        carta distribuita, nessun obiettivo assegnato. La distribuzione
        iniziale è responsabilità di chi chiama (state_machine o test setup).

        Args:
            giocatori: configurazione dei giocatori (2-6).
            gestore_mazzo: opzionale, se non fornito ne crea uno nuovo.
            rng: opzionale, per pescate riproducibili.
        """
        self._valida_configurazione(giocatori)

        self._rng: random.Random = rng if rng is not None else random.Random()
        self._mazzo: GestoreMazzo = (
            gestore_mazzo if gestore_mazzo is not None else GestoreMazzo.nuovo()
        )

        self._giocatori: dict[str, _StatoGiocatoreInterno] = {
            g.player_id: _StatoGiocatoreInterno(
                player_id=g.player_id,
                colore=g.colore,
                nome=g.nome,
            )
            for g in giocatori
        }
        self._ordine_giocatori: list[str] = [g.player_id for g in giocatori]

        self._controllori: dict[str, str] = {}
        self._armate: dict[str, int] = {}

        self._turno: int = 0
        self._giocatore_attivo_id: str | None = None
        self._vincitore_id: str | None = None

    # === Validazione setup ===

    @staticmethod
    def _valida_configurazione(
        giocatori: list[ConfigurazioneGiocatore],
    ) -> None:
        if not (NUMERO_MIN_GIOCATORI <= len(giocatori) <= NUMERO_MAX_GIOCATORI):
            raise NumeroGiocatoriError(
                f"Numero giocatori deve essere tra {NUMERO_MIN_GIOCATORI} "
                f"e {NUMERO_MAX_GIOCATORI}, ricevuto {len(giocatori)}"
            )

        ids = [g.player_id for g in giocatori]
        if len(ids) != len(set(ids)):
            raise PlayerIdDuplicatoError(
                f"player_id duplicati nella configurazione: {ids}"
            )

        colori = [g.colore for g in giocatori]
        if len(colori) != len(set(colori)):
            raise ColoreDuplicatoError(
                f"colori duplicati nella configurazione: {colori}"
            )

    # === Helper interni ===

    def _richiedi_giocatore(self, player_id: str) -> _StatoGiocatoreInterno:
        if player_id not in self._giocatori:
            raise GiocatoreInesistenteError(
                f"Giocatore '{player_id}' non presente in questa partita"
            )
        return self._giocatori[player_id]

    @staticmethod
    def _richiedi_territorio(territorio: str) -> None:
        if territorio not in TERRITORI:
            raise TerritorioInesistenteError(
                f"Territorio '{territorio}' non presente nella mappa"
            )

    # === Mutazioni: territori ===

    def assegna_territorio(
        self, territorio: str, player_id: str, n_armate: int = 1
    ) -> None:
        """Assegna un territorio a un giocatore con N armate iniziali."""
        self._richiedi_territorio(territorio)
        self._richiedi_giocatore(player_id)
        if n_armate < 1:
            raise ValueError(f"n_armate deve essere >= 1, ricevuto {n_armate}")

        self._controllori[territorio] = player_id
        self._armate[territorio] = n_armate

    def cambia_controllore(
        self, territorio: str, nuovo_player_id: str, n_armate: int
    ) -> None:
        """Cambia il controllore di un territorio già assegnato."""
        self._richiedi_territorio(territorio)
        self._richiedi_giocatore(nuovo_player_id)
        if territorio not in self._controllori:
            raise TerritorioNonAssegnatoError(
                f"Territorio '{territorio}' non è stato ancora assegnato"
            )
        if n_armate < 1:
            raise ValueError(f"n_armate deve essere >= 1, ricevuto {n_armate}")

        self._controllori[territorio] = nuovo_player_id
        self._armate[territorio] = n_armate

    def aggiungi_armate(self, territorio: str, n: int) -> None:
        """Aggiunge N armate a un territorio già assegnato."""
        self._richiedi_territorio(territorio)
        if territorio not in self._controllori:
            raise TerritorioNonAssegnatoError(
                f"Territorio '{territorio}' non è stato ancora assegnato"
            )
        if n < 1:
            raise ValueError(f"n deve essere >= 1, ricevuto {n}")
        self._armate[territorio] += n

    def rimuovi_armate(self, territorio: str, n: int) -> None:
        """Rimuove N armate da un territorio."""
        self._richiedi_territorio(territorio)
        if territorio not in self._controllori:
            raise TerritorioNonAssegnatoError(
                f"Territorio '{territorio}' non è stato ancora assegnato"
            )
        if n < 1:
            raise ValueError(f"n deve essere >= 1, ricevuto {n}")
        attuali = self._armate[territorio]
        if attuali < n:
            raise ArmateInsufficientiError(
                f"'{territorio}' ha {attuali} armate, non posso rimuoverne {n}"
            )
        self._armate[territorio] -= n

    # === Mutazioni: carte e obiettivi ===

    def pesca_carta(self, player_id: str) -> Carta:
        """Pesca una carta dal mazzo e la aggiunge alla mano del giocatore."""
        giocatore = self._richiedi_giocatore(player_id)
        if giocatore.eliminato:
            raise GiocatoreEliminatoError(
                f"Giocatore '{player_id}' è eliminato, non può pescare carte"
            )
        carta = self._mazzo.pesca()
        giocatore.mano_carte.append(carta)
        return carta

    def gioca_tris(self, player_id: str, carte: list[Carta]) -> None:
        """
        Rimuove le carte dalla mano del giocatore e le passa agli scarti.
        Validazione del fatto che siano un tris valido è del chiamante.
        """
        giocatore = self._richiedi_giocatore(player_id)
        # Verifica atomica: se anche solo una manca, nulla viene rimosso
        mano_temporanea = list(giocatore.mano_carte)
        for c in carte:
            try:
                mano_temporanea.remove(c)
            except ValueError as e:
                raise CarteInsufficientiError(
                    f"Carta {c} non presente nella mano di '{player_id}'"
                ) from e

        giocatore.mano_carte = mano_temporanea
        self._mazzo.gioca_tris(carte)

    def assegna_obiettivo(self, player_id: str, obiettivo: Obiettivo) -> None:
        """Assegna un obiettivo al giocatore (tipicamente al setup)."""
        giocatore = self._richiedi_giocatore(player_id)
        giocatore.obiettivo = obiettivo

    # === Mutazioni: turno ===

    def imposta_giocatore_attivo(self, player_id: str) -> None:
        self._richiedi_giocatore(player_id)
        self._giocatore_attivo_id = player_id

    def inizia_primo_turno(self, primo_giocatore_id: str) -> None:
        """
        Avvia la partita impostando il primo giocatore attivo e il turno a 1.

        Da chiamare una sola volta in fase di setup, dopo che territori e
        obiettivi sono stati assegnati ma prima della prima azione di gioco.

        Diverso da `avanza_turno`: non incrementa ciclicamente, parte direttamente
        dal giocatore specificato senza passare per la logica del successivo.
        """
        self._richiedi_giocatore(primo_giocatore_id)
        self._giocatore_attivo_id = primo_giocatore_id
        self._turno = 1

    def avanza_turno(self) -> None:
        """
        Passa il turno al prossimo giocatore non eliminato e incrementa il
        contatore di turno.
        """
        attivi = [
            pid
            for pid in self._ordine_giocatori
            if not self._giocatori[pid].eliminato
        ]
        if not attivi:
            return

        self._turno += 1

        if self._giocatore_attivo_id is None:
            self._giocatore_attivo_id = attivi[0]
            return

        try:
            idx_corrente = attivi.index(self._giocatore_attivo_id)
            idx_successivo = (idx_corrente + 1) % len(attivi)
        except ValueError:
            # Il giocatore attivo è stato eliminato dall'ultimo turno
            idx_successivo = 0

        self._giocatore_attivo_id = attivi[idx_successivo]

    def imposta_vincitore(self, player_id: str) -> None:
        """Marca la partita come finita con un vincitore."""
        self._richiedi_giocatore(player_id)
        self._vincitore_id = player_id

    def elimina_giocatore(self, player_id: str) -> None:
        """Marca un giocatore come eliminato."""
        giocatore = self._richiedi_giocatore(player_id)
        giocatore.eliminato = True

    # === Query ===

    @property
    def turno_corrente(self) -> int:
        return self._turno

    @property
    def giocatore_attivo_id(self) -> str | None:
        return self._giocatore_attivo_id

    @property
    def vincitore_id(self) -> str | None:
        return self._vincitore_id

    @property
    def partita_finita(self) -> bool:
        return self._vincitore_id is not None

    @property
    def lista_player_id(self) -> list[str]:
        """Lista dei player_id nell'ordine di seduta."""
        return list(self._ordine_giocatori)

    def territori_di(self, player_id: str) -> set[str]:
        """Set dei territori controllati dal giocatore."""
        self._richiedi_giocatore(player_id)
        return {
            terr for terr, pid in self._controllori.items() if pid == player_id
        }

    def controllore_di(self, territorio: str) -> str | None:
        """Player_id del controllore del territorio, None se non assegnato."""
        self._richiedi_territorio(territorio)
        return self._controllori.get(territorio)

    def armate_su(self, territorio: str) -> int:
        """Numero di armate sul territorio (0 se non assegnato)."""
        self._richiedi_territorio(territorio)
        return self._armate.get(territorio, 0)

    def conta_carte(self, player_id: str) -> int:
        """Numero di carte nella mano del giocatore."""
        return len(self._richiedi_giocatore(player_id).mano_carte)

    def conta_armate_totali(self, player_id: str) -> int:
        """Somma delle armate del giocatore su tutti i suoi territori."""
        self._richiedi_giocatore(player_id)
        return sum(
            self._armate.get(terr, 0)
            for terr, pid in self._controllori.items()
            if pid == player_id
        )

    def colore_di(self, player_id: str) -> ColoreGiocatore:
        return self._richiedi_giocatore(player_id).colore

    def player_id_per_colore(self, colore: ColoreGiocatore) -> str | None:
        """Ritorna il player_id che ha questo colore, o None."""
        for pid, g in self._giocatori.items():
            if g.colore == colore:
                return pid
        return None

    def verifica_vittoria_corrente(self, player_id: str) -> bool:
        """
        Verifica se il giocatore ha raggiunto il proprio obiettivo nello stato
        corrente. Ritorna False se non ha obiettivo assegnato.
        """
        giocatore = self._richiedi_giocatore(player_id)
        if giocatore.obiettivo is None:
            return False
        territori_propri = self.territori_di(player_id)
        return verifica_vittoria(giocatore.obiettivo, territori_propri)

    # === Viste segregate ===

    def _info_giocatori_pubbliche(self) -> tuple[InfoGiocatorePubblica, ...]:
        return tuple(
            InfoGiocatorePubblica(
                player_id=g.player_id,
                colore=g.colore,
                nome=g.nome,
                eliminato=g.eliminato,
            )
            for g in (self._giocatori[pid] for pid in self._ordine_giocatori)
        )

    def _info_territori(self) -> dict[str, InfoTerritorio]:
        return {
            terr: InfoTerritorio(
                nome=terr,
                controllore_id=self._controllori.get(terr),
                armate=self._armate.get(terr, 0),
            )
            for terr in TERRITORI
        }

    def _conteggio_mani(self) -> dict[str, int]:
        return {pid: len(g.mano_carte) for pid, g in self._giocatori.items()}

    def vista_arbitro(self) -> VistaArbitro:
        """Vista per l'arbitro: tutto tranne contenuto mani e obiettivi."""
        return VistaArbitro(
            turno=self._turno,
            giocatore_attivo_id=self._giocatore_attivo_id,
            vincitore_id=self._vincitore_id,
            giocatori=self._info_giocatori_pubbliche(),
            territori=self._info_territori(),
            conteggio_mani=self._conteggio_mani(),
            snapshot_mazzo=self._mazzo.snapshot_stato(),
        )

    def vista_giocatore(self, player_id: str) -> VistaGiocatore:
        """Vista personale: arbitro + propria mano + proprio obiettivo."""
        giocatore = self._richiedi_giocatore(player_id)
        return VistaGiocatore(
            arbitro=self.vista_arbitro(),
            player_id=player_id,
            mia_mano=tuple(giocatore.mano_carte),
            mio_obiettivo=giocatore.obiettivo,
        )

    def vista_pubblica(self) -> VistaPubblica:
        """Vista pubblica: come arbitro ma senza dettagli mazzo."""
        return VistaPubblica(
            turno=self._turno,
            giocatore_attivo_id=self._giocatore_attivo_id,
            vincitore_id=self._vincitore_id,
            giocatori=self._info_giocatori_pubbliche(),
            territori=self._info_territori(),
            conteggio_mani=self._conteggio_mani(),
        )

    def vista_post_partita(self) -> VistaPostPartita:
        """Vista a partita finita: rivela tutto."""
        if self._vincitore_id is None:
            raise StatoPartitaError(
                "Vista post-partita richiesta ma la partita non è ancora finita"
            )

        giocatori_completi = tuple(
            InfoGiocatoreCompleta(
                player_id=g.player_id,
                colore=g.colore,
                nome=g.nome,
                eliminato=g.eliminato,
                mano_carte=tuple(g.mano_carte),
                obiettivo=g.obiettivo,
            )
            for g in (self._giocatori[pid] for pid in self._ordine_giocatori)
        )

        return VistaPostPartita(
            vincitore_id=self._vincitore_id,
            turno_finale=self._turno,
            giocatori=giocatori_completi,
            territori_finali=self._info_territori(),
        )
