"""
Endpoint per la gestione delle inferenze CV (computer vision) e il
calcolo delle divergenze rispetto allo stato del motore.

Workflow tipico:
1. Pipeline esterna (script Roboflow / cv_servizio futuro) genera
   inferenze e le POSTa in batch.
2. Frontend RL chiede le divergenze per partita per la review umana.
3. Operatore risolve ogni divergenza (PATCH).
"""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import get_sessione_db, impostazioni
from app.modelli import (
    DivergenzaInferita,
    EventoValidato,
    InferenzaCV,
    Partita,
    StatoPartitaRicostruito,
)
from app.schemi.inferenze_cv import (
    AggiornamentoBulkDivergenze,
    AggiornamentoDivergenza,
    DivergenzaInferitaOutput,
    InferenzaCVOutput,
    InserimentoBatchInferenze,
    RiepilogoDiscrepanze,
    RisultatoBulkDivergenze,
)
from app.servizi.discrepanze_servizio import (
    calcola_discrepanze,
    stato_motore_da_snapshot,
)

if TYPE_CHECKING:
    from app.servizi.cv_servizio import ServizioCV

router = APIRouter(prefix="/partite/{partita_id}", tags=["inferenze-cv"])


@router.post(
    "/inferenze-cv",
    response_model=list[InferenzaCVOutput],
    status_code=status.HTTP_201_CREATED,
    summary="Inserisci un batch di inferenze CV per la partita",
)
async def inserisci_inferenze_batch(
    partita_id: str,
    body: InserimentoBatchInferenze,
    db: AsyncSession = Depends(get_sessione_db),
) -> list[InferenzaCV]:
    """
    Inserisce N inferenze CV in un colpo solo. Atomico: se uno qualunque
    dei record fallisce la validazione FK, nessuno viene committato.
    """
    # Verifica esistenza partita
    risultato = await db.execute(
        select(Partita).where(Partita.id == partita_id)
    )
    if risultato.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Partita '{partita_id}' non trovata",
        )

    # Se evento_validato_id sono specificati, verifica che appartengano
    # alla partita (defesa contro inserimenti incrociati)
    eventi_da_verificare = {
        i.evento_validato_id
        for i in body.inferenze
        if i.evento_validato_id is not None
    }
    if eventi_da_verificare:
        ris_ev = await db.execute(
            select(EventoValidato.id).where(
                EventoValidato.id.in_(eventi_da_verificare),
                EventoValidato.partita_id == partita_id,
            )
        )
        ids_validi = {row[0] for row in ris_ev.all()}
        ids_invalidi = eventi_da_verificare - ids_validi
        if ids_invalidi:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Eventi non appartenenti alla partita: "
                    f"{sorted(ids_invalidi)}"
                ),
            )

    creati: list[InferenzaCV] = []
    for inp in body.inferenze:
        rec = InferenzaCV(
            partita_id=partita_id,
            evento_validato_id=inp.evento_validato_id,
            modello_versione=inp.modello_versione,
            territorio=inp.territorio,
            colore=inp.colore,
            tipo_pedina_dominante=inp.tipo_pedina_dominante,
            n_armate_stimate=inp.n_armate_stimate,
            bbox=inp.bbox,
            confidence=inp.confidence,
            scomposizione=[s.model_dump() for s in inp.scomposizione],
            frame_hash=inp.frame_hash,
        )
        db.add(rec)
        creati.append(rec)
    await db.commit()
    for rec in creati:
        await db.refresh(rec)
    return creati


@router.get(
    "/inferenze-cv",
    response_model=list[InferenzaCVOutput],
    summary="Lista inferenze CV della partita",
)
async def lista_inferenze(
    partita_id: str,
    evento_validato_id: str | None = Query(default=None),
    modello_versione: str | None = Query(default=None),
    db: AsyncSession = Depends(get_sessione_db),
) -> list[InferenzaCV]:
    """
    Filtri opzionali: per evento, per versione modello.
    """
    stmt = select(InferenzaCV).where(InferenzaCV.partita_id == partita_id)
    if evento_validato_id is not None:
        stmt = stmt.where(InferenzaCV.evento_validato_id == evento_validato_id)
    if modello_versione is not None:
        stmt = stmt.where(InferenzaCV.modello_versione == modello_versione)
    stmt = stmt.order_by(InferenzaCV.creata_il)

    risultato = await db.execute(stmt)
    return list(risultato.scalars().all())


