"""
Test endpoint di import bundle prodotto dall'app mobile.

Crea bundle ZIP in-memory con manifest + video fake + eventi.jsonl,
li manda all'endpoint, verifica che la partita venga creata correttamente
e gli eventi BLE diventino EventoGrezzo con fonte=DADO_BLE.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


def _manifest_minimo(
    schema_version: str = "1.0",
    n_eventi: int = 0,
) -> dict:
    """Manifest valido base per i test."""
    inizio = datetime(2026, 5, 8, 20, 0, 0, tzinfo=UTC)
    fine = inizio + timedelta(seconds=600)
    return {
        "schema_version": schema_version,
        "partita_id_locale": "test-partita-001",
        "luogo": "Il Gufo · Roma",
        "note": "Test import bundle",
        "device": {
            "modello": "iPhone 11",
            "os": "iOS 17.4",
            "app_version": "1.0.0",
        },
        "registrazione": {
            "ts_inizio": inizio.isoformat(),
            "ts_fine": fine.isoformat(),
            "durata_sec": 600.0,
            "video_file": "video.mp4",
            "video_sha256": None,
            "video_dimensione_byte": 1024,
        },
        "godice": {
            "n_dadi_attaccante": 3,
            "n_dadi_difensore": 3,
            "ble_id_attaccante": ["AA:01", "AA:02", "AA:03"],
            "ble_id_difensore": ["BB:01", "BB:02", "BB:03"],
        },
        "eventi": {
            "n_eventi_totali": n_eventi,
            "eventi_file": "eventi.jsonl",
        },
        "giocatori": [
            {"nome": "Edoardo", "colore": "rosso", "ordine_seduta": 1},
            {"nome": "Alice", "colore": "blu", "ordine_seduta": 2},
        ],
    }


def _eventi_jsonl(eventi: list[dict]) -> str:
    """Serializza una lista di eventi come JSONL."""
    return "\n".join(json.dumps(e) for e in eventi) + ("\n" if eventi else "")


def _crea_bundle(
    manifest: dict,
    video_bytes: bytes = b"FAKE_MP4_BYTES",
    eventi_jsonl: str = "",
) -> bytes:
    """Crea uno ZIP in memoria con i file standard."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("video.mp4", video_bytes)
        zf.writestr("eventi.jsonl", eventi_jsonl)
    buffer.seek(0)
    return buffer.read()


# === Test felici ===


@pytest.mark.asyncio
async def test_import_bundle_minimo(client_test: AsyncClient) -> None:
    """Bundle senza eventi BLE: crea solo partita + giocatori + video."""
    bundle = _crea_bundle(_manifest_minimo())

    risposta = await client_test.post(
        "/api/import/bundle-mobile",
        files={"file": ("partita.zip", bundle, "application/zip")},
    )
    assert risposta.status_code == 201, risposta.text

    body = risposta.json()
    assert "partita_id" in body
    assert body["n_giocatori"] == 2
    assert body["n_eventi_grezzi_creati"] == 0
    assert body["n_eventi_scartati"] == 0
    assert body["durata_video_sec"] >= 0  # ffprobe può fallire su byte fake

    # Verifico che la partita esista davvero
    pid = body["partita_id"]
    r = await client_test.get(f"/api/partite/{pid}")
    assert r.status_code == 200
    partita = r.json()
    assert len(partita["giocatori"]) == 2
    assert partita["luogo"] == "Il Gufo · Roma"
    assert len(partita["video"]) == 1


@pytest.mark.asyncio
async def test_import_bundle_con_eventi_dadi(
    client_test: AsyncClient,
) -> None:
    """Bundle con eventi BLE: vengono importati come EventoGrezzo dado_ble."""
    eventi = [
        {
            "ts": "2026-05-08T20:14:32.451+00:00",
            "tipo": "dado_lanciato",
            "ble_id": "AA:01",
            "ruolo": "attaccante",
            "slot": 1,
            "valore": 5,
        },
        {
            "ts": "2026-05-08T20:14:32.473+00:00",
            "tipo": "dado_lanciato",
            "ble_id": "AA:02",
            "ruolo": "attaccante",
            "slot": 2,
            "valore": 3,
        },
        {
            "ts": "2026-05-08T20:14:33.012+00:00",
            "tipo": "dado_lanciato",
            "ble_id": "BB:01",
            "ruolo": "difensore",
            "slot": 1,
            "valore": 6,
        },
    ]
    bundle = _crea_bundle(
        _manifest_minimo(n_eventi=len(eventi)),
        eventi_jsonl=_eventi_jsonl(eventi),
    )

    risposta = await client_test.post(
        "/api/import/bundle-mobile",
        files={"file": ("partita.zip", bundle, "application/zip")},
    )
    assert risposta.status_code == 201, risposta.text

    body = risposta.json()
    assert body["n_eventi_grezzi_creati"] == 3
    assert body["n_eventi_scartati"] == 0

    # Gli eventi grezzi sono stati creati con fonte DADO_BLE
    pid = body["partita_id"]
    r = await client_test.get(f"/api/partite/{pid}/eventi-grezzi")
    grezzi = r.json()
    assert len(grezzi) == 3
    for e in grezzi:
        assert e["fonte"] == "dado_ble"
        assert e["tipo"] == "dadi_lanciati"
        assert e["dati"]["ruolo"] in {"attaccante", "difensore"}
        assert "ble_id" in e["dati"]
        assert "valore" in e["dati"]
        assert "slot" in e["dati"]


