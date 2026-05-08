"""
State machine del flusso di turno Risiko.

Orchestratore che pilota la partita attraverso le fasi:

    PRE_PARTITA -> RINFORZO -> ATTACCO -> SPOSTAMENTO -> FINE_TURNO -> RINFORZO -> ...

Quando un giocatore raggiunge il proprio obiettivo durante il turno, la
partita transisce a FINE_PARTITA e nessuna ulteriore azione è ammessa.

**Architettura**: la `MotorePartita` non gestisce direttamente lo stato
dei territori — quello è di responsabilità di `StatoPartita`. Il motore
si limita a:
- Tracciare la fase corrente e lo stato effimero del turno
  (armate residue da piazzare, tris già giocato, territori conquistati,
  spostamento effettuato)
- Validare che ogni azione sia ammissibile nella fase corrente
- Validare le regole di gioco (adiacenze, ownership, dadi, ecc.)
- Delegare le mutazioni di stato a `StatoPartita`
- Orchestrare le transizioni di fase

**Dadi iniettati**: `attacca()` riceve i valori dei dadi come parametri.
Il motore non lancia mai dadi internamente. Questo separa nettamente la
logica di gioco dalla sorgente di casualità (RNG simulato, dadi fisici BLE,
replay deterministico). Il chiamante è responsabile di lanciare i dadi
prima di chiamare `attacca()`.

**Conquista e movimento minimo**: alla conquista di un territorio, il
motore sposta automaticamente N armate dal territorio attaccante al
conquistato, dove N è il numero di dadi tirati dall'attaccante. Questo
è il minimo regolamentare. Spostamenti aggiuntivi possono essere fatti
nella fase SPOSTAMENTO o tramite attacchi successivi dal nuovo territorio.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from risiko_engine.bonus import (
    bonus_combinazione,
    bonus_per_continenti,
    bonus_per_territori,
    is_tris_valido,
)
from risiko_engine.carte import Carta
from risiko_engine.combattimento import (
    RisultatoCombattimento,
    risolvi_combattimento,
)
from risiko_engine.mappa import TERRITORI, adiacenti_a
from risiko_engine.stato_partita import (
    StatoPartita,
    StatoPartitaError,
)

# === Fasi turno ===


class FaseTurno(StrEnum):
    """Le fasi del flusso di partita."""

    PRE_PARTITA = "pre_partita"
    """Setup completato ma `inizia_partita()` non ancora chiamato."""

    RINFORZO = "rinforzo"
    """Il giocatore attivo riceve e piazza nuove armate."""

    ATTACCO = "attacco"
    """Il giocatore attivo può effettuare 0..N attacchi."""

    SPOSTAMENTO = "spostamento"
    """Il giocatore attivo può effettuare 0..1 spostamento finale."""

    FINE_PARTITA = "fine_partita"
    """La partita è terminata, c'è un vincitore."""


# === Eccezioni ===


class FaseSbagliataError(StatoPartitaError):
    """Azione richiesta in una fase di turno che non la permette."""


class AzioneIllegaleError(StatoPartitaError):
    """L'azione viola una regola di gioco (adiacenza, ownership, dadi, ecc.)."""


class TrisInvalidoError(StatoPartitaError):
    """Le carte non formano un tris valido secondo le regole."""


class TrisGiaGiocatoError(StatoPartitaError):
    """Tentativo di giocare un secondo tris nello stesso turno."""


class SpostamentoGiaEffettuatoError(StatoPartitaError):
    """Tentativo di un secondo spostamento di fine turno nello stesso turno."""


class ArmateNonTuttePiazzateError(StatoPartitaError):
    """Tentativo di passare ad ATTACCO senza aver piazzato tutte le armate."""


class SetupIncompletoError(StatoPartitaError):
    """`inizia_partita()` chiamata con setup non completato."""


# === Stato effimero del turno ===


@dataclass(slots=True)
class _StatoTurno:
    """
    Stato che dura solo per il turno corrente, resettato a inizio turno.
    Contiene info che non sono parte di `StatoPartita` ma servono al motore
    per applicare le regole.
    """

    fase: FaseTurno = FaseTurno.PRE_PARTITA
    armate_da_piazzare: int = 0
    tris_giocato: bool = False
    territori_conquistati: set[str] = field(default_factory=set)
    spostamento_effettuato: bool = False

    def reset_per_nuovo_turno(self, armate_iniziali: int) -> None:
        """Resetta lo stato per il nuovo turno e va in RINFORZO."""
        self.fase = FaseTurno.RINFORZO
        self.armate_da_piazzare = armate_iniziali
        self.tris_giocato = False
        self.territori_conquistati = set()
        self.spostamento_effettuato = False


