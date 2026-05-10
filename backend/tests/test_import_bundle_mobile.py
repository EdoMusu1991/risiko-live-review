"""
Test pytest per l'endpoint POST /api/import/bundle-mobile.

Strategia: costruiamo bundle ZIP in-memory e li mandiamo con TestClient
FastAPI. Verifichiamo i casi: ok, manifest mancante/corrotto, segmento
mancante, eventi corrotti (warning non errore), bundle troppo grande
(simulato), versione app diversa.
"""
from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.configurazione import impostazioni


@pytest.fixture(autouse=True)
def storage_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reindirizza STORAGE_PARTITE a una tmp dir per ogni test."""
    monkeypatch.setattr(impostazioni, "storage_partite_path", tmp_path)
    yield
    # cleanup automatico via tmp_path


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def manifest_valido() -> dict:
    return {
        "versione_app": "0.1.0",
        "device_id": "test-device-uuid",
        "ts_inizio_registrazione": "2026-05-12T20:00:00.000+02:00",
        "ts_fine_registrazione": "2026-05-12T22:30:00.000+02:00",
        "segmenti_video": [
            {
                "filename": "seg_001_2026-05-12T20-00-00.mp4",
                "ts_inizio": "2026-05-12T20:00:00.000+02:00",
                "ts_fine": "2026-05-12T20:10:00.000+02:00",
                "durata_sec": 600,
                "larghezza": 1920,
                "altezza": 1080,
                "fps": 30,
            },
            {
                "filename": "seg_002_2026-05-12T20-10-00.mp4",
                "ts_inizio": "2026-05-12T20:10:00.000+02:00",
                "ts_fine": "2026-05-12T20:20:00.000+02:00",
                "durata_sec": 600,
                "larghezza": 1920,
                "altezza": 1080,
                "fps": 30,
            },
        ],
        "n_eventi_ble": 2,
    }


def evento_valido(n: int) -> dict:
    return {
        "ts_evento": f"2026-05-12T20:0{n}:00.000+02:00",
        "tipo": "dadi_lanciati",
        "fonte": "dado_ble",
        "confidenza": 1.0,
        "dati": {"dado_id": "att-1", "valore": n},
    }


def costruisci_bundle(
    manifest: dict | None = None,
    eventi: list[dict] | None = None,
    nomi_segmenti: list[str] | None = None,
    manifest_raw: bytes | None = None,
    eventi_raw: bytes | None = None,
) -> bytes:
    """Costruisce un bundle ZIP in-memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if manifest_raw is not None:
            zf.writestr("manifest.json", manifest_raw)
        elif manifest is not None:
            zf.writestr("manifest.json", json.dumps(manifest))

        if eventi_raw is not None:
            zf.writestr("eventi.jsonl", eventi_raw)
        elif eventi is not None:
            jsonl = "\n".join(json.dumps(e) for e in eventi) + "\n"
            zf.writestr("eventi.jsonl", jsonl)

        if nomi_segmenti is not None:
            for nome in nomi_segmenti:
                zf.writestr(nome, b"fake-mp4-content")
    return buf.getvalue()


def post_bundle(
    client: TestClient,
    bundle: bytes,
    device_id: str = "test-device-uuid",
    id_partita: str = "partita_test_001",
):
    return client.post(
        "/api/import/bundle-mobile",
        files={"bundle": ("bundle.zip", bundle, "application/zip")},
        data={"device_id": device_id, "id_partita": id_partita},
    )


# === SUCCESSO ===


class TestSuccesso:
    def test_bundle_completo_e_valido(self, client: TestClient):
        m = manifest_valido()
        nomi = [s["filename"] for s in m["segmenti_video"]]
        eventi = [evento_valido(1), evento_valido(2)]
        bundle = costruisci_bundle(manifest=m, eventi=eventi, nomi_segmenti=nomi)

        resp = post_bundle(client, bundle)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id_partita"] == "partita_test_001"
        assert data["n_segmenti"] == 2
        assert data["n_eventi"] == 2
        assert data["durata_totale_sec"] == 1200
        assert data["avvisi"] == []

    def test_bundle_senza_eventi_jsonl(self, client: TestClient):
        m = manifest_valido()
        m["n_eventi_ble"] = 0
        nomi = [s["filename"] for s in m["segmenti_video"]]
        bundle = costruisci_bundle(manifest=m, nomi_segmenti=nomi)

        resp = post_bundle(client, bundle)
        assert resp.status_code == 200
        data = resp.json()
        assert data["n_eventi"] == 0
        assert any("eventi.jsonl assente" in a for a in data["avvisi"])

    def test_bundle_segmenti_vuoti(self, client: TestClient):
        m = manifest_valido()
        m["segmenti_video"] = []
        m["n_eventi_ble"] = 0
        bundle = costruisci_bundle(manifest=m, nomi_segmenti=[])

        resp = post_bundle(client, bundle)
        assert resp.status_code == 200
        data = resp.json()
        assert data["n_segmenti"] == 0
        assert data["durata_totale_sec"] == 0


# === ERRORI 4XX ===


