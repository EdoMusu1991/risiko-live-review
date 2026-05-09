"""
Test del servizio CV (orchestratore inferenza).

Usa `ClientCVMock` (no Roboflow richiesto) e gli stessi mock di
estrazione/raddrizzamento: il test e' fully deterministico e veloce.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import (
    EventoValidato,
    GiocatorePartita,
    InferenzaCV,
    Partita,
    StatoReview,
    TipoEvento,
    Video,
)
from app.servizi.cv_servizio import (
    ClientCVError,
    ClientCVMock,
    ClientCVNonConfiguratoError,
    ClientCVRoboflow,
    DetectionCV,
    ServizioCV,
)
from app.servizi.estrazione_frame_servizio import ServizioEstrazioneFrame
from app.servizi.raddrizzamento_servizio import (
    OmografiaNonCalibrataError,
    ServizioRaddrizzamento,
)
from app.storage.estrattore_frame import EstrattoreFrameMock
from app.storage.raddrizzatore import RaddrizzatoreMock
from app.storage.storage_frame import StorageFrame

# === Fixtures ===


@pytest.fixture
def storage(tmp_path: Path) -> StorageFrame:
    return StorageFrame(tmp_path / "frames")


@pytest.fixture
def video_finto(tmp_path: Path) -> Path:
    p = tmp_path / "video.mp4"
    p.write_bytes(b"fake-mp4")
    return p


@pytest.fixture
def servizio_cv(storage: StorageFrame) -> ServizioCV:
    estrazione = ServizioEstrazioneFrame(
        storage=storage, estrattore=EstrattoreFrameMock(),
    )
    raddrizzamento = ServizioRaddrizzamento(
        servizio_estrazione=estrazione,
        storage=storage,
        raddrizzatore=RaddrizzatoreMock(),
    )
    return ServizioCV(
        servizio_raddrizzamento=raddrizzamento,
        client_cv=ClientCVMock(versione="test-mock-v1"),
    )


# === Helpers ===


async def _crea_partita_con_evento(
    db: AsyncSession, video_path: Path,
) -> tuple[Partita, EventoValidato]:
    ts = datetime(2026, 5, 9, 21, 0, tzinfo=UTC)
    p = Partita(data_inizio=ts, stato_review=StatoReview.GREZZA)
    db.add(p)
    await db.flush()
    db.add_all([
        GiocatorePartita(partita_id=p.id, nome="Edo", colore="rosso", ordine_seduta=1),
        GiocatorePartita(partita_id=p.id, nome="Marco", colore="blu", ordine_seduta=2),
        Video(
            partita_id=p.id,
            file_path=str(video_path),
            nome_originale="v.mp4",
            ts_inizio=ts,
            durata_sec=600.0,
            codec="h264",
            risoluzione="1920x1080",
            dimensione_byte=1000,
        ),
    ])
    ev = EventoValidato(
        partita_id=p.id,
        ts_evento=ts + timedelta(seconds=60),
        tipo=TipoEvento.ATTACCO_RISOLTO,
        dati={"giocatore_id": "fake", "da": "x", "a": "y",
              "dadi_attaccante": [6], "dadi_difensore": [3]},
        evento_grezzo_id=None,
        validato_da="test",
    )
    db.add(ev)
    await db.commit()
    return p, ev


# === ClientCVMock ===


@pytest.mark.asyncio
async def test_mock_inferisci_genera_detection_deterministiche(
    tmp_path: Path,
) -> None:
    frame = tmp_path / "f.jpg"
    frame.write_bytes(b"fake")

    mock = ClientCVMock(n_detection_per_frame=5)
    det1 = await mock.inferisci(frame)
    det2 = await mock.inferisci(frame)

    # Deterministico: stesso path → stessa output
    assert len(det1) == 5
    assert det1 == det2


@pytest.mark.asyncio
async def test_mock_inferisci_path_diversi_output_diversi(
    tmp_path: Path,
) -> None:
    f1 = tmp_path / "uno.jpg"
    f2 = tmp_path / "due.jpg"
    f1.write_bytes(b"x")
    f2.write_bytes(b"x")

    mock = ClientCVMock()
    det1 = await mock.inferisci(f1)
    det2 = await mock.inferisci(f2)

    # Path diversi → seed diversi → detection diverse
    assert det1 != det2


@pytest.mark.asyncio
async def test_mock_inferisci_frame_inesistente_solleva(tmp_path: Path) -> None:
    mock = ClientCVMock()
    with pytest.raises(ClientCVError, match="non trovato"):
        await mock.inferisci(tmp_path / "non-esiste.jpg")


def test_mock_versione_modello() -> None:
    mock = ClientCVMock(versione="custom-v2")
    assert mock.versione_modello == "custom-v2"


# === ServizioCV ===


@pytest.mark.asyncio
async def test_servizio_analizza_evento_pipeline_completa(
    sessione_test: AsyncSession,
    servizio_cv: ServizioCV,
    storage: StorageFrame,
    video_finto: Path,
) -> None:
    p, ev = await _crea_partita_con_evento(sessione_test, video_finto)

    # Calibra preventivamente
    raddr = servizio_cv._raddrizzamento  # type: ignore[reportPrivateUsage]
    await raddr.calibra(sessione_test, p.id)

    # Esegue pipeline
    inferenze = await servizio_cv.analizza_evento(
        sessione_test, p.id, ev.id,
    )

    assert len(inferenze) == 5  # default mock
    # Tutte legate all'evento giusto
    for inf in inferenze:
        assert inf.partita_id == p.id
        assert inf.evento_validato_id == ev.id
        assert inf.modello_versione == "test-mock-v1"
        assert inf.frame_hash is not None
        assert len(inf.frame_hash) == 16  # SHA-256 troncato

    # Ritrova nel DB
    risultato = await sessione_test.execute(
        select(InferenzaCV).where(InferenzaCV.partita_id == p.id)
    )
    persistite = list(risultato.scalars().all())
    assert len(persistite) == 5


@pytest.mark.asyncio
async def test_servizio_analizza_evento_senza_calibrazione_solleva(
    sessione_test: AsyncSession,
    servizio_cv: ServizioCV,
    video_finto: Path,
) -> None:
    p, ev = await _crea_partita_con_evento(sessione_test, video_finto)

    # NESSUNA calibrazione
    with pytest.raises(OmografiaNonCalibrataError):
        await servizio_cv.analizza_evento(sessione_test, p.id, ev.id)


@pytest.mark.asyncio
async def test_servizio_analizza_tutti_eventi(
    sessione_test: AsyncSession,
    servizio_cv: ServizioCV,
    video_finto: Path,
) -> None:
    p, _ev1 = await _crea_partita_con_evento(sessione_test, video_finto)
    ts = datetime(2026, 5, 9, 21, 0, tzinfo=UTC)

    # Aggiungi 2 altri eventi
    sessione_test.add_all([
        EventoValidato(
            partita_id=p.id,
            ts_evento=ts + timedelta(seconds=120),
            tipo=TipoEvento.ATTACCO_RISOLTO,
            dati={"giocatore_id": "fake", "da": "x", "a": "y",
                  "dadi_attaccante": [5], "dadi_difensore": [2]},
            evento_grezzo_id=None,
            validato_da="test",
        ),
        EventoValidato(
            partita_id=p.id,
            ts_evento=ts + timedelta(seconds=180),
            tipo=TipoEvento.ATTACCO_RISOLTO,
            dati={"giocatore_id": "fake", "da": "x", "a": "y",
                  "dadi_attaccante": [4], "dadi_difensore": [1]},
            evento_grezzo_id=None,
            validato_da="test",
        ),
    ])
    await sessione_test.commit()

    raddr = servizio_cv._raddrizzamento  # type: ignore[reportPrivateUsage]
    await raddr.calibra(sessione_test, p.id)

    riepilogo = await servizio_cv.analizza_tutti_eventi(sessione_test, p.id)

    assert riepilogo["n_eventi_totali"] == 3
    assert riepilogo["n_riusciti"] == 3
    assert riepilogo["n_falliti"] == 0
    assert riepilogo["n_inferenze_totali"] == 15  # 5 mock detection x 3 eventi
    assert riepilogo["modello_versione"] == "test-mock-v1"


@pytest.mark.asyncio
async def test_servizio_analizza_tutti_senza_calibrazione_torna_falliti(
    sessione_test: AsyncSession,
    servizio_cv: ServizioCV,
    video_finto: Path,
) -> None:
    p, _ = await _crea_partita_con_evento(sessione_test, video_finto)

    # Niente calibrazione
    riepilogo = await servizio_cv.analizza_tutti_eventi(sessione_test, p.id)

    assert riepilogo["n_riusciti"] == 0
    assert riepilogo["n_falliti"] == 1
    assert riepilogo["n_inferenze_totali"] == 0
    assert isinstance(riepilogo["falliti"], list)


# === ClientCVRoboflow (placeholder) ===


def test_roboflow_richiede_api_key() -> None:
    with pytest.raises(ClientCVNonConfiguratoError, match="api_key"):
        ClientCVRoboflow(api_key="", project_endpoint="http://x")


def test_roboflow_richiede_endpoint() -> None:
    with pytest.raises(ClientCVNonConfiguratoError, match="endpoint"):
        ClientCVRoboflow(api_key="key", project_endpoint="")


def test_roboflow_versione_dedotta_da_endpoint() -> None:
    c = ClientCVRoboflow(
        api_key="key",
        project_endpoint="https://detect.roboflow.com/risiko-pieces/3",
    )
    assert c.versione_modello == "roboflow-risiko-pieces-v3"


def test_roboflow_versione_esplicita_priorita() -> None:
    c = ClientCVRoboflow(
        api_key="key",
        project_endpoint="https://detect.roboflow.com/risiko/3",
        versione="custom-tag-v9",
    )
    assert c.versione_modello == "custom-tag-v9"


@pytest.mark.asyncio
async def test_roboflow_inferisci_e_placeholder(tmp_path: Path) -> None:
    """Finche' il modello non e' addestrato, deve sollevare NotImplementedError."""
    c = ClientCVRoboflow(
        api_key="key",
        project_endpoint="https://detect.roboflow.com/risiko/1",
    )
    frame = tmp_path / "f.jpg"
    frame.write_bytes(b"x")
    with pytest.raises(NotImplementedError):
        await c.inferisci(frame)


# === DetectionCV ===


def test_detection_cv_e_immutabile() -> None:
    d = DetectionCV(
        territorio="x", colore="r", tipo_pedina_dominante="carro_piccolo",
        n_armate_stimate=1, bbox=(0, 0, 10, 10), confidence=0.9,
        scomposizione=[],
    )
    with pytest.raises(AttributeError):
        d.confidence = 0.5  # type: ignore[misc]