# === Costanti regolamento ===

#: Massimo numero di dadi che un attaccante può tirare in un singolo combattimento.
MAX_DADI_ATTACCANTE = 3

#: Massimo numero di dadi che un difensore può tirare.
MAX_DADI_DIFENSORE = 3

#: Armate minime che devono restare sul territorio attaccante DOPO un attacco
#: (nessun territorio può rimanere senza armate al di fuori della conquista).
ARMATE_MINIME_PRESIDIO = 1


# === Classe principale ===


class MotorePartita:
    """
    Orchestratore della partita Risiko.

    Mantiene la fase corrente e lo stato effimero del turno; valida le azioni
    del giocatore attivo e delega le mutazioni di stato a `StatoPartita`.
    """

    def __init__(self, stato: StatoPartita) -> None:
        self._stato: StatoPartita = stato
        self._turno: _StatoTurno = _StatoTurno()

    # === Properties ===

    @property
    def fase_corrente(self) -> FaseTurno:
        return self._turno.fase

    @property
    def armate_da_piazzare(self) -> int:
        """Armate che il giocatore attivo deve ancora piazzare in RINFORZO."""
        return self._turno.armate_da_piazzare

    @property
    def tris_giocato_questo_turno(self) -> bool:
        return self._turno.tris_giocato

    @property
    def spostamento_effettuato(self) -> bool:
        return self._turno.spostamento_effettuato

    @property
    def territori_conquistati_nel_turno(self) -> frozenset[str]:
        return frozenset(self._turno.territori_conquistati)

    @property
    def stato(self) -> StatoPartita:
        """Accesso allo stato sottostante (read-friendly per le viste)."""
        return self._stato

    @property
    def partita_finita(self) -> bool:
        return self._turno.fase == FaseTurno.FINE_PARTITA

    # === Setup ===

    def inizia_partita(self, primo_giocatore_id: str | None = None) -> None:
        """
        Verifica che il setup sia completo e parte con la fase RINFORZO
        del primo giocatore.

        Args:
            primo_giocatore_id: chi inizia la partita. Se None, viene preso
                                il primo giocatore in `lista_player_id`.
                                Se `giocatore_attivo_id` era già impostato in
                                `StatoPartita`, può essere None e si usa quello.

        Pre-condizioni:
        - Tutti e 42 i territori devono essere assegnati
        - Tutti i giocatori devono possedere almeno 1 territorio
        - Tutti i giocatori devono avere un obiettivo assegnato
        """
        if self._turno.fase != FaseTurno.PRE_PARTITA:
            raise FaseSbagliataError(
                f"inizia_partita richiede PRE_PARTITA, fase corrente: "
                f"{self._turno.fase}"
            )

        # Verifica che tutti i territori siano assegnati
        for terr in TERRITORI:
            if self._stato.controllore_di(terr) is None:
                raise SetupIncompletoError(
                    f"Territorio '{terr}' non assegnato a nessun giocatore"
                )

        # Verifica che ogni giocatore abbia territori e obiettivo
        for pid in self._stato.lista_player_id:
            if not self._stato.territori_di(pid):
                raise SetupIncompletoError(
                    f"Giocatore '{pid}' non controlla nessun territorio"
                )
            vista = self._stato.vista_giocatore(pid)
            if vista.mio_obiettivo is None:
                raise SetupIncompletoError(
                    f"Giocatore '{pid}' senza obiettivo assegnato"
                )

        # Determina chi inizia
        if primo_giocatore_id is not None:
            id_iniziale = primo_giocatore_id
        elif self._stato.giocatore_attivo_id is not None:
            id_iniziale = self._stato.giocatore_attivo_id
        else:
            id_iniziale = self._stato.lista_player_id[0]

        self._stato.inizia_primo_turno(id_iniziale)

        armate = self._calcola_rinforzi_iniziali(id_iniziale)
        self._turno.reset_per_nuovo_turno(armate)

    # === Fase RINFORZO ===

    def gioca_tris(self, carte: list[Carta]) -> int:
        """
        Il giocatore attivo gioca un tris di carte.

        Effetti:
        - Rimuove le 3 carte dalla mano
        - Aggiunge il bonus tris al pool di armate da piazzare
        - Per ogni carta del tris che mostra un territorio posseduto dal
          giocatore, aggiunge automaticamente +2 armate su quel territorio
        - Le carte vanno agli scarti del mazzo

        Returns:
            Il bonus armate del tris (4/6/8/10) — NON include il +2 sui
            territori, che è applicato direttamente alla mappa.

        Raises:
            FaseSbagliataError: se non siamo in RINFORZO.
            TrisInvalidoError: se le carte non formano un tris valido.
            TrisGiaGiocatoError: se è già stato giocato un tris in questo turno.
        """
        self._richiedi_fase(FaseTurno.RINFORZO)

        if self._turno.tris_giocato:
            raise TrisGiaGiocatoError(
                "Hai già giocato un tris in questo turno"
            )

        if not is_tris_valido(carte):
            raise TrisInvalidoError(
                f"Le carte fornite non formano un tris valido: {carte}"
            )

        player_id = self._giocatore_attivo()
        territori_giocatore = self._stato.territori_di(player_id)

        # Bonus tris (le carte vengono rimosse internamente da gioca_tris)
        bonus_tris = bonus_combinazione(carte)

        # Bonus +2 sui territori posseduti mostrati sulle carte (non jolly)
        for c in carte:
            if c.is_jolly or c.territorio is None:
                continue
            if c.territorio in territori_giocatore:
                self._stato.aggiungi_armate(c.territorio, 2)

        # Rimuovi le carte dalla mano (questo manda anche agli scarti del mazzo)
        self._stato.gioca_tris(player_id, carte)

        self._turno.armate_da_piazzare += bonus_tris
        self._turno.tris_giocato = True

        return bonus_tris

    def piazza_armate(self, territorio: str, n: int) -> None:
        """
        Il giocatore attivo piazza N armate su un territorio proprio.

        Raises:
            FaseSbagliataError: se non siamo in RINFORZO.
            AzioneIllegaleError: se territorio non è del giocatore attivo
                                 o se N supera le armate disponibili.
        """
        self._richiedi_fase(FaseTurno.RINFORZO)

        if n < 1:
            raise ValueError(f"n deve essere >= 1, ricevuto {n}")
        if n > self._turno.armate_da_piazzare:
            raise AzioneIllegaleError(
                f"Tentativo di piazzare {n} armate ma ne sono disponibili "
                f"solo {self._turno.armate_da_piazzare}"
            )

        player_id = self._giocatore_attivo()
        if self._stato.controllore_di(territorio) != player_id:
            raise AzioneIllegaleError(
                f"Territorio '{territorio}' non controllato dal giocatore "
                f"attivo '{player_id}'"
            )

        self._stato.aggiungi_armate(territorio, n)
        self._turno.armate_da_piazzare -= n

    def passa_a_attacco(self) -> None:
        """
        Termina la fase RINFORZO e entra in ATTACCO.

        Raises:
            ArmateNonTuttePiazzateError: se ci sono ancora armate da piazzare.
        """
        self._richiedi_fase(FaseTurno.RINFORZO)

        if self._turno.armate_da_piazzare > 0:
            raise ArmateNonTuttePiazzateError(
                f"Ci sono ancora {self._turno.armate_da_piazzare} armate "
                f"da piazzare prima di poter passare ad ATTACCO"
            )

        self._turno.fase = FaseTurno.ATTACCO

    # === Fase ATTACCO ===

    def attacca(
        self,
        da: str,
        a: str,
        dadi_attaccante: list[int],
        dadi_difensore: list[int],
    ) -> RisultatoCombattimento:
        """
        Esegue un attacco da un territorio proprio verso uno adiacente nemico.

        Args:
            da: territorio attaccante (deve essere del giocatore attivo, con
                almeno 2 armate).
            a: territorio difensore (deve essere adiacente a `da`, controllato
               da un avversario).
            dadi_attaccante: valori (1-6) dei dadi tirati dall'attaccante,
                             tra 1 e min(3, armate_di_da - 1).
            dadi_difensore: valori dei dadi tirati dal difensore, tra 1 e
                            min(3, armate_di_a).

        Conquista: se il difensore raggiunge 0 armate, il territorio passa
        all'attaccante. Vengono spostate automaticamente N armate dal
        territorio attaccante al conquistato, dove N = numero dadi attaccante
        (minimo regolamentare).

        Returns:
            Il `RisultatoCombattimento` con le perdite di entrambi i lati.

        Raises:
            FaseSbagliataError: se non siamo in ATTACCO.
            AzioneIllegaleError: per violazione delle regole di adiacenza,
                                 ownership, o dadi.
        """
        self._richiedi_fase(FaseTurno.ATTACCO)
        self._valida_attacco(da, a, dadi_attaccante, dadi_difensore)

        # Risolvi il combattimento (pure function, non ha effetti collaterali)
        risultato = risolvi_combattimento(dadi_attaccante, dadi_difensore)

        # Applica le perdite
        if risultato.perdite_attaccante > 0:
            self._stato.rimuovi_armate(da, risultato.perdite_attaccante)
        if risultato.perdite_difensore > 0:
            self._stato.rimuovi_armate(a, risultato.perdite_difensore)

        # Verifica conquista
        if self._stato.armate_su(a) == 0:
            n_armate_da_spostare = len(dadi_attaccante)
            player_id = self._giocatore_attivo()

            # Sposta esattamente N armate (= dadi attaccante) nel conquistato.
            # Le armate sono tolte dall'attaccante e messe sul conquistato
            # come parte del cambio di proprietà.
            self._stato.rimuovi_armate(da, n_armate_da_spostare)
            self._stato.cambia_controllore(a, player_id, n_armate_da_spostare)

            self._turno.territori_conquistati.add(a)

            # Se il vecchio proprietario non ha più territori, eliminalo
            self._gestisci_eventuale_eliminazione()

        return risultato

    def passa_a_spostamento(self) -> None:
        """Termina ATTACCO ed entra in SPOSTAMENTO."""
        self._richiedi_fase(FaseTurno.ATTACCO)
        self._turno.fase = FaseTurno.SPOSTAMENTO

    # === Fase SPOSTAMENTO ===

    def sposta(self, da: str, a: str, n: int) -> None:
        """
        Sposta N armate da un territorio proprio a uno adiacente proprio.
        Solo 1 spostamento per turno.

        Raises:
            FaseSbagliataError: se non siamo in SPOSTAMENTO.
            SpostamentoGiaEffettuatoError: se è già stato fatto in questo turno.
            AzioneIllegaleError: per violazioni di adiacenza/ownership/conteggio.
        """
        self._richiedi_fase(FaseTurno.SPOSTAMENTO)

        if self._turno.spostamento_effettuato:
            raise SpostamentoGiaEffettuatoError(
                "Hai già effettuato lo spostamento di questo turno"
            )
        if n < 1:
            raise ValueError(f"n deve essere >= 1, ricevuto {n}")

        player_id = self._giocatore_attivo()

        if self._stato.controllore_di(da) != player_id:
            raise AzioneIllegaleError(
                f"Territorio sorgente '{da}' non controllato da '{player_id}'"
            )
        if self._stato.controllore_di(a) != player_id:
            raise AzioneIllegaleError(
                f"Territorio destinazione '{a}' non controllato da '{player_id}'"
            )
        if a not in adiacenti_a(da):
            raise AzioneIllegaleError(
                f"'{da}' e '{a}' non sono adiacenti"
            )

        armate_disponibili = self._stato.armate_su(da) - ARMATE_MINIME_PRESIDIO
        if n > armate_disponibili:
            raise AzioneIllegaleError(
                f"Puoi spostare al massimo {armate_disponibili} armate da "
                f"'{da}' (devi lasciarne almeno {ARMATE_MINIME_PRESIDIO})"
            )

        self._stato.rimuovi_armate(da, n)
        self._stato.aggiungi_armate(a, n)
        self._turno.spostamento_effettuato = True

    def fine_turno(self) -> None:
        """
        Termina il turno corrente.

        Sequenza:
        1. Se il giocatore ha conquistato almeno 1 territorio nel turno,
           pesca 1 carta (regolamento Risiko EG)
        2. Verifica vittoria del giocatore attivo
        3. Se vittoria: marca la partita come finita (FINE_PARTITA)
        4. Altrimenti: avanza il turno al prossimo giocatore non eliminato e
           torna in RINFORZO per il nuovo giocatore.
        """
        self._richiedi_fase(FaseTurno.SPOSTAMENTO)
        player_id = self._giocatore_attivo()

        # Pesca carta se ha conquistato almeno un territorio
        if self._turno.territori_conquistati:
            try:
                self._stato.pesca_carta(player_id)
            except StatoPartitaError:
                # Mazzo esaurito o altre eccezioni: non bloccare il flusso turno
                pass

        # Verifica vittoria
        if self._stato.verifica_vittoria_corrente(player_id):
            self._stato.imposta_vincitore(player_id)
            self._turno.fase = FaseTurno.FINE_PARTITA
            return

        # Avanza il turno al prossimo giocatore
        self._stato.avanza_turno()
        prossimo_giocatore = self._stato.giocatore_attivo_id
        if prossimo_giocatore is None:
            # Caso degenere: nessun giocatore disponibile
            self._turno.fase = FaseTurno.FINE_PARTITA
            return

        armate = self._calcola_rinforzi_iniziali(prossimo_giocatore)
        self._turno.reset_per_nuovo_turno(armate)

    # === Helper interni ===

    def _giocatore_attivo(self) -> str:
        """Ritorna l'id del giocatore attivo. Solleva se non impostato."""
        pid = self._stato.giocatore_attivo_id
        if pid is None:
            raise SetupIncompletoError("Nessun giocatore attivo impostato")
        return pid

    def _richiedi_fase(self, fase_attesa: FaseTurno) -> None:
        if self._turno.fase != fase_attesa:
            raise FaseSbagliataError(
                f"Azione richiede fase {fase_attesa}, "
                f"fase corrente: {self._turno.fase}"
            )

    def _calcola_rinforzi_iniziali(self, player_id: str) -> int:
        """
        Calcola le armate base che il giocatore riceve in RINFORZO:
        bonus territori + bonus continenti. Tris e carte-su-territori
        sono aggiunti separatamente quando il giocatore decide di giocare
        un tris.
        """
        territori = self._stato.territori_di(player_id)
        n_territori = len(territori)
        return bonus_per_territori(n_territori) + bonus_per_continenti(territori)

    def _valida_attacco(
        self,
        da: str,
        a: str,
        dadi_att: list[int],
        dadi_dif: list[int],
    ) -> None:
        """Verifica tutte le precondizioni di un attacco."""
        player_id = self._giocatore_attivo()

        # Ownership
        if self._stato.controllore_di(da) != player_id:
            raise AzioneIllegaleError(
                f"Territorio attaccante '{da}' non controllato da '{player_id}'"
            )
        if self._stato.controllore_di(a) == player_id:
            raise AzioneIllegaleError(
                f"Non puoi attaccare il tuo territorio '{a}'"
            )
        if self._stato.controllore_di(a) is None:
            raise AzioneIllegaleError(
                f"Territorio difensore '{a}' non assegnato"
            )

        # Adiacenza
        if a not in adiacenti_a(da):
            raise AzioneIllegaleError(
                f"'{da}' e '{a}' non sono adiacenti, non puoi attaccare"
            )

        # Conteggio dadi attaccante
        n_att = len(dadi_att)
        armate_att = self._stato.armate_su(da)
        max_dadi_att_consentito = min(MAX_DADI_ATTACCANTE, armate_att - 1)
        if n_att < 1 or n_att > max_dadi_att_consentito:
            raise AzioneIllegaleError(
                f"Numero dadi attaccante ({n_att}) fuori range valido "
                f"[1, {max_dadi_att_consentito}] per '{da}' con "
                f"{armate_att} armate"
            )

        # Conteggio dadi difensore
        n_dif = len(dadi_dif)
        armate_dif = self._stato.armate_su(a)
        max_dadi_dif_consentito = min(MAX_DADI_DIFENSORE, armate_dif)
        if n_dif < 1 or n_dif > max_dadi_dif_consentito:
            raise AzioneIllegaleError(
                f"Numero dadi difensore ({n_dif}) fuori range valido "
                f"[1, {max_dadi_dif_consentito}] per '{a}' con "
                f"{armate_dif} armate"
            )

        # Valori dadi 1-6
        for d in dadi_att + dadi_dif:
            if not 1 <= d <= 6:
                raise AzioneIllegaleError(
                    f"Valore dado fuori range 1-6: {d}"
                )

    def _gestisci_eventuale_eliminazione(self) -> None:
        """
        Dopo una conquista, controlla se qualche giocatore (escluso quello
        attivo) ha perso tutti i territori. Se sì, lo marca come eliminato.
        """
        player_attivo = self._giocatore_attivo()
        for pid in self._stato.lista_player_id:
            if pid == player_attivo:
                continue
            # Salto i già eliminati
            vista = self._stato.vista_arbitro()
            info_g = next(
                (g for g in vista.giocatori if g.player_id == pid),
                None,
            )
            if info_g is None or info_g.eliminato:
                continue
            if not self._stato.territori_di(pid):
                self._stato.elimina_giocatore(pid)
