"""
Health-check della pipeline CV.

Endpoint diagnostico che riporta lo stato dei prerequisiti necessari
per far girare la pipeline computer vision end-to-end:
- ffmpeg installato (per estrazione frame)
- opencv-python installato (per raddrizzamento)
- immagine di riferimento presente (per calibrazione)
- client CV configurato (mock o Roboflow reale)

Utile per debug e per la UI: il pannello frontend puo' chiamare questo
endpoint all'avvio per mostrare un widget "stato pipeline" e segnalare
eventuali problemi di configurazione.
"""

from __future__ import annotations

import shutil
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.configurazione import impostazioni

router = APIRouter(tags=["diagnostica"])


# === Schemi ===


class StatoComponente(BaseModel):
    """Stato di un singolo componente della pipeline."""

    disponibile: bool
    nome: str
    dettaglio: str | None = None


class StatoPipelineCv(BaseModel):
    """Stato complessivo della pipeline CV."""

    ffmpeg: StatoComponente = Field(
        ..., description="Estrazione frame da video"
    )
    opencv: StatoComponente = Field(
        ..., description="Raddrizzamento prospettico"
    )
    immagine_riferimento: StatoComponente = Field(
        ..., description="Immagine di riferimento per calibrazione"
    )
    client_cv: StatoComponente = Field(
        ..., description="Modello CV (mock o reale)"
    )
    pronto: bool = Field(
        ...,
        description="True se tutti i componenti sono disponibili",
    )
    livello_pronto: Literal["completo", "parziale", "non_pronto"] = Field(
        ...,
        description=(
            "completo = pipeline reale pronta. "
            "parziale = pipeline mock funzionante (manca solo modello reale). "
            "non_pronto = manca qualcosa di critico (ffmpeg, opencv, ...)."
        ),
    )


# === Helpers ===


def _check_ffmpeg() -> StatoComponente:
    percorso = shutil.which("ffmpeg")
    if percorso is not None:
        return StatoComponente(
            disponibile=True,
            nome="ffmpeg",
            dettaglio=f"trovato in {percorso}",
        )
    return StatoComponente(
        disponibile=False,
        nome="ffmpeg",
        dettaglio=(
            "non trovato nel PATH. Installa con: "
            "winget install Gyan.FFmpeg (Windows), "
            "apt install ffmpeg (Linux), "
            "brew install ffmpeg (macOS)."
        ),
    )


def _check_opencv() -> StatoComponente:
    try:
        import cv2
        import numpy  # noqa: F401
        # Versione cv2 per debug
        try:
            versione = cv2.__version__
        except AttributeError:
            versione = "(versione sconosciuta)"
        return StatoComponente(
            disponibile=True,
            nome="opencv",
            dettaglio=f"opencv-python {versione}",
        )
    except ImportError:
        return StatoComponente(
            disponibile=False,
            nome="opencv",
            dettaglio=(
                "opencv-python non installato. "
                "Esegui: pip install -e \".[cv]\""
            ),
        )


def _check_immagine_riferimento() -> StatoComponente:
    percorso = impostazioni.storage_frame_path / "img_riferimento.jpg"
    if percorso.exists() and percorso.stat().st_size > 0:
        return StatoComponente(
            disponibile=True,
            nome="immagine_riferimento",
            dettaglio=(
                f"trovata in {percorso} "
                f"({percorso.stat().st_size // 1024} KB)"
            ),
        )
    return StatoComponente(
        disponibile=False,
        nome="immagine_riferimento",
        dettaglio=(
            f"manca {percorso}. Posiziona l'immagine canonica "
            f"della plancia raddrizzata in questa directory per "
            f"abilitare la calibrazione."
        ),
    )


def _check_client_cv() -> StatoComponente:
    """
    Stato del client CV: mock o reale.
    Per ora il client di default e' sempre il mock; quando configureremo
    Roboflow, leggeremo le credenziali dalle impostazioni.
    """
    # Controllo difensivo: anche se il modulo cv_servizio non si carica,
    # non vogliamo che l'health check crashi
    try:
        from app.servizi.cv_servizio import ClientCVMock
        client = ClientCVMock(versione="health-check")
        return StatoComponente(
            disponibile=True,
            nome="client_cv",
            dettaglio=(
                f"mock attivo (versione: {client.versione_modello}). "
                f"Per attivare Roboflow reale, configurare api_key e "
                f"project_endpoint in app/routers/inferenze_cv.py "
                f"(_crea_servizio_cv)."
            ),
        )
    except Exception as e:
        return StatoComponente(
            disponibile=False,
            nome="client_cv",
            dettaglio=f"errore caricamento: {e}",
        )


# === Endpoint ===


@router.get(
    "/diagnostica/pipeline-cv",
    response_model=StatoPipelineCv,
    summary="Stato dei prerequisiti della pipeline CV",
)
async def stato_pipeline_cv() -> StatoPipelineCv:
    """
    Verifica che ffmpeg, opencv, immagine di riferimento e client CV
    siano disponibili. Utile per la UI di onboarding e per debug.
    """
    ffmpeg = _check_ffmpeg()
    opencv = _check_opencv()
    img_rif = _check_immagine_riferimento()
    client = _check_client_cv()

    # Determina livello pronto
    componenti_critici = [ffmpeg, opencv, img_rif, client]
    if all(c.disponibile for c in componenti_critici):
        # Tutto disponibile, ma il client e' ancora mock?
        if client.dettaglio and "mock attivo" in client.dettaglio:
            livello: Literal["completo", "parziale", "non_pronto"] = "parziale"
        else:
            livello = "completo"
    else:
        livello = "non_pronto"

    return StatoPipelineCv(
        ffmpeg=ffmpeg,
        opencv=opencv,
        immagine_riferimento=img_rif,
        client_cv=client,
        pronto=all(c.disponibile for c in componenti_critici),
        livello_pronto=livello,
    )
