"""
Test endpoint di esportazione partita (JSON e HTML).
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


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


# === Test formato CSV (per analytics Excel/Sheets) ===


@pytest.mark.asyncio
async def test_esporta_csv_partita_vuota(client_test: AsyncClient) -> None:
    """CSV di partita senza eventi: solo header riga + BOM."""
    p = await _crea_partita_minima(client_test)

    risposta = await client_test.get(
        f"/api/partite/{p['id']}/esporta", params={"formato": "csv"}
    )
    assert risposta.status_code == 200
    assert risposta.headers["content-type"].startswith("text/csv")
    contenuto = risposta.text

    # BOM UTF-8 per Excel
    assert contenuto.startswith("\ufeff")

    # Header presente
    righe = contenuto.lstrip("\ufeff").strip().split("\n")
    assert len(righe) == 1  # solo header
    assert "posizione" in righe[0]
    assert "tipo" in righe[0]
    assert "dadi_attaccante" in righe[0]


@pytest.mark.asyncio
async def test_esporta_csv_dopo_setup(client_test: AsyncClient) -> None:
    """CSV con setup automatico contiene 1 riga per evento."""
    p = await _crea_partita_minima(client_test)
    setup = await client_test.post(
        f"/api/partite/{p['id']}/setup-automatico", params={"seed": 42}
    )
    assert setup.status_code == 201

    risposta = await client_test.get(
        f"/api/partite/{p['id']}/esporta", params={"formato": "csv"}
    )
    assert risposta.status_code == 200
    contenuto = risposta.text.lstrip("\ufeff")
    righe = [r for r in contenuto.split("\n") if r]
    # Header + 46 eventi setup (42 territori + 3 obiettivi + 1 partita_inizio)
    assert len(righe) == 47


@pytest.mark.asyncio
async def test_esporta_csv_attacco_serializza_dadi(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    """Per ATTACCO_RISOLTO i dadi sono pipe-separated."""
    from app.modelli import EventoValidato, TipoEvento

    p = await _crea_partita_minima(client_test)

    # Aggiungo un attacco direttamente al DB (skippo flusso completo)
    from sqlalchemy import select as _sel

    from app.modelli import GiocatorePartita as Giocatore

    res_g = await sessione_test.execute(
        _sel(Giocatore).where(Giocatore.partita_id == p["id"]).order_by(Giocatore.ordine_seduta)
    )
    g = next(iter(res_g.scalars()))

    sessione_test.add(
        EventoValidato(
            partita_id=p["id"],
            ts_evento=datetime(2026, 5, 8, 21, 30, tzinfo=UTC),
            tipo=TipoEvento.ATTACCO_RISOLTO,
            dati={
                "giocatore_id": g.id,
                "da": "kamchatka",
                "a": "alaska",
                "dadi_attaccante": [6, 4, 2],
                "dadi_difensore": [5, 3],
            },
            evento_grezzo_id=None,
            validato_da="test",
        )
    )
    await sessione_test.commit()

    risposta = await client_test.get(
        f"/api/partite/{p['id']}/esporta", params={"formato": "csv"}
    )
    contenuto = risposta.text
    # Cerca la riga con i dadi
    assert "6|4|2" in contenuto
    assert "5|3" in contenuto
    # Nome del giocatore risolto
    assert g.nome in contenuto


@pytest.mark.asyncio
async def test_esporta_csv_filename_dedicato(
    client_test: AsyncClient,
) -> None:
    p = await _crea_partita_minima(client_test)

    risposta = await client_test.get(
        f"/api/partite/{p['id']}/esporta", params={"formato": "csv"}
    )
    cd = risposta.headers.get("content-disposition", "")
    assert "risiko-eventi-" in cd
    assert ".csv" in cd
