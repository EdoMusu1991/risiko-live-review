"""
Schemi per le statistiche aggregate di una partita.

Le statistiche sono derivate **solo dagli `EventoValidato`** (più la
lista dei giocatori). Non richiedono il motore di gioco né lo stato
finale ricostruito.

Limiti consapevoli del MVP:
- Calcoliamo solo le statistiche dell'attaccante. Per le statistiche di
  difesa servirebbe sapere quale giocatore possedeva un territorio in
  un dato momento, e questo richiede di applicare gli eventi al motore.
  Aggiungeremo le difese in una versione successiva.
- "Territori conquistati" è il count di `TERRITORIO_CONQUISTATO` con
  giocatore_id corrispondente. Il motore li emette automaticamente
  quando il difensore va a 0, quindi è affidabile.
- "Carte pescate" è il count di `CARTA_PESCATA`. Non distinguiamo il
  simbolo (cannone/fante/cavaliere/jolly).
"""

from pydantic import BaseModel, Field

from app.modelli.tipi import ColoreGiocatore


class StatisticheGiocatore(BaseModel):
    """Metriche aggregate per un singolo giocatore."""

    giocatore_id: str
    nome: str
    colore: ColoreGiocatore

    # === Attacco ===
    n_attacchi: int = Field(
        ..., description="Numero di ATTACCO_RISOLTO dichiarati da questo giocatore"
    )
    armate_perse_attaccando: int = Field(
        ...,
        description=(
            "Somma armate perse dall'attaccante in tutti gli attacchi "
            "che ha dichiarato (calcolato confrontando dadi al meglio)"
        ),
    )
    armate_inflitte_attaccando: int = Field(
        ...,
        description=(
            "Somma armate inflitte al difensore in tutti gli attacchi "
            "che ha dichiarato"
        ),
    )
    n_dadi_lanciati: int = Field(
        ..., description="Totale dadi tirati attaccando (1 dado = 1 conteggio)"
    )
    media_dadi_lanciati: float | None = Field(
        None, description="Media valore dadi tirati. None se 0 dadi."
    )

    # === Difesa (popolato solo se ricostruito con motore) ===
    n_difese: int = Field(
        default=0,
        description=(
            "Numero attacchi subiti come difensore. Calcolato solo "
            "quando il motore di gioco è disponibile."
        ),
    )
    armate_perse_difendendo: int = Field(
        default=0,
        description="Somma armate perse difendendo i propri territori",
    )
    armate_inflitte_difendendo: int = Field(
        default=0,
        description="Somma armate inflitte all'attaccante difendendo",
    )

    # === Conquista / fortuna ===
    n_territori_conquistati: int = Field(
        ..., description="Numero TERRITORIO_CONQUISTATO con giocatore_id=lui"
    )

    # === Rinforzo ===
    n_armate_piazzate_totali: int = Field(
        ..., description="Somma N delle ARMATE_PIAZZATE"
    )
    n_tris_giocati: int = Field(..., description="Numero TRIS_GIOCATO")
    n_carte_pescate: int = Field(..., description="Numero CARTA_PESCATA")


class StatistichePartita(BaseModel):
    """Statistiche aggregate dell'intera partita."""

    partita_id: str
    n_eventi_validati: int
    durata_sec: float | None = Field(
        None,
        description=(
            "Durata partita in secondi. None se data_inizio o "
            "data_fine non sono settate sulla Partita."
        ),
    )
    n_turni: int = Field(
        ..., description="Numero di TURNO_INIZIATO osservati"
    )
    n_attacchi_totali: int
    statistiche_giocatori: list[StatisticheGiocatore]
