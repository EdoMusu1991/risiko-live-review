"""Test endpoint diagnostica pipeline CV."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_diagnostica_pipeline_cv_torna_struttura_completa(
    client_test: AsyncClient,
) -> None:
    risposta = await client_test.get("/api/diagnostica/pipeline-cv")
    assert risposta.status_code == 200
    body = risposta.json()

    # Verifica struttura
    assert "ffmpeg" in body
    assert "opencv" in body
    assert "immagine_riferimento" in body
    assert "client_cv" in body
    assert "pronto" in body
    assert "livello_pronto" in body

    # Ogni componente ha i campi attesi
    for nome in ("ffmpeg", "opencv", "immagine_riferimento", "client_cv"):
        comp = body[nome]
        assert "disponibile" in comp
        assert isinstance(comp["disponibile"], bool)
        assert "nome" in comp


@pytest.mark.asyncio
async def test_diagnostica_pipeline_cv_livello_consistente_con_pronto(
    client_test: AsyncClient,
) -> None:
    """`pronto` e `livello_pronto` devono essere coerenti."""
    risposta = await client_test.get("/api/diagnostica/pipeline-cv")
    body = risposta.json()

    if body["pronto"]:
        # Se pronto, livello e' completo o parziale (mock attivo)
        assert body["livello_pronto"] in ("completo", "parziale")
    else:
        assert body["livello_pronto"] == "non_pronto"


@pytest.mark.asyncio
async def test_diagnostica_pipeline_cv_client_default_e_mock(
    client_test: AsyncClient,
) -> None:
    """Finche' Roboflow non e' configurato, il client di default e' mock."""
    risposta = await client_test.get("/api/diagnostica/pipeline-cv")
    body = risposta.json()

    assert body["client_cv"]["disponibile"] is True
    assert "mock" in body["client_cv"]["dettaglio"].lower()