@router.delete(
    "/inferenze-cv",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancella tutte le inferenze CV della partita",
)
async def cancella_inferenze(
    partita_id: str,
    modello_versione: str | None = Query(
        default=None,
        description="Se specificato, cancella solo le inferenze di quel modello.",
    ),
    db: AsyncSession = Depends(get_sessione_db),
) -> None:
    """
    Utile dopo un re-training del modello per pulire le vecchie
    inferenze prima di rigenerarle.
    """
    stmt = select(InferenzaCV).where(InferenzaCV.partita_id == partita_id)
    if modello_versione is not None:
        stmt = stmt.where(InferenzaCV.modello_versione == modello_versione)
    risultato = await db.execute(stmt)
    for inf in risultato.scalars().all():
        await db.delete(inf)
    await db.commit()


# === Discrepanze ===


@router.post(
    "/calcola-discrepanze",
    response_model=RiepilogoDiscrepanze,
    summary="Calcola e persiste le divergenze CV ↔ motore per la partita",
)
async def calcola_e_salva_discrepanze(
    partita_id: str,
    modello_versione: str | None = Query(
        default=None,
        description="Filtra inferenze per versione modello (default: usa tutte).",
    ),
    db: AsyncSession = Depends(get_sessione_db),
) -> RiepilogoDiscrepanze:
    """
    Esegue il confronto fra:
    - lo stato finale della partita (da `StatoPartitaRicostruito`)
    - le inferenze CV più recenti (filtrabili per modello)

    Le divergenze vengono persistite come `DivergenzaInferita` con
    risoluzione="aperta". Le divergenze precedenti per la stessa partita
    vengono cancellate (questo endpoint è "computa da capo").

    Use case: dopo aver caricato un batch di inferenze CV, l'operatore
    chiama questo endpoint per generare la review delle discrepanze.
    """
    # 1. Carica stato motore (snapshot ricostruito)
    ris_snap = await db.execute(
        select(StatoPartitaRicostruito).where(
            StatoPartitaRicostruito.partita_id == partita_id
        )
    )
    snapshot = ris_snap.scalar_one_or_none()
    if snapshot is None or snapshot.stato_serializzato is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Stato partita non ricostruito. Chiamare prima "
                "POST /api/partite/{id}/ricostruisci."
            ),
        )

    stato_motore = stato_motore_da_snapshot(snapshot.stato_serializzato)

    # 2. Carica inferenze CV
    stmt_inf = select(InferenzaCV).where(InferenzaCV.partita_id == partita_id)
    if modello_versione is not None:
        stmt_inf = stmt_inf.where(InferenzaCV.modello_versione == modello_versione)
    ris_inf = await db.execute(stmt_inf)
    inferenze = list(ris_inf.scalars().all())

    # 3. Calcola
    divergenze_calcolate = calcola_discrepanze(stato_motore, inferenze)

    # 4. Cancella divergenze precedenti
    ris_old = await db.execute(
        select(DivergenzaInferita).where(
            DivergenzaInferita.partita_id == partita_id
        )
    )
    for old in ris_old.scalars().all():
        await db.delete(old)
    await db.flush()

    # 5. Persisti le nuove
    persistite: list[DivergenzaInferita] = []
    for d in divergenze_calcolate:
        rec = DivergenzaInferita(
            partita_id=partita_id,
            evento_validato_id=None,  # snapshot finale, non legato a evento
            territorio=d.territorio,
            colore=d.colore,
            valore_motore=d.valore_motore,
            valore_cv=d.valore_cv,
            confidence_cv=d.confidence_cv,
            delta_assoluto=d.delta_assoluto,
            inferenze_correlate=d.inferenze_correlate,
            risoluzione="aperta",
        )
        db.add(rec)
        persistite.append(rec)
    await db.commit()
    for rec in persistite:
        await db.refresh(rec)

    return RiepilogoDiscrepanze(
        n_divergenze_totali=len(persistite),
        n_aperte=len(persistite),
        n_risolte=0,
        delta_max=max(
            (d.delta_assoluto for d in persistite),
            default=0,
        ),
        divergenze=[DivergenzaInferitaOutput.model_validate(d) for d in persistite],
    )


