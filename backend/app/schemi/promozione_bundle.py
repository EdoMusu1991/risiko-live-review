"""Schemi Pydantic per la promozione di bundle a Partita SQL."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RichiestaPromozioneBundle(BaseModel):
    """Body opzionale del POST per arricchire i metadati della Partita."""

    luogo: str | None = Field(
        default=None,
        description="Luogo dove si e' svolta la partita (es. 'Il Gufo - Roma')",
        max_length=200,
    )
    note_extra: str | None = Field(
        default=None,
        description="Note aggiuntive (concatenate alle note auto-generate)",
        max_length=2000,
    )


class RispostaPromozioneBundle(BaseModel):
    """Esito dell'operazione di promozione bundle → Partita SQL."""

    id_partita: str
    n_video: int
    n_eventi_importati: int
    n_eventi_scartati: int
    avvisi: list[str]


class BundleDisponibile(BaseModel):
    """Riepilogo di un bundle presente in `storage_partite/` non promosso."""

    id_partita: str
    ts_inizio: str
    ts_fine: str
    n_segmenti: int
    n_eventi_dichiarati: int


class RispostaListaBundle(BaseModel):
    bundle: list[BundleDisponibile]
