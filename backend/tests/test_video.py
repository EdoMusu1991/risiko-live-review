"""
Test endpoint video.

Strategia: per i test isolati uso `EstrattoreMockVideo` (no ffprobe richiesto)
e una cartella storage temporanea dedicata. Override delle dependencies
FastAPI per sostituire estrattore + storage path.

Per testare upload uso un piccolo file MP4 generato runtime con ffmpeg
(via fixture) o file fittizi quando il contenuto non importa.
"""

from __future__ import annotations

import tempfile
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.configurazione import get_sessione_db
from app.main import app
from app.storage import (
    EstrattoreMetadataVideo,
    EstrattoreMockVideo,
    MetadataVideo,
    get_estrattore_metadata,
)
from tests.conftest import crea_dati_partita_minima

# === Fixtures specifiche per test video ===


@pytest.fixture
def cartella_storage_test() -> Generator[Path, None, None]:
    """Cartella temporanea per lo storage video durante un test."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def estrattore_mock() -> EstrattoreMockVideo:
    """Mock estrattore con metadata deterministici."""
    return EstrattoreMockVideo(
        MetadataVideo(
            durata_sec=120.5,
            larghezza=1280,
            altezza=720,
            codec="h264",
            ts_creazione=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        )
    )


@pytest.fixture
async def client_video(
    engine_test: object,
    estrattore_mock: EstrattoreMockVideo,
    cartella_storage_test: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Client httpx con override delle dependency:
    - Sessione DB → DB di test in-memory
    - Estrattore → mock
    - Cartella storage → temporanea isolata
    """
    factory = async_sessionmaker(bind=engine_test, expire_on_commit=False)  # type: ignore[arg-type]

    async def _override_get_sessione() -> AsyncGenerator[object, None]:
        async with factory() as sess:
            try:
                yield sess
            except Exception:
                await sess.rollback()
                raise

    def _override_estrattore() -> EstrattoreMetadataVideo:
        return estrattore_mock

    # Patch della cartella storage nelle impostazioni
    from app.configurazione import impostazioni as imp_mod

    monkeypatch.setattr(imp_mod, "storage_video_path", cartella_storage_test)

    app.dependency_overrides[get_sessione_db] = _override_get_sessione
    app.dependency_overrides[get_estrattore_metadata] = _override_estrattore

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# === Helper ===


async def _crea_partita(client: AsyncClient) -> str:
    risposta = await client.post(
        "/api/partite",
        json=crea_dati_partita_minima().model_dump(mode="json"),
    )
    assert risposta.status_code == 201
    return str(risposta.json()["id"])


def _file_video_finto(
    estensione: str = ".mp4",
    contenuto: bytes = b"X" * 1024,
) -> tuple[str, bytes, str]:
    """Tupla (nome, contenuto, mime) per simulare upload."""
    return (f"video{estensione}", contenuto, "video/mp4")


# === Upload ===


@pytest.mark.asyncio
async def test_upload_video_riuscito(client_video: AsyncClient) -> None:
    """Upload base con mock estrattore: il record DB viene creato."""
    pid = await _crea_partita(client_video)

    file_finto = _file_video_finto()
    risposta = await client_video.post(
        f"/api/partite/{pid}/video",
        files={"file": file_finto},
    )
    assert risposta.status_code == 201
    body = risposta.json()
    assert body["nome_originale"] == "video.mp4"
    assert body["durata_sec"] == 120.5
    assert body["codec"] == "h264"
    assert body["risoluzione"] == "1280x720"
    assert body["dimensione_byte"] == 1024


@pytest.mark.asyncio
async def test_upload_video_partita_inesistente(
    client_video: AsyncClient,
) -> None:
    file_finto = _file_video_finto()
    risposta = await client_video.post(
        "/api/partite/non-esiste/video",
        files={"file": file_finto},
    )
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_upload_estensione_non_ammessa(client_video: AsyncClient) -> None:
    pid = await _crea_partita(client_video)

    file_finto = ("script.exe", b"malicious", "application/octet-stream")
    risposta = await client_video.post(
        f"/api/partite/{pid}/video",
        files={"file": file_finto},
    )
    assert risposta.status_code == 400
    assert "estensione" in risposta.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_diverse_estensioni_ammesse(
    client_video: AsyncClient,
) -> None:
    """mp4, mov, m4v, avi, mkv, webm tutti ammessi."""
    pid = await _crea_partita(client_video)
    for ext in [".mov", ".m4v", ".webm", ".mkv"]:
        file_finto = _file_video_finto(estensione=ext)
        risposta = await client_video.post(
            f"/api/partite/{pid}/video",
            files={"file": file_finto},
        )
        assert risposta.status_code == 201, f"Estensione {ext} dovrebbe essere ammessa"


# === Lista e get ===


@pytest.mark.asyncio
async def test_lista_video_vuota(client_video: AsyncClient) -> None:
    pid = await _crea_partita(client_video)
    risposta = await client_video.get(f"/api/partite/{pid}/video")
    assert risposta.status_code == 200
    assert risposta.json() == []


@pytest.mark.asyncio
async def test_lista_video_dopo_upload(client_video: AsyncClient) -> None:
    pid = await _crea_partita(client_video)

    # Upload 3 video
    for i in range(3):
        file_finto = _file_video_finto(contenuto=b"X" * (100 + i))
        risposta = await client_video.post(
            f"/api/partite/{pid}/video",
            files={"file": file_finto},
        )
        assert risposta.status_code == 201

    # Lista
    risposta = await client_video.get(f"/api/partite/{pid}/video")
    assert risposta.status_code == 200
    body = risposta.json()
    assert len(body) == 3


