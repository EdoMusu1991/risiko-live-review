"""
Promozione di un bundle mobile a Partita SQL.

Flusso:
1. L'app mobile carica il bundle via M14 (`POST /api/import/bundle-mobile`)
   → finisce in `storage_partite/<id_partita>/` (filesystem, niente DB)
2. Quando l'arbitro vuole iniziare la review, chiama
   `POST /api/partite/da-bundle/{id_partita}` → questo servizio:
   a. Legge il manifest in `storage_partite/<id_partita>/manifest.json`
   b. Crea un record `Partita` SQL
   c. Per ogni segmento video del manifest, crea un record `Video` linkato
      e sposta il file mp4 in `storage_video/`
   d. Per ogni evento di `eventi.jsonl`, crea un `EventoGrezzo` linkato
   e. Ritorna `id_partita` SQL + statistiche (n eventi importati, ecc.)

Idempotenza: se la `Partita` con `id == id_partita` esiste gia', solleva
`PartitaGiaPromossaError`. Se vuoi reimportare, devi prima cancellarla via
`DELETE /api/partite/{id}`.

Mapping campi:
- bundle.versione_app             → ignorato (info, non si persiste)
- bundle.device_id                → Partita.note (annotato)
- bundle.ts_inizio_registrazione  → Partita.data_inizio
- bundle.ts_fine_registrazione    → Partita.data_fine
- bundle.segmenti_video[i]        → Video record (ts_inizio, durata,
                                     risoluzione, codec lasciato a None
                                     perche' il manifest non lo dichiara)
- eventi.jsonl[i].ts_evento       → EventoGrezzo.ts_evento
- eventi.jsonl[i].tipo            → EventoGrezzo.tipo (validato vs TipoEvento)
- eventi.jsonl[i].fonte           → EventoGrezzo.fonte (mappato vs FonteEvento)
- eventi.jsonl[i].confidenza      → EventoGrezzo.confidenza
- eventi.jsonl[i].dati            → EventoGrezzo.dati

Eventi malformati (tipo sconosciuto, fonte non riconosciuta, confidenza fuori
range) NON bloccano l'import: vengono saltati e contati negli avvisi.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.configurazione import impostazioni
from app.modelli.partita import EventoGrezzo, Partita, Video
from app.modelli.tipi import FonteEvento, TipoEvento
from app.schemi.bundle_mobile import EventoBundle, Manifest

#: Mapping `bundle.fonte` → `FonteEvento`.
#: Il bundle usa "dado_ble"/"manuale"/"sistema"; il backend ha un'enum piu' ricca.
MAPPA_FONTE: dict[str, FonteEvento] = {
    "dado_ble": FonteEvento.DADO_BLE,
    "manuale": FonteEvento.INPUT_MANUALE,
    "sistema": FonteEvento.INPUT_MANUALE,  # fallback ragionevole per "sistema"
}


class BundleNonTrovatoError(Exception):
    """Sollevato quando la cartella bundle non esiste in storage_partite/."""


class BundleCorruttoError(Exception):
    """Sollevato quando il manifest e' mancante o non parsabile."""


class PartitaGiaPromossaError(Exception):
    """Sollevato quando esiste gia' una Partita con questo id."""


def cancella_bundle(id_partita: str) -> bool:
    """
    Cancella la cartella bundle in `storage_partite/<id_partita>/` se
    esiste. Idempotente. Ritorna True se ha cancellato qualcosa, False
    se la cartella non esisteva.
    """
    cartella = impostazioni.storage_partite_path / id_partita
    if not cartella.exists() or not cartella.is_dir():
        return False
    shutil.rmtree(cartella)
    return True


