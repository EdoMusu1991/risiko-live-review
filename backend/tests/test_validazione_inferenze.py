"""
Test del servizio di validazione inferenze CV (linter semantico).
Algoritmo puro, niente DB.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.modelli import GiocatorePartita, InferenzaCV
from app.servizi.validazione_inferenze_servizio import (
    CODICE_BBOX_DEGENERE,
    CODICE_COLORE_NON_GIOCATORE,
    CODICE_CONFIDENCE_BASSA,
    CODICE_N_ARMATE_ASSURDO,
    CODICE_TERRITORIO_MANCANTE,
    CODICE_TERRITORIO_NON_VALIDO,
    conta_problemi_per_severita,
    valida_inferenze,
)


def _inf(
    *,
    territorio: str | None = "kamchatka",
    colore: str | None = "rosso",
    n_armate: int = 5,
    confidence: float = 0.9,
    bbox: list[int] | None = None,
    inf_id: str = "inf-1",
) -> InferenzaCV:
    return InferenzaCV(
        id=inf_id,
        partita_id="p1",
        evento_validato_id=None,
        modello_versione="test",
        territorio=territorio,
        colore=colore,
        tipo_pedina_dominante="carro_piccolo",
        n_armate_stimate=n_armate,
        bbox=bbox or [10, 20, 50, 50],
        confidence=confidence,
        scomposizione=[],
        creata_il=datetime(2026, 5, 9, tzinfo=UTC),
        frame_hash=None,
    )


def _giocatori(*colori: str) -> list[GiocatorePartita]:
    return [
        GiocatorePartita(
            id=f"g-{c}", partita_id="p1", nome=c.title(),
            colore=c, ordine_seduta=i + 1,
        )
        for i, c in enumerate(colori)
    ]


# === Casi positivi ===


def test_inferenza_valida_nessun_problema() -> None:
    problemi = valida_inferenze(
        [_inf()],
        territori_validi={"kamchatka", "alaska"},
        giocatori=_giocatori("rosso", "blu"),
    )
    assert problemi == []


def test_inferenze_multiple_valide() -> None:
    inferenze = [
        _inf(territorio="kamchatka", colore="rosso", inf_id="a"),
        _inf(territorio="alaska", colore="blu", inf_id="b"),
    ]
    problemi = valida_inferenze(
        inferenze,
        territori_validi={"kamchatka", "alaska"},
        giocatori=_giocatori("rosso", "blu"),
    )
    assert problemi == []


# === Territorio ===


def test_territorio_inesistente_e_error() -> None:
    problemi = valida_inferenze(
        [_inf(territorio="atlantide")],
        territori_validi={"kamchatka", "alaska"},
        giocatori=_giocatori("rosso"),
    )
    territorio_problemi = [p for p in problemi if p.codice == CODICE_TERRITORIO_NON_VALIDO]
    assert len(territorio_problemi) == 1
    assert territorio_problemi[0].severita == "error"


def test_territorio_none_e_warning() -> None:
    problemi = valida_inferenze(
        [_inf(territorio=None)],
        territori_validi={"kamchatka"},
        giocatori=_giocatori("rosso"),
    )
    pp = [p for p in problemi if p.codice == CODICE_TERRITORIO_MANCANTE]
    assert len(pp) == 1
    assert pp[0].severita == "warning"


def test_territori_validi_none_skippa_check() -> None:
    """Se non passo territori_validi, il check non viene eseguito."""
    problemi = valida_inferenze(
        [_inf(territorio="qualsiasi-cosa")],
        territori_validi=None,
        giocatori=_giocatori("rosso"),
    )
    assert all(p.codice != CODICE_TERRITORIO_NON_VALIDO for p in problemi)


# === Colore ===


def test_colore_non_giocatore_e_error() -> None:
    problemi = valida_inferenze(
        [_inf(colore="viola")],
        territori_validi={"kamchatka"},
        giocatori=_giocatori("rosso", "blu"),
    )
    pp = [p for p in problemi if p.codice == CODICE_COLORE_NON_GIOCATORE]
    assert len(pp) == 1
    assert pp[0].severita == "error"
    assert "viola" in pp[0].descrizione


def test_giocatori_none_skippa_check_colore() -> None:
    problemi = valida_inferenze(
        [_inf(colore="qualsiasi")],
        territori_validi={"kamchatka"},
        giocatori=None,
    )
    assert all(p.codice != CODICE_COLORE_NON_GIOCATORE for p in problemi)


# === n_armate ===


def test_n_armate_negativo_error() -> None:
    problemi = valida_inferenze([_inf(n_armate=-3)])
    pp = [p for p in problemi if p.codice == CODICE_N_ARMATE_ASSURDO]
    assert len(pp) == 1
    assert pp[0].severita == "error"


def test_n_armate_oltre_max_warning() -> None:
    problemi = valida_inferenze([_inf(n_armate=100)])
    pp = [p for p in problemi if p.codice == CODICE_N_ARMATE_ASSURDO]
    assert len(pp) == 1
    assert pp[0].severita == "warning"


def test_n_armate_60_e_dentro_soglia() -> None:
    """60 e' il limite incluso (N_ARMATE_MAX_PLAUSIBILE)."""
    problemi = valida_inferenze([_inf(n_armate=60)])
    assert all(p.codice != CODICE_N_ARMATE_ASSURDO for p in problemi)


# === Confidence ===


def test_confidence_bassa_warning() -> None:
    problemi = valida_inferenze([_inf(confidence=0.3)])
    pp = [p for p in problemi if p.codice == CODICE_CONFIDENCE_BASSA]
    assert len(pp) == 1
    assert pp[0].severita == "warning"


def test_confidence_alta_nessun_problema() -> None:
    problemi = valida_inferenze([_inf(confidence=0.95)])
    assert all(p.codice != CODICE_CONFIDENCE_BASSA for p in problemi)


# === Bbox ===


def test_bbox_larghezza_zero_error() -> None:
    problemi = valida_inferenze([_inf(bbox=[10, 10, 0, 50])])
    pp = [p for p in problemi if p.codice == CODICE_BBOX_DEGENERE]
    assert len(pp) == 1
    assert pp[0].severita == "error"


def test_bbox_dimensioni_enormi_warning() -> None:
    problemi = valida_inferenze([_inf(bbox=[10, 10, 9999, 9999])])
    pp = [p for p in problemi if p.codice == CODICE_BBOX_DEGENERE]
    assert len(pp) == 1
    assert pp[0].severita == "warning"


# === Helper conteggio ===


def test_conta_problemi_per_severita() -> None:
    problemi = valida_inferenze(
        [_inf(territorio="atlantide"), _inf(confidence=0.3, inf_id="b")],
        territori_validi={"kamchatka"},
    )
    conteggio = conta_problemi_per_severita(problemi)
    assert conteggio["error"] >= 1  # territorio_non_valido
    assert conteggio["warning"] >= 1  # confidence_bassa
