"""
Test dell'endpoint POST /api/partite/{id}/setup-automatico.

Coperti:
- Setup base 2 giocatori → 42 territori + 2 obiettivi + 1 partita_inizio.
- Distribuzione armate corretta (somma = totale regolamento EG).
- Round-robin territori (ogni giocatore ha 21 territori per 2-player game).
- Obiettivi distinti tra giocatori.
- primo_giocatore_id default e custom.
- seed riproducibile.
- Errori: partita inesistente, setup già presente, primo_giocatore invalido.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from tests.conftest import crea_dati_partita_minima


async def _crea_partita(client: AsyncClient) -> tuple[str, str, str]:
    """Crea partita 2 giocatori e ritorna (partita_id, p1_id, p2_id)."""
    risposta = await client.post(
        "/api/partite",
        json=crea_dati_partita_minima().model_dump(mode="json"),
    )
    assert risposta.status_code == 201
    body = risposta.json()
    return body["id"], body["giocatori"][0]["id"], body["giocatori"][1]["id"]


# === Successo ===


@pytest.mark.asyncio
async def test_setup_automatico_2_giocatori(client_test: AsyncClient) -> None:
    """Setup base: 42 territori + 2 obiettivi + 1 partita_inizio."""
    pid, p1, _p2 = await _crea_partita(client_test)

    risposta = await client_test.post(f"/api/partite/{pid}/setup-automatico")
    assert risposta.status_code == 201
    body = risposta.json()
    assert body["n_territori_assegnati"] == 42
    assert body["n_obiettivi_assegnati"] == 2
    assert body["primo_giocatore_id"] == p1
    assert body["armate_per_giocatore"] == 40  # 2 giocatori → 40 armate
    assert isinstance(body["seed_usato"], int)


@pytest.mark.asyncio
async def test_setup_automatico_crea_eventi_validati(
    client_test: AsyncClient,
) -> None:
    """Verifica che gli eventi siano effettivamente nel DB."""
    pid, _p1, _p2 = await _crea_partita(client_test)

    await client_test.post(f"/api/partite/{pid}/setup-automatico")

    eventi = (
        await client_test.get(f"/api/partite/{pid}/eventi-validati")
    ).json()
    assert len(eventi) == 45  # 42 + 2 + 1

    # Tipi: 42 territori, 2 obiettivi, 1 partita_inizio
    tipi_count: dict[str, int] = {}
    for e in eventi:
        tipi_count[e["tipo"]] = tipi_count.get(e["tipo"], 0) + 1

    assert tipi_count["territorio_assegnato_inizio"] == 42
    assert tipi_count["obiettivo_assegnato"] == 2
    assert tipi_count["partita_inizio"] == 1


@pytest.mark.asyncio
async def test_setup_automatico_distribuzione_armate(
    client_test: AsyncClient,
) -> None:
    """Le armate distribuite per giocatore devono sommare a 40 (2-player)."""
    pid, p1, p2 = await _crea_partita(client_test)
    await client_test.post(f"/api/partite/{pid}/setup-automatico")

    eventi = (
        await client_test.get(f"/api/partite/{pid}/eventi-validati")
    ).json()
    territori_eventi = [
        e for e in eventi if e["tipo"] == "territorio_assegnato_inizio"
    ]

    armate_p1 = sum(
        int(e["dati"]["n_armate"])
        for e in territori_eventi
        if e["dati"]["giocatore_id"] == p1
    )
    armate_p2 = sum(
        int(e["dati"]["n_armate"])
        for e in territori_eventi
        if e["dati"]["giocatore_id"] == p2
    )
    assert armate_p1 == 40
    assert armate_p2 == 40


@pytest.mark.asyncio
async def test_setup_automatico_round_robin_territori(
    client_test: AsyncClient,
) -> None:
    """In partita 2-player, ogni giocatore deve avere 21 territori."""
    pid, p1, p2 = await _crea_partita(client_test)
    await client_test.post(f"/api/partite/{pid}/setup-automatico")

    eventi = (
        await client_test.get(f"/api/partite/{pid}/eventi-validati")
    ).json()
    territori_eventi = [
        e for e in eventi if e["tipo"] == "territorio_assegnato_inizio"
    ]

    n_p1 = sum(1 for e in territori_eventi if e["dati"]["giocatore_id"] == p1)
    n_p2 = sum(1 for e in territori_eventi if e["dati"]["giocatore_id"] == p2)
    assert n_p1 == 21
    assert n_p2 == 21


@pytest.mark.asyncio
async def test_setup_automatico_obiettivi_distinti(
    client_test: AsyncClient,
) -> None:
    """I 2 giocatori devono avere obiettivi distinti."""
    pid, _p1, _p2 = await _crea_partita(client_test)
    await client_test.post(f"/api/partite/{pid}/setup-automatico")

    eventi = (
        await client_test.get(f"/api/partite/{pid}/eventi-validati")
    ).json()
    obiettivi_eventi = [e for e in eventi if e["tipo"] == "obiettivo_assegnato"]
    obiettivi_id = {int(e["dati"]["obiettivo_id"]) for e in obiettivi_eventi}
    assert len(obiettivi_id) == 2  # tutti distinti
    for oid in obiettivi_id:
        assert 1 <= oid <= 16


@pytest.mark.asyncio
async def test_setup_automatico_seed_riproducibile(
    client_test: AsyncClient,
) -> None:
    """Stesso seed → stessa distribuzione."""
    pid_a, _, _ = await _crea_partita(client_test)
    pid_b, _, _ = await _crea_partita(client_test)

    await client_test.post(
        f"/api/partite/{pid_a}/setup-automatico", json={"seed": 42}
    )
    await client_test.post(
        f"/api/partite/{pid_b}/setup-automatico", json={"seed": 42}
    )

    eventi_a = (
        await client_test.get(f"/api/partite/{pid_a}/eventi-validati")
    ).json()
    eventi_b = (
        await client_test.get(f"/api/partite/{pid_b}/eventi-validati")
    ).json()

    # I "dati" devono coincidere (gli id giocatori invece sono diversi tra
    # le due partite, quindi confronto solo i tipi e ordini)
    territori_a = [
        e["dati"]["territorio"]
        for e in eventi_a
        if e["tipo"] == "territorio_assegnato_inizio"
    ]
    territori_b = [
        e["dati"]["territorio"]
        for e in eventi_b
        if e["tipo"] == "territorio_assegnato_inizio"
    ]
    # Stesso seed → stessa permutazione di territori
    assert territori_a == territori_b


@pytest.mark.asyncio
async def test_setup_automatico_primo_giocatore_custom(
    client_test: AsyncClient,
) -> None:
    """Specifico primo_giocatore_id diverso dal default."""
    pid, _p1, p2 = await _crea_partita(client_test)

    risposta = await client_test.post(
        f"/api/partite/{pid}/setup-automatico",
        json={"primo_giocatore_id": p2},
    )
    assert risposta.status_code == 201
    assert risposta.json()["primo_giocatore_id"] == p2

    eventi = (
        await client_test.get(f"/api/partite/{pid}/eventi-validati")
    ).json()
    inizio = next(e for e in eventi if e["tipo"] == "partita_inizio")
    assert inizio["dati"]["primo_giocatore_id"] == p2


@pytest.mark.asyncio
async def test_setup_automatico_riproducibile_via_ricostruzione(
    client_test: AsyncClient,
) -> None:
    """
    Smoke test: dopo setup automatico, la ricostruzione del motore deve
    avere successo (no errori applicazione).
    """
    pid, _p1, _p2 = await _crea_partita(client_test)
    await client_test.post(f"/api/partite/{pid}/setup-automatico")

    risposta = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    body = risposta.json()
    assert body["successo"] is True, f"Errori: {body['errori']}"
    assert body["n_eventi_applicati"] == 45
    assert body["stato_finale"]["fase_corrente"] == "rinforzo"


# === Errori ===


@pytest.mark.asyncio
async def test_setup_automatico_partita_inesistente(
    client_test: AsyncClient,
) -> None:
    risposta = await client_test.post(
        "/api/partite/non-esiste/setup-automatico"
    )
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_setup_automatico_gia_presente(client_test: AsyncClient) -> None:
    """Setup su partita con eventi già esistenti → 409 conflict."""
    pid, _p1, _p2 = await _crea_partita(client_test)

    # Aggiungo un evento manuale
    await client_test.post(
        f"/api/partite/{pid}/eventi-validati",
        json={
            "ts_evento": datetime(2026, 5, 7, 21, 0, tzinfo=UTC).isoformat(),
            "tipo": "armate_piazzate",
            "dati": {"giocatore_id": "fake", "territorio": "alaska", "n": 1},
        },
    )

    risposta = await client_test.post(f"/api/partite/{pid}/setup-automatico")
    assert risposta.status_code == 409


@pytest.mark.asyncio
async def test_setup_automatico_doppio(client_test: AsyncClient) -> None:
    """Chiamare setup due volte → seconda volta 409."""
    pid, _p1, _p2 = await _crea_partita(client_test)

    r1 = await client_test.post(f"/api/partite/{pid}/setup-automatico")
    assert r1.status_code == 201

    r2 = await client_test.post(f"/api/partite/{pid}/setup-automatico")
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_setup_automatico_primo_giocatore_invalido(
    client_test: AsyncClient,
) -> None:
    """primo_giocatore_id che non appartiene alla partita → 400."""
    pid, _p1, _p2 = await _crea_partita(client_test)

    risposta = await client_test.post(
        f"/api/partite/{pid}/setup-automatico",
        json={"primo_giocatore_id": "non-appartiene"},
    )
    assert risposta.status_code == 400
