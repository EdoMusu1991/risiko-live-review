"""
Validazione coerenza delle inferenze CV rispetto al motore di gioco.

Un'inferenza CV puo' essere "tecnicamente valida" (rispetta il suo
schema Pydantic) ma "semanticamente sbagliata":

- Territorio inferito che non esiste sulla mappa del motore
- Colore inferito che nessun giocatore della partita usa
- n_armate stimato troppo alto (>50 in Risiko classico)
- bbox al di fuori delle dimensioni canoniche
- Confidence sospettosamente bassa

Questo modulo produce un "linter" delle inferenze: per ogni problema
ritorna un `ProblemaInferenza` con codice + severita' (warning/error).
La UI puo' mostrarli come avvisi e l'operatore decide se cancellarle.

Algoritmo: puro Python, dipende solo dai modelli SQLAlchemy passati.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.modelli import GiocatorePartita, InferenzaCV

SeveritaProblema = Literal["error", "warning"]


@dataclass(frozen=True)
class ProblemaInferenza:
    """
    Singolo problema rilevato su un'inferenza.

    Attributes:
        codice: identificatore stabile (per filtri/i18n)
        severita: error (inferenza inutilizzabile) | warning (sospetta)
        inferenza_id: UUID dell'inferenza problematica
        descrizione: messaggio leggibile per l'operatore
    """

    codice: str
    severita: SeveritaProblema
    inferenza_id: str
    descrizione: str


# === Codici di problema ===

CODICE_TERRITORIO_NON_VALIDO = "territorio_non_valido"
"""Territorio inferito non e' tra quelli noti del motore."""

CODICE_COLORE_NON_GIOCATORE = "colore_non_giocatore"
"""Colore inferito non corrisponde a nessun giocatore della partita."""

CODICE_N_ARMATE_ASSURDO = "n_armate_assurdo"
"""n_armate fuori da range plausibile (1..60 in Risiko classico)."""

CODICE_CONFIDENCE_BASSA = "confidence_bassa"
"""confidence < 0.5: detection sospetta, da verificare."""

CODICE_BBOX_DEGENERE = "bbox_degenere"
"""bbox con larghezza o altezza zero/negativa, oppure fuori scala."""

CODICE_TERRITORIO_MANCANTE = "territorio_mancante"
"""L'inferenza non ha territorio (None): non utilizzabile per discrepanze."""

CODICE_COLORE_MANCANTE = "colore_mancante"
"""L'inferenza non ha colore (None): non utilizzabile per discrepanze."""


# Soglie di plausibilita' (regolabili)
N_ARMATE_MAX_PLAUSIBILE = 60
CONFIDENCE_SOGLIA_BASSA = 0.5
DIMENSIONE_MAX_FRAME_RADDRIZZATO = 5000  # pixel, per bbox sanity check


