"""
Test del servizio e dell'endpoint di aggregazione eventi BLE → proposte.

Coperti:
- Cluster temporale corretto (gap < soglia → stesso cluster).
- Cluster temporale separato (gap > soglia → cluster distinti).
- Configurazioni canoniche (3 att + N dif → confidenza 1.0).
- Configurazioni sospette (solo att, troppi dadi).
- Eventi BLE già validati esclusi.
- Eventi non-BLE esclusi.
- Eventi con dati malformati gestiti senza crash.
- Endpoint: 404 per partita inesistente, 200 con risultato per partita valida.
- Soglia gap configurabile via query param.
"""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import EventoGrezzo, FonteEvento, TipoEvento
from app.servizi.aggregazione_dadi_servizio import ServizioAggregazioneDadi
from tests.conftest import crea_dati_partita_minima

# === Helper costruzione eventi ===


def _evento_ble(
    partita_id: str,
    secondi_offset: float,
    ruolo: str,
    slot: int,
    valore: int,
    *,
    base_ts: datetime = datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
    validato: bool = False,
) -> EventoGrezzo:
    return EventoGrezzo(
        partita_id=partita_id,
        ts_evento=base_ts + timedelta(seconds=secondi_offset),
        tipo=TipoEvento.DADI_LANCIATI,
        fonte=FonteEvento.DADO_BLE,
        confidenza=1.0,
        dati={
            "ble_id": f"ble-{slot}",
            "ruolo": ruolo,
            "slot": slot,
            "valore": valore,
        },
        validato=validato,
    )


async def _crea_partita_e_get_id(client: AsyncClient) -> str:
    risposta = await client.post(
        "/api/partite",
        json=crea_dati_partita_minima().model_dump(mode="json"),
    )
    assert risposta.status_code == 201
    return str(risposta.json()["id"])


async def _crea_partita_diretta(sessione: AsyncSession) -> str:
    """Crea una partita direttamente sul DB e ritorna l'id."""
    from app.modelli import Partita, StatoReview

    p = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione.add(p)
    await sessione.flush()
    return p.id


# === Test del servizio puro (senza HTTP) ===


@pytest.mark.asyncio
async def test_servizio_cluster_singolo_3_att_3_dif(sessione_test: AsyncSession) -> None:
    """6 dadi entro 1 secondo → 1 proposta con 3+3 dadi e confidenza 1.0."""
    pid = await _crea_partita_diretta(sessione_test)
    base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    # 3 dadi attaccante + 3 dadi difensore tutti entro 1s
    eventi = [
        _evento_ble(pid, 0.0, "attaccante", 1, 6, base_ts=base),
        _evento_ble(pid, 0.2, "attaccante", 2, 5, base_ts=base),
        _evento_ble(pid, 0.4, "attaccante", 3, 4, base_ts=base),
        _evento_ble(pid, 0.6, "difensore", 1, 3, base_ts=base),
        _evento_ble(pid, 0.8, "difensore", 2, 2, base_ts=base),
        _evento_ble(pid, 1.0, "difensore", 3, 1, base_ts=base),
    ]
    sessione_test.add_all(eventi)
    await sessione_test.commit()

    servizio = ServizioAggregazioneDadi()
    risultato = await servizio.proponi_aggregazioni(sessione_test, pid)

    assert risultato.n_eventi_grezzi_analizzati == 6
    assert risultato.n_proposte == 1
    p = risultato.proposte[0]
    assert p.dadi_attaccante == [6, 5, 4]
    assert p.dadi_difensore == [3, 2, 1]
    assert p.confidenza == 1.0
    assert p.note == []
    assert len(p.eventi_grezzi_id) == 6


@pytest.mark.asyncio
async def test_servizio_due_cluster_separati_da_gap_lungo(
    sessione_test: AsyncSession,
) -> None:
    """Due attacchi distanti 10s → 2 proposte separate."""
    pid = await _crea_partita_diretta(sessione_test)
    base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = [
        # Cluster 1 a t=0
        _evento_ble(pid, 0.0, "attaccante", 1, 6, base_ts=base),
        _evento_ble(pid, 0.5, "difensore", 1, 1, base_ts=base),
        # Cluster 2 a t=10 (gap = 9.5s, > 3s default)
        _evento_ble(pid, 10.0, "attaccante", 1, 4, base_ts=base),
        _evento_ble(pid, 10.5, "difensore", 1, 2, base_ts=base),
    ]
    sessione_test.add_all(eventi)
    await sessione_test.commit()

    servizio = ServizioAggregazioneDadi()
    risultato = await servizio.proponi_aggregazioni(sessione_test, pid)

    assert risultato.n_proposte == 2
    p1, p2 = risultato.proposte
    assert p1.dadi_attaccante == [6]
    assert p1.dadi_difensore == [1]
    assert p2.dadi_attaccante == [4]
    assert p2.dadi_difensore == [2]


