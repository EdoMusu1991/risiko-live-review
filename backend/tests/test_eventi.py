"""
Test endpoint eventi (grezzi e validati).

Coperti:
- Aggiunta evento grezzo singolo e batch.
- Lista eventi grezzi (con/senza filtro non-validati).
- Eliminazione evento grezzo.
- Promozione di evento grezzo a validato.
- Inserimento evento validato manuale (senza grezzo).
- Edge case: partita inesistente, evento inesistente.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from tests.conftest import crea_dati_partita_minima


async def _crea_partita_e_get_id(client: AsyncClient) -> str:
    """Helper: crea una partita di test e ritorna l'id."""
    risposta = await client.post(
        "/api/partite",
        json=crea_dati_partita_minima().model_dump(mode="json"),
    )
    assert risposta.status_code == 201
    return str(risposta.json()["id"])


def _evento_grezzo_dadi(secondi_offset: int = 0) -> dict[str, object]:
    """Costruisce un evento grezzo di tipo DADI_LANCIATI."""
    return {
        "ts_evento": (
            datetime(2026, 5, 7, 21, 0, tzinfo=UTC) + timedelta(seconds=secondi_offset)
        ).isoformat(),
        "tipo": "dadi_lanciati",
        "fonte": "dado_ble",
        "confidenza": 1.0,
        "dati": {"giocatore": "p1", "dadi": [4, 5, 6], "ruolo": "attaccante"},
    }


# === Eventi grezzi: aggiunta ===


@pytest.mark.asyncio
async def test_aggiungi_evento_grezzo(client_test: AsyncClient) -> None:
    pid = await _crea_partita_e_get_id(client_test)

    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-grezzi",
        json=_evento_grezzo_dadi(),
    )
    assert risposta.status_code == 201
    body = risposta.json()
    assert body["tipo"] == "dadi_lanciati"
    assert body["fonte"] == "dado_ble"
    assert body["validato"] is False
    assert body["dati"]["dadi"] == [4, 5, 6]


@pytest.mark.asyncio
async def test_aggiungi_evento_a_partita_inesistente(client_test: AsyncClient) -> None:
    risposta = await client_test.post(
        "/api/partite/non-esiste/eventi-grezzi",
        json=_evento_grezzo_dadi(),
    )
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_evento_grezzo_tipo_invalido(client_test: AsyncClient) -> None:
    """Tipo non in TipoEvento -> 422."""
    pid = await _crea_partita_e_get_id(client_test)
    payload = _evento_grezzo_dadi()
    payload["tipo"] = "tipo_che_non_esiste"
    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-grezzi", json=payload
    )
    assert risposta.status_code == 422


# === Batch ===


@pytest.mark.asyncio
async def test_aggiungi_eventi_batch(client_test: AsyncClient) -> None:
    pid = await _crea_partita_e_get_id(client_test)

    eventi = [_evento_grezzo_dadi(secondi_offset=i) for i in range(5)]
    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-grezzi/batch",
        json={"eventi": eventi},
    )
    assert risposta.status_code == 201
    body = risposta.json()
    assert len(body) == 5


@pytest.mark.asyncio
async def test_batch_vuoto_rifiutato(client_test: AsyncClient) -> None:
    """Batch con 0 eventi -> 422 (min_length=1)."""
    pid = await _crea_partita_e_get_id(client_test)
    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-grezzi/batch",
        json={"eventi": []},
    )
    assert risposta.status_code == 422


# === Lista ===


