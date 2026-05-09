"""Modelli SQLAlchemy ORM del dominio review partite."""

from app.modelli.inferenza_cv import (
    DivergenzaInferita,
    InferenzaCV,
)
from app.modelli.partita import (
    EventoGrezzo,
    EventoValidato,
    GiocatorePartita,
    Partita,
    StatoPartitaRicostruito,
    Video,
)
from app.modelli.tipi import (
    ColoreGiocatore,
    FonteEvento,
    StatoReview,
    TipoEvento,
)

__all__ = [
    "ColoreGiocatore",
    "DivergenzaInferita",
    "EventoGrezzo",
    "EventoValidato",
    "FonteEvento",
    "GiocatorePartita",
    "InferenzaCV",
    "Partita",
    "StatoPartitaRicostruito",
    "StatoReview",
    "TipoEvento",
    "Video",
]
