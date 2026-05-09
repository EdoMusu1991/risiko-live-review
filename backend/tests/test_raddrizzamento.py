"""
Test del servizio di raddrizzamento prospettico.

Usa `RaddrizzatoreMock` per evitare dipendenza da opencv. Verifica
l'orchestrazione applicativa: cache della matrice, riuso del frame raw,
gestione errori.
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
from app.servizi.estrazione_frame_servizio import ServizioEstrazioneFrame
from app.servizi.raddrizzamento_servizio import (
    OmografiaNonCalibrataError,
    ServizioRaddrizzamento,
)
from app.storage.estrattore_frame import EstrattoreFrameMock
from app.storage.raddrizzatore import (
    CalibrazioneFallitaError,
    OpencvNonDisponibileError,
    RaddrizzatoreMock,
)
from app.storage.storage_frame import StorageFrame

# === Fixtures ===


@pytest.fixture
def storage(tmp_path: Path) -> StorageFrame:
    return StorageFrame(tmp_path / "frames")


@pytest.fixture
def video_finto(tmp_path: Path) -> Path:
    p = tmp_path / "video_finto.mp4"
    p.write_bytes(b"non-un-vero-mp4")
    return p


@pytest.fixture
def servizio_raddrizzamento(
    storage: StorageFrame,
) -> ServizioRaddrizzamento:
    estrazione = ServizioEstrazioneFrame(
        storage=storage,
        estrattore=EstrattoreFrameMock(),
    )
    return ServizioRaddrizzamento(
        servizio_estrazione=estrazione,
        storage=storage,
        raddrizzatore=RaddrizzatoreMock(),
    )


# === Helper ===


async def _crea_partita_con_video_e_evento(
    db: AsyncSession,
    percorso_video: Path,
) -> tuple[Partita, EventoValidato]:
    ts = datetime(2026, 5, 7, 21, 0, tzinfo=UTC)
    p = Partita(data_inizio=ts, stato_review=StatoReview.GREZZA)
    db.add(p)
    await db.flush()
    db.add(GiocatorePartita(partita_id=p.id, nome="A", colore="rosso", ordine_seduta=1))
    db.add(GiocatorePartita(partita_id=p.id, nome="B", colore="blu", ordine_seduta=2))
    db.add(Video(
        partita_id=p.id,
        file_path=str(percorso_video),
        nome_originale="v.mp4",
        ts_inizio=ts,
        durata_sec=600.0,
        codec="h264",
        risoluzione="1920x1080",
        dimensione_byte=1000,
    ))
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


# === Calibrazione ===


@pytest.mark.asyncio
async def test_calibra_salva_matrice_in_cache(
    sessione_test: AsyncSession,
    servizio_raddrizzamento: ServizioRaddrizzamento,
    storage: StorageFrame,
    video_finto: Path,
) -> None:
    p, _ = await _crea_partita_con_video_e_evento(sessione_test, video_finto)

    matrice = await servizio_raddrizzamento.calibra(sessione_test, p.id)

    # Mock ritorna identità
    assert matrice == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    assert storage.esiste_omografia(p.id)
    assert storage.carica_omografia(p.id) == matrice


@pytest.mark.asyncio
async def test_calibra_seconda_chiamata_usa_cache(
    sessione_test: AsyncSession,
    storage: StorageFrame,
    video_finto: Path,
) -> None:
    contatore = ContatoreCalibrazioni()
    estrazione = ServizioEstrazioneFrame(
        storage=storage, estrattore=EstrattoreFrameMock()
    )
    servizio = ServizioRaddrizzamento(
        servizio_estrazione=estrazione,
        storage=storage,
        raddrizzatore=contatore,
    )
    p, _ = await _crea_partita_con_video_e_evento(sessione_test, video_finto)

    await servizio.calibra(sessione_test, p.id)
    await servizio.calibra(sessione_test, p.id)

    # Una sola calibrazione effettiva (la seconda è cache hit)
    assert contatore.n_calibrazioni == 1


@pytest.mark.asyncio
async def test_calibra_forza_ricalibra(
    sessione_test: AsyncSession,
    storage: StorageFrame,
    video_finto: Path,
) -> None:
    contatore = ContatoreCalibrazioni()
    estrazione = ServizioEstrazioneFrame(
        storage=storage, estrattore=EstrattoreFrameMock()
    )
    servizio = ServizioRaddrizzamento(
        servizio_estrazione=estrazione,
        storage=storage,
        raddrizzatore=contatore,
    )
    p, _ = await _crea_partita_con_video_e_evento(sessione_test, video_finto)

    await servizio.calibra(sessione_test, p.id)
    await servizio.calibra(sessione_test, p.id, forza=True)

    assert contatore.n_calibrazioni == 2


@pytest.mark.asyncio
async def test_calibra_propaga_fallimento_match(
    sessione_test: AsyncSession,
    storage: StorageFrame,
    video_finto: Path,
) -> None:
    estrazione = ServizioEstrazioneFrame(
        storage=storage, estrattore=EstrattoreFrameMock()
    )
    servizio = ServizioRaddrizzamento(
        servizio_estrazione=estrazione,
        storage=storage,
        raddrizzatore=RaddrizzatoreMock(simula_calibrazione_fallita=True),
    )
    p, _ = await _crea_partita_con_video_e_evento(sessione_test, video_finto)

    with pytest.raises(CalibrazioneFallitaError):
        await servizio.calibra(sessione_test, p.id)

    # La cache NON deve essere stata popolata
    assert not storage.esiste_omografia(p.id)


@pytest.mark.asyncio
async def test_calibra_propaga_opencv_mancante(
    sessione_test: AsyncSession,
    storage: StorageFrame,
    video_finto: Path,
) -> None:
    estrazione = ServizioEstrazioneFrame(
        storage=storage, estrattore=EstrattoreFrameMock()
    )
    servizio = ServizioRaddrizzamento(
        servizio_estrazione=estrazione,
        storage=storage,
        raddrizzatore=RaddrizzatoreMock(simula_opencv_mancante=True),
    )
    p, _ = await _crea_partita_con_video_e_evento(sessione_test, video_finto)

    with pytest.raises(OpencvNonDisponibileError):
        await servizio.calibra(sessione_test, p.id)


# === Raddrizzamento per evento ===


@pytest.mark.asyncio
async def test_raddrizza_per_evento_richiede_calibrazione(
    sessione_test: AsyncSession,
    servizio_raddrizzamento: ServizioRaddrizzamento,
    video_finto: Path,
) -> None:
    p, ev = await _crea_partita_con_video_e_evento(sessione_test, video_finto)

    # Senza calibrazione preventiva
    with pytest.raises(OmografiaNonCalibrataError):
        await servizio_raddrizzamento.raddrizza_per_evento(
            sessione_test, p.id, ev.id
        )


@pytest.mark.asyncio
async def test_raddrizza_per_evento_dopo_calibrazione(
    sessione_test: AsyncSession,
    servizio_raddrizzamento: ServizioRaddrizzamento,
    storage: StorageFrame,
    video_finto: Path,
) -> None:
    p, ev = await _crea_partita_con_video_e_evento(sessione_test, video_finto)

    await servizio_raddrizzamento.calibra(sessione_test, p.id)

    percorso = await servizio_raddrizzamento.raddrizza_per_evento(
        sessione_test, p.id, ev.id
    )

    assert percorso.exists()
    assert percorso.stat().st_size > 0
    assert "raddrizzato" in percorso.name
    assert storage.esiste_raddrizzato(p.id, ev.id)


@pytest.mark.asyncio
async def test_raddrizza_per_evento_usa_cache(
    sessione_test: AsyncSession,
    storage: StorageFrame,
    video_finto: Path,
) -> None:
    contatore = ContatoreCalibrazioni()
    estrazione = ServizioEstrazioneFrame(
        storage=storage, estrattore=EstrattoreFrameMock()
    )
    servizio = ServizioRaddrizzamento(
        servizio_estrazione=estrazione,
        storage=storage,
        raddrizzatore=contatore,
    )

    p, ev = await _crea_partita_con_video_e_evento(sessione_test, video_finto)
    await servizio.calibra(sessione_test, p.id)

    p1 = await servizio.raddrizza_per_evento(sessione_test, p.id, ev.id)
    n1 = contatore.n_applicazioni
    p2 = await servizio.raddrizza_per_evento(sessione_test, p.id, ev.id)

    assert p1 == p2
    # Seconda chiamata = cache hit, niente warp
    assert contatore.n_applicazioni == n1


# === Stato calibrazione ===


@pytest.mark.asyncio
async def test_stato_calibrazione_partita_non_calibrata(
    sessione_test: AsyncSession,
    servizio_raddrizzamento: ServizioRaddrizzamento,
    video_finto: Path,
) -> None:
    p, _ = await _crea_partita_con_video_e_evento(sessione_test, video_finto)

    stato = servizio_raddrizzamento.stato_calibrazione(p.id)
    assert stato["calibrata"] is False
    assert stato["matrice"] is None


@pytest.mark.asyncio
async def test_stato_calibrazione_dopo_calibra(
    sessione_test: AsyncSession,
    servizio_raddrizzamento: ServizioRaddrizzamento,
    video_finto: Path,
) -> None:
    p, _ = await _crea_partita_con_video_e_evento(sessione_test, video_finto)
    await servizio_raddrizzamento.calibra(sessione_test, p.id)

    stato = servizio_raddrizzamento.stato_calibrazione(p.id)
    assert stato["calibrata"] is True
    assert stato["matrice"] is not None


# === Helper interno ===


class ContatoreCalibrazioni(RaddrizzatoreMock):
    """Mock che conta calibrazioni e applicazioni separate."""

    def __init__(self) -> None:
        super().__init__()
        self.n_calibrazioni = 0
        self.n_applicazioni = 0

    def calibra(self, percorso_frame: Path) -> list[list[float]]:
        self.n_calibrazioni += 1
        return super().calibra(percorso_frame)

    def applica(
        self,
        percorso_frame: Path,
        matrice: list[list[float]],
        percorso_output: Path,
    ) -> None:
        self.n_applicazioni += 1
        return super().applica(percorso_frame, matrice, percorso_output)


# === Test batch raddrizzamento ===


@pytest.mark.asyncio
async def test_raddrizza_batch_processa_tutti_eventi_validati(
    sessione_test: AsyncSession,
    servizio_raddrizzamento: ServizioRaddrizzamento,
    storage: StorageFrame,
    video_finto: Path,
) -> None:
    """Smoke test: con 3 eventi validati, raddrizza tutti e cache popolata."""
    p, ev1 = await _crea_partita_con_video_e_evento(sessione_test, video_finto)

    # Aggiungi 2 altri eventi validati
    ts = p.data_inizio
    ev2 = EventoValidato(
        partita_id=p.id,
        ts_evento=ts + timedelta(seconds=120),
        tipo=TipoEvento.ATTACCO_RISOLTO,
        dati={"giocatore_id": "fake", "da": "x", "a": "y",
              "dadi_attaccante": [5], "dadi_difensore": [2]},
        evento_grezzo_id=None,
        validato_da="test",
    )
    ev3 = EventoValidato(
        partita_id=p.id,
        ts_evento=ts + timedelta(seconds=180),
        tipo=TipoEvento.ATTACCO_RISOLTO,
        dati={"giocatore_id": "fake", "da": "x", "a": "y",
              "dadi_attaccante": [4], "dadi_difensore": [1]},
        evento_grezzo_id=None,
        validato_da="test",
    )
    sessione_test.add_all([ev2, ev3])
    await sessione_test.commit()

    # Calibra
    await servizio_raddrizzamento.calibra(sessione_test, p.id)

    # Raddrizza tutti uno per uno (simula cosa fa l'endpoint batch)
    for ev_id in (ev1.id, ev2.id, ev3.id):
        percorso = await servizio_raddrizzamento.raddrizza_per_evento(
            sessione_test, p.id, ev_id
        )
        assert percorso.exists()

    # Cache popolata per tutti e 3
    assert storage.esiste_raddrizzato(p.id, ev1.id)
    assert storage.esiste_raddrizzato(p.id, ev2.id)
    assert storage.esiste_raddrizzato(p.id, ev3.id)
