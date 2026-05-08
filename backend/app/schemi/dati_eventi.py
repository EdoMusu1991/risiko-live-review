"""
Schemi Pydantic per il payload `dati` degli eventi validati.

Questi schemi sono **runtime validators**: quando il motore ricostruisce
una partita applicando gli eventi, parsa il dict `dati` di ogni
`EventoValidato` con lo schema corrispondente al `tipo`. Se la
struttura non è valida, l'evento è marcato in errore ma la ricostruzione
prosegue con gli eventi successivi.

Convenzione: ogni schema è prefissato `Dati...` per chiarire che
rappresenta il payload `dati` di un certo `tipo` di evento.

Tutti gli schemi includono `giocatore_id` come sanity check: la
ricostruzione verifica che il giocatore indicato sia effettivamente
quello attivo nel motore al momento dell'applicazione (eccezione:
TERRITORIO_ASSEGNATO_INIZIO e OBIETTIVO_ASSEGNATO che avvengono prima
di `inizia_partita`, quindi nessun "attivo").
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _BaseDatiEvento(BaseModel):
    """Base per tutti i payload: vieta campi non dichiarati per cogliere errori."""

    model_config = ConfigDict(extra="forbid")


# === Setup partita ===


class DatiTerritorioAssegnatoInizio(_BaseDatiEvento):
    """
    Distribuzione iniziale di un territorio a un giocatore.

    Tipicamente avviene prima di PARTITA_INIZIO. Tutti i 42 territori
    devono essere assegnati prima che il motore accetti `inizia_partita()`.
    """

    territorio: str = Field(min_length=1)
    giocatore_id: str = Field(min_length=1)
    n_armate: int = Field(ge=1)


class DatiObiettivoAssegnato(_BaseDatiEvento):
    """
    Assegnazione di un obiettivo a un giocatore.

    `obiettivo_id` è 1-16, corrisponde all'id stabile nel catalogo
    `risiko_engine.obiettivi.OBIETTIVI`.
    """

    giocatore_id: str = Field(min_length=1)
    obiettivo_id: int = Field(ge=1, le=16)


class DatiPartitaInizio(_BaseDatiEvento):
    """Avvio della partita: il primo giocatore entra in RINFORZO."""

    primo_giocatore_id: str = Field(min_length=1)


# === Fase RINFORZO ===


class DatiArmatePiazzate(_BaseDatiEvento):
    """Il giocatore attivo piazza N armate su un proprio territorio."""

    giocatore_id: str = Field(min_length=1)
    territorio: str = Field(min_length=1)
    n: int = Field(ge=1)


class DatiCarta(_BaseDatiEvento):
    """
    Serializzazione di una carta del Risiko.

    - Carte territorio: `territorio` valorizzato + `simbolo` in
      {cannone, fante, cavaliere}
    - Carte jolly: `territorio = None` + `simbolo = jolly`
    """

    territorio: str | None
    simbolo: str = Field(pattern="^(cannone|fante|cavaliere|jolly)$")


class DatiTrisGiocato(_BaseDatiEvento):
    """
    Il giocatore attivo gioca un tris di 3 carte (durante la fase RINFORZO).
    """

    giocatore_id: str = Field(min_length=1)
    carte: list[DatiCarta] = Field(min_length=3, max_length=3)


# === Fase ATTACCO ===


class DatiAttaccoRisolto(_BaseDatiEvento):
    """
    Un attacco con dadi già lanciati.

    Sia i dadi attaccante sia quelli difensore sono inclusi: il motore non
    lancia mai i dadi internamente, gli vengono iniettati. La conquista
    e lo spostamento minimo automatico sono gestiti dal motore se il
    difensore va a 0.
    """

    giocatore_id: str = Field(min_length=1)
    da: str = Field(min_length=1)
    a: str = Field(min_length=1)
    dadi_attaccante: list[int] = Field(min_length=1, max_length=3)
    dadi_difensore: list[int] = Field(min_length=1, max_length=3)


# === Fase SPOSTAMENTO ===


class DatiArmateSpostate(_BaseDatiEvento):
    """Spostamento finale di N armate fra due territori adiacenti."""

    giocatore_id: str = Field(min_length=1)
    da: str = Field(min_length=1)
    a: str = Field(min_length=1)
    n: int = Field(ge=1)


# === Fine turno / partita ===


class DatiTurnoFinito(_BaseDatiEvento):
    """Il giocatore attivo passa il turno (eventualmente pesca una carta)."""

    giocatore_id: str = Field(min_length=1)


class DatiPartitaFine(_BaseDatiEvento):
    """
    Evento informativo di fine partita.

    Il motore determina automaticamente la fine partita su `fine_turno()`
    se il giocatore attivo ha raggiunto l'obiettivo. Questo evento è
    quindi puramente documentativo (l'utente lo aggiunge per chiarire
    chi ha vinto), e non altera lo stato del motore in ricostruzione.
    """

    vincitore_id: str = Field(min_length=1)
