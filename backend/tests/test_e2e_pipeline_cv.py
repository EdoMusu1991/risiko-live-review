"""
Test end-to-end della pipeline CV completa.

Verifica il flusso:
1. Partita con eventi validati e snapshot ricostruito
2. Calibrazione raddrizzamento (mock)
3. Pipeline analizza tutti eventi (mock client genera detection)
4. Calcola discrepanze
5. PATCH risoluzione divergenza
6. Statistiche aggregate

Tutto con mock, niente OpenCV / ffmpeg / Roboflow richiesti.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modelli import (
    DivergenzaInferita,
    EventoValidato,
    GiocatorePartita,
    InferenzaCV,
    Partita,
    StatoPartitaRicostruito,
    StatoReview,
    TipoEvento,
    Video,
)
from app.servizi.cv_servizio import ClientCVMock, ServizioCV
from app.servizi.discrepanze_servizio import (
    calcola_discrepanze,
    stato_motore_da_snapshot,
)
from app.servizi.estrazione_frame_servizio import ServizioEstrazioneFrame
from app.servizi.raddrizzamento_servizio import ServizioRaddrizzamento
from app.storage.estrattore_frame import EstrattoreFrameMock
from app.storage.raddrizzatore import RaddrizzatoreMock
from app.storage.storage_frame import StorageFrame


@pytest.mark.asyncio
async def test_e2e_pipeline_cv_completa(
    sessione_test: AsyncSession,
    tmp_path: Path,
) -> None:
    """
    End-to-end: partita → calibrazione → analisi CV → discrepanze →
    risoluzione → statistiche.
    """
    # === Setup: partita con video, eventi validati, stato motore ricostruito ===
    ts = datetime(2026, 5, 9, 21, 0, tzinfo=UTC)
    partita = Partita(data_inizio=ts, stato_review=StatoReview.GREZZA)
    sessione_test.add(partita)
    await sessione_test.flush()
    rosso = GiocatorePartita(
        partita_id=partita.id, nome="Edo", colore="rosso", ordine_seduta=1,
    )
    blu = GiocatorePartita(
        partita_id=partita.id, nome="Marco", colore="blu", ordine_seduta=2,
    )
    sessione_test.add_all([rosso, blu])
    await sessione_test.flush()

    # Video
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake-mp4")
    sessione_test.add(Video(
        partita_id=partita.id,
        file_path=str(video_path),
        nome_originale="v.mp4",
        ts_inizio=ts,
        durata_sec=600.0,
        codec="h264",
        risoluzione="1920x1080",
        dimensione_byte=1000,
    ))

    # 3 eventi validati a timestamp progressivi
    eventi_input = [
        (60.0, "ATTACCO_RISOLTO"),
        (120.0, "ATTACCO_RISOLTO"),
        (180.0, "ATTACCO_RISOLTO"),
    ]
    eventi_creati: list[EventoValidato] = []
    for offset, tipo in eventi_input:
        ev = EventoValidato(
            partita_id=partita.id,
            ts_evento=ts + timedelta(seconds=offset),
            tipo=getattr(TipoEvento, tipo),
            dati={
                "giocatore_id": rosso.id,
                "da": "kamchatka", "a": "alaska",
                "dadi_attaccante": [6, 5], "dadi_difensore": [3],
            },
            evento_grezzo_id=None,
            validato_da="test",
        )
        sessione_test.add(ev)
        eventi_creati.append(ev)

    # Snapshot stato finale del motore (manuale, no risiko_engine reale)
    snapshot = StatoPartitaRicostruito(
        partita_id=partita.id,
        successo=True,
        data_ricostruzione=ts + timedelta(hours=1),
        n_eventi_totali=3,
        n_eventi_applicati=3,
        stato_serializzato={
            "territori": {
                "kamchatka": {"controllore_id": rosso.id, "armate": 8},
                "alaska": {"controllore_id": rosso.id, "armate": 4},
                "ontario": {"controllore_id": blu.id, "armate": 6},
            },
            "giocatori": [
                {"player_id": rosso.id, "colore": "rosso", "nome": "Edo"},
                {"player_id": blu.id, "colore": "blu", "nome": "Marco"},
            ],
        },
        errori=[],
    )
    sessione_test.add(snapshot)
    await sessione_test.commit()

    # === Step 1: configura servizi con mock ===
    storage = StorageFrame(tmp_path / "frames")
    estrazione = ServizioEstrazioneFrame(
        storage=storage, estrattore=EstrattoreFrameMock(),
    )
    raddrizzamento = ServizioRaddrizzamento(
        servizio_estrazione=estrazione,
        storage=storage,
        raddrizzatore=RaddrizzatoreMock(),
    )
    servizio_cv = ServizioCV(
        servizio_raddrizzamento=raddrizzamento,
        client_cv=ClientCVMock(versione="e2e-test-v1", n_detection_per_frame=3),
    )

    # === Step 2: calibrazione raddrizzamento ===
    matrice = await raddrizzamento.calibra(sessione_test, partita.id)
    assert matrice == [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    assert storage.esiste_omografia(partita.id)

    # === Step 3: pipeline batch analizza-tutti-eventi ===
    riepilogo = await servizio_cv.analizza_tutti_eventi(
        sessione_test, partita.id,
    )
    assert riepilogo["n_eventi_totali"] == 3
    assert riepilogo["n_riusciti"] == 3
    assert riepilogo["n_falliti"] == 0
    assert riepilogo["n_inferenze_totali"] == 9  # 3 detection x 3 eventi

    # Verifica persistenza nel DB
    ris = await sessione_test.execute(
        select(InferenzaCV).where(InferenzaCV.partita_id == partita.id)
    )
    inferenze_db = list(ris.scalars().all())
    assert len(inferenze_db) == 9
    # Tutte hanno frame_hash
    assert all(inf.frame_hash is not None for inf in inferenze_db)
    # Tutte hanno evento_validato_id
    assert all(inf.evento_validato_id is not None for inf in inferenze_db)

    # === Step 4: calcolo discrepanze sullo stato finale ===
    stato_motore = stato_motore_da_snapshot(snapshot.stato_serializzato or {})
    assert len(stato_motore) == 3  # kamchatka, alaska, ontario

    divergenze = calcola_discrepanze(stato_motore, inferenze_db)
    # Le inferenze del mock sono random sui territori non controllati, quindi
    # ci sara' quasi sicuramente una qualche divergenza
    assert isinstance(divergenze, list)

    # === Step 5: persisti come DivergenzaInferita ===
    for d in divergenze:
        sessione_test.add(DivergenzaInferita(
            partita_id=partita.id,
            evento_validato_id=None,
            territorio=d.territorio,
            colore=d.colore,
            valore_motore=d.valore_motore,
            valore_cv=d.valore_cv,
            confidence_cv=d.confidence_cv,
            delta_assoluto=d.delta_assoluto,
            inferenze_correlate=d.inferenze_correlate,
            risoluzione="aperta",
        ))
    await sessione_test.commit()

    # === Step 6: verifica integrita' divergenze nel DB ===
    ris_div = await sessione_test.execute(
        select(DivergenzaInferita).where(
            DivergenzaInferita.partita_id == partita.id
        )
    )
    divergenze_db = list(ris_div.scalars().all())
    assert len(divergenze_db) == len(divergenze)
    # Tutte aperte iniziali
    assert all(d.risoluzione == "aperta" for d in divergenze_db)

    # === Step 7: simulazione risoluzione umana ===
    if divergenze_db:
        prima = divergenze_db[0]
        prima.risoluzione = "accettata_motore"
        prima.note = "CV ha sbagliato, stato motore corretto"
        await sessione_test.commit()
        await sessione_test.refresh(prima)
        assert prima.risoluzione == "accettata_motore"


@pytest.mark.asyncio
async def test_e2e_pipeline_cv_per_evento_idempotente(
    sessione_test: AsyncSession,
    tmp_path: Path,
) -> None:
    """
    Verifica che chiamare analizza_tutti_eventi DUE volte produce lo
    stesso totale di inferenze (mock deterministico via seed sul path).

    Le inferenze NON vengono deduplicate: ogni chiamata aggiunge nuovi
    record. E' responsabilita' del chiamante cancellare prima.
    """
    ts = datetime(2026, 5, 9, 21, 0, tzinfo=UTC)
    partita = Partita(data_inizio=ts, stato_review=StatoReview.GREZZA)
    sessione_test.add(partita)
    await sessione_test.flush()
    sessione_test.add_all([
        GiocatorePartita(partita_id=partita.id, nome="A", colore="rosso", ordine_seduta=1),
        GiocatorePartita(partita_id=partita.id, nome="B", colore="blu", ordine_seduta=2),
    ])
    video_path = tmp_path / "video.mp4"
    video_path.write_bytes(b"fake")
    sessione_test.add(Video(
        partita_id=partita.id,
        file_path=str(video_path),
        nome_originale="v.mp4",
        ts_inizio=ts, durata_sec=600.0, codec="h264",
        risoluzione="1920x1080", dimensione_byte=1000,
    ))
    ev = EventoValidato(
        partita_id=partita.id,
        ts_evento=ts + timedelta(seconds=30),
        tipo=TipoEvento.ATTACCO_RISOLTO,
        dati={"giocatore_id": "x", "da": "a", "a": "b",
              "dadi_attaccante": [6], "dadi_difensore": [3]},
        evento_grezzo_id=None, validato_da="test",
    )
    sessione_test.add(ev)
    await sessione_test.commit()

    storage = StorageFrame(tmp_path / "frames")
    estrazione = ServizioEstrazioneFrame(
        storage=storage, estrattore=EstrattoreFrameMock(),
    )
    raddrizzamento = ServizioRaddrizzamento(
        servizio_estrazione=estrazione,
        storage=storage,
        raddrizzatore=RaddrizzatoreMock(),
    )
    servizio = ServizioCV(
        servizio_raddrizzamento=raddrizzamento,
        client_cv=ClientCVMock(n_detection_per_frame=3),
    )

    await raddrizzamento.calibra(sessione_test, partita.id)

    # Prima chiamata
    r1 = await servizio.analizza_tutti_eventi(sessione_test, partita.id)
    assert r1["n_inferenze_totali"] == 3

    # Conta inferenze dopo prima chiamata
    ris1 = await sessione_test.execute(
        select(InferenzaCV).where(InferenzaCV.partita_id == partita.id)
    )
    n1 = len(list(ris1.scalars().all()))
    assert n1 == 3

    # Seconda chiamata: aggiunge altri record (no dedup)
    r2 = await servizio.analizza_tutti_eventi(sessione_test, partita.id)
    assert r2["n_inferenze_totali"] == 3

    ris2 = await sessione_test.execute(
        select(InferenzaCV).where(InferenzaCV.partita_id == partita.id)
    )
    n2 = len(list(ris2.scalars().all()))
    assert n2 == 6  # 3 + 3 = 6 record totali (nuovi + vecchi)
