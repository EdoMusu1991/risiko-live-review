"""
Schemi per la validazione di coerenza degli `EventoValidato` di una
partita, **prima** della ricostruzione tramite motore.

Il motore (`risiko_engine`) solleva eccezioni quando uno stato è
incoerente, ma queste sono basate sull'ordine di applicazione e si
fermano al primo errore. Il validatore di coerenza scorre tutti gli
eventi e raccoglie **tutti** i problemi in un colpo solo, organizzati
per severità, così l'utente li vede tutti nella UI di review prima
di lanciare la ricostruzione.

Severità:
- `errore`: il motore certamente fallirà su questo evento (es. attacco
  fra territori non adiacenti, attacco da territorio non posseduto).
- `avviso`: comportamento sospetto ma applicabile (es. due TURNO_INIZIATO
  consecutivi senza eventi in mezzo, attacchi senza dadi difensori).
"""

from typing import Literal

from pydantic import BaseModel, Field

SeveritaProblema = Literal["errore", "avviso"]


CodiceProblema = Literal[
    "attacco_territori_non_adiacenti",
    "attacco_da_territorio_non_posseduto",
    "attacco_su_territorio_proprio",
    "attacco_difensore_inesistente",
    "doppio_turno_iniziato",
    "evento_fuori_ordine_temporale",
    "giocatore_id_inesistente",
    "territorio_inesistente",
    "armate_piazzate_su_territorio_altrui",
    "spostamento_territori_non_adiacenti",
]


class ProblemaCoerenza(BaseModel):
    """Singolo problema rilevato dal validatore."""

    severita: SeveritaProblema
    codice: CodiceProblema = Field(
        ..., description="Codice machine-readable del tipo di problema"
    )
    messaggio: str = Field(
        ..., description="Descrizione human-readable in italiano"
    )
    evento_id: str | None = Field(
        default=None,
        description="ID dell'EventoValidato problematico, None se globale",
    )
    posizione: int | None = Field(
        default=None,
        description="Posizione cronologica (0-indexed) dell'evento",
    )


class RisultatoValidazioneCoerenza(BaseModel):
    """Esito completo del validatore."""

    n_eventi_analizzati: int
    n_errori: int
    n_avvisi: int
    problemi: list[ProblemaCoerenza]

    @property
    def is_coerente(self) -> bool:
        """True se non ci sono errori (gli avvisi non bloccano)."""
        return self.n_errori == 0
