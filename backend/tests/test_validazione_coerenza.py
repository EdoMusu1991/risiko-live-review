"""
Test del servizio `valida_coerenza` (puro) e dell'endpoint
`GET /api/partite/{id}/valida-coerenza`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

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
from app.servizi.validazione_coerenza_servizio import valida_coerenza

# === Fixture ===


def _crea_partita() -> Partita:
    return Partita(
        id="test-partita-id",
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )


def _crea_giocatori() -> list[GiocatorePartita]:
    return [
        GiocatorePartita(
            id="g-rosso", partita_id="test-partita-id",
            nome="Edo", colore="rosso", ordine_seduta=1,
        ),
        GiocatorePartita(
            id="g-blu", partita_id="test-partita-id",
            nome="Marco", colore="blu", ordine_seduta=2,
        ),
    ]


def _evento(
    tipo: TipoEvento,
    dati: dict[str, Any],
    *,
    offset_sec: float = 0.0,
    id_evento: str | None = None,
) -> EventoValidato:
    return EventoValidato(
        id=id_evento or f"ev-{tipo.value}-{offset_sec}",
        partita_id="test-partita-id",
        ts_evento=datetime(2026, 5, 7, 21, 0, tzinfo=UTC) + timedelta(seconds=offset_sec),
        tipo=tipo,
        dati=dati,
        evento_grezzo_id=None,
        validato_da="test",
    )


# === Test validazioni globali (no motore) ===


class TestOrdineTemporale:
    def test_eventi_ordinati_nessun_problema(self) -> None:
        eventi = [
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-rosso"}, offset_sec=0),
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-blu"}, offset_sec=10),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        codici = [p.codice for p in ris.problemi]
        assert "evento_fuori_ordine_temporale" not in codici

    def test_evento_fuori_ordine_segnalato(self) -> None:
        eventi = [
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-rosso"}, offset_sec=10),
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-blu"}, offset_sec=5),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        problemi = [p for p in ris.problemi if p.codice == "evento_fuori_ordine_temporale"]
        assert len(problemi) == 1
        assert problemi[0].severita == "avviso"
        assert problemi[0].posizione == 1


class TestTurniConsecutivi:
    def test_turno_iniziato_seguito_da_eventi_normali(self) -> None:
        eventi = [
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-rosso"}, offset_sec=0),
            _evento(
                TipoEvento.ARMATE_PIAZZATE,
                {"giocatore_id": "g-rosso", "territorio": "kamchatka", "n": 3},
                offset_sec=1,
            ),
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-blu"}, offset_sec=10),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        codici = [p.codice for p in ris.problemi]
        assert "doppio_turno_iniziato" not in codici

    def test_due_turni_consecutivi_segnalati(self) -> None:
        eventi = [
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-rosso"}, offset_sec=0),
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-blu"}, offset_sec=1),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        problemi = [p for p in ris.problemi if p.codice == "doppio_turno_iniziato"]
        assert len(problemi) == 1
        assert problemi[0].severita == "avviso"


# === Test validazioni con motore ===


class TestAttacco:
    def test_attacco_giocatore_inesistente(self) -> None:
        eventi = [
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {
                    "giocatore_id": "fantasma",
                    "da": "kamchatka", "a": "alaska",
                    "dadi_attaccante": [6], "dadi_difensore": [3],
                },
            ),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        codici = [p.codice for p in ris.problemi if p.severita == "errore"]
        assert "giocatore_id_inesistente" in codici

    def test_attacco_territorio_inesistente(self) -> None:
        eventi = [
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {
                    "giocatore_id": "g-rosso",
                    "da": "atlantide", "a": "alaska",
                    "dadi_attaccante": [6], "dadi_difensore": [3],
                },
            ),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        codici = [p.codice for p in ris.problemi]
        assert "territorio_inesistente" in codici

    def test_attacco_territori_non_adiacenti(self) -> None:
        eventi = [
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {
                    "giocatore_id": "g-rosso",
                    "da": "kamchatka", "a": "argentina",  # opposti del mondo
                    "dadi_attaccante": [6], "dadi_difensore": [3],
                },
            ),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        codici_errore = [p.codice for p in ris.problemi if p.severita == "errore"]
        assert "attacco_territori_non_adiacenti" in codici_errore

    def test_attacco_da_territorio_adiacente_pulito(self) -> None:
        """Kamchatka e Alaska sono adiacenti — nessun problema di adiacenza."""
        eventi = [
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {
                    "giocatore_id": "g-rosso",
                    "da": "kamchatka", "a": "alaska",
                    "dadi_attaccante": [6], "dadi_difensore": [3],
                },
            ),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        codici = [p.codice for p in ris.problemi]
        assert "attacco_territori_non_adiacenti" not in codici

    def test_attacco_senza_dadi_difensore_avviso(self) -> None:
        eventi = [
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {
                    "giocatore_id": "g-rosso",
                    "da": "kamchatka", "a": "alaska",
                    "dadi_attaccante": [6], "dadi_difensore": [],
                },
            ),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        avvisi = [p for p in ris.problemi if p.severita == "avviso"]
        assert any(p.codice == "attacco_difensore_inesistente" for p in avvisi)


class TestArmatePiazzate:
    def test_armate_su_territorio_inesistente(self) -> None:
        eventi = [
            _evento(
                TipoEvento.ARMATE_PIAZZATE,
                {"giocatore_id": "g-rosso", "territorio": "atlantide", "n": 3},
            ),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        codici = [p.codice for p in ris.problemi]
        assert "territorio_inesistente" in codici


class TestSpostamento:
    def test_spostamento_non_adiacente(self) -> None:
        eventi = [
            _evento(
                TipoEvento.ARMATE_SPOSTATE,
                {
                    "giocatore_id": "g-rosso",
                    "da": "kamchatka", "a": "argentina", "n": 5,
                },
            ),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        codici = [p.codice for p in ris.problemi if p.severita == "errore"]
        assert "spostamento_territori_non_adiacenti" in codici


# === Test risultato globale ===


class TestRisultatoGlobale:
    def test_partita_vuota_zero_problemi(self) -> None:
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), [])
        assert ris.n_eventi_analizzati == 0
        assert ris.n_errori == 0
        assert ris.n_avvisi == 0
        assert ris.is_coerente is True
        assert ris.problemi == []

    def test_is_coerente_false_se_errori(self) -> None:
        eventi = [
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {
                    "giocatore_id": "fantasma",
                    "da": "kamchatka", "a": "alaska",
                    "dadi_attaccante": [6], "dadi_difensore": [3],
                },
            ),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        assert ris.n_errori >= 1
        assert ris.is_coerente is False

    def test_is_coerente_true_se_solo_avvisi(self) -> None:
        eventi = [
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-rosso"}, offset_sec=0),
            _evento(TipoEvento.TURNO_INIZIATO, {"giocatore_id": "g-blu"}, offset_sec=1),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        assert ris.n_avvisi >= 1
        assert ris.n_errori == 0
        assert ris.is_coerente is True

    def test_problemi_ordinati_per_posizione(self) -> None:
        eventi = [
            _evento(
                TipoEvento.ATTACCO_RISOLTO,
                {
                    "giocatore_id": "g-rosso",
                    "da": "atlantide", "a": "alaska",
                    "dadi_attaccante": [6], "dadi_difensore": [3],
                },
                offset_sec=10,
                id_evento="ev-attacco-1",
            ),
            _evento(
                TipoEvento.ARMATE_PIAZZATE,
                {"giocatore_id": "g-blu", "territorio": "atlantide", "n": 1},
                offset_sec=20,
                id_evento="ev-piazza-1",
            ),
        ]
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        posizioni = [p.posizione for p in ris.problemi if p.posizione is not None]
        assert posizioni == sorted(posizioni)


class TestEventiMalformati:
    def test_dati_non_dict_skippato(self) -> None:
        eventi = [
            EventoValidato(
                id="ev-malformato", partita_id="test-partita-id",
                ts_evento=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
                tipo=TipoEvento.ATTACCO_RISOLTO,
                dati="non-un-dict",  # type: ignore[arg-type]
                evento_grezzo_id=None, validato_da="test",
            ),
        ]
        # Non deve crashare
        ris = valida_coerenza(_crea_partita(), _crea_giocatori(), eventi)
        assert ris.n_eventi_analizzati == 1
        # Eventi malformati non sono nostro compito segnalare
        assert ris.n_errori == 0


# === Test endpoint ===


@pytest.mark.asyncio
async def test_endpoint_partita_inesistente(
    client_test: AsyncClient,
) -> None:
    risposta = await client_test.get("/api/partite/non-esiste/valida-coerenza")
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_endpoint_partita_pulita(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
    p = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add(p)
    await sessione_test.flush()
    sessione_test.add_all([
        GiocatorePartita(
            partita_id=p.id, nome="Edo", colore="rosso", ordine_seduta=1
        ),
        GiocatorePartita(
            partita_id=p.id, nome="Marco", colore="blu", ordine_seduta=2
        ),
    ])
    await sessione_test.commit()

    risposta = await client_test.get(f"/api/partite/{p.id}/valida-coerenza")
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["n_errori"] == 0
    assert body["n_avvisi"] == 0
    assert body["problemi"] == []


@pytest.mark.asyncio
async def test_endpoint_segnala_problemi(
    client_test: AsyncClient, sessione_test: AsyncSession
) -> None:
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

    # Aggiungo un attacco con territori non adiacenti (errore certo)
    sessione_test.add(
        EventoValidato(
            partita_id=p.id,
            ts_evento=datetime(2026, 5, 7, 21, 5, tzinfo=UTC),
            tipo=TipoEvento.ATTACCO_RISOLTO,
            dati={
                "giocatore_id": rosso.id,
                "da": "kamchatka", "a": "argentina",
                "dadi_attaccante": [6], "dadi_difensore": [3],
            },
            evento_grezzo_id=None,
            validato_da="test",
        )
    )
    await sessione_test.commit()

    risposta = await client_test.get(f"/api/partite/{p.id}/valida-coerenza")
    assert risposta.status_code == 200
    body = risposta.json()
    assert body["n_errori"] >= 1
    codici = [p["codice"] for p in body["problemi"]]
    assert "attacco_territori_non_adiacenti" in codici
