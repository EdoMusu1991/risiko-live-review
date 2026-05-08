"""
Endpoint per esporre le risorse statiche del `risiko_engine`:
- Lista dei 42 territori canonici
- Lista dei 16 obiettivi del Risiko classico EG

Servono al frontend per popolare i dropdown dell'editor eventi senza
duplicare i dati. Sono read-only e cacheable indefinitamente lato client.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from risiko_engine.mappa import TERRITORI, adiacenti_a, continente_di
from risiko_engine.obiettivi import OBIETTIVI

router = APIRouter(prefix="/risorse", tags=["risorse"])


class TerritorioInfo(BaseModel):
    """Info essenziali su un territorio della mappa."""

    nome: str
    continente: str
    adiacenti: list[str]


class ObiettivoInfo(BaseModel):
    """Info su un obiettivo del catalogo ufficiale."""

    id: int
    nome: str
    immagine: str
    territori_richiesti: list[str]


@router.get(
    "/territori",
    response_model=list[TerritorioInfo],
    summary="Lista 42 territori canonici",
)
async def lista_territori() -> list[TerritorioInfo]:
    """
    Ritorna i 42 territori del Risiko classico EG con le loro adiacenze
    e continente di appartenenza.

    Cache-friendly: i dati non cambiano mai, il frontend può cachearli
    per tutta la sessione.
    """
    return [
        TerritorioInfo(
            nome=nome,
            continente=continente_di(nome),
            adiacenti=sorted(adiacenti_a(nome)),
        )
        for nome in sorted(TERRITORI)
    ]


@router.get(
    "/obiettivi",
    response_model=list[ObiettivoInfo],
    summary="Lista 16 obiettivi ufficiali",
)
async def lista_obiettivi() -> list[ObiettivoInfo]:
    """Ritorna i 16 obiettivi del Risiko classico EG."""
    return [
        ObiettivoInfo(
            id=o.id,
            nome=o.nome,
            immagine=o.immagine,
            territori_richiesti=sorted(o.territori_richiesti),
        )
        for o in OBIETTIVI
    ]
