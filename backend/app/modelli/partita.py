"""
Modelli SQLAlchemy 2 per il dominio review partite Risiko.

Convenzioni:
- Tabelle nominate al singolare (italiano).
- ID come UUID4 in formato stringa per portabilità SQLite/Postgres.
- Timestamp UTC con timezone.
- Foreign key con `ondelete="CASCADE"` per pulizia automatica.
- Tutti i modelli ereditano da `Base` definita in configurazione.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.configurazione import Base
from app.modelli.tipi import (
    ColoreGiocatore,
    FonteEvento,
    StatoReview,
    TipoEvento,
)

if TYPE_CHECKING:
    pass


def _genera_id() -> str:
    """Genera un nuovo UUID4 come stringa."""
    return str(uuid.uuid4())


class Partita(Base):
    """
    Una partita Risiko registrata al club.

    È l'aggregato radice del modello: contiene metadati, riferimenti ai
    video registrati, agli eventi (grezzi e validati), e allo snapshot
    finale dello stato (quando la partita è ricostruita).
    """

    __tablename__ = "partita"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_genera_id)

    #: Data/ora di inizio della partita (al club). Estratta dai metadati video o
    #: inserita manualmente.
    data_inizio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    #: Data/ora di fine partita. Null se la partita non è ancora chiusa.
    data_fine: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    #: Luogo libero (es. "Il Gufo - Roma", "Casa di Marco").
    luogo: Mapped[str | None] = mapped_column(String(200), nullable=True)

    #: Note libere dell'arbitro/operatore.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Stato di review della partita.
    stato_review: Mapped[StatoReview] = mapped_column(
        String(20), nullable=False, default=StatoReview.GREZZA
    )

    #: Quando la partita è stata caricata nel sistema.
    data_creazione: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    #: Ultima modifica metadata.
    data_aggiornamento: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relazioni
    giocatori: Mapped[list[GiocatorePartita]] = relationship(
        back_populates="partita",
        cascade="all, delete-orphan",
        order_by="GiocatorePartita.ordine_seduta",
    )
    video: Mapped[list[Video]] = relationship(
        back_populates="partita",
        cascade="all, delete-orphan",
    )
    eventi_grezzi: Mapped[list[EventoGrezzo]] = relationship(
        back_populates="partita",
        cascade="all, delete-orphan",
        order_by="EventoGrezzo.ts_evento",
    )
    eventi_validati: Mapped[list[EventoValidato]] = relationship(
        back_populates="partita",
        cascade="all, delete-orphan",
        order_by="EventoValidato.ts_evento",
    )
    stato_ricostruito: Mapped[StatoPartitaRicostruito | None] = relationship(
        back_populates="partita",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"Partita(id={self.id[:8]}…, inizio={self.data_inizio}, stato={self.stato_review})"


class GiocatorePartita(Base):
    """
    Un giocatore in una specifica partita.

    Distinzione importante: in futuro potremmo avere una tabella `Giocatore`
    globale con identità persistente fra partite. Per ora ogni partita ha i
    suoi giocatori "locali" identificati da nome.
    """

    __tablename__ = "giocatore_partita"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_genera_id)
    partita_id: Mapped[str] = mapped_column(
        ForeignKey("partita.id", ondelete="CASCADE"), nullable=False
    )

    #: Nome del giocatore in questa partita.
    nome: Mapped[str] = mapped_column(String(100), nullable=False)

    #: Colore dei carri di questo giocatore.
    colore: Mapped[ColoreGiocatore] = mapped_column(String(20), nullable=False)

    #: Posizione di seduta al tavolo (1=primo a sinistra, 2=secondo, ...).
    #: Usato per dedurre da quale lato viene una mano nel CV.
    ordine_seduta: Mapped[int] = mapped_column(nullable=False)

    partita: Mapped[Partita] = relationship(back_populates="giocatori")

    __table_args__ = (
        Index("ix_giocatore_partita", "partita_id"),
    )

    def __repr__(self) -> str:
        return f"GiocatorePartita(nome={self.nome!r}, colore={self.colore})"


class Video(Base):
    """
    Un video registrato durante una partita.

    Tipicamente una partita ha un solo video (l'iPhone al soffitto), ma
    il modello supporta più riprese (es. una principale e una secondaria).
    """

    __tablename__ = "video"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_genera_id)
    partita_id: Mapped[str] = mapped_column(
        ForeignKey("partita.id", ondelete="CASCADE"), nullable=False
    )

    #: Path del file video sul filesystem locale.
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)

    #: Nome originale del file caricato (per UX, non per logica).
    nome_originale: Mapped[str] = mapped_column(String(200), nullable=False)

    #: Timestamp di inizio della registrazione (estratto dai metadata o input).
    #: Usato per allineare gli eventi: ogni evento ha un ts_evento, e la
    #: posizione nel video = ts_evento - ts_inizio_video.
    ts_inizio: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    #: Durata in secondi.
    durata_sec: Mapped[float] = mapped_column(nullable=False)

    #: Codec video (es. "h264", "hevc").
    codec: Mapped[str | None] = mapped_column(String(20), nullable=True)

    #: Risoluzione (es. "1920x1080").
    risoluzione: Mapped[str | None] = mapped_column(String(20), nullable=True)

    #: Dimensione file in byte.
    dimensione_byte: Mapped[int] = mapped_column(nullable=False)

    data_caricamento: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    partita: Mapped[Partita] = relationship(back_populates="video")

    __table_args__ = (
        Index("ix_video_partita", "partita_id"),
    )

    def __repr__(self) -> str:
        return f"Video(file={self.nome_originale}, durata={self.durata_sec}s)"


class EventoGrezzo(Base):
    """
    Un evento osservato durante la partita, prima della validazione.

    Esempi di eventi grezzi:
    - Lancio dado letto da BLE (timestamp + valore + dado_id)
    - Carta pescata letta da QR (timestamp + carta_id)
    - Movimento sospetto rilevato da CV (timestamp + descrizione + confidenza)
    - Inserimento manuale dell'utente (timestamp + tipo + dati)

    Gli eventi grezzi NON sono ancora applicati al motore regole — sono solo
    osservazioni. La validazione li promuove a `EventoValidato` (1:1, 1:N o
    aggregando più grezzi in un unico evento).
    """

    __tablename__ = "evento_grezzo"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_genera_id)
    partita_id: Mapped[str] = mapped_column(
        ForeignKey("partita.id", ondelete="CASCADE"), nullable=False
    )

    #: Timestamp UTC dell'evento (con precisione al millisecondo).
    ts_evento: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    #: Tipo di evento (vedi `TipoEvento`).
    tipo: Mapped[TipoEvento] = mapped_column(String(50), nullable=False)

    #: Origine dell'evento.
    fonte: Mapped[FonteEvento] = mapped_column(String(30), nullable=False)

    #: Confidenza 0.0-1.0 (rilevante per fonte CV; per altre fonti = 1.0).
    confidenza: Mapped[float] = mapped_column(nullable=False, default=1.0)

    #: Payload specifico dell'evento, in JSON. Schema dipende dal tipo.
    #: Esempi:
    #:   tipo=DADI_LANCIATI -> {"giocatore_id": "...", "dadi": [4,5,6], "tipo_dado": "att"}
    #:   tipo=CARTA_PESCATA -> {"giocatore_id": "...", "carta_id": "africa_set_cannone"}
    #:   tipo=CV_TRIS_RILEVATO -> {"giocatore_id_probabile": "...", "n_carte_visibili": 3}
    dati: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    #: True se questo evento è stato già validato (promosso a EventoValidato).
    validato: Mapped[bool] = mapped_column(nullable=False, default=False)

    data_creazione: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    partita: Mapped[Partita] = relationship(back_populates="eventi_grezzi")

    __table_args__ = (
        Index("ix_evento_grezzo_partita_ts", "partita_id", "ts_evento"),
        Index("ix_evento_grezzo_validato", "partita_id", "validato"),
    )

    def __repr__(self) -> str:
        return (
            f"EventoGrezzo(tipo={self.tipo}, ts={self.ts_evento}, "
            f"fonte={self.fonte}, validato={self.validato})"
        )


class EventoValidato(Base):
    """
    Un evento confermato, pronto per essere applicato al motore regole.

    Gli eventi validati sono la "verità ufficiale" della partita: sono ciò
    che il `risiko_engine` consuma per ricostruire lo stato finale.

    Possono derivare da:
    - Un singolo evento grezzo (auto-confermato se fonte è BLE/QR ad alta confidenza)
    - Più eventi grezzi correlati (es. dadi attaccante + dadi difensore = 1 attacco)
    - Input manuale durante review (no evento grezzo associato)
    """

    __tablename__ = "evento_validato"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_genera_id)
    partita_id: Mapped[str] = mapped_column(
        ForeignKey("partita.id", ondelete="CASCADE"), nullable=False
    )

    #: Timestamp dell'evento. Tipicamente coincide con quello dell'evento
    #: grezzo che lo ha originato; per input manuali è ts inserito.
    ts_evento: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    #: Tipo di evento (vedi `TipoEvento`).
    tipo: Mapped[TipoEvento] = mapped_column(String(50), nullable=False)

    #: Payload validato in JSON. Schema rigoroso (validato lato Pydantic).
    dati: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    #: ID dell'evento grezzo da cui questo deriva, se ne deriva da uno.
    #: Null se evento creato manualmente da zero.
    evento_grezzo_id: Mapped[str | None] = mapped_column(
        ForeignKey("evento_grezzo.id", ondelete="SET NULL"), nullable=True
    )

    #: Chi ha validato (per ora libero; futuro: user_id quando ci sarà auth).
    validato_da: Mapped[str] = mapped_column(String(100), nullable=False, default="anonimo")

    data_creazione: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    partita: Mapped[Partita] = relationship(back_populates="eventi_validati")

    __table_args__ = (
        Index("ix_evento_validato_partita_ts", "partita_id", "ts_evento"),
    )

    def __repr__(self) -> str:
        return f"EventoValidato(tipo={self.tipo}, ts={self.ts_evento})"


class StatoPartitaRicostruito(Base):
    """
    Snapshot dello stato di una partita dopo l'applicazione degli eventi
    validati al motore regole.

    Una partita ha al massimo UNO stato ricostruito (l'ultimo). Ogni
    ricostruzione sostituisce il precedente (upsert su `partita_id`).

    Lo `stato_serializzato` è un JSON che segue lo schema
    `StatoPartitaSnapshot`. Gli `errori` sono una lista di dict che
    seguono `ErroreRicostruzioneSchema`.
    """

    __tablename__ = "stato_partita_ricostruito"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_genera_id)

    partita_id: Mapped[str] = mapped_column(
        ForeignKey("partita.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 1:1 con Partita
    )

    #: Quando è stata fatta questa ricostruzione.
    data_ricostruzione: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    #: True se TUTTI gli eventi validati sono stati applicati senza errori.
    successo: Mapped[bool] = mapped_column(nullable=False)

    #: Numero totale di eventi validati nella sequenza.
    n_eventi_totali: Mapped[int] = mapped_column(nullable=False)

    #: Eventi che hanno effettivamente modificato il motore (esclusi quelli
    #: che hanno sollevato eccezione e sono stati saltati).
    n_eventi_applicati: Mapped[int] = mapped_column(nullable=False)

    #: Stato finale serializzato (JSON, schema StatoPartitaSnapshot).
    #: Null se la partita non è nemmeno partita (PARTITA_INIZIO mancante).
    stato_serializzato: Mapped[dict[str, object] | None] = mapped_column(
        JSON, nullable=True
    )

    #: Lista di errori (JSON, schema list[ErroreRicostruzioneSchema]).
    errori: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    partita: Mapped[Partita] = relationship(back_populates="stato_ricostruito")

    def __repr__(self) -> str:
        return (
            f"StatoPartitaRicostruito(partita={self.partita_id[:8]}…, "
            f"ok={self.successo}, applicati={self.n_eventi_applicati})"
        )