@pytest.mark.asyncio
async def test_get_video_singolo(client_video: AsyncClient) -> None:
    pid = await _crea_partita(client_video)
    upload = await client_video.post(
        f"/api/partite/{pid}/video",
        files={"file": _file_video_finto()},
    )
    vid = upload.json()["id"]

    risposta = await client_video.get(f"/api/partite/{pid}/video/{vid}")
    assert risposta.status_code == 200
    assert risposta.json()["id"] == vid


@pytest.mark.asyncio
async def test_get_video_inesistente(client_video: AsyncClient) -> None:
    pid = await _crea_partita(client_video)
    risposta = await client_video.get(f"/api/partite/{pid}/video/inesistente")
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_lista_video_partita_inesistente(client_video: AsyncClient) -> None:
    risposta = await client_video.get("/api/partite/non-esiste/video")
    assert risposta.status_code == 404


# === Streaming ===


@pytest.mark.asyncio
async def test_stream_video_completo(client_video: AsyncClient) -> None:
    pid = await _crea_partita(client_video)
    contenuto = b"VIDEODATA" * 1000  # 9000 byte

    upload = await client_video.post(
        f"/api/partite/{pid}/video",
        files={"file": ("test.mp4", contenuto, "video/mp4")},
    )
    vid = upload.json()["id"]

    risposta = await client_video.get(f"/api/partite/{pid}/video/{vid}/stream")
    assert risposta.status_code == 200
    assert risposta.headers["content-type"] == "video/mp4"
    assert risposta.headers["accept-ranges"] == "bytes"
    assert risposta.content == contenuto


@pytest.mark.asyncio
async def test_stream_video_range_request(client_video: AsyncClient) -> None:
    pid = await _crea_partita(client_video)
    contenuto = bytes(range(256)) * 10  # 2560 byte deterministici

    upload = await client_video.post(
        f"/api/partite/{pid}/video",
        files={"file": ("test.mp4", contenuto, "video/mp4")},
    )
    vid = upload.json()["id"]

    # Richiesta Range: bytes=10-19
    risposta = await client_video.get(
        f"/api/partite/{pid}/video/{vid}/stream",
        headers={"Range": "bytes=10-19"},
    )
    assert risposta.status_code == 206
    assert risposta.headers["content-range"] == f"bytes 10-19/{len(contenuto)}"
    assert risposta.content == contenuto[10:20]
    assert len(risposta.content) == 10


@pytest.mark.asyncio
async def test_stream_video_range_open_ended(
    client_video: AsyncClient,
) -> None:
    """Range header 'bytes=N-' (senza end) ritorna fino a EOF."""
    pid = await _crea_partita(client_video)
    contenuto = b"abcdefghijklmnopqrstuvwxyz"  # 26 byte

    upload = await client_video.post(
        f"/api/partite/{pid}/video",
        files={"file": ("test.mp4", contenuto, "video/mp4")},
    )
    vid = upload.json()["id"]

    risposta = await client_video.get(
        f"/api/partite/{pid}/video/{vid}/stream",
        headers={"Range": "bytes=20-"},
    )
    assert risposta.status_code == 206
    assert risposta.content == b"uvwxyz"


@pytest.mark.asyncio
async def test_stream_video_range_invalido(client_video: AsyncClient) -> None:
    pid = await _crea_partita(client_video)
    upload = await client_video.post(
        f"/api/partite/{pid}/video",
        files={"file": _file_video_finto(contenuto=b"X" * 100)},
    )
    vid = upload.json()["id"]

    # Range fuori range
    risposta = await client_video.get(
        f"/api/partite/{pid}/video/{vid}/stream",
        headers={"Range": "bytes=500-999"},
    )
    assert risposta.status_code == 416

    # Range malformato
    risposta = await client_video.get(
        f"/api/partite/{pid}/video/{vid}/stream",
        headers={"Range": "abc-def"},
    )
    assert risposta.status_code == 416


# === Eliminazione ===


@pytest.mark.asyncio
async def test_elimina_video(
    client_video: AsyncClient,
    cartella_storage_test: Path,
) -> None:
    pid = await _crea_partita(client_video)
    upload = await client_video.post(
        f"/api/partite/{pid}/video",
        files={"file": _file_video_finto()},
    )
    vid = upload.json()["id"]

    # Verifico che il file esista nella cartella storage
    file_in_storage = list(cartella_storage_test.glob("*.mp4"))
    assert len(file_in_storage) == 1

    # Elimino
    risposta = await client_video.delete(f"/api/partite/{pid}/video/{vid}")
    assert risposta.status_code == 204

    # File rimosso da DB e da filesystem
    get_risposta = await client_video.get(f"/api/partite/{pid}/video/{vid}")
    assert get_risposta.status_code == 404
    assert list(cartella_storage_test.glob("*.mp4")) == []


@pytest.mark.asyncio
async def test_elimina_video_inesistente(client_video: AsyncClient) -> None:
    pid = await _crea_partita(client_video)
    risposta = await client_video.delete(f"/api/partite/{pid}/video/non-esiste")
    assert risposta.status_code == 404


@pytest.mark.asyncio
async def test_elimina_partita_pulisce_video(
    client_video: AsyncClient,
    cartella_storage_test: Path,
) -> None:
    """Eliminando una partita, i suoi video vengono rimossi dal filesystem."""
    pid = await _crea_partita(client_video)

    # Carico 2 video
    for _ in range(2):
        await client_video.post(
            f"/api/partite/{pid}/video",
            files={"file": _file_video_finto()},
        )

    file_iniziali = list(cartella_storage_test.glob("*.mp4"))
    assert len(file_iniziali) == 2

    # Elimino la partita
    risposta = await client_video.delete(f"/api/partite/{pid}")
    assert risposta.status_code == 204

    # I file video sono stati puliti
    assert list(cartella_storage_test.glob("*.mp4")) == []
