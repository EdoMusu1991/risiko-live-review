"""
Test pytest per l'endpoint POST /api/partite/da-bundle/{id_partita}.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import impostazioni
from app.modelli.partita import EventoGrezzo, Partita, Video


def _crea_bundle_su_disco(
    base: Path,
    id_partita: str,
    *,
    eventi: list[dict] | None = None,
    n_segmenti: int = 1,
    versione_app: str = "0.1.0",
) -> Path:
    """Crea un bundle gia' estratto in `base/<id_partita>/` per i test."""
    cartella = base / id_partita
    cartella.mkdir(parents=True, exist_ok=True)

    segmenti = []
    for i in range(n_segmenti):
        filename = f"seg_{i:03d}.mp4"
        # mp4 fittizio (qualche byte, conta solo il file)
        (cartella / filename).write_bytes(b"\x00\x00\x00\x18ftyp" + b"x" * 100)
        segmenti.append(
            {
                "filename": filename,
                "ts_inizio": f"2026-05-12T20:0{i}:00.000+02:00",
                "ts_fine": f"2026-05-12T20:1{i}:00.000+02:00",
                "durata_sec": 600.0,
                "larghezza": 1920,
                "altezza": 1080,
                "fps": 30.0,
            }
        )

    manifest = {
        "versione_app": versione_app,
        "device_id": "test-device-123",
        "ts_inizio_registrazione": "2026-05-12T20:00:00.000+02:00",
        "ts_fine_registrazione": "2026-05-12T22:30:00.000+02:00",
        "segmenti_video": segmenti,
        "n_eventi_ble": len(eventi or []),
    }
    (cartella / "manifest.json").write_text(json.dumps(manifest))

    if eventi is not None:
        with (cartella / "eventi.jsonl").open("w", encoding="utf-8") as f:
            for ev in eventi:
                f.write(json.dumps(ev) + "\n")

    return cartella


@pytest.fixture
def storage_temp(tmp_path: Path, monkeypatch):
    """Reindirizza storage_partite_path e storage_video_path al tmp_path."""
    partite = tmp_path / "partite"
    video = tmp_path / "video"
    partite.mkdir()
    video.mkdir()
    monkeypatch.setattr(impostazioni, "storage_partite_path", partite)
    monkeypatch.setattr(impostazioni, "storage_video_path", video)
    return {"partite": partite, "video": video}


# ============================================================================
# GET /partite/bundle-disponibili
# ============================================================================


