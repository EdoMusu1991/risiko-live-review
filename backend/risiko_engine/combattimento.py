"""
Risoluzione del combattimento del Risiko classico Editrice Giochi.

Regole implementate:
- L'attaccante può usare fino a 3 dadi, ma deve sempre lasciare almeno
  1 armata nel territorio attaccante. Quindi `max_dadi = min(3, armate - 1)`.
- Il difensore può usare fino a 3 dadi, `max_dadi = min(3, armate)`.
- I dadi vengono ordinati in modo decrescente e confrontati a coppie.
- A parità di valore vince il difensore.
- Per ogni coppia: chi perde scarta 1 armata.

Esempio:
    Attaccante: [6, 5, 4]
    Difensore:  [6, 4]
    Confronti: 6 vs 6 -> difensore vince (pareggio), attaccante perde 1
              5 vs 4 -> attaccante vince, difensore perde 1
    Risultato: 1 perdita per parte.
"""

import random
from dataclasses import dataclass

# Massimo numero di dadi che ciascuna parte può tirare in un singolo scontro
MAX_DADI = 3


def max_dadi_attaccante(armate_in_territorio: int) -> int:
    """
    Calcola il numero massimo di dadi che l'attaccante può tirare.

    L'attaccante deve sempre lasciare almeno 1 armata nel territorio
    attaccante, quindi può tirare al massimo `armate - 1` dadi (fino a 3).

    Args:
        armate_in_territorio: numero di armate nel territorio attaccante

    Returns:
        Numero di dadi tirabili (0-3). Se < 2 armate, ritorna 0 (non si attacca).
    """
    return max(0, min(MAX_DADI, armate_in_territorio - 1))


def max_dadi_difensore(armate_in_territorio: int) -> int:
    """
    Calcola il numero massimo di dadi che il difensore può tirare.

    Il difensore può tirare 1 dado per ogni armata presente, fino a 3.

    Args:
        armate_in_territorio: numero di armate nel territorio difensore

    Returns:
        Numero di dadi tirabili (0-3).
    """
    return max(0, min(MAX_DADI, armate_in_territorio))


@dataclass(frozen=True, slots=True)
class RisultatoCombattimento:
    """Esito di un singolo scontro tra attaccante e difensore."""

    perdite_attaccante: int
    perdite_difensore: int

    @property
    def totale_perdite(self) -> int:
        return self.perdite_attaccante + self.perdite_difensore

    def __repr__(self) -> str:
        return (
            f"Risultato(att perde {self.perdite_attaccante}, "
            f"dif perde {self.perdite_difensore})"
        )


def risolvi_combattimento(
    dadi_attaccante: list[int],
    dadi_difensore: list[int],
) -> RisultatoCombattimento:
    """
    Calcola le perdite per attaccante e difensore in base ai dadi tirati.

    Args:
        dadi_attaccante: 1-3 valori interi tra 1 e 6
        dadi_difensore: 1-3 valori interi tra 1 e 6

    Returns:
        RisultatoCombattimento con le perdite per ciascuna parte.

    Raises:
        ValueError: se la quantità di dadi è fuori range (1-3) o se un valore
                    di dado non è tra 1 e 6.
    """
    _valida_dadi(dadi_attaccante, "attaccante")
    _valida_dadi(dadi_difensore, "difensore")

    # Ordina decrescente e confronta a coppie fino al minimo
    att_ord = sorted(dadi_attaccante, reverse=True)
    dif_ord = sorted(dadi_difensore, reverse=True)
    coppie = min(len(att_ord), len(dif_ord))

    perdite_att = 0
    perdite_dif = 0
    for i in range(coppie):
        if att_ord[i] > dif_ord[i]:
            perdite_dif += 1
        else:
            # A parità vince il difensore
            perdite_att += 1

    return RisultatoCombattimento(
        perdite_attaccante=perdite_att,
        perdite_difensore=perdite_dif,
    )


def _valida_dadi(dadi: list[int], parte: str) -> None:
    """Solleva ValueError se la lista dadi non rispetta i vincoli."""
    if not 1 <= len(dadi) <= MAX_DADI:
        raise ValueError(
            f"{parte.capitalize()} deve tirare 1-{MAX_DADI} dadi, "
            f"ne ha tirati {len(dadi)}"
        )
    for d in dadi:
        if not 1 <= d <= 6:
            raise ValueError(
                f"Valore dado non valido per {parte}: {d} (deve essere 1-6)"
            )


def lancia_dadi(n: int, rng: random.Random | None = None) -> list[int]:
    """
    Lancia N dadi a 6 facce.

    Args:
        n: numero di dadi (deve essere >= 0)
        rng: generatore casuale opzionale (per testing riproducibile).
             Se None, usa l'RNG di default.

    Returns:
        Lista di N valori interi tra 1 e 6 inclusi.

    Raises:
        ValueError: se n < 0
    """
    if n < 0:
        raise ValueError(f"Numero dadi negativo: {n}")
    rng_use = rng if rng is not None else random.Random()
    return [rng_use.randint(1, 6) for _ in range(n)]