@pytest.mark.asyncio
async def test_import_bundle_eventi_malformati_scartati(
    client_test: AsyncClient,
) -> None:
    """Eventi malformati vengono scartati con nota, non bloccano."""
    eventi_misti = [
        # Evento valido
        {
            "ts": "2026-05-08T20:14:32+00:00",
            "tipo": "dado_lanciato",
            "ble_id": "AA:01",
            "ruolo": "attaccante",
            "slot": 1,
            "valore": 5,
        },
        # Evento valido
        {
            "ts": "2026-05-08T20:14:33+00:00",
            "tipo": "dado_lanciato",
            "ble_id": "BB:01",
            "ruolo": "difensore",
            "slot": 1,
            "valore": 4,
        },
        # Manca campo obbligatorio (ble_id)
        {
            "ts": "2026-05-08T20:14:34+00:00",
            "tipo": "dado_lanciato",
            "ruolo": "attaccante",
            "slot": 1,
            "valore": 6,
        },
        # Tipo non supportato (skip silenzioso)
        {
            "ts": "2026-05-08T20:14:35+00:00",
            "tipo": "dado_collegato",
            "ble_id": "AA:01",
            "ruolo": "attaccante",
            "slot": 1,
        },
    ]

    # Costruisco JSONL "a mano" per includere anche una riga di JSON corrotto
    riga_corrotta = "{questo non è json valido}"
    jsonl = (
        _eventi_jsonl(eventi_misti)
        + riga_corrotta
        + "\n"
        + "\n"  # riga vuota
    )

    bundle = _crea_bundle(
        _manifest_minimo(n_eventi=len(eventi_misti)),
        eventi_jsonl=jsonl,
    )

    risposta = await client_test.post(
        "/api/import/bundle-mobile",
        files={"file": ("partita.zip", bundle, "application/zip")},
    )
    assert risposta.status_code == 201

    body = risposta.json()
    assert body["n_eventi_grezzi_creati"] == 2  # solo i primi 2
    # 1 ble_id mancante + 1 tipo non supportato + 1 json corrotto = 3 scartati
    assert body["n_eventi_scartati"] == 3
    # Il bundle import non blocca su righe vuote/malformate
    assert len(body["note"]) > 0


# === Test errori ===


@pytest.mark.asyncio
async def test_import_bundle_non_zip(client_test: AsyncClient) -> None:
    risposta = await client_test.post(
        "/api/import/bundle-mobile",
        files={"file": ("non.txt", b"hello", "text/plain")},
    )
    assert risposta.status_code == 400


@pytest.mark.asyncio
async def test_import_bundle_zip_corrotto(client_test: AsyncClient) -> None:
    risposta = await client_test.post(
        "/api/import/bundle-mobile",
        files={"file": ("partita.zip", b"NOTAZIP", "application/zip")},
    )
    assert risposta.status_code == 400
    assert "non valido" in risposta.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_bundle_senza_manifest(client_test: AsyncClient) -> None:
    # ZIP valido ma senza manifest.json
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("video.mp4", b"FAKE")
    buffer.seek(0)

    risposta = await client_test.post(
        "/api/import/bundle-mobile",
        files={"file": ("partita.zip", buffer.read(), "application/zip")},
    )
    assert risposta.status_code == 400
    assert "manifest" in risposta.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_bundle_schema_version_non_supportata(
    client_test: AsyncClient,
) -> None:
    bundle = _crea_bundle(_manifest_minimo(schema_version="999.0"))
    risposta = await client_test.post(
        "/api/import/bundle-mobile",
        files={"file": ("partita.zip", bundle, "application/zip")},
    )
    assert risposta.status_code == 400
    assert "schema_version" in risposta.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_bundle_manifest_invalido(
    client_test: AsyncClient,
) -> None:
    # Manifest senza campo obbligatorio (`device`)
    manifest = _manifest_minimo()
    del manifest["device"]
    bundle = _crea_bundle(manifest)

    risposta = await client_test.post(
        "/api/import/bundle-mobile",
        files={"file": ("partita.zip", bundle, "application/zip")},
    )
    assert risposta.status_code == 400
    assert "manifest" in risposta.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_bundle_video_mancante(client_test: AsyncClient) -> None:
    """Manifest dichiara video.mp4 ma il file non c'è nello ZIP."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("manifest.json", json.dumps(_manifest_minimo()))
        zf.writestr("eventi.jsonl", "")
        # niente video
    buffer.seek(0)

    risposta = await client_test.post(
        "/api/import/bundle-mobile",
        files={"file": ("partita.zip", buffer.read(), "application/zip")},
    )
    assert risposta.status_code == 400
    assert "video" in risposta.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_bundle_hash_video_errato(
    client_test: AsyncClient,
) -> None:
    """Se manifest dichiara hash sbagliato, l'import fallisce."""
    manifest = _manifest_minimo()
    manifest["registrazione"]["video_sha256"] = "deadbeef" * 8  # 64 hex
    bundle = _crea_bundle(manifest, video_bytes=b"VIDEO_DIFFERENTE")

    risposta = await client_test.post(
        "/api/import/bundle-mobile",
        files={"file": ("partita.zip", bundle, "application/zip")},
    )
    assert risposta.status_code == 400
    assert "hash" in risposta.json()["detail"].lower()