@pytest.mark.asyncio
async def test_lista_eventi_grezzi_ordinata_per_ts(client_test: AsyncClient) -> None:
    pid = await _crea_partita_e_get_id(client_test)

    # Inserisci in ordine sparso, l'API deve ritornarli ordinati
    for offset in [10, 1, 5, 20, 3]:
        await client_test.post(
            f"/api/partite/{pid}/eventi-grezzi",
            json=_evento_grezzo_dadi(secondi_offset=offset),
        )

    risposta = await client_test.get(f"/api/partite/{pid}/eventi-grezzi")
    assert risposta.status_code == 200
    body = risposta.json()
    timestamps = [e["ts_evento"] for e in body]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_lista_solo_non_validati(client_test: AsyncClient) -> None:
    """Filtro solo_non_validati esclude eventi grezzi già validati."""
    pid = await _crea_partita_e_get_id(client_test)

    # Crea due eventi grezzi
    for offset in [1, 2]:
        await client_test.post(
            f"/api/partite/{pid}/eventi-grezzi",
            json=_evento_grezzo_dadi(secondi_offset=offset),
        )

    # Recupero gli id
    eventi_grezzi = (await client_test.get(
        f"/api/partite/{pid}/eventi-grezzi"
    )).json()
    primo_id = eventi_grezzi[0]["id"]

    # Promuovo il primo a validato
    await client_test.post(
        f"/api/partite/{pid}/eventi-validati",
        json={
            "ts_evento": eventi_grezzi[0]["ts_evento"],
            "tipo": "dadi_lanciati",
            "dati": {"dadi": [4, 5, 6]},
            "evento_grezzo_id": primo_id,
        },
    )

    # Senza filtro: 2 eventi
    risposta = await client_test.get(f"/api/partite/{pid}/eventi-grezzi")
    assert len(risposta.json()) == 2

    # Solo non validati: 1 evento
    risposta = await client_test.get(
        f"/api/partite/{pid}/eventi-grezzi?solo_non_validati=true"
    )
    assert len(risposta.json()) == 1


# === Eliminazione ===


@pytest.mark.asyncio
async def test_elimina_evento_grezzo(client_test: AsyncClient) -> None:
    pid = await _crea_partita_e_get_id(client_test)
    creazione = await client_test.post(
        f"/api/partite/{pid}/eventi-grezzi",
        json=_evento_grezzo_dadi(),
    )
    evento_id = creazione.json()["id"]

    risposta = await client_test.delete(
        f"/api/partite/{pid}/eventi-grezzi/{evento_id}"
    )
    assert risposta.status_code == 204

    # Ora la lista è vuota
    lista = await client_test.get(f"/api/partite/{pid}/eventi-grezzi")
    assert lista.json() == []


@pytest.mark.asyncio
async def test_elimina_evento_inesistente(client_test: AsyncClient) -> None:
    pid = await _crea_partita_e_get_id(client_test)
    risposta = await client_test.delete(
        f"/api/partite/{pid}/eventi-grezzi/non-esiste"
    )
    assert risposta.status_code == 404


# === Eventi validati ===


@pytest.mark.asyncio
async def test_crea_evento_validato_manuale(client_test: AsyncClient) -> None:
    """Crea un evento validato senza riferimento a un grezzo."""
    pid = await _crea_partita_e_get_id(client_test)

    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-validati",
        json={
            "ts_evento": datetime(2026, 5, 7, 21, 0, tzinfo=UTC).isoformat(),
            "tipo": "armate_piazzate",
            "dati": {"giocatore": "p1", "territorio": "alaska", "n": 3},
            "validato_da": "test_user",
        },
    )
    assert risposta.status_code == 201
    body = risposta.json()
    assert body["tipo"] == "armate_piazzate"
    assert body["evento_grezzo_id"] is None


@pytest.mark.asyncio
async def test_promuove_grezzo_a_validato(client_test: AsyncClient) -> None:
    """Crea grezzo, promuove a validato, verifica che il grezzo sia marcato."""
    pid = await _crea_partita_e_get_id(client_test)

    grezzo_creazione = await client_test.post(
        f"/api/partite/{pid}/eventi-grezzi",
        json=_evento_grezzo_dadi(),
    )
    grezzo_id = grezzo_creazione.json()["id"]
    assert grezzo_creazione.json()["validato"] is False

    # Promuovi
    await client_test.post(
        f"/api/partite/{pid}/eventi-validati",
        json={
            "ts_evento": grezzo_creazione.json()["ts_evento"],
            "tipo": "dadi_lanciati",
            "dati": {"dadi": [4, 5, 6]},
            "evento_grezzo_id": grezzo_id,
        },
    )

    # Ricarica il grezzo dalla lista
    lista = await client_test.get(f"/api/partite/{pid}/eventi-grezzi")
    grezzi = lista.json()
    assert len(grezzi) == 1
    assert grezzi[0]["validato"] is True


