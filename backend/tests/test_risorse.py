"""
Test endpoint risorse (territori e obiettivi).
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_lista_territori(client_test: AsyncClient) -> None:
    risposta = await client_test.get("/api/risorse/territori")
    assert risposta.status_code == 200
    body = risposta.json()
    assert len(body) == 42

    # Ogni territorio ha i campi attesi
    primo = body[0]
    assert "nome" in primo
    assert "continente" in primo
    assert "adiacenti" in primo
    assert isinstance(primo["adiacenti"], list)
    assert len(primo["adiacenti"]) >= 1

    # Ordinamento alfabetico
    nomi = [t["nome"] for t in body]
    assert nomi == sorted(nomi)


@pytest.mark.asyncio
async def test_lista_territori_contiene_canonici(client_test: AsyncClient) -> None:
    """Sanity check: alcuni nomi noti devono esserci."""
    risposta = await client_test.get("/api/risorse/territori")
    nomi = {t["nome"] for t in risposta.json()}
    assert "alaska" in nomi
    assert "africa_settentrionale" in nomi
    assert "venezuela" in nomi
    assert "afghanistan" in nomi


@pytest.mark.asyncio
async def test_continenti_tutti_presenti(client_test: AsyncClient) -> None:
    """I 6 continenti EG devono essere rappresentati."""
    risposta = await client_test.get("/api/risorse/territori")
    continenti = {t["continente"] for t in risposta.json()}
    assert continenti == {
        "nordamerica",
        "sudamerica",
        "europa",
        "africa",
        "asia",
        "oceania",
    }


@pytest.mark.asyncio
async def test_lista_obiettivi(client_test: AsyncClient) -> None:
    risposta = await client_test.get("/api/risorse/obiettivi")
    assert risposta.status_code == 200
    body = risposta.json()
    assert len(body) == 16

    # Tutti gli id sono unici e da 1 a 16
    ids = {o["id"] for o in body}
    assert ids == set(range(1, 17))

    # Ogni obiettivo ha territori richiesti non vuoti
    for o in body:
        assert isinstance(o["territori_richiesti"], list)
        assert len(o["territori_richiesti"]) >= 1
