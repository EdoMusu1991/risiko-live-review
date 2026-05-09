"""
Schemi Pydantic per l'API delle inferenze CV.

Schema input:
- `InferenzaCVInput`: il client (script Roboflow / pipeline esterna)
  POSTa una lista di queste per popolare il DB.

Schema output:
- `InferenzaCVOutput`: lettura standard di un'inferenza dal DB.
- `DivergenzaInferitaOutput`: discrepanza fra motore e CV.
- `RiepilogoDiscrepanze`: aggregato per partita.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# === Sub-schema scomposizione ===


class SubDetection(BaseModel):
    """Una singola pedina detettata dentro un blob (sub-detection)."""

    tipo: Literal["carro_piccolo", "carro_medio", "carro_grande"]
    bbox: list[int] = Field(..., min_length=4, max_length=4)
    confidence: float = Field(..., ge=0.0, le=1.0)


# === Input ===


class InferenzaCVInput(BaseModel):
    """Body POST per inserire una nuova inferenza CV."""

    evento_validato_id: str | None = Field(
        default=None,
        description=(
            "UUID dell'evento associato. None = inferenza snapshot non "
            "legata a un evento specifico."
        ),
    )
    modello_versione: str = Field(
        ..., min_length=1, max_length=80,
        description="Tag identificativo del modello CV usato.",
    )
    territorio: str | None = Field(default=None, max_length=50)
    colore: str | None = Field(default=None, max_length=20)
    tipo_pedina_dominante: Literal[
        "carro_piccolo", "carro_medio", "carro_grande"
    ] | None = None
    n_armate_stimate: int = Field(..., ge=0)
    bbox: list[int] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="[x, y, w, h] in pixel sul frame raddrizzato",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    scomposizione: list[SubDetection] = Field(default_factory=list)
    frame_hash: str | None = Field(default=None, max_length=64)


class InserimentoBatchInferenze(BaseModel):
    """Body POST per inserire N inferenze in un colpo solo."""

    inferenze: list[InferenzaCVInput] = Field(..., min_length=1)


# === Output ===


class InferenzaCVOutput(BaseModel):
    """Inferenza CV letta dal DB."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    partita_id: str
    evento_validato_id: str | None
    modello_versione: str
    territorio: str | None
    colore: str | None
    tipo_pedina_dominante: str | None
    n_armate_stimate: int
    bbox: list[int]
    confidence: float
    scomposizione: list[dict[str, object]]
    frame_hash: str | None
    creata_il: datetime


class DivergenzaInferitaOutput(BaseModel):
    """Divergenza CV ↔ motore letta dal DB."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    partita_id: str
    evento_validato_id: str | None
    territorio: str
    colore: str
    valore_motore: int
    valore_cv: int
    confidence_cv: float
    delta_assoluto: int
    inferenze_correlate: list[str]
    risoluzione: str
    note: str | None
    creata_il: datetime
    aggiornata_il: datetime


class AggiornamentoDivergenza(BaseModel):
    """Body PATCH per aggiornare la risoluzione di una divergenza."""

    risoluzione: Literal[
        "aperta", "accettata_motore", "accettata_cv", "evento_aggiunto",
    ]
    note: str | None = Field(default=None, max_length=500)


class AggiornamentoBulkDivergenze(BaseModel):
    """
    Body POST per aggiornare in batch la risoluzione di piu' divergenze.

    I filtri sono additivi (AND): solo le divergenze che soddisfano TUTTI
    i filtri specificati vengono aggiornate.
    """

    risoluzione: Literal[
        "aperta", "accettata_motore", "accettata_cv", "evento_aggiunto",
    ]
    note: str | None = Field(default=None, max_length=500)

    # Filtri di selezione (tutti opzionali, AND tra loro)
    delta_minimo: int | None = Field(
        default=None,
        ge=0,
        description="Solo divergenze con delta_assoluto >= delta_minimo",
    )
    delta_massimo: int | None = Field(
        default=None,
        ge=0,
        description="Solo divergenze con delta_assoluto <= delta_massimo",
    )
    territorio: str | None = Field(default=None, max_length=50)
    colore: str | None = Field(default=None, max_length=20)
    solo_aperte: bool = Field(
        default=True,
        description=(
            "Se true, applica solo a divergenze attualmente 'aperte' "
            "(default: true)."
        ),
    )


class RisultatoBulkDivergenze(BaseModel):
    """Risposta del bulk update."""

    n_aggiornate: int
    risoluzione_applicata: str


class RiepilogoDiscrepanze(BaseModel):
    """Riepilogo divergenze per partita."""

    n_divergenze_totali: int
    n_aperte: int
    n_risolte: int
    delta_max: int = Field(
        ...,
        description="Massimo delta_assoluto tra le divergenze aperte (0 se nessuna)",
    )
    divergenze: list[DivergenzaInferitaOutput]