@router.post(
    "/calcola-discrepanze-per-evento",
    response_model=RiepilogoDiscrepanze,
    summary="Calcola divergenze evento-per-evento (snapshot intermedi)",
)
async def calcola_discrepanze_per_evento(
    partita_id: str,
    modello_versione: str | None = Query(default=None),
    db: AsyncSession = Depends(get_sessione_db),
) -> RiepilogoDiscrepanze:
    """
    A differenza di `/calcola-discrepanze` che lavora sullo snapshot
    finale, qui il calcolo gira **per ogni evento che ha inferenze CV
    associate**: per ognuno ricostruisce lo stato motore intermedio
    (fino a quell'evento) e calcola le divergenze locali.

    Le divergenze risultanti hanno `evento_validato_id` valorizzato.
    Le divergenze precedenti per la partita vengono rimosse.

    Use case principale: pipeline CV reale che produce inferenze
    legate a singoli eventi BLE → confronto locale.
    """
    from app.servizi.ricostruzione_servizio import ServizioRicostruzione

    # 1. Carica tutte le inferenze raggruppate per evento_validato_id
    stmt = select(InferenzaCV).where(InferenzaCV.partita_id == partita_id)
    if modello_versione is not None:
        stmt = stmt.where(InferenzaCV.modello_versione == modello_versione)
    risultato = await db.execute(stmt)
    inferenze = list(risultato.scalars().all())

    # Raggruppa per evento_validato_id
    per_evento: dict[str | None, list[InferenzaCV]] = {}
    for inf in inferenze:
        chiave = inf.evento_validato_id
        per_evento.setdefault(chiave, []).append(inf)

    # 2. Cancella divergenze precedenti
    ris_old = await db.execute(
        select(DivergenzaInferita).where(
            DivergenzaInferita.partita_id == partita_id
        )
    )
    for old in ris_old.scalars().all():
        await db.delete(old)
    await db.flush()

    if not per_evento:
        await db.commit()
        return RiepilogoDiscrepanze(
            n_divergenze_totali=0, n_aperte=0, n_risolte=0,
            delta_max=0, divergenze=[],
        )

    persistite: list[DivergenzaInferita] = []

    for evento_id, inf_evento in per_evento.items():
        if evento_id is None:
            # Inferenze "snapshot" senza evento → confronto con stato finale
            ris_snap = await db.execute(
                select(StatoPartitaRicostruito).where(
                    StatoPartitaRicostruito.partita_id == partita_id
                )
            )
            snap = ris_snap.scalar_one_or_none()
            if snap is None or snap.stato_serializzato is None:
                continue
            stato_motore = stato_motore_da_snapshot(snap.stato_serializzato)
        else:
            try:
                snapshot_pyd = (
                    await ServizioRicostruzione.ricostruisci_fino_a_evento(
                        db, partita_id, evento_id,
                    )
                )
            except ValueError:
                continue
            if snapshot_pyd is None:
                continue
            stato_motore = stato_motore_da_snapshot(
                snapshot_pyd.model_dump(mode="json")
            )

        divergenze_calcolate = calcola_discrepanze(stato_motore, inf_evento)
        for d in divergenze_calcolate:
            rec = DivergenzaInferita(
                partita_id=partita_id,
                evento_validato_id=evento_id,
                territorio=d.territorio,
                colore=d.colore,
                valore_motore=d.valore_motore,
                valore_cv=d.valore_cv,
                confidence_cv=d.confidence_cv,
                delta_assoluto=d.delta_assoluto,
                inferenze_correlate=d.inferenze_correlate,
                risoluzione="aperta",
            )
            db.add(rec)
            persistite.append(rec)

    await db.commit()
    for rec in persistite:
        await db.refresh(rec)

    return RiepilogoDiscrepanze(
        n_divergenze_totali=len(persistite),
        n_aperte=len(persistite),
        n_risolte=0,
        delta_max=max(
            (d.delta_assoluto for d in persistite), default=0,
        ),
        divergenze=[
            DivergenzaInferitaOutput.model_validate(d) for d in persistite
        ],
    )