@pytest.mark.asyncio
async def test_promuove_grezzo_inesistente(client_test: AsyncClient) -> None:
    """Riferimento a evento_grezzo_id che non esiste -> 400."""
    pid = await _crea_partita_e_get_id(client_test)

    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-validati",
        json={
            "ts_evento": datetime(2026, 5, 7, 21, 0, tzinfo=UTC).isoformat(),
            "tipo": "dadi_lanciati",
            "dati": {"dadi": [1, 2, 3]},
            "evento_grezzo_id": "id-che-non-esiste",
        },
    )
    assert risposta.status_code == 400


@pytest.mark.asyncio
async def test_lista_eventi_validati(client_test: AsyncClient) -> None:
    pid = await _crea_partita_e_get_id(client_test)

    for offset in [1, 5, 3]:
        await client_test.post(
            f"/api/partite/{pid}/eventi-validati",
            json={
                "ts_evento": (
                    datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
                    + timedelta(seconds=offset)
                ).isoformat(),
                "tipo": "armate_piazzate",
                "dati": {"giocatore": "p1", "territorio": "alaska", "n": offset},
            },
        )

    risposta = await client_test.get(f"/api/partite/{pid}/eventi-validati")
    assert risposta.status_code == 200
    body = risposta.json()
    assert len(body) == 3
    # Ordinati per ts
    timestamps = [e["ts_evento"] for e in body]
    assert timestamps == sorted(timestamps)


# === PATCH eventi validati ===


@pytest.mark.asyncio
async def test_aggiorna_evento_validato_dati(client_test: AsyncClient) -> None:
    pid = await _crea_partita_e_get_id(client_test)

    creazione = await client_test.post(
        f"/api/partite/{pid}/eventi-validati",
        json={
            "ts_evento": datetime(2026, 5, 7, 21, 0, tzinfo=UTC).isoformat(),
            "tipo": "armate_piazzate",
            "dati": {"territorio": "alaska", "n": 3},
        },
    )
    eid = creazione.json()["id"]

    risposta = await client_test.patch(
        f"/api/partite/{pid}/eventi-validati/{eid}",
        json={"dati": {"territorio": "kamchatka", "n": 5}},
    )
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["dati"]["territorio"] == "kamchatka"
    assert body["dati"]["n"] == 5
    # Tipo invariato
    assert body["tipo"] == "armate_piazzate"


@pytest.mark.asyncio
async def test_aggiorna_evento_validato_ts_e_tipo(client_test: AsyncClient) -> None:
    pid = await _crea_partita_e_get_id(client_test)

    creazione = await client_test.post(
        f"/api/partite/{pid}/eventi-validati",
        json={
            "ts_evento": datetime(2026, 5, 7, 21, 0, tzinfo=UTC).isoformat(),
            "tipo": "armate_piazzate",
            "dati": {"n": 1},
        },
    )
    eid = creazione.json()["id"]

    nuovo_ts = datetime(2026, 5, 7, 21, 30, tzinfo=UTC).isoformat()
    risposta = await client_test.patch(
        f"/api/partite/{pid}/eventi-validati/{eid}",
        json={"ts_evento": nuovo_ts, "tipo": "turno_finito"},
    )
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["ts_evento"].startswith("2026-05-07T21:30")
    assert body["tipo"] == "turno_finito"


@pytest.mark.asyncio
async def test_aggiorna_evento_validato_inesistente(client_test: AsyncClient) -> None:
    pid = await _crea_partita_e_get_id(client_test)
    risposta = await client_test.patch(
        f"/api/partite/{pid}/eventi-validati/non-esiste",
        json={"validato_da": "edoardo"},
    )
    assert risposta.status_code == 404