async def test_get_bundle_disponibili_vuoto(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    r = await client_test.get("/api/partite/bundle-disponibili")
    assert r.status_code == 200
    assert r.json() == {"bundle": []}


async def test_get_bundle_disponibili_lista_un_bundle(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    _crea_bundle_su_disco(storage_temp["partite"], "abc-123")
    r = await client_test.get("/api/partite/bundle-disponibili")
    assert r.status_code == 200
    bundle = r.json()["bundle"]
    assert len(bundle) == 1
    assert bundle[0]["id_partita"] == "abc-123"
    assert bundle[0]["n_segmenti"] == 1
    assert bundle[0]["n_eventi_dichiarati"] == 0


async def test_get_bundle_disponibili_ordina_per_ts_desc(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
    tmp_path: Path,
) -> None:
    # bundle 1: precedente
    cart1 = storage_temp["partite"] / "vecchio"
    cart1.mkdir()
    (cart1 / "manifest.json").write_text(
        json.dumps(
            {
                "versione_app": "0.1.0",
                "device_id": "x",
                "ts_inizio_registrazione": "2026-01-01T10:00:00+00:00",
                "ts_fine_registrazione": "2026-01-01T12:00:00+00:00",
                "segmenti_video": [],
                "n_eventi_ble": 0,
            }
        )
    )
    # bundle 2: piu' recente
    cart2 = storage_temp["partite"] / "nuovo"
    cart2.mkdir()
    (cart2 / "manifest.json").write_text(
        json.dumps(
            {
                "versione_app": "0.1.0",
                "device_id": "x",
                "ts_inizio_registrazione": "2026-05-12T20:00:00+02:00",
                "ts_fine_registrazione": "2026-05-12T22:00:00+02:00",
                "segmenti_video": [],
                "n_eventi_ble": 0,
            }
        )
    )

    r = await client_test.get("/api/partite/bundle-disponibili")
    bundle = r.json()["bundle"]
    assert len(bundle) == 2
    assert bundle[0]["id_partita"] == "nuovo"
    assert bundle[1]["id_partita"] == "vecchio"


async def test_get_bundle_disponibili_salta_manifest_corrotto(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    cart = storage_temp["partite"] / "corrotto"
    cart.mkdir()
    (cart / "manifest.json").write_text("non json valido {{{")

    r = await client_test.get("/api/partite/bundle-disponibili")
    assert r.json() == {"bundle": []}


# ============================================================================
# POST /partite/da-bundle/{id_partita}
# ============================================================================


async def test_post_promuovi_bundle_minimo(
    client_test: AsyncClient,
    sessione_test: AsyncSession,
    storage_temp: dict[str, Path],
) -> None:
    _crea_bundle_su_disco(storage_temp["partite"], "p-001")

    r = await client_test.post("/api/partite/da-bundle/p-001")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id_partita"] == "p-001"
    assert body["n_video"] == 1
    assert body["n_eventi_importati"] == 0

    # Verifica record SQL creati
    partita = await sessione_test.scalar(
        select(Partita).where(Partita.id == "p-001")
    )
    assert partita is not None
    assert partita.note is not None
    assert "test-device-123" in partita.note

    video_count = (
        await sessione_test.execute(
            select(Video).where(Video.partita_id == "p-001")
        )
    ).all()
    assert len(video_count) == 1


async def test_post_promuovi_bundle_con_eventi(
    client_test: AsyncClient,
    sessione_test: AsyncSession,
    storage_temp: dict[str, Path],
) -> None:
    eventi = [
        {
            "ts_evento": "2026-05-12T20:01:00.000+02:00",
            "tipo": "dadi_lanciati",
            "fonte": "dado_ble",
            "confidenza": 1.0,
            "dati": {"giocatore_id": "g1", "dadi": [4, 5, 6], "tipo_dado": "att"},
        },
        {
            "ts_evento": "2026-05-12T20:01:30.000+02:00",
            "tipo": "attacco_risolto",
            "fonte": "manuale",
            "confidenza": 1.0,
            "dati": {"da": "alaska", "verso": "kamchatka"},
        },
    ]
    _crea_bundle_su_disco(storage_temp["partite"], "p-002", eventi=eventi)

    r = await client_test.post("/api/partite/da-bundle/p-002")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["n_eventi_importati"] == 2
    assert body["n_eventi_scartati"] == 0

    eventi_db = (
        await sessione_test.execute(
            select(EventoGrezzo).where(EventoGrezzo.partita_id == "p-002")
        )
    ).all()
    assert len(eventi_db) == 2


async def test_post_promuovi_bundle_eventi_tipo_sconosciuto_scartati(
    client_test: AsyncClient,
    sessione_test: AsyncSession,
    storage_temp: dict[str, Path],
) -> None:
    eventi = [
        {
            "ts_evento": "2026-05-12T20:01:00+02:00",
            "tipo": "dadi_lanciati",  # OK
            "fonte": "dado_ble",
            "confidenza": 1.0,
            "dati": {},
        },
        {
            "ts_evento": "2026-05-12T20:01:00+02:00",
            "tipo": "evento_inventato_xyz",  # tipo sconosciuto
            "fonte": "dado_ble",
            "confidenza": 1.0,
            "dati": {},
        },
    ]
    _crea_bundle_su_disco(storage_temp["partite"], "p-003", eventi=eventi)

    r = await client_test.post("/api/partite/da-bundle/p-003")
    body = r.json()
    assert body["n_eventi_importati"] == 1
    assert body["n_eventi_scartati"] == 1
    assert any("evento_inventato_xyz" in a for a in body["avvisi"])


async def test_post_promuovi_bundle_404_se_non_esiste(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    r = await client_test.post("/api/partite/da-bundle/non-esiste")
    assert r.status_code == 404


async def test_post_promuovi_bundle_400_manifest_corrotto(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    cart = storage_temp["partite"] / "p-corr"
    cart.mkdir()
    (cart / "manifest.json").write_text("{ json invalido")

    r = await client_test.post("/api/partite/da-bundle/p-corr")
    assert r.status_code == 400


async def test_post_promuovi_bundle_409_se_gia_promosso(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    _crea_bundle_su_disco(storage_temp["partite"], "p-dup")
    # prima promozione: OK
    r = await client_test.post("/api/partite/da-bundle/p-dup")
    assert r.status_code == 201
    # Il bundle viene cancellato dopo la promozione, lo ricreo per simulare
    # un secondo upload con lo stesso id
    _crea_bundle_su_disco(storage_temp["partite"], "p-dup")
    # seconda promozione: 409
    r = await client_test.post("/api/partite/da-bundle/p-dup")
    assert r.status_code == 409


async def test_post_promuovi_bundle_con_luogo_e_note(
    client_test: AsyncClient,
    sessione_test: AsyncSession,
    storage_temp: dict[str, Path],
) -> None:
    _crea_bundle_su_disco(storage_temp["partite"], "p-meta")

    r = await client_test.post(
        "/api/partite/da-bundle/p-meta",
        json={"luogo": "Il Gufo - Roma", "note_extra": "Torneo serale"},
    )
    assert r.status_code == 201

    partita = await sessione_test.scalar(
        select(Partita).where(Partita.id == "p-meta")
    )
    assert partita is not None
    assert partita.luogo == "Il Gufo - Roma"
    assert "Torneo serale" in (partita.note or "")


async def test_post_promuovi_bundle_sposta_video_a_storage_video(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    _crea_bundle_su_disco(
        storage_temp["partite"],
        "p-video",
        n_segmenti=3,
    )

    r = await client_test.post("/api/partite/da-bundle/p-video")
    assert r.status_code == 201
    assert r.json()["n_video"] == 3

    # I 3 file devono essere in storage_video, prefissati con id_partita
    video_files = list(storage_temp["video"].iterdir())
    assert len(video_files) == 3
    for vf in video_files:
        assert vf.name.startswith("p-video__")

    # La cartella bundle deve essere stata pulita dopo la promozione
    assert not (storage_temp["partite"] / "p-video").exists()


async def test_post_promuovi_bundle_eventi_jsonl_assente(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    # n_segmenti=0 + niente eventi_jsonl
    cart = storage_temp["partite"] / "p-vuoto"
    cart.mkdir()
    (cart / "manifest.json").write_text(
        json.dumps(
            {
                "versione_app": "0.1.0",
                "device_id": "x",
                "ts_inizio_registrazione": "2026-05-12T20:00:00+02:00",
                "ts_fine_registrazione": "2026-05-12T20:30:00+02:00",
                "segmenti_video": [],
                "n_eventi_ble": 0,
            }
        )
    )

    r = await client_test.post("/api/partite/da-bundle/p-vuoto")
    assert r.status_code == 201
    body = r.json()
    assert body["n_video"] == 0
    assert body["n_eventi_importati"] == 0
    assert any("eventi.jsonl assente" in a for a in body["avvisi"])


# ============================================================================
# DELETE /partite/bundle/{id_partita}
# ============================================================================


async def test_delete_bundle_esistente_204(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    _crea_bundle_su_disco(storage_temp["partite"], "p-da-scartare")
    r = await client_test.delete("/api/partite/bundle/p-da-scartare")
    assert r.status_code == 204
    assert not (storage_temp["partite"] / "p-da-scartare").exists()


async def test_delete_bundle_inesistente_idempotente_204(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    r = await client_test.delete("/api/partite/bundle/non-esiste")
    assert r.status_code == 204


async def test_delete_bundle_cancella_anche_video_segmenti(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    _crea_bundle_su_disco(storage_temp["partite"], "p-multi", n_segmenti=3)
    cartella = storage_temp["partite"] / "p-multi"
    assert len(list(cartella.iterdir())) >= 4  # manifest + 3 segmenti

    r = await client_test.delete("/api/partite/bundle/p-multi")
    assert r.status_code == 204
    assert not cartella.exists()


# ============================================================================
# DELETE /partite/bundle?older_than_days=N (cleanup vecchi)
# ============================================================================


async def test_delete_bundle_vecchi_cancella_solo_oltre_soglia(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    """Bundle vecchio (2026-01-01) viene cancellato; bundle recente no."""
    # Vecchio: ts_fine 2026-01-01
    cart_v = storage_temp["partite"] / "vecchio"
    cart_v.mkdir()
    (cart_v / "manifest.json").write_text(
        json.dumps(
            {
                "versione_app": "0.1.0",
                "device_id": "x",
                "ts_inizio_registrazione": "2026-01-01T10:00:00+00:00",
                "ts_fine_registrazione": "2026-01-01T12:00:00+00:00",
                "segmenti_video": [],
                "n_eventi_ble": 0,
            }
        )
    )
    # Recente: ts_fine = oggi
    from datetime import datetime, timezone

    oggi_iso = datetime.now(timezone.utc).isoformat()
    cart_r = storage_temp["partite"] / "recente"
    cart_r.mkdir()
    (cart_r / "manifest.json").write_text(
        json.dumps(
            {
                "versione_app": "0.1.0",
                "device_id": "x",
                "ts_inizio_registrazione": oggi_iso,
                "ts_fine_registrazione": oggi_iso,
                "segmenti_video": [],
                "n_eventi_ble": 0,
            }
        )
    )

    r = await client_test.delete("/api/partite/bundle?older_than_days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["n_cancellati"] == 1
    assert "vecchio" in body["ids_cancellati"]
    assert not cart_v.exists()
    assert cart_r.exists()


async def test_delete_bundle_vecchi_validazione_giorni(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    r = await client_test.delete("/api/partite/bundle?older_than_days=0")
    assert r.status_code == 400


async def test_delete_bundle_vecchi_salta_manifest_corrotto(
    client_test: AsyncClient,
    storage_temp: dict[str, Path],
) -> None:
    """Bundle con manifest corrotto NON viene cancellato (safety)."""
    cart = storage_temp["partite"] / "corrotto"
    cart.mkdir()
    (cart / "manifest.json").write_text("{ corrotto")

    r = await client_test.delete("/api/partite/bundle?older_than_days=30")
    assert r.json()["n_cancellati"] == 0
    assert cart.exists()  # NON cancellato per safety