@router.get(
    "/discrepanze",
    response_model=RiepilogoDiscrepanze,
    summary="Lista divergenze CV ↔ motore correnti",
)
async def lista_discrepanze(
    partita_id: str,
    solo_aperte: bool = Query(default=False),
    db: AsyncSession = Depends(get_sessione_db),
) -> RiepilogoDiscrepanze:
    """Legge le divergenze già calcolate per la partita."""
    stmt = select(DivergenzaInferita).where(
        DivergenzaInferita.partita_id == partita_id
    )
    if solo_aperte:
        stmt = stmt.where(DivergenzaInferita.risoluzione == "aperta")
    stmt = stmt.order_by(DivergenzaInferita.delta_assoluto.desc())

    risultato = await db.execute(stmt)
    divergenze = list(risultato.scalars().all())

    n_aperte = sum(1 for d in divergenze if d.risoluzione == "aperta")
    delta_max = max((d.delta_assoluto for d in divergenze if d.risoluzione == "aperta"), default=0)

    return RiepilogoDiscrepanze(
        n_divergenze_totali=len(divergenze),
        n_aperte=n_aperte,
        n_risolte=len(divergenze) - n_aperte,
        delta_max=delta_max,
        divergenze=[DivergenzaInferitaOutput.model_validate(d) for d in divergenze],
    )


@router.get(
    "/discrepanze/statistiche",
    summary="Statistiche aggregate sulle divergenze CV ↔ motore",
)
async def statistiche_discrepanze(
    partita_id: str,
    db: AsyncSession = Depends(get_sessione_db),
) -> dict[str, object]:
    """
    Aggregato per dashboard:
    - Distribuzione delta_assoluto (istogramma)
    - Conteggio per stato (aperta, accettata_motore, ...)
    - Top territori per delta
    - Conteggio per colore
    - Confidence media CV
    """
    stmt = select(DivergenzaInferita).where(
        DivergenzaInferita.partita_id == partita_id
    )
    risultato = await db.execute(stmt)
    divergenze = list(risultato.scalars().all())

    if not divergenze:
        return {
            "n_totali": 0,
            "distribuzione_delta": {},
            "per_risoluzione": {},
            "top_territori": [],
            "per_colore": {},
            "confidence_media": 0.0,
        }

    # Distribuzione delta (bucket: 1, 2, 3, 4, 5+)
    distribuzione: dict[str, int] = {}
    for d in divergenze:
        bucket = "5+" if d.delta_assoluto >= 5 else str(d.delta_assoluto)
        distribuzione[bucket] = distribuzione.get(bucket, 0) + 1

    # Per risoluzione
    per_risoluzione: dict[str, int] = {}
    for d in divergenze:
        per_risoluzione[d.risoluzione] = per_risoluzione.get(d.risoluzione, 0) + 1

    # Top territori (per delta totale)
    territorio_delta: dict[str, int] = {}
    for d in divergenze:
        territorio_delta[d.territorio] = (
            territorio_delta.get(d.territorio, 0) + d.delta_assoluto
        )
    top_territori = sorted(
        territorio_delta.items(), key=lambda kv: kv[1], reverse=True,
    )[:10]

    # Per colore (n divergenze per colore)
    per_colore: dict[str, int] = {}
    for d in divergenze:
        per_colore[d.colore] = per_colore.get(d.colore, 0) + 1

    # Confidence media
    conf_totale = sum(d.confidence_cv for d in divergenze)
    confidence_media = conf_totale / len(divergenze)

    return {
        "n_totali": len(divergenze),
        "distribuzione_delta": distribuzione,
        "per_risoluzione": per_risoluzione,
        "top_territori": [
            {"territorio": t, "delta_totale": delta}
            for t, delta in top_territori
        ],
        "per_colore": per_colore,
        "confidence_media": round(confidence_media, 3),
    }


@router.get(
    "/discrepanze/esporta-csv",
    response_class=PlainTextResponse,
    summary="Esporta divergenze in CSV (per analisi esterna)",
)
async def esporta_divergenze_csv(
    partita_id: str,
    solo_aperte: bool = Query(default=False),
    db: AsyncSession = Depends(get_sessione_db),
) -> PlainTextResponse:
    """
    Esporta le divergenze in formato CSV con BOM UTF-8 per
    compatibilita' Excel italiana.

    Colonne: id, evento_id, territorio, colore, valore_motore, valore_cv,
    delta_assoluto, confidence_cv, risoluzione, note, creata_il.
    """
    import csv
    import io

    stmt = select(DivergenzaInferita).where(
        DivergenzaInferita.partita_id == partita_id
    )
    if solo_aperte:
        stmt = stmt.where(DivergenzaInferita.risoluzione == "aperta")
    stmt = stmt.order_by(DivergenzaInferita.delta_assoluto.desc())

    risultato = await db.execute(stmt)
    divergenze = list(risultato.scalars().all())

    buffer = io.StringIO()
    # BOM UTF-8 per Excel italiano
    buffer.write("\ufeff")
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "id",
        "evento_validato_id",
        "territorio",
        "colore",
        "valore_motore",
        "valore_cv",
        "delta_assoluto",
        "confidence_cv",
        "risoluzione",
        "note",
        "creata_il",
        "aggiornata_il",
    ])
    for d in divergenze:
        writer.writerow([
            d.id,
            d.evento_validato_id or "",
            d.territorio,
            d.colore,
            d.valore_motore,
            d.valore_cv,
            d.delta_assoluto,
            f"{d.confidence_cv:.3f}",
            d.risoluzione,
            (d.note or "").replace("\n", " ").replace("\r", ""),
            d.creata_il.isoformat() if d.creata_il else "",
            d.aggiornata_il.isoformat() if d.aggiornata_il else "",
        ])

    nome_file = f"divergenze-{partita_id[:8]}.csv"
    return PlainTextResponse(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{nome_file}"',
        },
    )


