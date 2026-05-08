"""
Schemi per la classifica club (statistiche aggregate cross-partita).

A differenza di `StatistichePartita` che lavora su una singola partita,
qui aggreghiamo tutte le partite del DB per dare una vista "stagionale"
del club: chi è il giocatore più forte, totali aggregati, ecc.

Aggregazione per **nome giocatore** (case-insensitive, trimmed): nel
contesto club gli stessi giocatori tornano in più partite ma con
`giocatore_id` diverso ogni volta (UUID per partita). Il nome è la
chiave naturale.
"""

from pydantic import BaseModel, Field


class GiocatoreClub(BaseModel):
    """Statistiche aggregate di un singolo giocatore del club."""

    nome: str
    nome_normalizzato: str = Field(
        ..., description="Lowercase + trim, usato come chiave aggregazione"
    )

    # Conteggi base
    n_partite: int = Field(..., description="Numero partite a cui ha partecipato")
    n_attacchi_totali: int
    n_difese_totali: int

    # Performance attacco
    armate_inflitte_attaccando_tot: int
    armate_perse_attaccando_tot: int

    # Performance difesa
    armate_inflitte_difendendo_tot: int
    armate_perse_difendendo_tot: int

    # Conquiste
    n_territori_conquistati_tot: int

    # Risorse di gioco
    n_carte_pescate_tot: int
    n_tris_giocati_tot: int

    # Dadi
    n_dadi_lanciati_tot: int
    media_dadi_globale: float | None = Field(
        None, description="Media valore dadi su tutte le partite. None se 0 dadi."
    )

    @property
    def bilancio_armate(self) -> int:
        """Armate inflitte (att + dif) - armate perse (att + dif)."""
        return (
            self.armate_inflitte_attaccando_tot
            + self.armate_inflitte_difendendo_tot
            - self.armate_perse_attaccando_tot
            - self.armate_perse_difendendo_tot
        )


class ClassificaClub(BaseModel):
    """Snapshot dell'intero club aggregato cross-partita."""

    n_partite_totali: int
    n_partite_con_eventi: int = Field(
        ...,
        description="Partite con almeno 1 evento validato (escluse vuote)",
    )
    n_giocatori_distinti: int
    durata_totale_sec: float = Field(
        ..., description="Somma durate (solo partite con data_inizio+fine)"
    )
    n_attacchi_totali: int

    giocatori: list[GiocatoreClub] = Field(
        ...,
        description=(
            "Lista giocatori ordinata per bilancio_armate decrescente. "
            "Il client può ri-ordinare per altre metriche."
        ),
    )