@pytest.mark.asyncio
async def test_servizio_solo_dadi_attaccante_confidenza_dimezzata(
    sessione_test: AsyncSession,
) -> None:
    """Cluster con solo dadi attaccante → confidenza 0.5 + nota."""
    pid = await _crea_partita_diretta(sessione_test)
    base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = [
        _evento_ble(pid, 0.0, "attaccante", 1, 6, base_ts=base),
        _evento_ble(pid, 0.3, "attaccante", 2, 5, base_ts=base),
    ]
    sessione_test.add_all(eventi)
    await sessione_test.commit()

    servizio = ServizioAggregazioneDadi()
    risultato = await servizio.proponi_aggregazioni(sessione_test, pid)

    assert risultato.n_proposte == 1
    p = risultato.proposte[0]
    assert p.dadi_attaccante == [6, 5]
    assert p.dadi_difensore == []
    assert p.confidenza == 0.5
    assert any("Nessun dado difensore" in n for n in p.note)


@pytest.mark.asyncio
async def test_servizio_troppi_dadi_attaccante_confidenza_bassa(
    sessione_test: AsyncSession,
) -> None:
    """4 dadi attaccante + 1 difensore in cluster → confidenza 0.3 + nota."""
    pid = await _crea_partita_diretta(sessione_test)
    base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = [
        _evento_ble(pid, 0.0, "attaccante", 1, 6, base_ts=base),
        _evento_ble(pid, 0.2, "attaccante", 2, 5, base_ts=base),
        _evento_ble(pid, 0.4, "attaccante", 3, 4, base_ts=base),
        _evento_ble(pid, 0.6, "attaccante", 1, 3, base_ts=base),  # 4° dado
        _evento_ble(pid, 0.8, "difensore", 1, 2, base_ts=base),
    ]
    sessione_test.add_all(eventi)
    await sessione_test.commit()

    servizio = ServizioAggregazioneDadi()
    risultato = await servizio.proponi_aggregazioni(sessione_test, pid)

    assert risultato.n_proposte == 1
    p = risultato.proposte[0]
    assert len(p.dadi_attaccante) == 4
    assert p.confidenza == 0.3
    assert any("Troppi dadi attaccante" in n for n in p.note)


@pytest.mark.asyncio
async def test_servizio_eventi_validati_esclusi(sessione_test: AsyncSession) -> None:
    """Eventi grezzi con validato=True non vengono inclusi nelle proposte."""
    pid = await _crea_partita_diretta(sessione_test)
    base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = [
        _evento_ble(pid, 0.0, "attaccante", 1, 6, base_ts=base, validato=True),
        _evento_ble(pid, 0.5, "difensore", 1, 1, base_ts=base),
    ]
    sessione_test.add_all(eventi)
    await sessione_test.commit()

    servizio = ServizioAggregazioneDadi()
    risultato = await servizio.proponi_aggregazioni(sessione_test, pid)

    assert risultato.n_eventi_grezzi_analizzati == 1
    assert risultato.n_proposte == 1
    p = risultato.proposte[0]
    assert p.dadi_attaccante == []
    assert p.dadi_difensore == [1]


@pytest.mark.asyncio
async def test_servizio_dati_malformati_skippati_con_nota(
    sessione_test: AsyncSession,
) -> None:
    """Eventi BLE con dati incompleti vengono saltati senza crashare."""
    pid = await _crea_partita_diretta(sessione_test)
    base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    # Un evento valido + uno con campo `valore` mancante + uno con valore fuori range
    valido = _evento_ble(pid, 0.0, "attaccante", 1, 6, base_ts=base)
    malformato = EventoGrezzo(
        partita_id=pid,
        ts_evento=base + timedelta(seconds=0.3),
        tipo=TipoEvento.DADI_LANCIATI,
        fonte=FonteEvento.DADO_BLE,
        confidenza=1.0,
        dati={"ble_id": "x", "ruolo": "attaccante", "slot": 2},  # niente "valore"
        validato=False,
    )
    fuori_range = EventoGrezzo(
        partita_id=pid,
        ts_evento=base + timedelta(seconds=0.6),
        tipo=TipoEvento.DADI_LANCIATI,
        fonte=FonteEvento.DADO_BLE,
        confidenza=1.0,
        dati={"ble_id": "y", "ruolo": "difensore", "slot": 1, "valore": 99},
        validato=False,
    )
    sessione_test.add_all([valido, malformato, fuori_range])
    await sessione_test.commit()

    servizio = ServizioAggregazioneDadi()
    risultato = await servizio.proponi_aggregazioni(sessione_test, pid)

    assert risultato.n_proposte == 1
    p = risultato.proposte[0]
    # Solo il valido è confluito nei dadi
    assert p.dadi_attaccante == [6]
    assert p.dadi_difensore == []
    # Le note documentano gli scarti
    assert len(p.note) >= 2


