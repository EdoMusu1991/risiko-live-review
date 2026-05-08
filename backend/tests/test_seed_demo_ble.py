"""
Test della logica pura di generazione eventi seed.

Lo script `scripts/seed_demo_ble.py` ha una funzione `genera_eventi_attacco`
che è puro Python (no DB) e merita test perché determina la qualità
dei dati seed che Edoardo userà per testare la UI.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

# Aggiungi scripts/ al path per importare il modulo seed
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from seed_demo_ble import (  # type: ignore[import-not-found]
    genera_eventi_attacco,
    scenari_attacchi,
)

from app.modelli import FonteEvento, TipoEvento


def test_genera_eventi_caso_3v3() -> None:
    """Caso classico: 3 attaccanti + 3 difensori = 6 eventi."""
    ts = datetime(2026, 5, 7, 21, 0, 0, tzinfo=UTC)
    eventi = genera_eventi_attacco(
        partita_id="p1",
        ts_inizio_attacco=ts,
        ble_attaccante_ids=["A1", "A2", "A3"],
        ble_difensore_ids=["D1", "D2", "D3"],
        valori_attaccante=[6, 4, 2],
        valori_difensore=[5, 3, 1],
    )

    assert len(eventi) == 6
    # Tutti sono DADI_LANCIATI / DADO_BLE
    for e in eventi:
        assert e.tipo == TipoEvento.DADI_LANCIATI
        assert e.fonte == FonteEvento.DADO_BLE
        assert e.confidenza == 1.0
        assert e.validato is False
        assert e.partita_id == "p1"

    # Primi 3 attaccanti, ultimi 3 difensori
    assert all(e.dati["ruolo"] == "attaccante" for e in eventi[:3])
    assert all(e.dati["ruolo"] == "difensore" for e in eventi[3:])

    # Slot 1,2,3 progressivi per ruolo
    assert [e.dati["slot"] for e in eventi[:3]] == [1, 2, 3]
    assert [e.dati["slot"] for e in eventi[3:]] == [1, 2, 3]

    # Valori corretti
    assert [e.dati["valore"] for e in eventi[:3]] == [6, 4, 2]
    assert [e.dati["valore"] for e in eventi[3:]] == [5, 3, 1]


def test_eventi_distanziati_correttamente() -> None:
    """Gli eventi sono spaziati di delta_dado_sec come da config."""
    ts = datetime(2026, 5, 7, 21, 0, 0, tzinfo=UTC)
    eventi = genera_eventi_attacco(
        partita_id="p1",
        ts_inizio_attacco=ts,
        ble_attaccante_ids=["A1", "A2"],
        ble_difensore_ids=["D1"],
        valori_attaccante=[5, 3],
        valori_difensore=[2],
        delta_dado_sec=0.5,
    )

    # 3 eventi totali, distanziati 0.5s
    assert len(eventi) == 3
    delta01 = (eventi[1].ts_evento - eventi[0].ts_evento).total_seconds()
    delta12 = (eventi[2].ts_evento - eventi[1].ts_evento).total_seconds()
    assert abs(delta01 - 0.5) < 0.01
    assert abs(delta12 - 0.5) < 0.01


def test_attacco_solo_attaccante() -> None:
    """Caso con difensore vuoto (territorio sgombro)."""
    ts = datetime(2026, 5, 7, 21, 0, 0, tzinfo=UTC)
    eventi = genera_eventi_attacco(
        partita_id="p1",
        ts_inizio_attacco=ts,
        ble_attaccante_ids=["A1"],
        ble_difensore_ids=[],
        valori_attaccante=[6],
        valori_difensore=[],
    )
    assert len(eventi) == 1
    assert eventi[0].dati["ruolo"] == "attaccante"


def test_scenari_default_tre_cluster_distinti() -> None:
    """
    I 3 attacchi default sono spaziati > finestra clustering (3s default
    del servizio): devono produrre 3 cluster distinti.
    """
    ts = datetime(2026, 5, 7, 21, 0, 0, tzinfo=UTC)
    scenari = scenari_attacchi(ts)
    assert len(scenari) == 3

    # Verifica che ogni attacco sia distanziato di > 10s dal precedente
    ts_inizi = [s["ts_inizio_attacco"] for s in scenari]
    for i in range(1, len(ts_inizi)):
        gap = (ts_inizi[i] - ts_inizi[i - 1]).total_seconds()
        assert gap > 10.0, f"Gap {gap}s troppo stretto fra attacco {i-1} e {i}"


def test_scenari_coprono_anomalie_note() -> None:
    """
    Gli scenari devono includere casi-test interessanti per la UI:
    - un caso pulito 3v3
    - un caso 2v1 (territorio quasi sgombro)
    - un caso 1v0 (anomalia: difensore non registrato)
    """
    ts = datetime(2026, 5, 7, 21, 0, 0, tzinfo=UTC)
    scenari = scenari_attacchi(ts)

    # Caso 1: 3v3
    assert len(scenari[0]["valori_attaccante"]) == 3
    assert len(scenari[0]["valori_difensore"]) == 3

    # Caso 2: 2v1
    assert len(scenari[1]["valori_attaccante"]) == 2
    assert len(scenari[1]["valori_difensore"]) == 1

    # Caso 3: 1v0 (anomalia)
    assert len(scenari[2]["valori_attaccante"]) == 1
    assert len(scenari[2]["valori_difensore"]) == 0


def test_dati_contengono_chiavi_attese_per_servizio_aggregazione() -> None:
    """
    Il payload `dati` di ogni evento deve contenere ble_id, ruolo,
    slot, valore — esattamente le chiavi attese da
    `ServizioAggregazioneDadi._costruisci_proposta`. Se questo test
    fallisce, il seed non è più compatibile col servizio.
    """
    ts = datetime(2026, 5, 7, 21, 0, 0, tzinfo=UTC)
    eventi = genera_eventi_attacco(
        partita_id="p1",
        ts_inizio_attacco=ts,
        ble_attaccante_ids=["A1"],
        ble_difensore_ids=["D1"],
        valori_attaccante=[3],
        valori_difensore=[5],
    )
    chiavi_attese = {"ble_id", "ruolo", "slot", "valore"}
    for e in eventi:
        assert chiavi_attese.issubset(e.dati.keys()), (
            f"Mancano chiavi nel dato seed: presenti {set(e.dati.keys())}"
        )


def test_valori_dadi_in_range_legale() -> None:
    """Tutti i valori generati dagli scenari default sono 1..6."""
    ts = datetime(2026, 5, 7, 21, 0, 0, tzinfo=UTC)
    for scenario in scenari_attacchi(ts):
        for v in scenario["valori_attaccante"]:
            assert 1 <= v <= 6, f"Valore {v} fuori range 1-6"
        for v in scenario["valori_difensore"]:
            assert 1 <= v <= 6