def valida_inferenze(
    inferenze: list[InferenzaCV],
    *,
    territori_validi: set[str] | None = None,
    giocatori: list[GiocatorePartita] | None = None,
) -> list[ProblemaInferenza]:
    """
    Esegue tutte le validazioni su una lista di inferenze.

    Args:
        inferenze: lista da validare.
        territori_validi: set di slug territorio noti al motore. Se
            None, il check `territorio_non_valido` non viene eseguito
            (utile quando lo snapshot motore non e' disponibile).
        giocatori: lista di GiocatorePartita della partita. Se None,
            il check `colore_non_giocatore` non viene eseguito.

    Returns:
        Lista di problemi rilevati (vuota se tutto ok).
    """
    problemi: list[ProblemaInferenza] = []
    colori_validi = (
        {g.colore for g in giocatori} if giocatori is not None else None
    )

    for inf in inferenze:
        # 1. Territorio mancante
        if inf.territorio is None:
            problemi.append(ProblemaInferenza(
                codice=CODICE_TERRITORIO_MANCANTE,
                severita="warning",
                inferenza_id=inf.id,
                descrizione=(
                    "Inferenza senza territorio: non sara' usata nelle "
                    "discrepanze. Probabile bbox non mappata."
                ),
            ))
        elif (
            territori_validi is not None
            and inf.territorio not in territori_validi
        ):
            problemi.append(ProblemaInferenza(
                codice=CODICE_TERRITORIO_NON_VALIDO,
                severita="error",
                inferenza_id=inf.id,
                descrizione=(
                    f"Territorio '{inf.territorio}' non esiste sulla "
                    f"mappa del motore. Falso positivo del modello."
                ),
            ))

        # 2. Colore mancante
        if inf.colore is None:
            problemi.append(ProblemaInferenza(
                codice=CODICE_COLORE_MANCANTE,
                severita="warning",
                inferenza_id=inf.id,
                descrizione=(
                    "Inferenza senza colore: non sara' usata nelle "
                    "discrepanze."
                ),
            ))
        elif (
            colori_validi is not None
            and inf.colore not in colori_validi
        ):
            problemi.append(ProblemaInferenza(
                codice=CODICE_COLORE_NON_GIOCATORE,
                severita="error",
                inferenza_id=inf.id,
                descrizione=(
                    f"Colore '{inf.colore}' non corrisponde a nessun "
                    f"giocatore della partita. Falso positivo del modello."
                ),
            ))

        # 3. n_armate fuori range
        if inf.n_armate_stimate < 0:
            problemi.append(ProblemaInferenza(
                codice=CODICE_N_ARMATE_ASSURDO,
                severita="error",
                inferenza_id=inf.id,
                descrizione=(
                    f"n_armate negativo: {inf.n_armate_stimate}. Bug del "
                    f"client CV."
                ),
            ))
        elif inf.n_armate_stimate > N_ARMATE_MAX_PLAUSIBILE:
            problemi.append(ProblemaInferenza(
                codice=CODICE_N_ARMATE_ASSURDO,
                severita="warning",
                inferenza_id=inf.id,
                descrizione=(
                    f"n_armate {inf.n_armate_stimate} > "
                    f"{N_ARMATE_MAX_PLAUSIBILE}: improbabile in Risiko "
                    f"classico. Verifica manuale."
                ),
            ))

        # 4. Confidence bassa
        if inf.confidence < CONFIDENCE_SOGLIA_BASSA:
            problemi.append(ProblemaInferenza(
                codice=CODICE_CONFIDENCE_BASSA,
                severita="warning",
                inferenza_id=inf.id,
                descrizione=(
                    f"Confidence {inf.confidence:.2f} < "
                    f"{CONFIDENCE_SOGLIA_BASSA}: detection sospetta."
                ),
            ))

        # 5. Bbox degenere o fuori scala
        if len(inf.bbox) == 4:
            x, y, w, h = inf.bbox
            if w <= 0 or h <= 0:
                problemi.append(ProblemaInferenza(
                    codice=CODICE_BBOX_DEGENERE,
                    severita="error",
                    inferenza_id=inf.id,
                    descrizione=(
                        f"Bbox con larghezza={w} o altezza={h} non "
                        f"positive. Bug del client CV."
                    ),
                ))
            elif (
                x > DIMENSIONE_MAX_FRAME_RADDRIZZATO
                or y > DIMENSIONE_MAX_FRAME_RADDRIZZATO
                or w > DIMENSIONE_MAX_FRAME_RADDRIZZATO
                or h > DIMENSIONE_MAX_FRAME_RADDRIZZATO
            ):
                problemi.append(ProblemaInferenza(
                    codice=CODICE_BBOX_DEGENERE,
                    severita="warning",
                    inferenza_id=inf.id,
                    descrizione=(
                        f"Bbox ({x},{y},{w},{h}) supera "
                        f"{DIMENSIONE_MAX_FRAME_RADDRIZZATO}px. Frame "
                        f"raddrizzato fuori scala?"
                    ),
                ))

    return problemi


def conta_problemi_per_severita(
    problemi: list[ProblemaInferenza],
) -> dict[str, int]:
    """Helper: conta quanti error vs warning."""
    return {
        "error": sum(1 for p in problemi if p.severita == "error"),
        "warning": sum(1 for p in problemi if p.severita == "warning"),
    }