@router.delete(
    "/inferenze-cv/{inferenza_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancella una singola inferenza CV",
)
async def cancella_singola_inferenza(
    partita_id: str,
    inferenza_id: str,
    db: AsyncSession = Depends(get_sessione_db),
) -> None:
    """
    Cancella una singola inferenza CV (utile per pulizia mirata da UI:
    es. "questo falso positivo non lo voglio").

    Le `DivergenzaInferita` che riferivano questa inferenza nel campo
    `inferenze_correlate` rimangono invariate (campo JSON, non FK).
    Per ripulire le divergenze stale, ricalcolare con `/calcola-discrepanze`.
    """
    stmt = select(InferenzaCV).where(
        InferenzaCV.id == inferenza_id,
        InferenzaCV.partita_id == partita_id,
    )
    risultato = await db.execute(stmt)
    inferenza = risultato.scalar_one_or_none()
    if inferenza is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inferenza '{inferenza_id}' non trovata",
        )
    await db.delete(inferenza)
    await db.commit()


@router.get(
    "/inferenze-cv/validazione",
    summary="Linter semantico delle inferenze CV (territori, colori, ranges)",
)
async def valida_inferenze_endpoint(
    partita_id: str,
    modello_versione: str | None = Query(default=None),
    db: AsyncSession = Depends(get_sessione_db),
) -> dict[str, object]:
    """
    Esegue le validazioni cross-check delle inferenze CV rispetto al
    motore di gioco:
    - Territorio inferito esiste sulla mappa?
    - Colore inferito appartiene a un giocatore della partita?
    - n_armate e bbox in range plausibile?
    - Confidence sufficientemente alta?

    Returns:
        Riepilogo: n_inferenze, n_problemi, n_error, n_warning,
        problemi (lista, max 200 entries).
    """
    from app.modelli import GiocatorePartita as _Giocatore
    from app.modelli import StatoPartitaRicostruito as _Snapshot
    from app.servizi.validazione_inferenze_servizio import (
        conta_problemi_per_severita,
        valida_inferenze,
    )

    # Carica inferenze
    stmt_inf = select(InferenzaCV).where(InferenzaCV.partita_id == partita_id)
    if modello_versione is not None:
        stmt_inf = stmt_inf.where(
            InferenzaCV.modello_versione == modello_versione
        )
    risultato = await db.execute(stmt_inf)
    inferenze = list(risultato.scalars().all())

    # Carica giocatori (per check colore)
    ris_g = await db.execute(
        select(_Giocatore).where(_Giocatore.partita_id == partita_id)
    )
    giocatori = list(ris_g.scalars().all())

    # Carica territori validi (dallo snapshot motore se disponibile)
    territori_validi: set[str] | None = None
    ris_snap = await db.execute(
        select(_Snapshot).where(_Snapshot.partita_id == partita_id)
    )
    snap = ris_snap.scalar_one_or_none()
    if snap is not None and snap.stato_serializzato is not None:
        territori = snap.stato_serializzato.get("territori")
        if isinstance(territori, dict):
            territori_validi = set(territori.keys())

    problemi = valida_inferenze(
        inferenze,
        territori_validi=territori_validi,
        giocatori=giocatori,
    )
    conteggio = conta_problemi_per_severita(problemi)

    return {
        "n_inferenze": len(inferenze),
        "n_problemi": len(problemi),
        "n_error": conteggio["error"],
        "n_warning": conteggio["warning"],
        "territori_validi_disponibili": territori_validi is not None,
        "problemi": [
            {
                "codice": p.codice,
                "severita": p.severita,
                "inferenza_id": p.inferenza_id,
                "descrizione": p.descrizione,
            }
            for p in problemi[:200]  # cap per evitare risposte enormi
        ],
        "troncato": len(problemi) > 200,
    }


