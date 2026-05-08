"""
Calcolo dei bonus rinforzo del Risiko classico Editrice Giochi.

Tre tipi di bonus che si sommano in fase rinforzo:

1. **Per territori posseduti**: max(3, n_territori // 3)
2. **Per continenti completi**: somma dei bonus dei continenti controllati
3. **Per combinazioni di carte (tris)**: 4/6/8/10 a seconda della combo

In aggiunta, se una carta del tris giocato corrisponde a un territorio
posseduto, il giocatore riceve un bonus di 2 armate da posizionare
specificamente su quel territorio.

NOTA SUI VALORI: i bonus tris (4/6/8/10) sono quelli del Risiko classico EG.
Alcune varianti casalinghe usano valori diversi o bonus progressivi
(il bonus aumenta ad ogni tris giocato). Se le tue regole sono diverse,
modifica le costanti BONUS_TRIS_* in cima al file.
"""

from collections import Counter

from risiko_engine.carte import Carta, Simbolo
from risiko_engine.mappa import (
    BONUS_CONTINENTE,
    Continente,
    territori_di,
)

# === Costanti di gioco ===

#: Bonus minimo armate per turno indipendentemente dal numero di territori.
BONUS_TERRITORI_MIN = 3

#: Bonus per 3 carte fanti dello stesso simbolo.
BONUS_TRIS_FANTI = 4

#: Bonus per 3 carte cavalieri dello stesso simbolo.
BONUS_TRIS_CAVALIERI = 6

#: Bonus per 3 carte cannoni dello stesso simbolo.
BONUS_TRIS_CANNONI = 8

#: Bonus per un tris misto (1 fante + 1 cavaliere + 1 cannone).
BONUS_TRIS_MISTO = 10

#: Bonus armate aggiuntive per ogni carta giocata che corrisponde a un
#: territorio posseduto dal giocatore. Le armate vanno posizionate
#: specificamente su quel territorio.
BONUS_CARTA_SU_PROPRIO_TERRITORIO = 2


# === Bonus territori ===


