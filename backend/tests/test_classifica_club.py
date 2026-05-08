"""
Test del servizio `calcola_classifica_club` e dell'endpoint
`GET /api/club/classifica`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import (
    EventoValidato,
    GiocatorePartita,
    Partita,
    StatoReview,
    TipoEvento,
)
from app.servizi.classifica_club_servizio import (
    _normalizza_nome,
    calcola_classifica_club,
)

# === Test helper di normalizzazione ===


class TestNormalizzaNome:
    def test_lowercase(self) -> None:
        assert _normalizza_nome("EDO") == "edo"

    def test_trim(self) -> None:
        assert _normalizza_nome("  Edo  ") == "edo"

    def test_combinato(self) -> None:
        assert _normalizza_nome("  EDOARDO  ") == "edoardo"

    def test_stringa_vuota(self) -> None:
        assert _normalizza_nome("") == ""

    def test_solo_whitespace(self) -> None:
        assert _normalizza_nome("   ") == ""


# === Test servizio ===


@pytest.mark.asyncio
async def test_classifica_db_vuoto(sessione_test: AsyncSession) -> None:
    """Senza partite la classifica è vuota, niente crash."""
    cls = await calcola_classifica_club(sessione_test)
    assert cls.n_partite_totali == 0
    assert cls.n_partite_con_eventi == 0
    assert cls.n_giocatori_distinti == 0
    assert cls.giocatori == []


@pytest.mark.asyncio
async def test_classifica_partita_senza_giocatori_skippata(
    sessione_test: AsyncSession,
) -> None:
    """Partita creata senza giocatori non contribuisce alla classifica."""
    p = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add(p)
    await sessione_test.commit()

    cls = await calcola_classifica_club(sessione_test)
    assert cls.n_partite_totali == 1
    assert cls.n_partite_con_eventi == 0
    assert cls.n_giocatori_distinti == 0


@pytest.mark.asyncio
async def test_classifica_aggrega_per_nome_normalizzato(
    sessione_test: AsyncSession,
) -> None:
    """Stesso giocatore in 2 partite (con case diverse) → 1 entry aggregata."""
    # Partita 1: "Edo" e "Marco"
    p1 = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add(p1)
    await sessione_test.flush()
    edo1 = GiocatorePartita(
        partita_id=p1.id, nome="Edo", colore="rosso", ordine_seduta=1
    )
    marco1 = GiocatorePartita(
        partita_id=p1.id, nome="Marco", colore="blu", ordine_seduta=2
    )
    sessione_test.add_all([edo1, marco1])
    await sessione_test.flush()
    sessione_test.add(
        EventoValidato(
            partita_id=p1.id,
            ts_evento=datetime(2026, 5, 7, 21, 5, tzinfo=UTC),
            tipo=TipoEvento.ATTACCO_RISOLTO,
            dati={
                "giocatore_id": edo1.id,
                "da": "kamchatka", "a": "alaska",
                "dadi_attaccante": [6, 4], "dadi_difensore": [3],
            },
            evento_grezzo_id=None,
            validato_da="test",
        )
    )

    # Partita 2: "EDO" (uppercase) e "Alice"
    p2 = Partita(
        data_inizio=datetime(2026, 5, 8, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add(p2)
    await sessione_test.flush()
    edo2 = GiocatorePartita(
        partita_id=p2.id, nome="EDO", colore="rosso", ordine_seduta=1
    )
    alice = GiocatorePartita(
        partita_id=p2.id, nome="Alice", colore="verde", ordine_seduta=2
    )
    sessione_test.add_all([edo2, alice])
    await sessione_test.flush()
    sessione_test.add(
        EventoValidato(
            partita_id=p2.id,
            ts_evento=datetime(2026, 5, 8, 21, 5, tzinfo=UTC),
            tipo=TipoEvento.ATTACCO_RISOLTO,
            dati={
                "giocatore_id": edo2.id,
                "da": "kamchatka", "a": "alaska",
                "dadi_attaccante": [6], "dadi_difensore": [3],
            },
            evento_grezzo_id=None,
            validato_da="test",
        )
    )

    await sessione_test.commit()

    cls = await calcola_classifica_club(sessione_test)
    assert cls.n_partite_totali == 2
    assert cls.n_partite_con_eventi == 2
    # Edo (con due case) deve aggregarsi a 1 entry
    nomi_norm = {g.nome_normalizzato for g in cls.giocatori}
    assert "edo" in nomi_norm
    assert "marco" in nomi_norm
    assert "alice" in nomi_norm
    assert cls.n_giocatori_distinti == 3

    edo_aggregato = next(
        g for g in cls.giocatori if g.nome_normalizzato == "edo"
    )
    assert edo_aggregato.n_partite == 2
    assert edo_aggregato.n_attacchi_totali == 2  # 1 per partita


@pytest.mark.asyncio
async def test_classifica_ordinamento_per_bilancio_armate(
    sessione_test: AsyncSession,
) -> None:
    """Il giocatore con bilancio armate maggiore appare per primo."""
    p = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add(p)
    await sessione_test.flush()
    rosso = GiocatorePartita(
        partita_id=p.id, nome="Vincente", colore="rosso", ordine_seduta=1
    )
    blu = GiocatorePartita(
        partita_id=p.id, nome="Perdente", colore="blu", ordine_seduta=2
    )
    sessione_test.add_all([rosso, blu])
    await sessione_test.flush()

    # Rosso attacca con dadi sempre buoni: domina
    sessione_test.add(
        EventoValidato(
            partita_id=p.id,
            ts_evento=datetime(2026, 5, 7, 21, 5, tzinfo=UTC),
            tipo=TipoEvento.ATTACCO_RISOLTO,
            dati={
                "giocatore_id": rosso.id,
                "da": "kamchatka", "a": "alaska",
                "dadi_attaccante": [6, 6, 6], "dadi_difensore": [1, 1],
            },
            evento_grezzo_id=None,
            validato_da="test",
        )
    )
    await sessione_test.commit()

    cls = await calcola_classifica_club(sessione_test)
    nomi_in_ordine = [g.nome_normalizzato for g in cls.giocatori]
    # Il primo è quello con bilancio armate più alto
    assert nomi_in_ordine[0] == "vincente"


@pytest.mark.asyncio
async def test_classifica_durata_aggregata(
    sessione_test: AsyncSession,
) -> None:
    """Durate sommate solo per partite con data_fine valida."""
    inizio = datetime(2026, 5, 7, 20, 0, tzinfo=UTC)

    # Partita 1: 1 ora
    p1 = Partita(
        data_inizio=inizio,
        data_fine=inizio + timedelta(hours=1),
        stato_review=StatoReview.GREZZA,
    )
    # Partita 2: 30 minuti
    p2 = Partita(
        data_inizio=inizio,
        data_fine=inizio + timedelta(minutes=30),
        stato_review=StatoReview.GREZZA,
    )
    # Partita 3: senza data_fine, non contribuisce
    p3 = Partita(
        data_inizio=inizio,
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add_all([p1, p2, p3])
    await sessione_test.flush()

    # Aggiungo giocatori (servono per non skippare le partite)
    for p in [p1, p2, p3]:
        sessione_test.add(
            GiocatorePartita(
                partita_id=p.id, nome="Tizio", colore="rosso", ordine_seduta=1
            )
        )
        sessione_test.add(
            GiocatorePartita(
                partita_id=p.id, nome="Caio", colore="blu", ordine_seduta=2
            )
        )

    await sessione_test.commit()

    cls = await calcola_classifica_club(sessione_test)
    # 1h + 30m = 5400 secondi
    assert cls.durata_totale_sec == 5400.0


# === Test endpoint ===


@pytest.mark.asyncio
async def test_endpoint_classifica_db_vuoto(client_test: AsyncClient) -> None:
    risposta = await client_test.get("/api/club/classifica")
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["n_partite_totali"] == 0
    assert body["giocatori"] == []


@pytest.mark.asyncio
async def test_endpoint_classifica_con_dati(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    """Smoke test end-to-end: crea una partita con eventi, chiama endpoint."""
    p = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add(p)
    await sessione_test.flush()
    rosso = GiocatorePartita(
        partita_id=p.id, nome="Edo", colore="rosso", ordine_seduta=1
    )
    blu = GiocatorePartita(
        partita_id=p.id, nome="Marco", colore="blu", ordine_seduta=2
    )
    sessione_test.add_all([rosso, blu])
    await sessione_test.flush()

    sessione_test.add(
        EventoValidato(
            partita_id=p.id,
            ts_evento=datetime(2026, 5, 7, 21, 5, tzinfo=UTC),
            tipo=TipoEvento.ATTACCO_RISOLTO,
            dati={
                "giocatore_id": rosso.id,
                "da": "kamchatka", "a": "alaska",
                "dadi_attaccante": [6, 4], "dadi_difensore": [3],
            },
            evento_grezzo_id=None,
            validato_da="test",
        )
    )
    await sessione_test.commit()

    risposta = await client_test.get("/api/club/classifica")
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["n_partite_totali"] == 1
    assert body["n_partite_con_eventi"] == 1
    assert len(body["giocatori"]) == 2
    edo = next(g for g in body["giocatori"] if g["nome_normalizzato"] == "edo")
    assert edo["n_attacchi_totali"] == 1
    assert edo["n_dadi_lanciati_tot"] == 2
