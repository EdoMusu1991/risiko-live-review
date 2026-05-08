"""
Test del modulo `storage` (estrattore metadata + storage filesystem).

Test unitari, indipendenti dall'API HTTP.
"""

import asyncio
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.storage import (
    EstrattoreFfprobe,
    EstrattoreMockVideo,
    MetadataVideo,
    StorageVideo,
    StorageVideoError,
    pulisci_cartella_storage,
)
from app.storage.estrattore_metadata import (
    EstrazioneMetadataError,
    VideoCorrottoError,
)

# === Fixtures ===


def _genera_video_test(percorso: Path, durata_sec: int = 1) -> Path:
    """
    Genera un video MP4 valido di N secondi con ffmpeg.
    Usato per testare l'estrattore reale.
    """
    cmd = [
        "ffmpeg",
        "-y",  # sovrascrivi se esiste
        "-f", "lavfi",
        "-i", f"testsrc=duration={durata_sec}:size=320x240:rate=10",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-loglevel", "error",
        str(percorso),
    ]
    proc = asyncio.run(_run_subprocess(cmd))
    if proc != 0:
        raise RuntimeError("ffmpeg ha fallito nel generare il video di test")
    return percorso


async def _run_subprocess(cmd: list[str]) -> int:
    p = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    await p.communicate()
    return p.returncode or 0


@pytest.fixture
def cartella_temporanea() -> Path:
    """Cartella temporanea pulita per ogni test."""
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def video_di_test(cartella_temporanea: Path) -> Path:
    """Genera un piccolo video MP4 di 1 secondo per i test."""
    percorso = cartella_temporanea / "video_test.mp4"
    return _genera_video_test(percorso, durata_sec=1)


# === EstrattoreMockVideo ===


@pytest.mark.asyncio
async def test_mock_estrattore_ritorna_metadata_default(
    cartella_temporanea: Path,
) -> None:
    file_finto = cartella_temporanea / "fake.mp4"
    file_finto.write_bytes(b"not a real video")

    estrattore = EstrattoreMockVideo()
    metadata = await estrattore.estrai(file_finto)

    assert metadata.durata_sec == 600.0
    assert metadata.larghezza == 1920
    assert metadata.altezza == 1080
    assert metadata.codec == "h264"
    assert metadata.risoluzione == "1920x1080"


@pytest.mark.asyncio
async def test_mock_estrattore_metadata_personalizzati(
    cartella_temporanea: Path,
) -> None:
    file_finto = cartella_temporanea / "fake.mp4"
    file_finto.write_bytes(b"x")

    metadata_custom = MetadataVideo(
        durata_sec=123.45,
        larghezza=640,
        altezza=480,
        codec="hevc",
        ts_creazione=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    estrattore = EstrattoreMockVideo(metadata_custom)
    risultato = await estrattore.estrai(file_finto)
    assert risultato == metadata_custom


@pytest.mark.asyncio
async def test_mock_estrattore_file_inesistente_solleva(
    cartella_temporanea: Path,
) -> None:
    estrattore = EstrattoreMockVideo()
    with pytest.raises(EstrazioneMetadataError):
        await estrattore.estrai(cartella_temporanea / "non_esiste.mp4")


# === EstrattoreFfprobe (richiede ffprobe installato) ===


@pytest.mark.asyncio
async def test_ffprobe_estrae_metadata_da_video_reale(
    video_di_test: Path,
) -> None:
    estrattore = EstrattoreFfprobe()
    metadata = await estrattore.estrai(video_di_test)

    # Video generato 320x240 a 1 secondo, codec h264
    assert 0.9 <= metadata.durata_sec <= 1.5
    assert metadata.larghezza == 320
    assert metadata.altezza == 240
    assert metadata.codec == "h264"


@pytest.mark.asyncio
async def test_ffprobe_file_inesistente_solleva(cartella_temporanea: Path) -> None:
    estrattore = EstrattoreFfprobe()
    with pytest.raises(EstrazioneMetadataError):
        await estrattore.estrai(cartella_temporanea / "manca.mp4")


@pytest.mark.asyncio
async def test_ffprobe_file_corrotto_solleva(cartella_temporanea: Path) -> None:
    fake = cartella_temporanea / "corrotto.mp4"
    fake.write_bytes(b"not a video at all" * 100)

    estrattore = EstrattoreFfprobe()
    with pytest.raises(VideoCorrottoError):
        await estrattore.estrai(fake)


# === StorageVideo ===


@pytest.mark.asyncio
async def test_storage_crea_cartella_se_manca(cartella_temporanea: Path) -> None:
    sotto = cartella_temporanea / "non_esiste"
    StorageVideo(sotto)
    assert sotto.exists()
    assert sotto.is_dir()


@pytest.mark.asyncio
async def test_storage_elimina_file(cartella_temporanea: Path) -> None:
    storage = StorageVideo(cartella_temporanea)
    file_target = cartella_temporanea / "x.mp4"
    file_target.write_bytes(b"data")
    storage.elimina(file_target)
    assert not file_target.exists()


@pytest.mark.asyncio
async def test_storage_elimina_file_inesistente_no_solleva(
    cartella_temporanea: Path,
) -> None:
    storage = StorageVideo(cartella_temporanea)
    # Non deve sollevare per missing_ok=True
    storage.elimina(cartella_temporanea / "non_esiste.mp4")


@pytest.mark.asyncio
async def test_storage_elimina_path_esterno_solleva(
    cartella_temporanea: Path,
) -> None:
    """Tentativo di eliminare file fuori dalla cartella radice (path traversal)."""
    storage = StorageVideo(cartella_temporanea / "interno")

    fuori = cartella_temporanea / "fuori.mp4"
    fuori.write_bytes(b"x")

    with pytest.raises(StorageVideoError):
        storage.elimina(fuori)
    # Il file fuori non deve essere stato toccato
    assert fuori.exists()


@pytest.mark.asyncio
async def test_storage_stream_lettura_completa(cartella_temporanea: Path) -> None:
    storage = StorageVideo(cartella_temporanea)
    contenuto = b"X" * 5_000_000  # 5 MB
    file_target = cartella_temporanea / "video.mp4"
    file_target.write_bytes(contenuto)

    raccolto = bytearray()
    async for chunk in storage.stream_lettura(file_target):
        raccolto.extend(chunk)

    assert bytes(raccolto) == contenuto


@pytest.mark.asyncio
async def test_storage_stream_lettura_con_offset(cartella_temporanea: Path) -> None:
    storage = StorageVideo(cartella_temporanea)
    contenuto = bytes(range(256)) * 100  # 25600 byte deterministici
    file_target = cartella_temporanea / "video.mp4"
    file_target.write_bytes(contenuto)

    raccolto = bytearray()
    async for chunk in storage.stream_lettura(file_target, offset=10, lunghezza=50):
        raccolto.extend(chunk)

    assert len(raccolto) == 50
    assert bytes(raccolto) == contenuto[10:60]


@pytest.mark.asyncio
async def test_pulisci_cartella_storage(cartella_temporanea: Path) -> None:
    target = cartella_temporanea / "storage"
    target.mkdir()
    (target / "file1.mp4").write_bytes(b"x")
    (target / "file2.mp4").write_bytes(b"y")

    pulisci_cartella_storage(target)

    assert target.exists()
    assert list(target.iterdir()) == []
