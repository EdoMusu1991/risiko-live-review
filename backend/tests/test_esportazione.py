"""
Test endpoint di esportazione partita (JSON e HTML).
"""


import pytest
from httpx import AsyncClient


async def _crea_partita_minima(client: AsyncClient) -> dict:
    """Crea partita 3 giocatori, fa setup automatico, e ritorna i dati."""
    risposta = await client.post(
        "/api/partite",
        json={
            "data_inizio": "2026-05-08T20:00:00+00:00",
            "luogo": "Il Gufo · Roma",
            "note": "Test export",
            "giocatori": [
                {"nome": "Edoardo", "colore": "rosso", "ordine_seduta": 1},
                {"nome": "Alice", "colore": "blu", "ordine_seduta": 2},
                {"nome": "Bob", "colore": "verde", "ordine_seduta": 3},
            ],
        },
    )
    assert risposta.status_code == 201
    return risposta.json()


@pytest.mark.asyncio
async def test_esporta_json_partita_vuota(client_test: AsyncClient) -> None:
    p = await _crea_partita_minima(client_test)
    pid = p["id"]

    risposta = await client_test.get(f"/api/partite/{pid}/esporta")
    assert risposta.status_code == 200
    assert risposta.headers["content-type"].startswith("application/json")

    bundle = risposta.json()
    assert bundle["schema_version"] == "1.0"
    assert "data_esportazione" in bundle
    assert bundle["partita"]["id"] == pid
    assert bundle["partita"]["luogo"] == "Il Gufo · Roma"
    assert len(bundle["giocatori"]) == 3
    assert bundle["eventi_validati"] == []
    # Senza eventi validati la ricostruzione produce snapshot vuoto


@pytest.mark.asyncio
async def test_esporta_json_dopo_setup(client_test: AsyncClient) -> None:
    p = await _crea_partita_minima(client_test)
    pid = p["id"]
    primo = p["giocatori"][0]["id"]

    # Setup automatico
    r = await client_test.post(
        f"/api/partite/{pid}/setup-automatico",
        json={"primo_giocatore_id": primo, "seed": 42},
    )
    assert r.status_code in (200, 201)

    risposta = await client_test.get(f"/api/partite/{pid}/esporta")
    assert risposta.status_code == 200

    bundle = risposta.json()
    # 42 territori + 3 obiettivi + 1 partita_inizio = 46 eventi
    assert len(bundle["eventi_validati"]) == 46
    # Stato finale ricostruito deve esserci
    assert bundle["stato_finale"] is not None
    assert bundle["stato_finale"]["fase_corrente"] == "rinforzo"
    assert bundle["stato_finale"]["turno"] == 1
    # 3 giocatori con 14 territori a testa (42/3)
    territori = bundle["stato_finale"]["territori"]
    assert len(territori) == 42


@pytest.mark.asyncio
async def test_esporta_html(client_test: AsyncClient) -> None:
    p = await _crea_partita_minima(client_test)
    pid = p["id"]
    primo = p["giocatori"][0]["id"]

    await client_test.post(
        f"/api/partite/{pid}/setup-automatico",
        json={"primo_giocatore_id": primo, "seed": 1},
    )

    risposta = await client_test.get(
        f"/api/partite/{pid}/esporta", params={"formato": "html"}
    )
    assert risposta.status_code == 200
    assert risposta.headers["content-type"].startswith("text/html")

    html = risposta.text
    # Contiene struttura attesa
    assert "<!DOCTYPE html>" in html
    assert "Risiko Live" in html
    assert "Edoardo" in html
    assert "Alice" in html
    assert "Bob" in html
    assert "Cronologia eventi" in html
    assert "Stato finale" in html
    # CSS inline (nessun link esterno)
    assert "<link" not in html or "stylesheet" not in html
    # Niente JS (autocontenuto)
    assert "<script" not in html