@router.post(
    "/discrepanze/aggiorna-bulk",
    response_model=RisultatoBulkDivergenze,
    summary="Aggiorna in batch la risoluzione di piu' divergenze",
)
async def aggiorna_divergenze_bulk(
    partita_id: str,
    body: AggiornamentoBulkDivergenze,
    db: AsyncSession = Depends(get_sessione_db),
) -> dict[str, object]:
    """
    Applica una risoluzione a tutte le divergenze che soddisfano i
    filtri specificati nel body. Use case principali:

    - "Accetta motore tutte sotto delta=2" (filtro `delta_massimo=2`)
    - "Accetta CV tutte su un dato colore" (filtro `colore`)
    - "Riapri tutte le risolte di un territorio" (filtro `territorio` +
      `solo_aperte=false`)

    Idempotente: rieseguire con stessi filtri non cambia altro.
    """
    stmt = select(DivergenzaInferita).where(
        DivergenzaInferita.partita_id == partita_id
    )
    if body.solo_aperte:
        stmt = stmt.where(DivergenzaInferita.risoluzione == "aperta")
    if body.delta_minimo is not None:
        stmt = stmt.where(
            DivergenzaInferita.delta_assoluto >= body.delta_minimo
        )
    if body.delta_massimo is not None:
        stmt = stmt.where(
            DivergenzaInferita.delta_assoluto <= body.delta_massimo
        )
    if body.territorio is not None:
        stmt = stmt.where(DivergenzaInferita.territorio == body.territorio)
    if body.colore is not None:
        stmt = stmt.where(DivergenzaInferita.colore == body.colore)

    risultato = await db.execute(stmt)
    divergenze = list(risultato.scalars().all())

    n_aggiornate = 0
    for d in divergenze:
        d.risoluzione = body.risoluzione
        if body.note is not None:
            d.note = body.note
        n_aggiornate += 1
    await db.commit()

    return {
        "n_aggiornate": n_aggiornate,
        "risoluzione_applicata": body.risoluzione,
    }


@router.patch(
    "/discrepanze/{divergenza_id}",
    response_model=DivergenzaInferitaOutput,
    summary="Aggiorna risoluzione di una divergenza (review umana)",
)
async def aggiorna_divergenza(
    partita_id: str,
    divergenza_id: str,
    body: AggiornamentoDivergenza,
    db: AsyncSession = Depends(get_sessione_db),
) -> DivergenzaInferita:
    """
    L'operatore risolve la divergenza scegliendo:
    - "accettata_motore": la CV ha sbagliato, considera valida la versione motore
    - "accettata_cv": il motore ha torto (probabilmente manca un evento)
    - "evento_aggiunto": ho creato manualmente l'evento mancante
    - "aperta": riapri (es. per revisione successiva)
    """
    risultato = await db.execute(
        select(DivergenzaInferita).where(
            DivergenzaInferita.id == divergenza_id,
            DivergenzaInferita.partita_id == partita_id,
        )
    )
    divergenza = risultato.scalar_one_or_none()
    if divergenza is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Divergenza '{divergenza_id}' non trovata",
        )

    divergenza.risoluzione = body.risoluzione
    if body.note is not None:
        divergenza.note = body.note
    await db.commit()
    await db.refresh(divergenza)
    return divergenza


