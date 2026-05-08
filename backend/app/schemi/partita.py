"""
Schemi Pydantic v2 per il dominio Partita.

Pattern:
- `*Lettura`: ritornati dagli endpoint GET (response model).
- `*Creazione`: ricevuti dagli endpoint POST (request body).
- `*Aggiornamento`: ricevuti dagli endpoint PATCH (campi opzionali).

Gli schemi sono separati dai modelli ORM per:
- Validazione input rigorosa con Pydantic v2.
- Disaccoppiare il contratto API dall'implementazione DB.
- Permettere evoluzione indipendente del DB e dell'API.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modelli.tipi import (
    ColoreGiocatore,
    FonteEvento,
    StatoReview,
    TipoEvento,
)

# === Configurazione comune ===


class _SchemaBase(BaseModel):
    """Base per tutti gli schemi: ammette popolamento da attributi (ORM)."""

    model_config = ConfigDict(from_attributes=True)


# === Giocatore ===


class GiocatorePartitaCreazione(BaseModel):
    """Dati per creare un giocatore in una partita."""

    nome: str = Field(min_length=1, max_length=100)
    colore: ColoreGiocatore
    ordine_seduta: int = Field(ge=1, le=6)


class GiocatorePartitaLettura(_SchemaBase):
    """Giocatore così come ritornato dall'API."""

    id: str
    nome: str
    colore: ColoreGiocatore
    ordine_seduta: int


# === Video ===


class VideoLettura(_SchemaBase):
    """Metadati di un video, senza il contenuto binario."""

    id: str
    nome_originale: str
    ts_inizio: datetime
    durata_sec: float
    codec: str | None
    risoluzione: str | None
    dimensione_byte: int
    data_caricamento: datetime


# === Evento grezzo ===


class EventoGrezzoCreazione(BaseModel):
    """Inserimento manuale di un evento grezzo (es. dall'app web)."""

    ts_evento: datetime
    tipo: TipoEvento
    fonte: FonteEvento = FonteEvento.INPUT_MANUALE
    confidenza: float = Field(default=1.0, ge=0.0, le=1.0)
    dati: dict[str, object] = Field(default_factory=dict)


class EventoGrezzoAggiornamento(BaseModel):
    """Modifica parziale di un evento grezzo. Tutti i campi opzionali."""

    ts_evento: datetime | None = None
    tipo: TipoEvento | None = None
    fonte: FonteEvento | None = None
    confidenza: float | None = Field(default=None, ge=0.0, le=1.0)
    dati: dict[str, object] | None = None


class EventoGrezzoLettura(_SchemaBase):
    """Evento grezzo letto."""

    id: str
    partita_id: str
    ts_evento: datetime
    tipo: TipoEvento
    fonte: FonteEvento
    confidenza: float
    dati: dict[str, object]
    validato: bool
    data_creazione: datetime


class EventoGrezzoBatch(BaseModel):
    """Upload massivo di eventi (tipico dal tablet osservatore)."""

    eventi: list[EventoGrezzoCreazione] = Field(min_length=1, max_length=10000)


# === Evento validato ===


class EventoValidatoCreazione(BaseModel):
    """Crea un evento validato (da grezzo o manualmente)."""

    ts_evento: datetime
    tipo: TipoEvento
    dati: dict[str, object] = Field(default_factory=dict)
    evento_grezzo_id: str | None = None
    validato_da: str = "anonimo"


class EventoValidatoBatch(BaseModel):
    """Inserimento atomico di più eventi validati (es. setup automatico)."""

    eventi: list[EventoValidatoCreazione] = Field(min_length=1, max_length=10000)


class EventoValidatoAggiornamento(BaseModel):
    """Modifica parziale di un evento validato. Tutti i campi opzionali."""

    ts_evento: datetime | None = None
    tipo: TipoEvento | None = None
    dati: dict[str, object] | None = None
    validato_da: str | None = None


class EventoValidatoLettura(_SchemaBase):
    """Evento validato letto."""

    id: str
    partita_id: str
    ts_evento: datetime
    tipo: TipoEvento
    dati: dict[str, object]
    evento_grezzo_id: str | None
    validato_da: str
    data_creazione: datetime


# === Partita ===


class PartitaCreazione(BaseModel):
    """Dati per creare una nuova partita."""

    data_inizio: datetime
    luogo: str | None = Field(default=None, max_length=200)
    note: str | None = None
    giocatori: list[GiocatorePartitaCreazione] = Field(min_length=2, max_length=6)


class PartitaAggiornamento(BaseModel):
    """Aggiornamento metadata partita. Tutti i campi opzionali."""

    data_inizio: datetime | None = None
    data_fine: datetime | None = None
    luogo: str | None = Field(default=None, max_length=200)
    note: str | None = None
    stato_review: StatoReview | None = None


class PartitaLetturaSommario(_SchemaBase):
    """Vista sommario per la lista partite (no eventi, no giocatori)."""

    id: str
    data_inizio: datetime
    data_fine: datetime | None
    luogo: str | None
    stato_review: StatoReview
    data_creazione: datetime


class PartitaLetturaDettaglio(_SchemaBase):
    """Vista dettagliata di una partita: include giocatori e video."""

    id: str
    data_inizio: datetime
    data_fine: datetime | None
    luogo: str | None
    note: str | None
    stato_review: StatoReview
    data_creazione: datetime
    data_aggiornamento: datetime
    giocatori: list[GiocatorePartitaLettura]
    video: list[VideoLettura]


# === Setup automatico ===


class SetupAutomaticoRichiesta(BaseModel):
    """Parametri opzionali per la generazione automatica del setup."""

    primo_giocatore_id: str | None = None
    """Chi inizia. Default: giocatore con ordine_seduta=1."""

    seed: int | None = None
    """Seed RNG per riproducibilità. Default: random."""


class SetupAutomaticoRisposta(BaseModel):
    """Riepilogo dell'operazione di setup automatico."""

    n_territori_assegnati: int
    n_obiettivi_assegnati: int
    primo_giocatore_id: str
    armate_per_giocatore: int
    seed_usato: int
