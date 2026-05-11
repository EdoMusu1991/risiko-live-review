"""
Test pytest del modulo `app.utili.scheduler`.

NB: lo scheduler e' disabilitato di default (`scheduler_abilitato=False`),
quindi questi test devono attivarlo esplicitamente via monkeypatch sulla
config.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.configurazione import impostazioni
from app.utili import scheduler as mod_scheduler


def _crea_bundle_vecchio(base: Path, id_partita: str, ts_fine_iso: str) -> None:
    """Crea un bundle finto in `base/<id>/manifest.json` con ts_fine arbitrario."""
    cart = base / id_partita
    cart.mkdir(parents=True, exist_ok=True)
    cart.joinpath("manifest.json").write_text(
        json.dumps(
            {
                "versione_app": "0.1.0",
                "device_id": "test",
                "ts_inizio_registrazione": ts_fine_iso,
                "ts_fine_registrazione": ts_fine_iso,
                "segmenti_video": [],
                "n_eventi_ble": 0,
            }
        )
    )


# ============================================================================
# stato_scheduler
# ============================================================================


def test_stato_scheduler_disabilitato_di_default() -> None:
    s = mod_scheduler.stato_scheduler()
    assert s["abilitato"] is False
    assert s["in_esecuzione"] is False
    assert s["prossima_esecuzione"] is None


def test_stato_scheduler_abilitato_ma_non_avviato(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(impostazioni, "scheduler_abilitato", True)
    # Niente avvia_scheduler(): _scheduler resta None
    monkeypatch.setattr(mod_scheduler, "_scheduler", None)
    s = mod_scheduler.stato_scheduler()
    assert s["abilitato"] is True
    assert s["in_esecuzione"] is False
    assert s["prossima_esecuzione"] is None
    assert s["giorni_cleanup"] == impostazioni.bundle_cleanup_giorni


# ============================================================================
# avvia_scheduler / ferma_scheduler
# ============================================================================


def test_avvia_scheduler_no_op_se_disabilitato(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(impostazioni, "scheduler_abilitato", False)
    monkeypatch.setattr(mod_scheduler, "_scheduler", None)
    mod_scheduler.avvia_scheduler()
    # _scheduler resta None (no-op)
    assert mod_scheduler._scheduler is None


async def test_avvia_scheduler_idempotente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(impostazioni, "scheduler_abilitato", True)
    monkeypatch.setattr(mod_scheduler, "_scheduler", None)
    try:
        mod_scheduler.avvia_scheduler()
        primo = mod_scheduler._scheduler
        assert primo is not None
        assert primo.running

        # seconda chiamata: stesso oggetto, idempotente
        mod_scheduler.avvia_scheduler()
        assert mod_scheduler._scheduler is primo
    finally:
        mod_scheduler.ferma_scheduler()


def test_ferma_scheduler_no_op_se_non_avviato(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod_scheduler, "_scheduler", None)
    mod_scheduler.ferma_scheduler()  # non solleva
    assert mod_scheduler._scheduler is None


async def test_avvia_scheduler_con_ora_invalida_usa_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(impostazioni, "scheduler_abilitato", True)
    monkeypatch.setattr(impostazioni, "bundle_cleanup_ora", "non_una_ora_valida")
    monkeypatch.setattr(mod_scheduler, "_scheduler", None)
    try:
        mod_scheduler.avvia_scheduler()
        # Deve essere comunque avviato (con ora di default 03:00)
        assert mod_scheduler._scheduler is not None
        assert mod_scheduler._scheduler.running
    finally:
        mod_scheduler.ferma_scheduler()


# ============================================================================
# _job_cleanup_bundle (chiamabile direttamente per test)
# ============================================================================


def test_job_cleanup_bundle_cancella_solo_vecchi(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(impostazioni, "storage_partite_path", tmp_path)
    monkeypatch.setattr(impostazioni, "bundle_cleanup_giorni", 30)

    # bundle vecchio (1 anno fa)
    _crea_bundle_vecchio(tmp_path, "vecchio", "2025-05-12T20:00:00+00:00")
    # bundle nuovo (oggi)
    _crea_bundle_vecchio(tmp_path, "nuovo", "2099-01-01T00:00:00+00:00")

    mod_scheduler._job_cleanup_bundle()

    assert not (tmp_path / "vecchio").exists(), "il bundle vecchio doveva essere cancellato"
    assert (tmp_path / "nuovo").exists(), "il bundle nuovo NON doveva essere cancellato"


def test_job_cleanup_bundle_non_solleva_su_storage_inesistente(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Il job e' robusto: non solleva eccezioni anche se il dir non esiste."""
    inesistente = tmp_path / "nonesiste"
    monkeypatch.setattr(impostazioni, "storage_partite_path", inesistente)
    # non solleva
    mod_scheduler._job_cleanup_bundle()


# ============================================================================
# Endpoint /api/scheduler
# ============================================================================


async def test_get_scheduler_endpoint(client_test: AsyncClient) -> None:
    r = await client_test.get("/api/scheduler")
    assert r.status_code == 200
    body = r.json()
    assert "abilitato" in body
    assert "in_esecuzione" in body
    assert "giorni_cleanup" in body


# ============================================================================
# Endpoint POST /api/scheduler/run-now
# ============================================================================


async def test_post_scheduler_run_now_cancella_bundle_vecchi(
    client_test: AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`run-now` esegue immediatamente il cleanup, anche se scheduler off."""
    monkeypatch.setattr(impostazioni, "storage_partite_path", tmp_path)
    monkeypatch.setattr(impostazioni, "bundle_cleanup_giorni", 30)

    # bundle vecchio (cancellabile) + bundle nuovo (no)
    _crea_bundle_vecchio(tmp_path, "vecchio", "2025-05-12T20:00:00+00:00")
    _crea_bundle_vecchio(tmp_path, "nuovo", "2099-01-01T00:00:00+00:00")

    r = await client_test.post("/api/scheduler/run-now")
    assert r.status_code == 200
    body = r.json()
    assert body["n_cancellati"] == 1
    assert body["ids_cancellati"] == ["vecchio"]
    assert body["giorni_soglia"] == 30

    # filesystem coerente
    assert not (tmp_path / "vecchio").exists()
    assert (tmp_path / "nuovo").exists()