def bonus_per_territori(n_territori_posseduti: int) -> int:
    """
    Calcola il bonus armate per il numero di territori controllati.

    Formula: max(3, n // 3). Il minimo è sempre 3, anche se possiedi 0 territori
    (caso teorico, non si verifica in partita reale).

    Esempi:
        bonus_per_territori(0) -> 3
        bonus_per_territori(8) -> 3 (8//3 = 2, ma minimo è 3)
        bonus_per_territori(9) -> 3 (9//3 = 3)
        bonus_per_territori(12) -> 4
        bonus_per_territori(42) -> 14 (caso vittoria, possiede tutto)
    """
    if n_territori_posseduti < 0:
        raise ValueError(f"Territori posseduti negativi: {n_territori_posseduti}")
    return max(BONUS_TERRITORI_MIN, n_territori_posseduti // 3)


# === Bonus continenti ===


def bonus_per_continenti(territori_posseduti: set[str]) -> int:
    """
    Calcola il bonus totale per i continenti completamente controllati.

    Args:
        territori_posseduti: insieme dei territori posseduti dal giocatore

    Returns:
        Somma dei bonus dei continenti completi
    """
    bonus = 0
    for continente in Continente:
        territori_continente = set(territori_di(continente))
        if territori_continente.issubset(territori_posseduti):
            bonus += BONUS_CONTINENTE[continente]
    return bonus


def continenti_controllati(territori_posseduti: set[str]) -> list[Continente]:
    """
    Ritorna la lista dei continenti completamente controllati.

    Utile per debug e per mostrare in UI quali continenti possiede il giocatore.
    """
    risultato: list[Continente] = []
    for continente in Continente:
        territori_continente = set(territori_di(continente))
        if territori_continente.issubset(territori_posseduti):
            risultato.append(continente)
    return risultato


# === Bonus carte (tris) ===


def is_tris_valido(carte: list[Carta]) -> bool:
    """
    Verifica se 3 carte formano un tris valido per il bonus rinforzo.

    Tris validi nel Risiko classico EG:
    - 3 carte con lo stesso simbolo (3 fanti, 3 cavalieri, o 3 cannoni)
    - 1 carta di ogni simbolo (1 fante + 1 cavaliere + 1 cannone)

    I jolly possono sostituire qualsiasi simbolo. Qualsiasi combinazione
    contenente almeno 1 jolly è considerata tris valido (il giocatore
    sceglie come usare il jolly per massimizzare il bonus).

    Args:
        carte: lista di carte da controllare

    Returns:
        True se è un tris valido, False altrimenti.
    """
    if len(carte) != 3:
        return False

    n_jolly = sum(1 for c in carte if c.is_jolly)

    # 2 o 3 jolly: sempre valido (qualsiasi terza carta completa)
    if n_jolly >= 2:
        return True

    # 1 jolly + 2 carte non-jolly: sempre valido
    # (il jolly può sempre completare in tris uguale o misto)
    if n_jolly == 1:
        return True

    # 0 jolly: deve essere stesso simbolo o tris misto
    simboli = [c.simbolo for c in carte]
    counter = Counter(simboli)
    return len(counter) == 1 or len(counter) == 3


def bonus_combinazione(carte: list[Carta]) -> int:
    """
    Calcola il bonus armate per un tris di carte giocato.

    Il giocatore sceglie come usare i jolly per massimizzare il bonus.
    Se la combinazione non è un tris valido, ritorna 0.

    Args:
        carte: lista di 3 carte

    Returns:
        Bonus armate. 0 se non è un tris valido.

    Esempi:
        3 fanti -> 4
        3 cavalieri -> 6
        3 cannoni -> 8
        1 cannone + 1 fante + 1 cavaliere -> 10
        1 jolly + 1 fante + 1 cavaliere -> 10 (jolly = cannone, tris misto)
        1 jolly + 2 cannoni -> 10 (jolly = fante o cavaliere... no, valutiamo)
    """
    if not is_tris_valido(carte):
        return 0

    n_jolly = sum(1 for c in carte if c.is_jolly)
    simboli_non_jolly = [c.simbolo for c in carte if not c.is_jolly]

    # Caso senza jolly: combinazione esatta
    if n_jolly == 0:
        counter = Counter(simboli_non_jolly)
        if len(counter) == 1:
            return _bonus_tris_uguale(simboli_non_jolly[0])
        return BONUS_TRIS_MISTO  # uno di ognuno

    # Con jolly: il giocatore sceglie il bonus massimo possibile
    return _bonus_jolly_massimo(simboli_non_jolly, n_jolly)


def _bonus_tris_uguale(simbolo: Simbolo) -> int:
    """Bonus per 3 carte con lo stesso simbolo."""
    if simbolo == Simbolo.FANTE:
        return BONUS_TRIS_FANTI
    if simbolo == Simbolo.CAVALIERE:
        return BONUS_TRIS_CAVALIERI
    if simbolo == Simbolo.CANNONE:
        return BONUS_TRIS_CANNONI
    raise ValueError(f"Simbolo non valido per tris uguale: {simbolo}")


def _bonus_jolly_massimo(simboli_non_jolly: list[Simbolo], n_jolly: int) -> int:
    """
    Calcola il massimo bonus possibile usando i jolly come sostituti.

    Strategia: il giocatore sceglie sempre la combinazione che massimizza il
    bonus. Visto che il tris misto (10) è il bonus più alto, il jolly viene
    quasi sempre usato per completare un tris misto.
    Eccezione: se le carte non-jolly hanno tutte lo stesso simbolo e
    non c'è abbastanza varietà per fare un misto.
    """
    # 3 jolly (caso impossibile: solo 2 jolly nel mazzo, ma gestito)
    if n_jolly == 3:
        return BONUS_TRIS_MISTO

    # 2 jolly + 1 carta: i jolly possono completare misto (10) o tris uguale
    # (4/6/8). Il misto è sempre >= di tutti gli uguali, quindi misto vince.
    if n_jolly == 2:
        return BONUS_TRIS_MISTO

    # 1 jolly + 2 carte
    if n_jolly == 1:
        if len(simboli_non_jolly) != 2:
            raise ValueError("Stato inconsistente: 1 jolly e numero carte non corretto")

        if simboli_non_jolly[0] == simboli_non_jolly[1]:
            # 2 carte stesso simbolo + 1 jolly
            # - jolly = stesso simbolo: tris uguale (4, 6, o 8)
            # - jolly = altro simbolo: solo 2 simboli totali, NON è tris valido
            # Quindi unica opzione: tris uguale
            return _bonus_tris_uguale(simboli_non_jolly[0])

        # 2 carte simboli diversi + 1 jolly: jolly diventa il terzo simbolo
        # -> tris misto (10)
        return BONUS_TRIS_MISTO

    raise ValueError(f"Numero di jolly impossibile: {n_jolly}")


# === Bonus carte su territori posseduti ===


def bonus_carte_su_territori(
    carte_giocate: list[Carta],
    territori_posseduti: set[str],
) -> dict[str, int]:
    """
    Calcola le armate bonus che il giocatore deve posizionare specificamente
    sui territori delle carte giocate, se quei territori sono in suo possesso.

    Regola Risiko classico EG: per ogni carta del tris giocato che corrisponde
    a un territorio posseduto dal giocatore, riceve +2 armate da posizionare
    su quel territorio specifico (non su un territorio a scelta).

    Args:
        carte_giocate: le 3 carte del tris
        territori_posseduti: territori controllati dal giocatore

    Returns:
        Dict territorio -> bonus armate aggiuntive da piazzare lì.
        Solo i territori con bonus > 0 sono inclusi.
    """
    risultato: dict[str, int] = {}
    for carta in carte_giocate:
        if carta.territorio is not None and carta.territorio in territori_posseduti:
            risultato[carta.territorio] = (
                risultato.get(carta.territorio, 0)
                + BONUS_CARTA_SU_PROPRIO_TERRITORIO
            )
    return risultato


# === API di alto livello ===


def calcola_rinforzi_totali(
    territori_posseduti: set[str],
    tris_giocato: list[Carta] | None = None,
) -> int:
    """
    Calcola il totale dei rinforzi armati a inizio turno (esclusi quelli
    speciali da posizionare su territori specifici per il bonus carte).

    Args:
        territori_posseduti: insieme dei territori controllati dal giocatore
        tris_giocato: lista di 3 carte del tris giocato, oppure None se nessun tris

    Returns:
        Totale armate da posizionare liberamente sui propri territori.
    """
    totale = bonus_per_territori(len(territori_posseduti))
    totale += bonus_per_continenti(territori_posseduti)
    if tris_giocato is not None:
        totale += bonus_combinazione(tris_giocato)
    return totale
