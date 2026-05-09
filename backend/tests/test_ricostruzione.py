"""
Test della ricostruzione partita via `risiko_engine`.

Strategia:
- Helper `crea_partita_e_setup` crea una partita 2-giocatori e gli eventi
  validati di setup completo (42 territori distribuiti round-robin,
  obiettivi assegnati, partita_inizio).
- Test progressivi: dal caso più semplice (no eventi) al più complesso
  (turno completo con attacco + spostamento + fine turno).
- Verifiche su `n_eventi_applicati`, `errori`, e contenuto di `stato_finale`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from risiko_engine.mappa import TERRITORI
from tests.conftest import crea_dati_partita_minima

# === Helper di setup ===


def _territori_distribuiti() -> tuple[list[str], list[str]]:
    """Round-robin: territori pari → P1, dispari → P2."""
    sorted_t = sorted(TERRITORI)
    return sorted_t[::2], sorted_t[1::2]


# Coppia adiacente p1→p2 utile per test attacco
TERRITORIO_P1_ATTACCO = "afghanistan"
TERRITORIO_P2_DIFESA = "ucraina"
# Coppia adiacente p1→p1 utile per test spostamento
TERRITORIO_P1_SOSTA_DA = "afghanistan"
TERRITORIO_P1_SOSTA_A = "cina"


async def _crea_partita(client: AsyncClient) -> tuple[str, str, str]:
    """
    Crea una partita 2-giocatori e ritorna (partita_id, p1_id, p2_id).
    """
    risposta = await client.post(
        "/api/partite",
        json=crea_dati_partita_minima().model_dump(mode="json"),
    )
    assert risposta.status_code == 201
    partita = risposta.json()
    p1_id = partita["giocatori"][0]["id"]
    p2_id = partita["giocatori"][1]["id"]
    return partita["id"], p1_id, p2_id


def _eventi_setup_completo(
    p1_id: str, p2_id: str, ts_base: datetime, *, armate_per_territorio: int = 2
) -> list[dict]:
    """
    Costruisce gli eventi di setup di una partita 2 giocatori:
    - 42 eventi TERRITORIO_ASSEGNATO_INIZIO (distribuzione round-robin)
    - 2 eventi OBIETTIVO_ASSEGNATO (entrambi obiettivo 1, neutrale)
    - 1 evento PARTITA_INIZIO

    Ritorna una lista di dict pronti per `EventoValidatoCreazione`.
    """
    p1_terr, p2_terr = _territori_distribuiti()
    eventi: list[dict] = []
    offset_sec = 0

    for terr in p1_terr:
        eventi.append(
            {
                "ts_evento": (ts_base + timedelta(seconds=offset_sec)).isoformat(),
                "tipo": "territorio_assegnato_inizio",
                "dati": {
                    "territorio": terr,
                    "giocatore_id": p1_id,
                    "n_armate": armate_per_territorio,
                },
            }
        )
        offset_sec += 1

    for terr in p2_terr:
        eventi.append(
            {
                "ts_evento": (ts_base + timedelta(seconds=offset_sec)).isoformat(),
                "tipo": "territorio_assegnato_inizio",
                "dati": {
                    "territorio": terr,
                    "giocatore_id": p2_id,
                    "n_armate": armate_per_territorio,
                },
            }
        )
        offset_sec += 1

    # Obiettivi (uso id=1 per entrambi, è abbastanza neutrale)
    for pid in (p1_id, p2_id):
        eventi.append(
            {
                "ts_evento": (ts_base + timedelta(seconds=offset_sec)).isoformat(),
                "tipo": "obiettivo_assegnato",
                "dati": {"giocatore_id": pid, "obiettivo_id": 1},
            }
        )
        offset_sec += 1

    eventi.append(
        {
            "ts_evento": (ts_base + timedelta(seconds=offset_sec)).isoformat(),
            "tipo": "partita_inizio",
            "dati": {"primo_giocatore_id": p1_id},
        }
    )

    return eventi


async def _carica_eventi(
    client: AsyncClient,
    partita_id: str,
    eventi: list[dict],
) -> None:
    """Crea gli eventi validati nella partita uno per uno."""
    for e in eventi:
        risposta = await client.post(
            f"/api/partite/{partita_id}/eventi-validati",
            json=e,
        )
        assert risposta.status_code == 201, f"Fallito {e['tipo']}: {risposta.text}"


# === Test base: ricostruzione di partita "vuota" ===


@pytest.mark.asyncio
async def test_ricostruisci_partita_senza_eventi(client_test: AsyncClient) -> None:
    """Partita senza eventi: stato_finale=None, n_eventi=0."""
    pid, _p1, _p2 = await _crea_partita(client_test)

    risposta = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["partita_id"] == pid
    assert body["n_eventi_totali"] == 0
    assert body["n_eventi_applicati"] == 0
    assert body["n_errori"] == 0
    assert body["stato_finale"] is None
    # successo=False perché non c'è stato applicato nulla
    assert body["successo"] is False


@pytest.mark.asyncio
async def test_ricostruisci_partita_inesistente(client_test: AsyncClient) -> None:
    risposta = await client_test.post("/api/partite/non-esiste/ricostruisci")
    assert risposta.status_code == 404


# === Test setup completo ===


@pytest.mark.asyncio
async def test_ricostruisci_setup_completo_inizia_partita(
    client_test: AsyncClient,
) -> None:
    """
    Setup di 42 territori + 2 obiettivi + partita_inizio:
    motore arriva in fase RINFORZO con armate da piazzare per P1.
    """
    pid, p1, p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = _eventi_setup_completo(p1, p2, ts_base)
    await _carica_eventi(client_test, pid, eventi)

    risposta = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["n_eventi_totali"] == 45  # 42 + 2 + 1
    assert body["n_eventi_applicati"] == 45
    assert body["n_errori"] == 0
    assert body["successo"] is True

    stato = body["stato_finale"]
    assert stato is not None
    assert stato["fase_corrente"] == "rinforzo"
    assert stato["giocatore_attivo_id"] == p1
    assert stato["turno"] == 1
    assert stato["vincitore_id"] is None
    # armate_da_piazzare > 0 in RINFORZO
    assert stato["armate_da_piazzare"] > 0
    # 21 territori controllati da p1, 21 da p2
    territori_p1 = [
        t for t in stato["territori"].values() if t["controllore_id"] == p1
    ]
    territori_p2 = [
        t for t in stato["territori"].values() if t["controllore_id"] == p2
    ]
    assert len(territori_p1) == 21
    assert len(territori_p2) == 21


# === Test piazzamento armate ===


@pytest.mark.asyncio
async def test_ricostruisci_con_piazzamento_armate(
    client_test: AsyncClient,
) -> None:
    """Dopo setup, P1 piazza N armate su un suo territorio."""
    pid, p1, p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = _eventi_setup_completo(p1, p2, ts_base)

    # Aggiungo evento ARMATE_PIAZZATE dopo setup
    eventi.append(
        {
            "ts_evento": (ts_base + timedelta(minutes=5)).isoformat(),
            "tipo": "armate_piazzate",
            "dati": {
                "giocatore_id": p1,
                "territorio": TERRITORIO_P1_ATTACCO,
                "n": 3,
            },
        }
    )
    await _carica_eventi(client_test, pid, eventi)

    risposta = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    body = risposta.json()
    assert body["successo"] is True
    assert body["n_eventi_applicati"] == 46

    stato = body["stato_finale"]
    armate_su_terr = stato["territori"][TERRITORIO_P1_ATTACCO]["armate"]
    # Iniziali (2) + piazzate (3) = 5
    assert armate_su_terr == 5


# === Test attacco con transizione implicita RINFORZO → ATTACCO ===


@pytest.mark.asyncio
async def test_ricostruisci_attacco_con_transizione_implicita(
    client_test: AsyncClient,
) -> None:
    """
    Sequenza: setup → piazza tutte le armate → attacca.
    L'attacco viene applicato nonostante non ci sia evento esplicito di
    `passa_a_attacco`: il dispatcher fa transizione implicita.
    """
    pid, p1, p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = _eventi_setup_completo(p1, p2, ts_base)

    # P1 ottiene rinforzi base. Per 21 territori il bonus è 21//3 = 7 armate
    # base + bonus continenti. Per semplicità, piazzo TUTTE quelle che ha
    # in un colpo solo (motore controlla che non superi armate_da_piazzare).
    # Strategia: piazzo 1 alla volta finché armate_da_piazzare = 0.

    # Ricostruisco prima per leggere armate_da_piazzare
    await _carica_eventi(client_test, pid, eventi)
    primo_check = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    armate_iniziali = primo_check.json()["stato_finale"]["armate_da_piazzare"]
    assert armate_iniziali > 0

    # Piazzo tutte le armate sul territorio attaccante (concentro forze)
    eventi.append(
        {
            "ts_evento": (ts_base + timedelta(minutes=5)).isoformat(),
            "tipo": "armate_piazzate",
            "dati": {
                "giocatore_id": p1,
                "territorio": TERRITORIO_P1_ATTACCO,
                "n": armate_iniziali,
            },
        }
    )
    # Attacco: 3 dadi per attaccante (vincenti), 1 dado per difensore (perdente)
    eventi.append(
        {
            "ts_evento": (ts_base + timedelta(minutes=10)).isoformat(),
            "tipo": "attacco_risolto",
            "dati": {
                "giocatore_id": p1,
                "da": TERRITORIO_P1_ATTACCO,
                "a": TERRITORIO_P2_DIFESA,
                "dadi_attaccante": [6, 6, 6],
                "dadi_difensore": [1],
            },
        }
    )
    # Carico solo i 2 nuovi eventi
    for e in eventi[-2:]:
        risposta = await client_test.post(
            f"/api/partite/{pid}/eventi-validati", json=e
        )
        assert risposta.status_code == 201, risposta.text

    risposta = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    body = risposta.json()
    assert body["successo"] is True, f"Errori: {body['errori']}"

    stato = body["stato_finale"]
    # Difensore con 2 armate, attaccante 3 dadi (sempre 6) vs difensore 1 dado (1)
    # → difensore perde 1, ne resta 1. Territorio NON conquistato.
    armate_difesa = stato["territori"][TERRITORIO_P2_DIFESA]["armate"]
    assert armate_difesa == 1
    assert stato["territori"][TERRITORIO_P2_DIFESA]["controllore_id"] == p2
    # Fase finale: ATTACCO (transizione implicita avvenuta)
    assert stato["fase_corrente"] == "attacco"


@pytest.mark.asyncio
async def test_ricostruisci_attacco_con_conquista(
    client_test: AsyncClient,
) -> None:
    """Attacco vittorioso: il difensore va a 0, territorio conquistato."""
    pid, p1, p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = _eventi_setup_completo(p1, p2, ts_base)

    await _carica_eventi(client_test, pid, eventi)
    primo_check = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    armate_iniziali = primo_check.json()["stato_finale"]["armate_da_piazzare"]

    # Piazzo tutto su attaccante
    nuovi_eventi = [
        {
            "ts_evento": (ts_base + timedelta(minutes=5)).isoformat(),
            "tipo": "armate_piazzate",
            "dati": {
                "giocatore_id": p1,
                "territorio": TERRITORIO_P1_ATTACCO,
                "n": armate_iniziali,
            },
        },
        # Primo attacco: difensore perde 1, ne resta 1
        {
            "ts_evento": (ts_base + timedelta(minutes=10)).isoformat(),
            "tipo": "attacco_risolto",
            "dati": {
                "giocatore_id": p1,
                "da": TERRITORIO_P1_ATTACCO,
                "a": TERRITORIO_P2_DIFESA,
                "dadi_attaccante": [6, 6, 6],
                "dadi_difensore": [1],
            },
        },
        # Secondo attacco: difensore va a 0, conquista
        {
            "ts_evento": (ts_base + timedelta(minutes=11)).isoformat(),
            "tipo": "attacco_risolto",
            "dati": {
                "giocatore_id": p1,
                "da": TERRITORIO_P1_ATTACCO,
                "a": TERRITORIO_P2_DIFESA,
                "dadi_attaccante": [6, 6, 6],
                "dadi_difensore": [1],
            },
        },
    ]
    for e in nuovi_eventi:
        risposta = await client_test.post(
            f"/api/partite/{pid}/eventi-validati", json=e
        )
        assert risposta.status_code == 201

    risposta = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    body = risposta.json()
    assert body["successo"] is True, f"Errori: {body['errori']}"

    stato = body["stato_finale"]
    # Territorio conquistato: ora di p1
    assert stato["territori"][TERRITORIO_P2_DIFESA]["controllore_id"] == p1
    # Movimento minimo: 3 armate (= dadi attaccante) trasferite
    assert stato["territori"][TERRITORIO_P2_DIFESA]["armate"] == 3
    assert TERRITORIO_P2_DIFESA in stato["territori_conquistati_nel_turno"]


# === Test errori durante ricostruzione ===


@pytest.mark.asyncio
async def test_evento_payload_invalido_segnalato(client_test: AsyncClient) -> None:
    """Payload con campi mancanti → errore registrato, ricostruzione prosegue."""
    pid, p1, _p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)

    # Inserisco solo l'evento "rotto"
    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-validati",
        json={
            "ts_evento": ts_base.isoformat(),
            "tipo": "armate_piazzate",
            "dati": {"giocatore_id": p1},  # manca territorio + n
        },
    )
    assert risposta.status_code == 201

    risposta = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    body = risposta.json()
    assert body["successo"] is False
    assert body["n_errori"] == 1
    assert body["n_eventi_applicati"] == 0
    err = body["errori"][0]
    assert err["classe_errore"] == "PayloadInvalidoError"


@pytest.mark.asyncio
async def test_azione_illegale_segnalata(client_test: AsyncClient) -> None:
    """
    Setup completo + tentativo di piazzare armate su territorio non posseduto.
    Il motore solleva AzioneIllegaleError.
    """
    pid, p1, p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = _eventi_setup_completo(p1, p2, ts_base)

    # P1 tenta di piazzare su un territorio di P2
    territorio_p2 = TERRITORIO_P2_DIFESA  # ucraina è di p2
    eventi.append(
        {
            "ts_evento": (ts_base + timedelta(minutes=5)).isoformat(),
            "tipo": "armate_piazzate",
            "dati": {
                "giocatore_id": p1,
                "territorio": territorio_p2,
                "n": 3,
            },
        }
    )
    await _carica_eventi(client_test, pid, eventi)

    risposta = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    body = risposta.json()
    assert body["successo"] is False
    assert body["n_errori"] == 1
    # 45 setup + 1 fallito = 45 applicati, 1 errore
    assert body["n_eventi_applicati"] == 45
    err = body["errori"][0]
    assert err["classe_errore"] == "AzioneIllegaleError"
    # Stato finale comunque presente (motore attivo prima dell'errore)
    assert body["stato_finale"] is not None


@pytest.mark.asyncio
async def test_tipo_evento_non_supportato(client_test: AsyncClient) -> None:
    """Eventi tipo CV_PESCA_RILEVATA non sono applicabili al motore."""
    pid, _p1, _p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)

    risposta = await client_test.post(
        f"/api/partite/{pid}/eventi-validati",
        json={
            "ts_evento": ts_base.isoformat(),
            "tipo": "cv_pesca_rilevata",
            "dati": {"foo": "bar"},
        },
    )
    assert risposta.status_code == 201

    risposta = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    body = risposta.json()
    assert body["n_errori"] == 1
    assert body["errori"][0]["classe_errore"] == "TipoEventoNonSupportatoError"


# === Test idempotenza ===


@pytest.mark.asyncio
async def test_ricostruzione_idempotente(client_test: AsyncClient) -> None:
    """Due ricostruzioni consecutive producono risultati equivalenti."""
    pid, p1, p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = _eventi_setup_completo(p1, p2, ts_base)
    await _carica_eventi(client_test, pid, eventi)

    r1 = (await client_test.post(f"/api/partite/{pid}/ricostruisci")).json()
    r2 = (await client_test.post(f"/api/partite/{pid}/ricostruisci")).json()

    # I dati stato dovrebbero coincidere (escludo data_ricostruzione che cambia)
    assert r1["n_eventi_totali"] == r2["n_eventi_totali"]
    assert r1["n_eventi_applicati"] == r2["n_eventi_applicati"]
    assert r1["successo"] == r2["successo"]
    assert r1["stato_finale"] == r2["stato_finale"]


# === Test endpoint stato-finale ===


@pytest.mark.asyncio
async def test_stato_finale_prima_di_ricostruire(
    client_test: AsyncClient,
) -> None:
    """Endpoint GET /stato-finale → 404 se ricostruzione mai eseguita."""
    pid, _p1, _p2 = await _crea_partita(client_test)
    risposta = await client_test.get(f"/api/partite/{pid}/stato-finale")
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_stato_finale_dopo_ricostruzione(client_test: AsyncClient) -> None:
    """Dopo ricostruzione, GET /stato-finale ritorna lo snapshot."""
    pid, p1, p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = _eventi_setup_completo(p1, p2, ts_base)
    await _carica_eventi(client_test, pid, eventi)

    await client_test.post(f"/api/partite/{pid}/ricostruisci")

    risposta = await client_test.get(f"/api/partite/{pid}/stato-finale")
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["partita_id"] == pid
    assert body["successo"] is True
    assert body["stato_finale"]["fase_corrente"] == "rinforzo"


@pytest.mark.asyncio
async def test_stato_finale_partita_inesistente(client_test: AsyncClient) -> None:
    risposta = await client_test.get("/api/partite/non-esiste/stato-finale")
    assert risposta.status_code == 404


# === Test eliminazione partita pulisce snapshot ===


@pytest.mark.asyncio
async def test_elimina_partita_pulisce_snapshot(client_test: AsyncClient) -> None:
    """Eliminando la partita, anche StatoPartitaRicostruito viene rimosso (CASCADE)."""
    pid, p1, p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = _eventi_setup_completo(p1, p2, ts_base)
    await _carica_eventi(client_test, pid, eventi)
    await client_test.post(f"/api/partite/{pid}/ricostruisci")

    # Snapshot esiste
    r = await client_test.get(f"/api/partite/{pid}/stato-finale")
    assert r.status_code == 200

    # Elimino partita
    r = await client_test.delete(f"/api/partite/{pid}")
    assert r.status_code == 204

    # Sia partita che snapshot non esistono più
    r = await client_test.get(f"/api/partite/{pid}/stato-finale")
    assert r.status_code == 404


# === Test scenario completo: turno completo con conquista + spostamento + fine turno ===


@pytest.mark.asyncio
async def test_ricostruisci_turno_completo(client_test: AsyncClient) -> None:
    """
    Scenario realistico: P1 fa un turno completo:
    rinforzo → attacco con conquista → spostamento → fine turno.
    Stato finale: il turno passa a P2.
    """
    pid, p1, p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = _eventi_setup_completo(p1, p2, ts_base)

    await _carica_eventi(client_test, pid, eventi)
    check = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    armate_iniziali = check.json()["stato_finale"]["armate_da_piazzare"]

    nuovi = [
        # Piazzo TUTTE le armate sull'attaccante
        {
            "ts_evento": (ts_base + timedelta(minutes=5)).isoformat(),
            "tipo": "armate_piazzate",
            "dati": {
                "giocatore_id": p1,
                "territorio": TERRITORIO_P1_ATTACCO,
                "n": armate_iniziali,
            },
        },
        # Conquisto in 2 attacchi
        {
            "ts_evento": (ts_base + timedelta(minutes=10)).isoformat(),
            "tipo": "attacco_risolto",
            "dati": {
                "giocatore_id": p1,
                "da": TERRITORIO_P1_ATTACCO,
                "a": TERRITORIO_P2_DIFESA,
                "dadi_attaccante": [6, 6, 6],
                "dadi_difensore": [1],
            },
        },
        {
            "ts_evento": (ts_base + timedelta(minutes=11)).isoformat(),
            "tipo": "attacco_risolto",
            "dati": {
                "giocatore_id": p1,
                "da": TERRITORIO_P1_ATTACCO,
                "a": TERRITORIO_P2_DIFESA,
                "dadi_attaccante": [6, 6, 6],
                "dadi_difensore": [1],
            },
        },
        # Spostamento finale (transizione implicita ATTACCO → SPOSTAMENTO)
        {
            "ts_evento": (ts_base + timedelta(minutes=15)).isoformat(),
            "tipo": "armate_spostate",
            "dati": {
                "giocatore_id": p1,
                "da": TERRITORIO_P1_SOSTA_DA,
                "a": TERRITORIO_P1_SOSTA_A,
                "n": 1,
            },
        },
        # Fine turno
        {
            "ts_evento": (ts_base + timedelta(minutes=20)).isoformat(),
            "tipo": "turno_finito",
            "dati": {"giocatore_id": p1},
        },
    ]
    for e in nuovi:
        await client_test.post(f"/api/partite/{pid}/eventi-validati", json=e)

    risposta = await client_test.post(f"/api/partite/{pid}/ricostruisci")
    body = risposta.json()
    assert body["successo"] is True, f"Errori: {body['errori']}"

    stato = body["stato_finale"]
    # Turno passato a P2 in RINFORZO
    assert stato["fase_corrente"] == "rinforzo"
    assert stato["giocatore_attivo_id"] == p2
    assert stato["turno"] == 2  # avanzato
    # P1 ha pescato una carta (per la conquista)
    assert stato["conteggio_mani"][p1] == 1
    # Spostamento conteggio: cina ha le 2 iniziali + 1 spostata
    assert stato["territori"][TERRITORIO_P1_SOSTA_A]["armate"] == 3


# === Test ricostruisci fino a evento N (snapshot intermedi) ===


@pytest.mark.asyncio
async def test_ricostruisci_fino_a_evento_snapshot_intermedio(
    sessione_test,
    client_test: AsyncClient,
) -> None:
    """
    Ricostruisci fino a un evento intermedio: stato motore subito DOPO
    quell'evento. Permette discrepanze evento-per-evento (non solo finale).
    """
    from sqlalchemy import select

    from app.modelli import EventoValidato
    from app.servizi.ricostruzione_servizio import ServizioRicostruzione

    pid, p1, p2 = await _crea_partita(client_test)
    ts_base = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    eventi = _eventi_setup_completo(p1, p2, ts_base)

    # Aggiungi evento di piazzamento dopo setup
    eventi.append({
        "ts_evento": (ts_base + timedelta(minutes=5)).isoformat(),
        "tipo": "armate_piazzate",
        "dati": {
            "giocatore_id": p1,
            "territorio": TERRITORIO_P1_ATTACCO,
            "n": 1,
        },
    })
    await _carica_eventi(client_test, pid, eventi)

    # Recupera ID dell'ultimo evento di setup (PARTITA_INIZIO, indice 44)
    ris = await sessione_test.execute(
        select(EventoValidato)
        .where(EventoValidato.partita_id == pid)
        .order_by(EventoValidato.ts_evento)
    )
    eventi_db = list(ris.scalars().all())
    assert len(eventi_db) == 46  # 42 + 2 + 1 + 1

    # Stato dopo PARTITA_INIZIO (indice 44, 45esimo): RINFORZO, no armate piazzate
    evento_partita_inizio_id = eventi_db[44].id
    snapshot_inizio = await ServizioRicostruzione.ricostruisci_fino_a_evento(
        sessione_test, pid, evento_partita_inizio_id,
    )
    assert snapshot_inizio is not None
    assert snapshot_inizio.fase_corrente == "rinforzo"
    armate_iniziali = snapshot_inizio.territori[TERRITORIO_P1_ATTACCO].armate

    # Stato dopo ARMATE_PIAZZATE (ultimo evento)
    evento_piazzate_id = eventi_db[45].id
    snapshot_dopo = await ServizioRicostruzione.ricostruisci_fino_a_evento(
        sessione_test, pid, evento_piazzate_id,
    )
    assert snapshot_dopo is not None
    armate_dopo = snapshot_dopo.territori[TERRITORIO_P1_ATTACCO].armate
    assert armate_dopo == armate_iniziali + 1


@pytest.mark.asyncio
async def test_ricostruisci_fino_a_evento_inesistente_solleva(
    sessione_test,
    client_test: AsyncClient,
) -> None:
    from app.servizi.ricostruzione_servizio import ServizioRicostruzione

    pid, _p1, _p2 = await _crea_partita(client_test)
    with pytest.raises(ValueError, match="non trovato"):
        await ServizioRicostruzione.ricostruisci_fino_a_evento(
            sessione_test, pid, "00000000-0000-0000-0000-000000000000",
        )
