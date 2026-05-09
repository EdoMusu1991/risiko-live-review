"""
Test del servizio di estrazione frame da video.

Usano `EstrattoreFrameMock` per evitare di dipendere da ffmpeg
installato sull'host di test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import (
    EventoValidato,
    GiocatorePartita,
    Partita,
    StatoReview,
    TipoEvento,
    Video,
)
from app.servizi.estrazione_frame_servizio import (
    EventoFuoriDuratavideoError,
    EventoSenzaVideoError,
    ServizioEstrazioneFrame,
)
from app.storage.estrattore_frame import (
    EstrattoreFrameMock,
    FfmpegNonDisponibileError,
    TimestampFuoriRangeError,
)
from app.storage.storage_frame import StorageFrame

# === Fixtures ===


@pytest.fixture
def storage_frame(tmp_path: Path) -> StorageFrame:
    """StorageFrame su tmp_path (auto-pulito da pytest)."""
    return StorageFrame(tmp_path / "frames")


@pytest.fixture
def video_finto(tmp_path: Path) -> Path:
    """File 'video' fasullo: il mock non lo legge davvero, basta che esista."""
    p = tmp_path / "video_finto.mp4"
    p.write_bytes(b"non-un-vero-mp4")
    return p


@pytest.fixture
def servizio(storage_frame: StorageFrame) -> ServizioEstrazioneFrame:
    return ServizioEstrazioneFrame(
        storage=storage_frame,
        estrattore=EstrattoreFrameMock(),
    )


# === Helper: crea partita + video + evento ===


async def _crea_partita_con_video(
    db: AsyncSession,
    percorso_video: Path,
    *,
    ts_inizio: datetime | None = None,
    durata_sec: float = 600.0,
) -> tuple[Partita, Video]:
    ts_inizio = ts_inizio or datetime(2026, 5, 7, 21, 0, tzinfo=UTC)

    p = Partita(
        data_inizio=ts_inizio,
        stato_review=StatoReview.GREZZA,
    )
    db.add(p)
    await db.flush()
    db.add(GiocatorePartita(partita_id=p.id, nome="Edo", colore="rosso", ordine_seduta=1))
    db.add(GiocatorePartita(partita_id=p.id, nome="Marco", colore="blu", ordine_seduta=2))

    video = Video(
        partita_id=p.id,
        file_path=str(percorso_video),
        nome_originale="video.mp4",
        ts_inizio=ts_inizio,
        durata_sec=durata_sec,
        codec="h264",
        risoluzione="1920x1080",
        dimensione_byte=1000,
    )
    db.add(video)
    await db.commit()
    return p, video


async def _aggiungi_evento(
    db: AsyncSession,
    partita_id: str,
    *,
    secondi_dopo_inizio: float,
    ts_inizio: datetime | None = None,
) -> EventoValidato:
    ts_inizio = ts_inizio or datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    ev = EventoValidato(
        partita_id=partita_id,
        ts_evento=ts_inizio + timedelta(seconds=secondi_dopo_inizio),
        tipo=TipoEvento.ATTACCO_RISOLTO,
        dati={"giocatore_id": "fake", "da": "kamchatka", "a": "alaska",
              "dadi_attaccante": [6], "dadi_difensore": [3]},
        evento_grezzo_id=None,
        validato_da="test",
    )
    db.add(ev)
    await db.commit()
    return ev


# === Test estrazione per evento ===


@pytest.mark.asyncio
async def test_estrai_per_evento_estrae_e_salva_in_cache(
    sessione_test: AsyncSession,
    servizio: ServizioEstrazioneFrame,
    video_finto: Path,
) -> None:
    p, _ = await _crea_partita_con_video(sessione_test, video_finto)
    ev = await _aggiungi_evento(sessione_test, p.id, secondi_dopo_inizio=120.0)

    percorso = await servizio.estrai_per_evento(sessione_test, p.id, ev.id)

    assert percorso.exists()
    assert percorso.stat().st_size > 0
    assert percorso.suffix == ".jpg"


@pytest.mark.asyncio
async def test_estrai_per_evento_usa_cache_seconda_chiamata(
    sessione_test: AsyncSession,
    servizio: ServizioEstrazioneFrame,
    storage_frame: StorageFrame,
    video_finto: Path,
) -> None:
    p, _ = await _crea_partita_con_video(sessione_test, video_finto)
    ev = await _aggiungi_evento(sessione_test, p.id, secondi_dopo_inizio=60.0)

    # Prima chiamata: estrae
    percorso1 = await servizio.estrai_per_evento(sessione_test, p.id, ev.id)
    mtime1 = percorso1.stat().st_mtime_ns

    # Seconda chiamata: dovrebbe usare la cache (mtime invariato)
    percorso2 = await servizio.estrai_per_evento(sessione_test, p.id, ev.id)
    mtime2 = percorso2.stat().st_mtime_ns

    assert percorso1 == percorso2
    assert mtime1 == mtime2  # cache hit, file non riscritto


@pytest.mark.asyncio
async def test_estrai_per_evento_forza_riestrae(
    sessione_test: AsyncSession,
    storage_frame: StorageFrame,
    video_finto: Path,
) -> None:
    estrattore_contatore = ContatoreEstrazioni()
    servizio = ServizioEstrazioneFrame(
        storage=storage_frame,
        estrattore=estrattore_contatore,
    )

    p, _ = await _crea_partita_con_video(sessione_test, video_finto)
    ev = await _aggiungi_evento(sessione_test, p.id, secondi_dopo_inizio=30.0)

    await servizio.estrai_per_evento(sessione_test, p.id, ev.id)
    await servizio.estrai_per_evento(sessione_test, p.id, ev.id, forza=True)

    # 2 estrazioni effettive, anche se la cache ce l'aveva alla seconda
    assert estrattore_contatore.n_chiamate == 2


@pytest.mark.asyncio
async def test_estrai_per_evento_partita_senza_video(
    sessione_test: AsyncSession,
    servizio: ServizioEstrazioneFrame,
) -> None:
    # Partita SENZA video associato
    p = Partita(
        data_inizio=datetime(2026, 5, 7, 21, 0, tzinfo=UTC),
        stato_review=StatoReview.GREZZA,
    )
    sessione_test.add(p)
    await sessione_test.flush()
    sessione_test.add(GiocatorePartita(partita_id=p.id, nome="A", colore="rosso", ordine_seduta=1))
    sessione_test.add(GiocatorePartita(partita_id=p.id, nome="B", colore="blu", ordine_seduta=2))
    ev = EventoValidato(
        partita_id=p.id,
        ts_evento=datetime(2026, 5, 7, 21, 5, tzinfo=UTC),
        tipo=TipoEvento.ATTACCO_RISOLTO,
        dati={"giocatore_id": "fake", "da": "x", "a": "y",
              "dadi_attaccante": [6], "dadi_difensore": [3]},
        evento_grezzo_id=None,
        validato_da="test",
    )
    sessione_test.add(ev)
    await sessione_test.commit()

    with pytest.raises(EventoSenzaVideoError):
        await servizio.estrai_per_evento(sessione_test, p.id, ev.id)


@pytest.mark.asyncio
async def test_estrai_per_evento_oltre_durata_video(
    sessione_test: AsyncSession,
    servizio: ServizioEstrazioneFrame,
    video_finto: Path,
) -> None:
    # Video di soli 60 secondi
    p, _ = await _crea_partita_con_video(
        sessione_test, video_finto, durata_sec=60.0
    )
    # Evento al secondo 120 (oltre la durata)
    ev = await _aggiungi_evento(sessione_test, p.id, secondi_dopo_inizio=120.0)

    with pytest.raises(EventoFuoriDuratavideoError):
        await servizio.estrai_per_evento(sessione_test, p.id, ev.id)


@pytest.mark.asyncio
async def test_estrai_per_evento_propaga_ffmpeg_mancante(
    sessione_test: AsyncSession,
    storage_frame: StorageFrame,
    video_finto: Path,
) -> None:
    servizio_rotto = ServizioEstrazioneFrame(
        storage=storage_frame,
        estrattore=EstrattoreFrameMock(simula_errore_ffmpeg=True),
    )
    p, _ = await _crea_partita_con_video(sessione_test, video_finto)
    ev = await _aggiungi_evento(sessione_test, p.id, secondi_dopo_inizio=10.0)

    with pytest.raises(FfmpegNonDisponibileError):
        await servizio_rotto.estrai_per_evento(sessione_test, p.id, ev.id)


# === Test estrazione per offset arbitrario ===


@pytest.mark.asyncio
async def test_estrai_per_offset_funziona(
    sessione_test: AsyncSession,
    servizio: ServizioEstrazioneFrame,
    video_finto: Path,
) -> None:
    p, _ = await _crea_partita_con_video(sessione_test, video_finto)

    percorso = await servizio.estrai_per_offset(
        sessione_test, p.id, 45.0, "snapshot-45s"
    )
    assert percorso.exists()
    assert "snapshot-45s" in str(percorso)


@pytest.mark.asyncio
async def test_estrai_per_offset_negativo(
    sessione_test: AsyncSession,
    servizio: ServizioEstrazioneFrame,
    video_finto: Path,
) -> None:
    p, _ = await _crea_partita_con_video(sessione_test, video_finto)
    with pytest.raises(TimestampFuoriRangeError):
        await servizio.estrai_per_offset(sessione_test, p.id, -1.0, "test")


# === Test pulizia ===


@pytest.mark.asyncio
async def test_cancella_partita_pulisce_cache(
    sessione_test: AsyncSession,
    servizio: ServizioEstrazioneFrame,
    storage_frame: StorageFrame,
    video_finto: Path,
) -> None:
    p, _ = await _crea_partita_con_video(sessione_test, video_finto)
    ev1 = await _aggiungi_evento(sessione_test, p.id, secondi_dopo_inizio=10.0)
    ev2 = await _aggiungi_evento(sessione_test, p.id, secondi_dopo_inizio=20.0)

    await servizio.estrai_per_evento(sessione_test, p.id, ev1.id)
    await servizio.estrai_per_evento(sessione_test, p.id, ev2.id)

    n = storage_frame.cancella_partita(p.id)
    assert n == 2
    assert storage_frame.lista_frame(p.id) == []


# === Helper interno ===


class ContatoreEstrazioni(EstrattoreFrameMock):
    """Mock che conta le chiamate, per verificare che la cache funzioni."""

    def __init__(self) -> None:
        super().__init__()
        self.n_chiamate = 0

    async def estrai(
        self,
        percorso_video: Path,
        offset_sec: float,
        percorso_output: Path,
    ) -> None:
        self.n_chiamate += 1
        await super().estrai(percorso_video, offset_sec, percorso_output)
