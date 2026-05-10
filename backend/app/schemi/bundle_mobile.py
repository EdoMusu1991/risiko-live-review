"""
Modelli Pydantic v2 per il bundle dell'app mobile risiko-live.

Specchiano gli schema TypeScript in `risiko-live-mobile/src/tipi/manifest.ts`
e i JSON Schema in `risiko-live-mobile/schemas/`.

Differenze rispetto allo schema legacy (vedi `app/servizi/import_bundle_servizio.py`):
- niente `schema_version` ma `versione_app` (semver dell'app)
- `segmenti_video: list[SegmentoVideo]` invece di `video: VideoMeta`
  (Vision Camera ruota il segmento ogni 10min per resilienza al crash)

Tutti i modelli usano `extra="allow"` per forward-compatibility: campi
addizionali nel JSON non rompono il parsing.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

VERSIONE_MANIFEST_SUPPORTATA = "0.1.0"

FonteEvento = Literal["dado_ble", "manuale", "sistema"]


class SegmentoVideo(BaseModel):
    """Singolo segmento mp4 della registrazione segmentata."""

    model_config = ConfigDict(extra="allow")

    filename: str
    ts_inizio: str
    ts_fine: str
    durata_sec: float = Field(ge=0)
    larghezza: int = Field(ge=1)
    altezza: int = Field(ge=1)
    fps: float = Field(ge=1)


class Manifest(BaseModel):
    """Manifest del bundle ZIP."""

    model_config = ConfigDict(extra="allow")

    versione_app: str
    device_id: str
    ts_inizio_registrazione: str
    ts_fine_registrazione: str
    segmenti_video: list[SegmentoVideo]
    n_eventi_ble: int = Field(ge=0)


class EventoBundle(BaseModel):
    """Singola riga di eventi.jsonl."""

    model_config = ConfigDict(extra="allow")

    ts_evento: str
    tipo: str
    fonte: FonteEvento
    confidenza: float = Field(ge=0, le=1)
    dati: dict[str, Any]


class RispostaImportBundle(BaseModel):
    """Risposta del backend dopo accettazione del bundle."""

    id_partita: str
    n_segmenti: int
    n_eventi: int
    durata_totale_sec: float
    avvisi: list[str] = Field(default_factory=list)
