"""
Schemi Pydantic per la serializzazione dello stato di una partita.

Usati per:
- Salvare snapshot in DB (campo JSON di `StatoPartitaRicostruito`).
- Esporre lo stato corrente al frontend via API.

Il modello segue la `vista_arbitro` di `risiko_engine` (l'arbitro vede
chi controlla cosa con quante armate, ma non i contenuti delle mani
né gli obiettivi). Questo è il livello di info appropriato per la review.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _SchemaBase(BaseModel):
    """Base: ammette popolamento da attributi (utile per copia da dataclass)."""

    model_config = ConfigDict(from_attributes=True)


class InfoTerritorioSchema(_SchemaBase):
    """Stato di un territorio: chi controlla, con quante armate."""

    nome: str
    controllore_id: str | None
    armate: int


class InfoGiocatoreSchema(_SchemaBase):
    """Info pubblica di un giocatore: senza mano e senza obiettivo."""

    player_id: str
    colore: str
    nome: str
    eliminato: bool


class StatoPartitaSnapshot(_SchemaBase):
    """
    Snapshot completo dello stato di una partita in un dato momento.

    Contiene info "vista arbitro": stato pubblico + conteggio mani
    + stato del flusso turno (fase, armate da piazzare, ecc.).
    """

    fase_corrente: str
    """Una di: pre_partita, rinforzo, attacco, spostamento, fine_partita."""

    turno: int
    giocatore_attivo_id: str | None
    vincitore_id: str | None

    armate_da_piazzare: int
    """Solo significativo in fase RINFORZO. Altrimenti 0."""

    tris_giocato_questo_turno: bool
    spostamento_effettuato: bool
    territori_conquistati_nel_turno: list[str]

    giocatori: list[InfoGiocatoreSchema]
    territori: dict[str, InfoTerritorioSchema]
    conteggio_mani: dict[str, int]
    """Mappa player_id → numero di carte in mano (non i contenuti)."""

    snapshot_mazzo: dict[str, int]
    """Conteggi del mazzo: pila_principale, scarti, totale, ecc."""


# === Risultato ricostruzione ===


class ErroreRicostruzioneSchema(_SchemaBase):
    """Errore avvenuto durante l'applicazione di un singolo evento."""

    evento_validato_id: str
    posizione_nella_sequenza: int
    """Indice 0-based dell'evento nella lista ordinata per ts_evento."""

    tipo_evento: str
    ts_evento: datetime
    classe_errore: str
    """Nome della classe di eccezione (es. 'AzioneIllegaleError')."""

    messaggio: str


class RisultatoRicostruzione(_SchemaBase):
    """Risposta dell'endpoint POST /partite/{id}/ricostruisci."""

    partita_id: str
    successo: bool
    """True se TUTTI gli eventi sono stati applicati senza errori."""

    n_eventi_totali: int
    n_eventi_applicati: int
    """Eventi che hanno avuto effetto sul motore (esclusi quelli con errore)."""

    n_errori: int
    errori: list[ErroreRicostruzioneSchema]
    stato_finale: StatoPartitaSnapshot | None
    """Stato dopo l'ultimo evento applicato. None se la partita non è
    nemmeno stata avviata correttamente (PARTITA_INIZIO mancante)."""

    data_ricostruzione: datetime