@pytest.mark.asyncio
async def test_servizio_partita_senza_eventi(sessione_test: AsyncSession) -> None:
    """Partita senza eventi BLE → risultato vuoto, no crash."""
    pid = await _crea_partita_diretta(sessione_test)
    servizio = ServizioAggregazioneDadi()
    risultato = await servizio.proponi_aggregazioni(sessione_test, pid)
    assert risultato.n_eventi_grezzi_analizzati == 0
    assert risultato.n_proposte == 0


@pytest.mark.asyncio
async def test_servizio_soglia_gap_personalizzata() -> None:
    """Soglia <=0 deve sollevare ValueError."""
    import pytest as _pytest

    with _pytest.raises(ValueError):
        ServizioAggregazioneDadi(soglia_gap_secondi=0)
    with _pytest.raises(ValueError):
        ServizioAggregazioneDadi(soglia_gap_secondi=-1)


# === Test endpoint HTTP ===


@pytest.mark.asyncio
async def test_endpoint_partita_inesistente(client_test: AsyncClient) -> None:
    risposta = await client_test.post(
        "/api/partite/non-esiste/proponi-aggregazioni-dadi"
    )
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_endpoint_partita_vuota_ritorna_zero_proposte(
    client_test: AsyncClient,
) -> None:
    pid = await _crea_partita_e_get_id(client_test)
    risposta = await client_test.post(
        f"/api/partite/{pid}/proponi-aggregazioni-dadi"
    )
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["n_eventi_grezzi_analizzati"] == 0
    assert body["n_proposte"] == 0
    assert body["proposte"] == []


@pytest.mark.asyncio
async def test_endpoint_soglia_gap_invalida(client_test: AsyncClient) -> None:
    """Soglia gap fuori range → 422."""
    pid = await _crea_partita_e_get_id(client_test)
    risposta = await client_test.post(
        f"/api/partite/{pid}/proponi-aggregazioni-dadi",
        params={"soglia_gap_secondi": 0},
    )
    assert risposta.status_code == 422
    risposta = await client_test.post(
        f"/api/partite/{pid}/proponi-aggregazioni-dadi",
        params={"soglia_gap_secondi": 100},
    )
    assert risposta.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_soglia_gap_stretta_separa_cluster(
    client_test: AsyncClient,
    sessione_test: AsyncSession,
) -> None:
    """
    Con soglia 0.3s, due dadi distanziati 0.5s appartengono a cluster
    diversi. Con soglia default (3s) sono nello stesso cluster.
    """
    pid = await _crea_partita_e_get_id(client_test)
    base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    sessione_test.add_all(
        [
            _evento_ble(pid, 0.0, "attaccante", 1, 6, base_ts=base),
            _evento_ble(pid, 0.5, "difensore", 1, 1, base_ts=base),
        ]
    )
    await sessione_test.commit()

    # Default → 1 cluster
    risposta = await client_test.post(
        f"/api/partite/{pid}/proponi-aggregazioni-dadi"
    )
    assert risposta.status_code == 200
    assert risposta.json()["n_proposte"] == 1

    # Soglia stretta → 2 cluster
    risposta = await client_test.post(
        f"/api/partite/{pid}/proponi-aggregazioni-dadi",
        params={"soglia_gap_secondi": 0.3},
    )
    assert risposta.status_code == 200
    assert risposta.json()["n_proposte"] == 2


# === Test endpoint accetta-aggregazione-dadi ===


