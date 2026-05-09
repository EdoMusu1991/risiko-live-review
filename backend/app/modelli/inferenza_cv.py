"""
Modelli SQLAlchemy per le inferenze CV (computer vision).

Architettura "evidence-based" (vedi design fase A/C):
- Una `InferenzaCV` rappresenta UNA detection di un modello CV su un
  frame video di un evento. Più detection per evento (una per ogni
  blob di pedine identificato), più inferenze nel tempo (re-runs con
  modelli diversi).
- Conserviamo la **bbox** (bounding box pixel) e la **confidence**
  grezza, non solo la conclusione "10 carri rossi su Kamchatka".
  Questo permette in futuro di:
  1. Riprocessare con soglie diverse senza ri-girare il modello
  2. Distinguere falsi negativi (alta conf scartata per soglia) da
     veri (mai vista la pedina)
  3. Versionare le inferenze: tag `modello_versione` per ogni record

- Una `DivergenzaInferita` rappresenta uno scarto fra ciò che il motore
  derivato dalla cronologia eventi pensa per un territorio, e ciò che
  la CV vede su un frame. È materiale per la review umana.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.configurazione import Base

if TYPE_CHECKING:
    from app.modelli.partita import EventoValidato, Partita


def _genera_id() -> str:
    return str(uuid.uuid4())


class InferenzaCV(Base):
    """
    Inferenza di un modello CV su un singolo frame video di una partita.

    Una inferenza "atomica" rappresenta:
    - UNA bbox detettata dal modello sul frame
    - associata a UN territorio (post-mapping bbox -> mappa canonica)
    - di UN colore (giocatore)
    - con UN tipo di pedina dominante (carro_piccolo / carro_medio / carro_grande)
    - con un n_armate_stimate dedotto dal tipo + count

    Un evento ha tipicamente N inferenze (una per ogni blob di pedine
    visibile sul frame raddrizzato).
    """

    __tablename__ = "inferenza_cv"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_genera_id
    )

    #: Partita di appartenenza (denormalizzato per query veloci).
    partita_id: Mapped[str] = mapped_column(
        ForeignKey("partita.id", ondelete="CASCADE"), nullable=False
    )

    #: Evento validato a cui questa inferenza si riferisce. NULL se è
    #: una inferenza "snapshot" non legata a un evento specifico.
    evento_validato_id: Mapped[str | None] = mapped_column(
        ForeignKey("evento_validato.id", ondelete="CASCADE"), nullable=True
    )

    #: Versione del modello che ha prodotto l'inferenza (tag versionato).
    #: Esempi: "yolo-risiko-v0.3-20260601", "rt-detr-v1.0".
    #: Permette di re-eseguire le inferenze con modelli più nuovi e
    #: confrontare i risultati storici.
    modello_versione: Mapped[str] = mapped_column(String(80), nullable=False)

    #: Territorio rilevato (slug, es. "kamchatka"). Null se la bbox
    #: non è stata mappata a nessun territorio (errore di calibrazione).
    territorio: Mapped[str | None] = mapped_column(String(50), nullable=True)

    #: Colore del giocatore (rosso, blu, giallo, verde, nero, viola).
    colore: Mapped[str | None] = mapped_column(String(20), nullable=True)

    #: Tipo dominante di pedina nel blob detettato.
    #: Valori attesi: "carro_piccolo" (1 armata), "carro_medio" (5),
    #: "carro_grande" (10). Stringa libera per estensibilità.
    tipo_pedina_dominante: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    #: Numero di armate stimato dalla scomposizione delle pedine
    #: (somma_pesata dei tipi). Esempio: 1 carro_grande + 2 carro_piccolo
    #: = 12 armate.
    n_armate_stimate: Mapped[int] = mapped_column(nullable=False)

    #: Bounding box [x, y, w, h] in pixel sul frame raddrizzato.
    bbox: Mapped[list[int]] = mapped_column(JSON, nullable=False)

    #: Confidence aggregata (0..1) dell'intera detection sul blob.
    confidence: Mapped[float] = mapped_column(nullable=False)

    #: Scomposizione completa: lista di sub-detection grezze del modello,
    #: una per ogni pedina individuale identificata. Schema:
    #: [{"tipo": "carro_piccolo", "bbox": [x,y,w,h], "confidence": 0.85}, ...].
    #: Mantenuto per evidence-based reasoning (fase C/D).
    scomposizione: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    #: Timestamp di creazione dell'inferenza nel DB.
    creata_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    #: Hash del frame su cui è stata calcolata (utile per dedup e per
    #: verificare se la sorgente è cambiata). Vuoto = inferenza
    #: importata senza tracking del frame.
    frame_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_inferenza_cv_partita", "partita_id"),
        Index("ix_inferenza_cv_evento", "evento_validato_id"),
        Index("ix_inferenza_cv_modello", "modello_versione"),
    )

    partita: Mapped[Partita] = relationship()
    evento: Mapped[EventoValidato | None] = relationship()

    def __repr__(self) -> str:
        return (
            f"InferenzaCV({self.territorio}={self.n_armate_stimate} "
            f"{self.colore}, conf={self.confidence:.2f})"
        )


class DivergenzaInferita(Base):
    """
    Discrepanza fra lo stato derivato dal motore (eventi BLE/manuali) e
    lo stato dedotto dalle inferenze CV.

    Esempio: il motore dice che Kamchatka ha 8 armate rosse al turno 50
    (basato sulla cronologia degli eventi), la CV su quel frame vede 10
    carri rossi. Delta = +2: probabile evento di rinforzo non registrato.

    La review umana esamina le divergenze e decide:
    - "accettata_motore": la CV ha sbagliato, ignora
    - "accettata_cv": il motore ha torto, aggiungi un evento mancante
    - "evento_aggiunto": ho creato manualmente l'evento mancante
    - "aperta": non risolta
    """

    __tablename__ = "divergenza_inferita"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_genera_id
    )

    partita_id: Mapped[str] = mapped_column(
        ForeignKey("partita.id", ondelete="CASCADE"), nullable=False
    )

    #: Evento validato in corrispondenza del quale è stata rilevata la
    #: divergenza. La snapshot dello stato motore è quella DOPO l'evento.
    evento_validato_id: Mapped[str | None] = mapped_column(
        ForeignKey("evento_validato.id", ondelete="CASCADE"), nullable=True
    )

    #: Territorio interessato (slug).
    territorio: Mapped[str] = mapped_column(String(50), nullable=False)

    #: Colore (giocatore) interessato.
    colore: Mapped[str] = mapped_column(String(20), nullable=False)

    #: Quante armate dice il motore.
    valore_motore: Mapped[int] = mapped_column(nullable=False)

    #: Quante armate dice la CV (somma delle inferenze su quel territorio).
    valore_cv: Mapped[int] = mapped_column(nullable=False)

    #: Confidence aggregata della CV per questo territorio.
    confidence_cv: Mapped[float] = mapped_column(nullable=False)

    #: |valore_motore - valore_cv|. Denormalizzato per filtri/sort veloci.
    delta_assoluto: Mapped[int] = mapped_column(nullable=False)

    #: Lista di ID di `InferenzaCV` che hanno generato questa divergenza.
    #: Schema: list[str].
    inferenze_correlate: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )

    #: Stato della risoluzione. Valori: "aperta", "accettata_motore",
    #: "accettata_cv", "evento_aggiunto".
    risoluzione: Mapped[str] = mapped_column(
        String(30), nullable=False, default="aperta"
    )

    #: Note libere della review (chi ha risolto, perché).
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    creata_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    aggiornata_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_divergenza_partita", "partita_id"),
        Index("ix_divergenza_evento", "evento_validato_id"),
        Index("ix_divergenza_aperta", "risoluzione"),
    )

    partita: Mapped[Partita] = relationship()
    evento: Mapped[EventoValidato | None] = relationship()

    def __repr__(self) -> str:
        return (
            f"DivergenzaInferita({self.territorio} {self.colore}: "
            f"motore={self.valore_motore} cv={self.valore_cv} "
            f"[{self.risoluzione}])"
        )
