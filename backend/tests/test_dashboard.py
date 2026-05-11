"""Test per l'endpoint /api/dashboard/sommario."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.configurazione import impostazioni


async def test_dashboard_sommario_db_vuoto(client_test: AsyncClient) -> None:
    """Su DB vuoto ritorna 200 con tutti i count a zero."""
    r = await client_test.get("/api/dashboard/sommario")
    assert r.status_code == 200
    body = r.json()

    assert "partite" in body
    assert "bundle" in body
    assert "spazio" in body
    assert "servizi" in body
    assert "timestamp" in body

    p = body["partite"]
    assert p["n_partite_totali"] == 0
    assert p["n_partite_ultimo_mese"] == 0
    assert p["n_partite_ultima_settimana"] == 0
    assert p["n_eventi_totali"] == 0
    assert p["n_video_totali"] == 0
    assert p["durata_video_totale_sec"] == 0


async def test_dashboard_sommario_struttura(client_test: AsyncClient) -> None:
    """Verifica che la struttura della risposta sia quella attesa."""
    r = await client_test.get("/api/dashboard/sommario")
    body = r.json()

    # tutti i campi typed devono esistere
    assert isinstance(body["partite"]["n_partite_totali"], int)
    assert isinstance(body["bundle"]["n_bundle_in_attesa"], int)
    assert isinstance(body["bundle"]["dimensione_totale_byte"], int)
    assert isinstance(body["spazio"]["totale_byte"], int)
    assert isinstance(body["servizi"]["scheduler_abilitato"], bool)
    assert isinstance(body["servizi"]["roboflow_configurato"], bool)


async def test_dashboard_sommario_conta_bundle(
    client_test: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Conta correttamente i bundle non promossi presenti in storage."""
    monkeypatch.setattr(impostazioni, "storage_partite_path", tmp_path)

    # crea 2 bundle finti
    for nome in ("bundle1", "bundle2"):
        cart = tmp_path / nome
        cart.mkdir()
        cart.joinpath("manifest.json").write_text(
            json.dumps({
                "versione_app": "0.1.0",
                "device_id": "test",
                "ts_inizio_registrazione": "2026-01-01T00:00:00+00:00",
                "ts_fine_registrazione": "2026-01-01T01:00:00+00:00",
                "segmenti_video": [],
                "n_eventi_ble": 0,
            })
        )
        # un file finto per dimensione > 0
        cart.joinpath("seg_001.mp4").write_bytes(b"x" * 1024)

    r = await client_test.get("/api/dashboard/sommario")
    body = r.json()

    assert body["bundle"]["n_bundle_in_attesa"] == 2
    assert body["bundle"]["dimensione_totale_byte"] >= 2048  # almeno 2 KB
    assert body["bundle"]["bundle_piu_vecchio_giorni"] is not None


async def test_dashboard_sommario_servizi_default(
    client_test: AsyncClient,
) -> None:
    """Con configurazione di default, scheduler off e Roboflow non configurato."""
    r = await client_test.get("/api/dashboard/sommario")
    body = r.json()

    # In test: scheduler_abilitato e' False di default
    assert body["servizi"]["scheduler_abilitato"] is False
    # Roboflow non configurato se le env sono vuote
    if not impostazioni.roboflow_api_key:
        assert body["servizi"]["roboflow_configurato"] is False


async def test_dashboard_sommario_bundle_dir_inesistente(
    client_test: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Robusto se storage_partite_path non esiste."""
    monkeypatch.setattr(impostazioni, "storage_partite_path", tmp_path / "no")

    r = await client_test.get("/api/dashboard/sommario")
    assert r.status_code == 200
    body = r.json()
    assert body["bundle"]["n_bundle_in_attesa"] == 0
    assert body["bundle"]["bundle_piu_vecchio_giorni"] is None