# === DELETE eventi validati ===


@pytest.mark.asyncio
async def test_elimina_evento_validato(client_test: AsyncClient) -> None:
    pid = await _crea_partita_e_get_id(client_test)

    creazione = await client_test.post(
        f"/api/partite/{pid}/eventi-validati",
        json={
            "ts_evento": datetime(2026, 5, 7, 21, 0, tzinfo=UTC).isoformat(),
            "tipo": "armate_piazzate",
            "dati": {"n": 1},
        },
    )
    eid = creazione.json()["id"]

    risposta = await client_test.delete(
        f"/api/partite/{pid}/eventi-validati/{eid}"
    )
    assert risposta.status_code == 204

    # Lista ora vuota
    lista = await client_test.get(f"/api/partite/{pid}/eventi-validati")
    assert lista.json() == []


@pytest.mark.asyncio
async def test_elimina_evento_validato_inesistente(
    client_test: AsyncClient,
) -> None:
    pid = await _crea_partita_e_get_id(client_test)
    risposta = await client_test.delete(
        f"/api/partite/{pid}/eventi-validati/non-esiste"
    )
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_elimina_validato_lascia_grezzo_marcato(
    client_test: AsyncClient,
) -> None:
    """Eliminando il validato, il grezzo originale resta validato=True."""
    pid = await _crea_partita_e_get_id(client_test)

    grezzo = await client_test.post(
        f"/api/partite/{pid}/eventi-grezzi",
        json=_evento_grezzo_dadi(),
    )
    grezzo_id = grezzo.json()["id"]

    validato = await client_test.post(
        f"/api/partite/{pid}/eventi-validati",
        json={
            "ts_evento": grezzo.json()["ts_evento"],
            "tipo": "dadi_lanciati",
            "dati": {"dadi": [4, 5, 6]},
            "evento_grezzo_id": grezzo_id,
        },
    )
    vid = validato.json()["id"]

    # Elimino il validato
    await client_test.delete(f"/api/partite/{pid}/eventi-validati/{vid}")

    # Il grezzo resta validato=True (comportamento intenzionale)
    grezzi = (await client_test.get(f"/api/partite/{pid}/eventi-grezzi")).json()
    assert grezzi[0]["validato"] is True


# === Aggiornamento eventi grezzi ===


@pytest.mark.asyncio
async def test_aggiorna_evento_grezzo(client_test: AsyncClient) -> None:
    """Modifica del payload `dati` di un evento grezzo."""
    pid = await _crea_partita_e_get_id(client_test)
    creazione = await client_test.post(
        f"/api/partite/{pid}/eventi-grezzi",
        json=_evento_grezzo_dadi(),
    )
    eid = creazione.json()["id"]

    risposta = await client_test.patch(
        f"/api/partite/{pid}/eventi-grezzi/{eid}",
        json={"dati": {"giocatore": "p2", "dadi": [1, 2, 3], "ruolo": "difensore"}},
    )
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["dati"]["giocatore"] == "p2"
    assert body["dati"]["dadi"] == [1, 2, 3]
    # Altri campi invariati
    assert body["fonte"] == "dado_ble"


@pytest.mark.asyncio
async def test_aggiorna_evento_grezzo_ts(client_test: AsyncClient) -> None:
    """Aggiornamento del timestamp (correzione drift CV)."""
    pid = await _crea_partita_e_get_id(client_test)
    creazione = await client_test.post(
        f"/api/partite/{pid}/eventi-grezzi",
        json=_evento_grezzo_dadi(),
    )
    eid = creazione.json()["id"]

    nuovo_ts = "2026-05-07T22:00:00+00:00"
    risposta = await client_test.patch(
        f"/api/partite/{pid}/eventi-grezzi/{eid}",
        json={"ts_evento": nuovo_ts},
    )
    assert risposta.status_code == 200
    assert risposta.json()["ts_evento"].startswith("2026-05-07T22:00")