@pytest.mark.asyncio
async def test_esporta_html_descrizioni_leggibili(
    client_test: AsyncClient,
) -> None:
    """L'HTML deve mostrare descrizioni umane degli eventi."""
    p = await _crea_partita_minima(client_test)
    pid = p["id"]
    primo = p["giocatori"][0]["id"]

    await client_test.post(
        f"/api/partite/{pid}/setup-automatico",
        json={"primo_giocatore_id": primo, "seed": 1},
    )

    risposta = await client_test.get(
        f"/api/partite/{pid}/esporta", params={"formato": "html"}
    )
    html = risposta.text

    # Deve esserci almeno una descrizione di tipo "riceve" (territorio assegnato)
    assert "riceve" in html.lower()
    # I nomi giocatori compaiono nella cronologia
    assert html.count("Edoardo") >= 2  # roster + cronologia


@pytest.mark.asyncio
async def test_esporta_partita_inesistente(client_test: AsyncClient) -> None:
    risposta = await client_test.get(
        "/api/partite/non-esiste/esporta"
    )
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_esporta_formato_invalido(client_test: AsyncClient) -> None:
    p = await _crea_partita_minima(client_test)
    risposta = await client_test.get(
        f"/api/partite/{p['id']}/esporta", params={"formato": "xml"}
    )
    assert risposta.status_code == 422  # Pydantic literal validation


# === Test nuovo formato 'replay' (bundle per Battle Commander) ===


@pytest.mark.asyncio
async def test_esporta_replay_partita_vuota(client_test: AsyncClient) -> None:
    """Bundle replay produce schema_version + partita + giocatori (vuoti) + eventi vuoti."""
    p = await _crea_partita_minima(client_test)

    risposta = await client_test.get(
        f"/api/partite/{p['id']}/esporta", params={"formato": "replay"}
    )
    assert risposta.status_code == 200
    body = risposta.json()

    # Struttura conforme a SchemaBundleReplay zod
    assert body["schema_version"] == "1.0"
    assert "partita" in body
    assert body["partita"]["id"] == p["id"]
    assert "giocatori" in body
    assert len(body["giocatori"]) == 3
    assert "eventi" in body  # NON eventi_validati
    assert body["eventi"] == []

    # Campi NON presenti (specchio del .strict() zod)
    assert "data_esportazione" not in body
    assert "stato_finale" not in body
    assert "stato_review" not in body["partita"]


@pytest.mark.asyncio
async def test_esporta_replay_dopo_setup_eventi_serializzati(
    client_test: AsyncClient,
) -> None:
    """Dopo setup automatico, il bundle replay contiene tutti gli eventi."""
    p = await _crea_partita_minima(client_test)
    setup = await client_test.post(
        f"/api/partite/{p['id']}/setup-automatico", params={"seed": 42}
    )
    assert setup.status_code == 201

    risposta = await client_test.get(
        f"/api/partite/{p['id']}/esporta", params={"formato": "replay"}
    )
    body = risposta.json()
    assert len(body["eventi"]) > 40  # 42 territori + obiettivi + partita_inizio

    # Ogni evento ha i campi attesi dallo schema discriminated union
    for ev in body["eventi"]:
        assert "id" in ev
        assert "tipo" in ev
        assert "dati" in ev
        assert "ts_evento" in ev
        # partita_id propagato come da contratto BundleReplay
        assert ev["partita_id"] == p["id"]


@pytest.mark.asyncio
async def test_esporta_replay_giocatori_ordinati_per_seduta(
    client_test: AsyncClient,
) -> None:
    """I giocatori sono ordinati per ordine_seduta crescente."""
    p = await _crea_partita_minima(client_test)

    risposta = await client_test.get(
        f"/api/partite/{p['id']}/esporta", params={"formato": "replay"}
    )
    body = risposta.json()
    ordini = [g["ordine_seduta"] for g in body["giocatori"]]
    assert ordini == sorted(ordini)


@pytest.mark.asyncio
async def test_esporta_replay_filename_dedicato(
    client_test: AsyncClient,
) -> None:
    """Il filename usa prefisso 'risiko-replay-' per distinguerlo dal JSON normale."""
    p = await _crea_partita_minima(client_test)

    risposta = await client_test.get(
        f"/api/partite/{p['id']}/esporta", params={"formato": "replay"}
    )
    cd = risposta.headers.get("content-disposition", "")
    assert "risiko-replay-" in cd
    assert ".json" in cd