@router.get(
    "/discrepanze/{divergenza_id}/suggerisci-evento",
    summary="Suggerisce un evento candidato per risolvere la divergenza",
)
async def suggerisci_evento_per_divergenza(
    partita_id: str,
    divergenza_id: str,
    db: AsyncSession = Depends(get_sessione_db),
) -> dict[str, object]:
    """
    Dato uno scarto fra motore (N armate) e CV (M armate) su un dato
    territorio, propone un evento candidato che potrebbe colmare il
    delta. La logica e' euristica:

    - delta > 0 (CV vede piu' del motore) → suggerisce ARMATE_PIAZZATE
      con n=delta sul territorio. Probabile rinforzo non registrato.
    - delta < 0 (CV vede meno del motore) → suggerisce ARMATE_SPOSTATE
      o ATTACCO_RISOLTO. Difficile inferire, mostra commento.
    - territorio nuovo (motore=0, CV>0) → TERRITORIO_ASSEGNATO_INIZIO
      o ARMATE_PIAZZATE.

    L'utente puo' modificare il candidato prima di crearlo davvero.
    Returns:
        dict con campi:
        - tipo: TipoEvento suggerito
        - dati: payload candidato
        - commento: spiegazione testuale
        - confidence_suggerimento: 0..1 (quanto e' affidabile l'euristica)
    """
    risultato = await db.execute(
        select(DivergenzaInferita).where(
            DivergenzaInferita.id == divergenza_id,
            DivergenzaInferita.partita_id == partita_id,
        )
    )
    divergenza = risultato.scalar_one_or_none()
    if divergenza is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Divergenza '{divergenza_id}' non trovata",
        )

    # Trova il giocatore con il colore della divergenza
    giocatore_id = await _trova_giocatore_per_colore(
        db, partita_id, divergenza.colore,
    )

    delta = divergenza.valore_cv - divergenza.valore_motore  # con segno

    # Euristica
    if delta > 0:
        if divergenza.valore_motore == 0:
            # Territorio "nuovo" per il motore: evento di assegnazione iniziale?
            tipo = "armate_piazzate"
            commento = (
                f"La CV vede {divergenza.valore_cv} armate {divergenza.colore} "
                f"su {divergenza.territorio}, ma il motore non lo controlla. "
                f"Probabile evento di conquista o assegnazione mancante. "
                f"Verifica manualmente il tipo corretto."
            )
            conf = 0.5
        else:
            tipo = "armate_piazzate"
            commento = (
                f"La CV vede {delta} armate in piu' del motore su "
                f"{divergenza.territorio}. Probabile RINFORZO non registrato."
            )
            conf = 0.8
        dati: dict[str, object] = {
            "giocatore_id": giocatore_id,
            "territorio": divergenza.territorio,
            "n": abs(delta),
        }
    elif delta < 0:
        # CV vede meno del motore: spostamento, attacco, ecc.
        tipo = "armate_spostate"
        commento = (
            f"La CV vede {abs(delta)} armate in meno del motore su "
            f"{divergenza.territorio}. Possibile spostamento non registrato "
            f"oppure attacco subito. Evento candidato suggerito (verifica "
            f"il territorio destinazione/origine)."
        )
        conf = 0.4
        dati = {
            "giocatore_id": giocatore_id,
            "da": divergenza.territorio,
            "a": "?",  # da specificare manualmente
            "n": abs(delta),
        }
    else:
        # delta == 0: non dovremmo mai arrivare qui (no divergenza)
        return {
            "tipo": None,
            "dati": {},
            "commento": "Nessuna divergenza: motore e CV concordano.",
            "confidence_suggerimento": 0.0,
        }

    return {
        "tipo": tipo,
        "dati": dati,
        "commento": commento,
        "confidence_suggerimento": conf,
        "divergenza_id": divergenza_id,
    }


async def _trova_giocatore_per_colore(
    db: AsyncSession, partita_id: str, colore: str,
) -> str | None:
    """Cerca il giocatore con il colore dato. None se non trovato."""
    from app.modelli import GiocatorePartita

    risultato = await db.execute(
        select(GiocatorePartita).where(
            GiocatorePartita.partita_id == partita_id,
            GiocatorePartita.colore == colore,
        )
    )
    giocatore = risultato.scalar_one_or_none()
    return giocatore.id if giocatore else None


# === Pipeline CV (orchestratore: estrazione + raddrizzamento + inferenza) ===