@pytest.mark.asyncio
async def test_aggiorna_evento_grezzo_inesistente(client_test: AsyncClient) -> None:
    pid = await _crea_partita_e_get_id(client_test)
    risposta = await client_test.patch(
        f"/api/partite/{pid}/eventi-grezzi/non-esiste",
        json={"dati": {"x": 1}},
    )
    assert risposta.status_code == 404


# === POST batch eventi validati ===


@pytest.mark.asyncio
async def test_crea_eventi_validati_batch(client_test: AsyncClient) -> None:
    """Inserimento batch atomico di N eventi validati."""
    pid = await _crea_partita_e_get_id(client_test)
    base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)

    eventi = [
        {
            "ts_evento": (base + timedelta(seconds=i)).isoformat(),
            "tipo": "armate_piazzate",
            "dati": {"giocatore_id": "p1", "territorio": "alaska", "n": i + 1},
        }
        for i in range(5)
    ]

    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-validati/batch",
        json={"eventi": eventi},
    )
    assert risposta.status_code == 201
    body = risposta.json()
    assert len(body) == 5

    # Lista dovrebbe ora avere tutti e 5
    lista = await client_test.get(f"/api/partite/{pid}/eventi-validati")
    assert len(lista.json()) == 5


@pytest.mark.asyncio
async def test_batch_validati_partita_inesistente(client_test: AsyncClient) -> None:
    risposta = await client_test.post(
        "/api/partite/non-esiste/eventi-validati/batch",
        json={
            "eventi": [
                {
                    "ts_evento": datetime(2026, 5, 7, 21, 0, tzinfo=UTC).isoformat(),
                    "tipo": "armate_piazzate",
                    "dati": {"n": 1},
                }
            ]
        },
    )
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_batch_validati_grezzo_referenziato_inesistente(
    client_test: AsyncClient,
) -> None:
    """Se un evento_grezzo_id non esiste, l'intero batch fallisce."""
    pid = await _crea_partita_e_get_id(client_test)
    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-validati/batch",
        json={
            "eventi": [
                {
                    "ts_evento": datetime(2026, 5, 7, 21, 0, tzinfo=UTC).isoformat(),
                    "tipo": "armate_piazzate",
                    "dati": {"n": 1},
                    "evento_grezzo_id": "id-inesistente",
                }
            ]
        },
    )
    assert risposta.status_code == 400
    # Nessun evento creato (rollback)
    lista = await client_test.get(f"/api/partite/{pid}/eventi-validati")
    assert lista.json() == []


@pytest.mark.asyncio
async def test_batch_validati_marca_grezzi_referenziati(
    client_test: AsyncClient,
) -> None:
    """Promozione batch: tutti i grezzi referenziati sono marcati validato=True."""
    pid = await _crea_partita_e_get_id(client_test)

    # Creo 3 grezzi
    grezzi_ids = []
    for i in range(3):
        r = await client_test.post(
            f"/api/partite/{pid}/eventi-grezzi",
            json=_evento_grezzo_dadi(secondi_offset=i),
        )
        grezzi_ids.append(r.json()["id"])

    # Promuovo tutti in batch
    base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi_validati = [
        {
            "ts_evento": (base + timedelta(seconds=i)).isoformat(),
            "tipo": "dadi_lanciati",
            "dati": {"dadi": [4, 5, 6]},
            "evento_grezzo_id": gid,
        }
        for i, gid in enumerate(grezzi_ids)
    ]
    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-validati/batch",
        json={"eventi": eventi_validati},
    )
    assert risposta.status_code == 201

    # Tutti i grezzi devono essere validato=True
    grezzi = (await client_test.get(f"/api/partite/{pid}/eventi-grezzi")).json()
    assert all(g["validato"] for g in grezzi)


@pytest.mark.asyncio
async def test_batch_validati_vuoto_rifiutato(client_test: AsyncClient) -> None:
    """Batch con 0 eventi → 422 (min_length=1)."""
    pid = await _crea_partita_e_get_id(client_test)
    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-validati/batch",
        json={"eventi": []},
    )
    assert risposta.status_code == 422