async def _crea_partita_con_giocatori(
    sessione: AsyncSession,
) -> tuple[str, str]:
    """Partita con 2 giocatori; ritorna (partita_id, giocatore_rosso_id)."""
    from app.modelli import GiocatorePartita, Partita, StatoReview

    p = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione.add(p)
    await sessione.flush()

    rosso = GiocatorePartita(
        partita_id=p.id, nome="Edo", colore="rosso", ordine_seduta=1
    )
    blu = GiocatorePartita(
        partita_id=p.id, nome="Marco", colore="blu", ordine_seduta=2
    )
    sessione.add_all([rosso, blu])
    await sessione.flush()
    return p.id, rosso.id


@pytest.mark.asyncio
async def test_accetta_proposta_caso_felice(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    """3 dadi att + 2 dif → accetta → EventoValidato + grezzi marcati."""
    from app.modelli import EventoGrezzo, EventoValidato

    pid, rosso_id = await _crea_partita_con_giocatori(sessione_test)
    eventi = [
        _evento_ble(pid, 0.0, "attaccante", 1, 6),
        _evento_ble(pid, 0.3, "attaccante", 2, 4),
        _evento_ble(pid, 0.6, "attaccante", 3, 2),
        _evento_ble(pid, 1.0, "difensore", 1, 5),
        _evento_ble(pid, 1.3, "difensore", 2, 3),
    ]
    sessione_test.add_all(eventi)
    await sessione_test.commit()

    risposta = await client_test.post(
        f"/api/partite/{pid}/accetta-aggregazione-dadi",
        json={
            "eventi_grezzi_id": [e.id for e in eventi],
            "giocatore_id": rosso_id,
            "da": "kamchatka",
            "a": "alaska",
            "dadi_attaccante": [6, 4, 2],
            "dadi_difensore": [5, 3],
            "validato_da": "edo@iphone",
        },
    )
    assert risposta.status_code == 201, risposta.text
    body = risposta.json()
    assert body["tipo"] == "attacco_risolto"
    assert body["validato_da"] == "edo@iphone"
    assert body["dati"]["giocatore_id"] == rosso_id
    assert body["dati"]["da"] == "kamchatka"
    assert body["dati"]["a"] == "alaska"
    assert body["dati"]["dadi_attaccante"] == [6, 4, 2]
    assert body["dati"]["dadi_difensore"] == [5, 3]

    # Tutti gli eventi grezzi sono ora marcati validato=True
    sessione_test.expire_all()
    grezzi = await sessione_test.execute(
        select(EventoGrezzo).where(EventoGrezzo.partita_id == pid)
    )
    for e in grezzi.scalars():
        assert e.validato is True

    # Esiste 1 EventoValidato
    validati = await sessione_test.execute(
        select(EventoValidato).where(EventoValidato.partita_id == pid)
    )
    rows = list(validati.scalars())
    assert len(rows) == 1
    # Legato al primo evento grezzo del cluster (rappresentante)
    assert rows[0].evento_grezzo_id == eventi[0].id


@pytest.mark.asyncio
async def test_accetta_proposta_dopo_proponi_non_riappare(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    """Eventi grezzi accettati spariscono dalle proposte successive."""
    pid, rosso_id = await _crea_partita_con_giocatori(sessione_test)
    eventi = [
        _evento_ble(pid, 0.0, "attaccante", 1, 6),
        _evento_ble(pid, 0.5, "difensore", 1, 4),
    ]
    sessione_test.add_all(eventi)
    await sessione_test.commit()

    # Prima: ho 1 proposta
    r1 = await client_test.post(
        f"/api/partite/{pid}/proponi-aggregazioni-dadi"
    )
    assert r1.json()["n_proposte"] == 1

    # Accetto
    r2 = await client_test.post(
        f"/api/partite/{pid}/accetta-aggregazione-dadi",
        json={
            "eventi_grezzi_id": [e.id for e in eventi],
            "giocatore_id": rosso_id,
            "da": "kamchatka",
            "a": "alaska",
            "dadi_attaccante": [6],
            "dadi_difensore": [4],
        },
    )
    assert r2.status_code == 201

    # Dopo: 0 proposte
    r3 = await client_test.post(
        f"/api/partite/{pid}/proponi-aggregazioni-dadi"
    )
    assert r3.json()["n_proposte"] == 0
    assert r3.json()["n_eventi_grezzi_analizzati"] == 0


@pytest.mark.asyncio
async def test_accetta_partita_inesistente_404(
    client_test: AsyncClient,
) -> None:
    risposta = await client_test.post(
        "/api/partite/non-esiste/accetta-aggregazione-dadi",
        json={
            "eventi_grezzi_id": ["x"],
            "giocatore_id": "y",
            "da": "kamchatka",
            "a": "alaska",
            "dadi_attaccante": [6],
            "dadi_difensore": [4],
        },
    )
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_accetta_giocatore_non_appartiene_400(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    pid, _ = await _crea_partita_con_giocatori(sessione_test)
    eventi = [
        _evento_ble(pid, 0.0, "attaccante", 1, 6),
        _evento_ble(pid, 0.5, "difensore", 1, 4),
    ]
    sessione_test.add_all(eventi)
    await sessione_test.commit()

    risposta = await client_test.post(
        f"/api/partite/{pid}/accetta-aggregazione-dadi",
        json={
            "eventi_grezzi_id": [e.id for e in eventi],
            "giocatore_id": "estraneo-id",
            "da": "kamchatka",
            "a": "alaska",
            "dadi_attaccante": [6],
            "dadi_difensore": [4],
        },
    )
    assert risposta.status_code == 400
    assert "non appartiene" in risposta.json()["detail"].lower()


@pytest.mark.asyncio
async def test_accetta_evento_inesistente_404(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    pid, rosso_id = await _crea_partita_con_giocatori(sessione_test)
    await sessione_test.commit()

    risposta = await client_test.post(
        f"/api/partite/{pid}/accetta-aggregazione-dadi",
        json={
            "eventi_grezzi_id": ["evento-inventato-1", "evento-inventato-2"],
            "giocatore_id": rosso_id,
            "da": "kamchatka",
            "a": "alaska",
            "dadi_attaccante": [6],
            "dadi_difensore": [4],
        },
    )
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_accetta_evento_gia_validato_400(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    pid, rosso_id = await _crea_partita_con_giocatori(sessione_test)
    eventi = [
        _evento_ble(pid, 0.0, "attaccante", 1, 6, validato=True),  # già!
        _evento_ble(pid, 0.5, "difensore", 1, 4),
    ]
    sessione_test.add_all(eventi)
    await sessione_test.commit()

    risposta = await client_test.post(
        f"/api/partite/{pid}/accetta-aggregazione-dadi",
        json={
            "eventi_grezzi_id": [e.id for e in eventi],
            "giocatore_id": rosso_id,
            "da": "kamchatka",
            "a": "alaska",
            "dadi_attaccante": [6],
            "dadi_difensore": [4],
        },
    )
    assert risposta.status_code == 400
    assert "validato" in risposta.json()["detail"].lower()


@pytest.mark.asyncio
async def test_accetta_evento_di_altra_partita_400(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    """Eventi appartenenti a un'altra partita devono essere rifiutati."""
    pid_a, rosso_id = await _crea_partita_con_giocatori(sessione_test)
    pid_b = await _crea_partita_diretta(sessione_test)
    # Evento sulla partita B
    evento_b = _evento_ble(pid_b, 0.0, "attaccante", 1, 6)
    sessione_test.add(evento_b)
    await sessione_test.commit()

    risposta = await client_test.post(
        f"/api/partite/{pid_a}/accetta-aggregazione-dadi",
        json={
            "eventi_grezzi_id": [evento_b.id],
            "giocatore_id": rosso_id,
            "da": "kamchatka",
            "a": "alaska",
            "dadi_attaccante": [6],
            "dadi_difensore": [4],
        },
    )
    assert risposta.status_code == 400


@pytest.mark.asyncio
async def test_accetta_dadi_modificati_dall_utente(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    """L'utente può modificare i valori dei dadi rispetto alla proposta."""
    pid, rosso_id = await _crea_partita_con_giocatori(sessione_test)
    eventi = [
        _evento_ble(pid, 0.0, "attaccante", 1, 1),  # BLE diceva 1
        _evento_ble(pid, 0.5, "difensore", 1, 6),
    ]
    sessione_test.add_all(eventi)
    await sessione_test.commit()

    # Utente corregge: ha visto un 6, non un 1
    risposta = await client_test.post(
        f"/api/partite/{pid}/accetta-aggregazione-dadi",
        json={
            "eventi_grezzi_id": [e.id for e in eventi],
            "giocatore_id": rosso_id,
            "da": "kamchatka",
            "a": "alaska",
            "dadi_attaccante": [6],  # corretto a mano
            "dadi_difensore": [6],
        },
    )
    assert risposta.status_code == 201
    assert risposta.json()["dati"]["dadi_attaccante"] == [6]