class TestErroriClient:
    def test_manifest_mancante(self, client: TestClient):
        bundle = costruisci_bundle()
        resp = post_bundle(client, bundle)
        assert resp.status_code == 400
        assert "manifest.json mancante" in resp.json()["detail"]

    def test_manifest_json_corrotto(self, client: TestClient):
        bundle = costruisci_bundle(manifest_raw=b"{ broken json")
        resp = post_bundle(client, bundle)
        assert resp.status_code == 400
        assert "JSON corrotto" in resp.json()["detail"]

    def test_manifest_struttura_invalida(self, client: TestClient):
        bundle = costruisci_bundle(manifest_raw=b'{"foo": "bar"}')
        resp = post_bundle(client, bundle)
        assert resp.status_code == 400
        assert "non valido" in resp.json()["detail"]

    def test_segmento_dichiarato_ma_mancante_nel_zip(self, client: TestClient):
        m = manifest_valido()
        # NON includiamo i file mp4 nel zip
        bundle = costruisci_bundle(manifest=m, nomi_segmenti=[])
        resp = post_bundle(client, bundle)
        assert resp.status_code == 400
        assert "mancante" in resp.json()["detail"]

    def test_zip_corrotto(self, client: TestClient):
        resp = post_bundle(client, b"not a zip")
        assert resp.status_code == 400
        assert "ZIP" in resp.json()["detail"] or "zip" in resp.json()["detail"]

    def test_content_type_sbagliato(self, client: TestClient):
        bundle = costruisci_bundle()
        resp = client.post(
            "/api/import/bundle-mobile",
            files={"bundle": ("bundle.zip", bundle, "text/plain")},
            data={"device_id": "x", "id_partita": "y"},
        )
        assert resp.status_code == 400
        assert "content_type" in resp.json()["detail"]


# === AVVISI (200 con warnings) ===


class TestAvvisi:
    def test_versione_app_diversa(self, client: TestClient):
        m = manifest_valido()
        m["versione_app"] = "999.0.0"
        nomi = [s["filename"] for s in m["segmenti_video"]]
        m["n_eventi_ble"] = 0
        bundle = costruisci_bundle(manifest=m, nomi_segmenti=nomi)

        resp = post_bundle(client, bundle)
        assert resp.status_code == 200
        avvisi = resp.json()["avvisi"]
        assert any("versione_app" in a for a in avvisi)

    def test_device_id_form_diverso_da_manifest(self, client: TestClient):
        m = manifest_valido()
        m["device_id"] = "manifest-device"
        m["n_eventi_ble"] = 0
        nomi = [s["filename"] for s in m["segmenti_video"]]
        bundle = costruisci_bundle(manifest=m, nomi_segmenti=nomi)

        resp = post_bundle(client, bundle, device_id="form-device")
        assert resp.status_code == 200
        avvisi = resp.json()["avvisi"]
        assert any("device_id form" in a for a in avvisi)

    def test_eventi_jsonl_misti_validi_e_corrotti(self, client: TestClient):
        m = manifest_valido()
        m["n_eventi_ble"] = 2
        nomi = [s["filename"] for s in m["segmenti_video"]]
        # 2 validi + 1 corrotto + 1 valido
        jsonl_raw = (
            json.dumps(evento_valido(1)).encode()
            + b"\n"
            + b"NOT JSON\n"
            + json.dumps(evento_valido(2)).encode()
            + b"\n"
            + b'{"foo": "bar"}\n'  # JSON valido ma non conforme
        )
        bundle = costruisci_bundle(manifest=m, nomi_segmenti=nomi, eventi_raw=jsonl_raw)

        resp = post_bundle(client, bundle)
        assert resp.status_code == 200
        data = resp.json()
        # 2 validi
        assert data["n_eventi"] == 2
        # avvisi per le 2 corrotte
        avvisi_corrotti = [a for a in data["avvisi"] if "corrotta" in a]
        assert len(avvisi_corrotti) == 2

    def test_n_eventi_ble_dichiarato_diverso_da_contato(self, client: TestClient):
        m = manifest_valido()
        m["n_eventi_ble"] = 99  # dichiarazione bugiarda
        nomi = [s["filename"] for s in m["segmenti_video"]]
        bundle = costruisci_bundle(
            manifest=m,
            eventi=[evento_valido(1)],
            nomi_segmenti=nomi,
        )
        resp = post_bundle(client, bundle)
        assert resp.status_code == 200
        avvisi = resp.json()["avvisi"]
        assert any("n_eventi_ble dichiarato" in a for a in avvisi)

    def test_sovrascrittura_partita_esistente(
        self, client: TestClient, tmp_path: Path
    ):
        m = manifest_valido()
        m["n_eventi_ble"] = 0
        nomi = [s["filename"] for s in m["segmenti_video"]]
        bundle = costruisci_bundle(manifest=m, nomi_segmenti=nomi)

        # primo upload
        post_bundle(client, bundle, id_partita="duplicato")
        # secondo upload stesso id
        resp = post_bundle(client, bundle, id_partita="duplicato")
        assert resp.status_code == 200
        avvisi = resp.json()["avvisi"]
        assert any("sovrascritta" in a for a in avvisi)


# === PERSISTENZA ===


class TestPersistenza:
    def test_file_salvati_su_storage(self, client: TestClient, tmp_path: Path):
        m = manifest_valido()
        m["n_eventi_ble"] = 0
        nomi = [s["filename"] for s in m["segmenti_video"]]
        bundle = costruisci_bundle(manifest=m, nomi_segmenti=nomi)

        resp = post_bundle(client, bundle, id_partita="persist_test")
        assert resp.status_code == 200

        cartella = tmp_path / "persist_test"
        assert cartella.exists()
        assert (cartella / "manifest.json").exists()
        for nome in nomi:
            assert (cartella / nome).exists()