def cancella_bundle_vecchi(giorni: int) -> dict[str, int | list[str]]:
    """
    Cancella tutti i bundle il cui `manifest.json` riporta
    `ts_fine_registrazione` precedente a `now - giorni`.

    Bundle con manifest illeggibile vengono **saltati** (non cancellati)
    per sicurezza: meglio sprecare disco che cancellare per errore.

    Ritorna `{n_cancellati, ids_cancellati[]}`.
    """
    from datetime import datetime, timedelta

    base = impostazioni.storage_partite_path
    if not base.exists():
        return {"n_cancellati": 0, "ids_cancellati": []}

    soglia = datetime.now(UTC) - timedelta(days=giorni)
    cancellati: list[str] = []

    for cartella in base.iterdir():
        if not cartella.is_dir():
            continue
        manifest_path = cartella / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = Manifest.model_validate_json(manifest_path.read_bytes())
            ts_fine = _parse_iso(manifest.ts_fine_registrazione)
        except Exception:
            continue

        if ts_fine < soglia:
            shutil.rmtree(cartella)
            cancellati.append(cartella.name)

    return {"n_cancellati": len(cancellati), "ids_cancellati": cancellati}


def lista_bundle_disponibili() -> list[dict[str, str]]:
    """
    Lista i bundle in `storage_partite/` con un manifest valido.

    Per ogni bundle ritorna `{id_partita, ts_inizio, ts_fine, n_segmenti,
    n_eventi_dichiarati}`.
    """
    base = impostazioni.storage_partite_path
    if not base.exists():
        return []

    risultati: list[dict[str, str]] = []
    for cartella in base.iterdir():
        if not cartella.is_dir():
            continue
        manifest_path = cartella / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = Manifest.model_validate_json(manifest_path.read_bytes())
        except Exception:  # manifest corrotto: lo saltiamo silenziosamente
            continue
        risultati.append(
            {
                "id_partita": cartella.name,
                "ts_inizio": manifest.ts_inizio_registrazione,
                "ts_fine": manifest.ts_fine_registrazione,
                "n_segmenti": str(len(manifest.segmenti_video)),
                "n_eventi_dichiarati": str(manifest.n_eventi_ble),
            }
        )
    risultati.sort(key=lambda b: b["ts_inizio"], reverse=True)
    return risultati


