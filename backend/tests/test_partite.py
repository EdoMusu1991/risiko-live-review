"""
Test degli endpoint partite.

Coperti:
- Creazione partita valida e con errori di validazione.
- Lista partite con filtri.
- Get singola partita esistente / inesistente.
- Aggiornamento partita.
- Eliminazione partita.
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from tests.conftest import crea_dati_partita_minima

# === Creazione ===


@pytest.mark.asyncio
async def test_crea_partita_valida(client_test: AsyncClient) -> None:
    dati = crea_dati_partita_minima().model_dump(mode="json")
    risposta = await client_test.post("/api/partite", json=dati)
    assert risposta.status_code == 201
    body = risposta.json()
    assert body["luogo"] == "Test Lab"
    assert body["stato_review"] == "grezza"
    assert len(body["giocatori"]) == 2
    assert body["giocatori"][0]["nome"] == "Edoardo"
    assert body["giocatori"][0]["colore"] == "rosso"


@pytest.mark.asyncio
async def test_crea_partita_colori_duplicati(client_test: AsyncClient) -> None:
    """Due giocatori con stesso colore -> 400."""
    dati = crea_dati_partita_minima().model_dump(mode="json")
    dati["giocatori"][1]["colore"] = "rosso"  # entrambi rossi
    risposta = await client_test.post("/api/partite", json=dati)
    assert risposta.status_code == 400
    assert "duplicat" in risposta.json()["detail"].lower()


@pytest.mark.asyncio
async def test_crea_partita_ordine_seduta_invalido(client_test: AsyncClient) -> None:
    """Ordini di seduta non consecutivi -> 400."""
    dati = crea_dati_partita_minima().model_dump(mode="json")
    dati["giocatori"][1]["ordine_seduta"] = 5  # gap
    risposta = await client_test.post("/api/partite", json=dati)
    assert risposta.status_code == 400


@pytest.mark.asyncio
async def test_crea_partita_un_solo_giocatore(client_test: AsyncClient) -> None:
    """Solo 1 giocatore -> errore di validazione Pydantic (422)."""
    dati = crea_dati_partita_minima().model_dump(mode="json")
    dati["giocatori"] = dati["giocatori"][:1]
    risposta = await client_test.post("/api/partite", json=dati)
    assert risposta.status_code == 422


@pytest.mark.asyncio
async def test_crea_partita_troppi_giocatori(client_test: AsyncClient) -> None:
    """7 giocatori (max 6) -> 422."""
    dati = crea_dati_partita_minima().model_dump(mode="json")
    base = dati["giocatori"][0]
    colori = ["rosso", "blu", "verde", "giallo", "nero", "viola", "rosso"]
    dati["giocatori"] = [
        {**base, "nome": f"P{i}", "colore": c, "ordine_seduta": i + 1}
        for i, c in enumerate(colori)
    ]
    risposta = await client_test.post("/api/partite", json=dati)
    assert risposta.status_code == 422


# === Lista ===


@pytest.mark.asyncio
async def test_lista_vuota(client_test: AsyncClient) -> None:
    risposta = await client_test.get("/api/partite")
    assert risposta.status_code == 200
    assert risposta.json() == []


@pytest.mark.asyncio
async def test_lista_dopo_creazioni(client_test: AsyncClient) -> None:
    """Crea 3 partite, verifica che la lista le ritorni in ordine cronologico inverso."""
    for i, anno in enumerate([2024, 2025, 2026]):
        dati = crea_dati_partita_minima().model_dump(mode="json")
        dati["data_inizio"] = datetime(anno, 5, 7, 21, 0, tzinfo=UTC).isoformat()
        dati["luogo"] = f"Sede {i}"
        risposta = await client_test.post("/api/partite", json=dati)
        assert risposta.status_code == 201

    risposta = await client_test.get("/api/partite")
    assert risposta.status_code == 200
    body = risposta.json()
    assert len(body) == 3
    # Ordine decrescente per data_inizio
    assert body[0]["luogo"] == "Sede 2"  # 2026
    assert body[2]["luogo"] == "Sede 0"  # 2024


@pytest.mark.asyncio
async def test_lista_paginata(client_test: AsyncClient) -> None:
    for _ in range(5):
        await client_test.post(
            "/api/partite",
            json=crea_dati_partita_minima().model_dump(mode="json"),
        )
    risposta = await client_test.get("/api/partite?limite=2")
    assert risposta.status_code == 200
    assert len(risposta.json()) == 2

    risposta = await client_test.get("/api/partite?offset=4&limite=2")
    assert risposta.status_code == 200
    assert len(risposta.json()) == 1


@pytest.mark.asyncio
async def test_lista_filtra_per_stato(client_test: AsyncClient) -> None:
    """Crea 2 partite, marca una come VALIDATA, filtra."""
    risposte = []
    for _ in range(2):
        r = await client_test.post(
            "/api/partite",
            json=crea_dati_partita_minima().model_dump(mode="json"),
        )
        risposte.append(r.json())

    # Marca la prima come validata
    pid = risposte[0]["id"]
    await client_test.patch(
        f"/api/partite/{pid}", json={"stato_review": "validata"}
    )

    # Filtra solo validate
    r = await client_test.get("/api/partite?stato=validata")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == pid


# === Get singola ===


@pytest.mark.asyncio
async def test_get_partita_inesistente(client_test: AsyncClient) -> None:
    risposta = await client_test.get("/api/partite/non-esiste")
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_get_partita_esistente(client_test: AsyncClient) -> None:
    creazione = await client_test.post(
        "/api/partite",
        json=crea_dati_partita_minima().model_dump(mode="json"),
    )
    pid = creazione.json()["id"]

    risposta = await client_test.get(f"/api/partite/{pid}")
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["id"] == pid
    assert "giocatori" in body


# === Aggiornamento ===


@pytest.mark.asyncio
async def test_aggiorna_partita_metadata(client_test: AsyncClient) -> None:
    creazione = await client_test.post(
        "/api/partite",
        json=crea_dati_partita_minima().model_dump(mode="json"),
    )
    pid = creazione.json()["id"]

    risposta = await client_test.patch(
        f"/api/partite/{pid}",
        json={"luogo": "Nuovo Luogo", "note": "Aggiornata"},
    )
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["luogo"] == "Nuovo Luogo"
    assert body["note"] == "Aggiornata"


@pytest.mark.asyncio
async def test_aggiorna_stato_review(client_test: AsyncClient) -> None:
    creazione = await client_test.post(
        "/api/partite",
        json=crea_dati_partita_minima().model_dump(mode="json"),
    )
    pid = creazione.json()["id"]

    risposta = await client_test.patch(
        f"/api/partite/{pid}", json={"stato_review": "in_review"}
    )
    assert risposta.status_code == 200
    assert risposta.json()["stato_review"] == "in_review"


@pytest.mark.asyncio
async def test_aggiorna_partita_inesistente(client_test: AsyncClient) -> None:
    risposta = await client_test.patch(
        "/api/partite/fake-id", json={"luogo": "X"}
    )
    assert risposta.status_code == 404


# === Eliminazione ===


@pytest.mark.asyncio
async def test_elimina_partita_esistente(client_test: AsyncClient) -> None:
    creazione = await client_test.post(
        "/api/partite",
        json=crea_dati_partita_minima().model_dump(mode="json"),
    )
    pid = creazione.json()["id"]

    risposta = await client_test.delete(f"/api/partite/{pid}")
    assert risposta.status_code == 204

    # Ora la partita non esiste più
    get_risposta = await client_test.get(f"/api/partite/{pid}")
    assert get_risposta.status_code == 404


@pytest.mark.asyncio
async def test_elimina_partita_inesistente(client_test: AsyncClient) -> None:
    risposta = await client_test.delete("/api/partite/non-esiste")
    assert risposta.status_code == 404
