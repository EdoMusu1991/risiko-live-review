"""
Test del servizio di calcolo discrepanze fra stato motore e inferenze CV.

Niente DB, niente CV reale: testano solo l'algoritmo puro.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.modelli import InferenzaCV
from app.servizi.discrepanze_servizio import (
    DivergenzaCalcolata,
    StatoTerritorioMotore,
    calcola_discrepanze,
    stato_motore_da_snapshot,
)


def _inf(
    territorio: str,
    colore: str,
    n_armate: int,
    confidence: float = 0.9,
    inf_id: str | None = None,
) -> InferenzaCV:
    """Helper: crea una InferenzaCV non persistita."""
    rec = InferenzaCV(
        id=inf_id or f"inf-{territorio}-{colore}-{n_armate}",
        partita_id="p1",
        evento_validato_id=None,
        modello_versione="test-v0.1",
        territorio=territorio,
        colore=colore,
        tipo_pedina_dominante="carro_piccolo",
        n_armate_stimate=n_armate,
        bbox=[0, 0, 10, 10],
        confidence=confidence,
        scomposizione=[],
        creata_il=datetime(2026, 5, 9, tzinfo=UTC),
        frame_hash=None,
    )
    return rec


# === Casi base ===


def test_match_perfetto_nessuna_divergenza() -> None:
    motore = [StatoTerritorioMotore("kamchatka", "rosso", 5)]
    cv = [_inf("kamchatka", "rosso", 5)]

    div = calcola_discrepanze(motore, cv)
    assert div == []


def test_motore_e_cv_disaccordo_su_n_armate() -> None:
    motore = [StatoTerritorioMotore("kamchatka", "rosso", 5)]
    cv = [_inf("kamchatka", "rosso", 8)]

    div = calcola_discrepanze(motore, cv)
    assert len(div) == 1
    d = div[0]
    assert d.territorio == "kamchatka"
    assert d.colore == "rosso"
    assert d.valore_motore == 5
    assert d.valore_cv == 8
    assert d.delta_assoluto == 3


def test_motore_vede_cv_no() -> None:
    """Motore: 7 armate. CV: nulla. Divergenza con valore_cv=0."""
    motore = [StatoTerritorioMotore("alaska", "blu", 7)]
    cv: list[InferenzaCV] = []

    div = calcola_discrepanze(motore, cv)
    assert len(div) == 1
    assert div[0].valore_motore == 7
    assert div[0].valore_cv == 0
    assert div[0].confidence_cv == 0.0
    assert div[0].delta_assoluto == 7


def test_cv_vede_motore_no() -> None:
    """CV: 3 armate su un territorio che il motore non considera."""
    motore: list[StatoTerritorioMotore] = []
    cv = [_inf("madagascar", "verde", 3)]

    div = calcola_discrepanze(motore, cv)
    assert len(div) == 1
    assert div[0].valore_motore == 0
    assert div[0].valore_cv == 3
    assert div[0].delta_assoluto == 3


def test_inferenze_aggregate_per_territorio_colore() -> None:
    """Più inferenze sullo stesso (terr, colore) si sommano in n_armate."""
    motore = [StatoTerritorioMotore("kamchatka", "rosso", 10)]
    cv = [
        _inf("kamchatka", "rosso", 5, inf_id="inf-1"),
        _inf("kamchatka", "rosso", 3, inf_id="inf-2"),
        _inf("kamchatka", "rosso", 2, inf_id="inf-3"),
    ]

    div = calcola_discrepanze(motore, cv)
    # Somma 5+3+2 = 10, match con motore = no divergenza
    assert div == []


def test_aggregazione_con_divergenza() -> None:
    motore = [StatoTerritorioMotore("kamchatka", "rosso", 10)]
    cv = [
        _inf("kamchatka", "rosso", 4, inf_id="inf-a"),
        _inf("kamchatka", "rosso", 4, inf_id="inf-b"),
    ]
    # CV: 4+4=8, motore: 10 → divergenza delta=2
    div = calcola_discrepanze(motore, cv)
    assert len(div) == 1
    assert div[0].valore_cv == 8
    assert div[0].delta_assoluto == 2
    assert set(div[0].inferenze_correlate) == {"inf-a", "inf-b"}


def test_confidence_aggregata_e_media_aritmetica() -> None:
    motore = [StatoTerritorioMotore("kamchatka", "rosso", 10)]
    cv = [
        _inf("kamchatka", "rosso", 3, confidence=0.8),
        _inf("kamchatka", "rosso", 3, confidence=0.4),
    ]
    div = calcola_discrepanze(motore, cv)
    assert len(div) == 1
    # Media = (0.8 + 0.4) / 2 = 0.6
    assert div[0].confidence_cv == pytest.approx(0.6)


def test_ordina_per_delta_decrescente() -> None:
    motore = [
        StatoTerritorioMotore("alaska", "blu", 1),
        StatoTerritorioMotore("kamchatka", "rosso", 1),
    ]
    cv = [
        _inf("alaska", "blu", 5),       # delta 4
        _inf("kamchatka", "rosso", 11),  # delta 10
    ]
    div = calcola_discrepanze(motore, cv)
    assert [d.territorio for d in div] == ["kamchatka", "alaska"]


def test_zeri_su_entrambi_lati_nessuna_divergenza() -> None:
    """Edge case: territorio nel motore con 0 armate, CV niente. Nessuna div."""
    motore = [StatoTerritorioMotore("alaska", "blu", 0)]
    cv: list[InferenzaCV] = []

    div = calcola_discrepanze(motore, cv)
    assert div == []


def test_inferenze_senza_territorio_o_colore_ignorate() -> None:
    """Inferenze con territorio=None o colore=None non producono divergenze."""
    motore: list[StatoTerritorioMotore] = []
    cv = [
        _inf("kamchatka", "rosso", 5),  # ok
    ]
    cv.append(InferenzaCV(
        id="inf-vuota",
        partita_id="p1",
        evento_validato_id=None,
        modello_versione="test",
        territorio=None,  # <-- ignorata
        colore=None,
        tipo_pedina_dominante=None,
        n_armate_stimate=99,
        bbox=[0, 0, 10, 10],
        confidence=0.9,
        scomposizione=[],
        creata_il=datetime(2026, 5, 9, tzinfo=UTC),
        frame_hash=None,
    ))

    div = calcola_discrepanze(motore, cv)
    # Solo l'inferenza valida produce una divergenza (CV vede, motore no)
    assert len(div) == 1
    assert div[0].territorio == "kamchatka"


def test_stato_motore_duplicato_solleva() -> None:
    motore = [
        StatoTerritorioMotore("kamchatka", "rosso", 5),
        StatoTerritorioMotore("kamchatka", "rosso", 7),  # duplicato
    ]
    with pytest.raises(ValueError, match="duplicato"):
        calcola_discrepanze(motore, [])


# === Helper: stato_motore_da_snapshot ===


def test_stato_motore_da_snapshot_caso_base() -> None:
    snapshot = {
        "territori": {
            "kamchatka": {"controllore_id": "id-rosso", "armate": 5},
            "alaska": {"controllore_id": "id-blu", "armate": 3},
        },
        "giocatori": [
            {"player_id": "id-rosso", "colore": "rosso", "nome": "Edo"},
            {"player_id": "id-blu", "colore": "blu", "nome": "Marco"},
        ],
    }
    stato = stato_motore_da_snapshot(snapshot)
    chiavi = {(s.territorio, s.colore): s.n_armate for s in stato}
    assert chiavi == {
        ("kamchatka", "rosso"): 5,
        ("alaska", "blu"): 3,
    }


def test_stato_motore_da_snapshot_giocatore_mancante_skippa_territorio() -> None:
    """Se controllore_id non ha corrispondenza nei giocatori, salta."""
    snapshot = {
        "territori": {
            "kamchatka": {"controllore_id": "id-fantasma", "armate": 5},
        },
        "giocatori": [],
    }
    stato = stato_motore_da_snapshot(snapshot)
    assert stato == []


def test_stato_motore_da_snapshot_dati_malformati_torna_lista_vuota() -> None:
    assert stato_motore_da_snapshot({}) == []
    assert stato_motore_da_snapshot({"territori": "non-un-dict"}) == []
    assert stato_motore_da_snapshot({"territori": {}, "giocatori": "x"}) == []


# === Type checking del DivergenzaCalcolata ===


def test_divergenza_calcolata_e_immutabile() -> None:
    d = DivergenzaCalcolata(
        territorio="x", colore="r", valore_motore=1, valore_cv=2,
        confidence_cv=0.9, delta_assoluto=1, inferenze_correlate=[],
    )
    with pytest.raises(AttributeError):
        d.valore_motore = 99  # type: ignore[misc]