def _crea_servizio_cv() -> "ServizioCV":
    """
    Costruisce il servizio CV con dipendenze di default.

    Il client CV e' `ClientCVRoboflow` se le env vars `ROBOFLOW_API_KEY` e
    `ROBOFLOW_ENDPOINT` sono settate. Altrimenti fallback a `ClientCVMock`
    (utile in dev/test).
    """
    from app.servizi.cv_servizio import (
        ClientCVMock,
        ClientCVRoboflow,
        ServizioCV,
    )
    from app.servizi.estrazione_frame_servizio import ServizioEstrazioneFrame
    from app.servizi.raddrizzamento_servizio import ServizioRaddrizzamento
    from app.storage.estrattore_frame import get_estrattore_frame
    from app.storage.raddrizzatore import (
        OpencvNonDisponibileError,
        RaddrizzatoreOpencv,
        RiferimentoNonTrovatoError,
    )
    from app.storage.storage_frame import StorageFrame

    storage = StorageFrame(impostazioni.storage_frame_path)
    estrazione = ServizioEstrazioneFrame(
        storage=storage, estrattore=get_estrattore_frame(),
    )

    percorso_riferimento = (
        impostazioni.storage_frame_path / "img_riferimento.jpg"
    )
    try:
        raddrizzatore = RaddrizzatoreOpencv(percorso_riferimento)
    except OpencvNonDisponibileError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "OpenCV non installato. Esegui: pip install -e \".[cv]\""
            ),
        ) from e
    except RiferimentoNonTrovatoError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Immagine di riferimento mancante: {percorso_riferimento}"
            ),
        ) from e

    raddrizzamento = ServizioRaddrizzamento(
        servizio_estrazione=estrazione,
        storage=storage,
        raddrizzatore=raddrizzatore,
    )

    # Client CV: Roboflow se configurato, altrimenti mock
    if impostazioni.roboflow_api_key and impostazioni.roboflow_endpoint:
        client = ClientCVRoboflow(
            api_key=impostazioni.roboflow_api_key,
            project_endpoint=impostazioni.roboflow_endpoint,
            confidence_minima=impostazioni.roboflow_confidence_min,
            iou_minimo=impostazioni.roboflow_iou_min,
        )
    else:
        client = ClientCVMock(versione="mock-default-v1")

    return ServizioCV(
        servizio_raddrizzamento=raddrizzamento,
        client_cv=client,
    )


@router.post(
    "/eventi/{evento_id}/analizza-cv",
    response_model=list[InferenzaCVOutput],
    summary="Pipeline CV completa per un singolo evento",
)
async def analizza_evento_cv(
    partita_id: str,
    evento_id: str,
    forza_raddrizzamento: bool = Query(default=False),
    db: AsyncSession = Depends(get_sessione_db),
) -> list[InferenzaCV]:
    """
    Esegue la pipeline CV completa per un evento:
    1. Estrai frame video al timestamp dell'evento
    2. Raddrizza prospettiva (richiede calibrazione preventiva)
    3. Inferisci con il modello CV
    4. Persisti le inferenze nel DB

    Ritorna la lista di `InferenzaCV` create.

    Errori comuni:
    - 409: partita non calibrata (chiamare prima `/calibra-raddrizzamento`)
    - 503: OpenCV non installato sul server, o modello CV non configurato
    """
    from app.servizi.cv_servizio import ClientCVError
    from app.servizi.raddrizzamento_servizio import OmografiaNonCalibrataError

    servizio = _crea_servizio_cv()
    try:
        creati = await servizio.analizza_evento(
            db, partita_id, evento_id,
            forza_raddrizzamento=forza_raddrizzamento,
        )
    except OmografiaNonCalibrataError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{e} Chiama prima POST "
                f"/api/partite/{partita_id}/calibra-raddrizzamento."
            ),
        ) from e
    except ClientCVError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Modello CV non disponibile: {e}",
        ) from e
    except NotImplementedError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"Modello CV reale non ancora configurato: {e}"
            ),
        ) from e
    return creati


@router.post(
    "/analizza-tutti-eventi-cv",
    summary="Pipeline CV completa per TUTTI gli eventi validati",
)
async def analizza_tutti_eventi_cv(
    partita_id: str,
    forza_raddrizzamento: bool = Query(default=False),
    db: AsyncSession = Depends(get_sessione_db),
) -> dict[str, object]:
    """
    Batch: scorre tutti gli eventi validati della partita ed esegue la
    pipeline CV per ciascuno. Ritorna riepilogo.

    Costo per partita ~200 eventi:
    - Frame estratti: ~30-60s (cached dopo prima volta)
    - Frame raddrizzati: ~3-5s (cached dopo prima volta)
    - Inferenze: dipende dal modello (mock: ~istantaneo)

    I fallimenti per singolo evento NON bloccano gli altri: vengono
    riportati nella lista `falliti` del riepilogo.
    """
    servizio = _crea_servizio_cv()
    try:
        riepilogo = await servizio.analizza_tutti_eventi(
            db, partita_id, forza_raddrizzamento=forza_raddrizzamento,
        )
    except NotImplementedError as e:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Modello CV non configurato: {e}",
        ) from e
    return riepilogo