async def promuovi_bundle_a_partita(
    db: AsyncSession,
    id_partita: str,
    *,
    luogo: str | None = None,
    note_extra: str | None = None,
) -> dict[str, int | str | list[str]]:
    """
    Crea record SQL `Partita` + `Video` + `EventoGrezzo` da un bundle
    gia' estratto in `storage_partite/<id_partita>/`.

    Ritorna `{id_partita, n_video, n_eventi_importati, n_eventi_scartati,
    avvisi[]}`.

    Raises:
        BundleNonTrovatoError: cartella bundle inesistente
        BundleCorruttoError: manifest mancante o non valido
        PartitaGiaPromossaError: gia' esiste record con questo id
    """
    avvisi: list[str] = []

    cartella_bundle = impostazioni.storage_partite_path / id_partita
    if not cartella_bundle.is_dir():
        raise BundleNonTrovatoError(
            f"bundle non trovato: {cartella_bundle}"
        )

    manifest_path = cartella_bundle / "manifest.json"
    if not manifest_path.exists():
        raise BundleCorruttoError(
            f"manifest.json mancante in {cartella_bundle}"
        )

    try:
        manifest = Manifest.model_validate_json(manifest_path.read_bytes())
    except Exception as e:
        raise BundleCorruttoError(f"manifest non parsabile: {e}") from e

    # Idempotenza: la partita non deve gia' esistere
    esistente = await db.scalar(
        select(Partita).where(Partita.id == id_partita)
    )
    if esistente is not None:
        raise PartitaGiaPromossaError(
            f"Partita {id_partita} gia' presente; cancellala prima di reimportare"
        )

    # 1. Crea Partita SQL
    note_iniziali = f"device_id={manifest.device_id}, app_v{manifest.versione_app}"
    if note_extra:
        note_iniziali += f"\n{note_extra}"

    partita = Partita(
        id=id_partita,
        data_inizio=_parse_iso(manifest.ts_inizio_registrazione),
        data_fine=_parse_iso(manifest.ts_fine_registrazione),
        luogo=luogo,
        note=note_iniziali,
    )
    db.add(partita)
    await db.flush()  # serve per fk dei figli

    # 2. Sposta segmenti video → storage_video/, crea record Video
    storage_video = impostazioni.storage_video_path
    storage_video.mkdir(parents=True, exist_ok=True)

    n_video = 0
    for seg in manifest.segmenti_video:
        src = cartella_bundle / seg.filename
        if not src.exists():
            avvisi.append(f"segmento {seg.filename} dichiarato ma assente: skip")
            continue

        # destinazione: storage_video/<id_partita>__<filename>
        # (prefisso id_partita evita collisioni tra bundle diversi)
        dst_name = f"{id_partita}__{seg.filename}"
        dst = storage_video / dst_name

        # spostiamo (rename atomico se stesso filesystem; altrimenti copy+delete)
        shutil.move(str(src), str(dst))

        video = Video(
            partita_id=id_partita,
            file_path=str(dst),
            nome_originale=seg.filename,
            ts_inizio=_parse_iso(seg.ts_inizio),
            durata_sec=seg.durata_sec,
            codec=None,
            risoluzione=f"{seg.larghezza}x{seg.altezza}",
            dimensione_byte=dst.stat().st_size,
        )
        db.add(video)
        n_video += 1

    # 3. Importa eventi.jsonl come EventoGrezzo
    n_importati = 0
    n_scartati = 0
    eventi_path = cartella_bundle / "eventi.jsonl"
    if eventi_path.exists():
        for n_riga, linea in enumerate(
            eventi_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not linea.strip():
                continue
            try:
                ev_bundle = EventoBundle.model_validate_json(linea)
            except Exception:
                n_scartati += 1
                if n_scartati <= 3:
                    avvisi.append(f"eventi.jsonl riga {n_riga}: parse error, skip")
                continue

            # Validazione tipo (deve essere in TipoEvento enum)
            try:
                tipo = TipoEvento(ev_bundle.tipo)
            except ValueError:
                n_scartati += 1
                if n_scartati <= 3:
                    avvisi.append(
                        f"eventi.jsonl riga {n_riga}: tipo '{ev_bundle.tipo}' "
                        f"non riconosciuto, skip"
                    )
                continue

            # Mapping fonte
            fonte = MAPPA_FONTE.get(ev_bundle.fonte)
            if fonte is None:
                n_scartati += 1
                if n_scartati <= 3:
                    avvisi.append(
                        f"eventi.jsonl riga {n_riga}: fonte '{ev_bundle.fonte}' "
                        f"non riconosciuta, skip"
                    )
                continue

            # Sanity check confidenza (gia' validata dal Pydantic, ma double-check)
            confidenza = max(0.0, min(1.0, ev_bundle.confidenza))

            evento = EventoGrezzo(
                partita_id=id_partita,
                ts_evento=_parse_iso(ev_bundle.ts_evento),
                tipo=tipo,
                fonte=fonte,
                confidenza=confidenza,
                dati=ev_bundle.dati,
            )
            db.add(evento)
            n_importati += 1

        if n_scartati > 3:
            avvisi.append(f"+{n_scartati - 3} altri eventi scartati (omessi)")
    else:
        avvisi.append("eventi.jsonl assente: partita senza eventi")

    await db.commit()

    # Pulizia: rimuoviamo la cartella bundle (i video sono stati spostati)
    # eventi.jsonl + manifest.json restano disponibili come backup, oppure no
    # Decisione: cancelliamo tutto. Il bundle e' nel DB ora.
    shutil.rmtree(cartella_bundle, ignore_errors=True)

    return {
        "id_partita": id_partita,
        "n_video": n_video,
        "n_eventi_importati": n_importati,
        "n_eventi_scartati": n_scartati,
        "avvisi": avvisi,
    }


def _parse_iso(s: str) -> datetime:
    """Parse ISO 8601 con timezone. Solleva ValueError se invalido."""
    return datetime.fromisoformat(s)
