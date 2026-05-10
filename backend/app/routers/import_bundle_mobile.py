"""
Endpoint per accettare bundle ZIP dall'app mobile Risiko Live (schema M14).

Differenze vs `import_bundle.py` (legacy, schema 1.0):
- Manifest con `segmenti_video[]` invece di `video` singolo
- Form fields aggiuntivi `device_id` e `id_partita` (ridondanti col manifest
  per defense-in-depth)
- Storage SOLO filesystem (`impostazioni.storage_partite_path / id_partita/`),
  niente record SQL `Partita`. Il flusso review SQL rimane sotto
  l'endpoint legacy `/api/import/bundle-mobile-legacy` finche' non
  decideremo come integrare.

Flusso:
1. Riceve multipart con `bundle` (file zip), `device_id`, `id_partita`
2. Stream verso tempfile, controllo dimensione (max 5 GB)
3. Apre lo zip → `manifest.json` deve esistere
4. Parsa manifest con Pydantic (errore 400 se corrotto/non valido)
5. Verifica che ogni `segmenti_video[].filename` esista nello zip (400 se manca)
6. Parsa `eventi.jsonl` riga per riga: righe corrotte → warning, NON errore
7. Sanity check: `n_eventi_ble` dichiarato vs contato → warning se mismatch
8. Estrazione zip in `storage_partite_path / id_partita/`
9. Risposta 200 con `RispostaImportBundle` + lista avvisi

Errori:
- 400: bundle malformato, manifest non valido, segmenti mancanti
- 413: bundle troppo grande (> 5 GB)
- 500: errore di scrittura storage (con cleanup della cartella parziale)
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError

from app.configurazione import impostazioni
from app.schemi.bundle_mobile import (
    VERSIONE_MANIFEST_SUPPORTATA,
    EventoBundle,
    Manifest,
    RispostaImportBundle,
)

router = APIRouter(prefix="/import", tags=["import"])

#: Soglia massima bundle: 5 GB (registrazione 2.5h FullHD ~3-4 GB).
DIMENSIONE_MAX_BUNDLE_BYTE = 5 * 1024 * 1024 * 1024


@router.post(
    "/bundle-mobile",
    response_model=RispostaImportBundle,
    status_code=status.HTTP_200_OK,
    summary="Importa bundle ZIP prodotto dall'app mobile (schema segmenti_video)",
)
async def import_bundle_mobile(
    bundle: UploadFile = File(...),
    device_id: str = Form(...),
    id_partita: str = Form(...),
) -> RispostaImportBundle:
    # validazione mime
    if bundle.content_type not in (
        "application/zip",
        "application/x-zip-compressed",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"content_type non valido: {bundle.content_type}",
        )

    # leggi tutto in tempfile per validazione zip
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        dimensione = 0
        while chunk := await bundle.read(1024 * 1024):
            dimensione += len(chunk)
            if dimensione > DIMENSIONE_MAX_BUNDLE_BYTE:
                Path(tmp.name).unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"bundle supera {DIMENSIONE_MAX_BUNDLE_BYTE} byte",
                )
            tmp.write(chunk)
        tmp_path = Path(tmp.name)

    try:
        return _processa_bundle(tmp_path, device_id, id_partita)
    finally:
        tmp_path.unlink(missing_ok=True)


def _processa_bundle(
    zip_path: Path,
    device_id: str,
    id_partita: str,
) -> RispostaImportBundle:
    avvisi: list[str] = []

    # apertura zip
    try:
        zf = zipfile.ZipFile(zip_path, "r")
    except zipfile.BadZipFile as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="bundle non e' un file ZIP valido",
        ) from e

    with zf:
        nomi_file = set(zf.namelist())

        # manifest.json deve esistere
        if "manifest.json" not in nomi_file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="manifest.json mancante nel bundle",
            )

        try:
            manifest_bytes = zf.read("manifest.json")
            manifest = Manifest.model_validate_json(manifest_bytes)
        except ValidationError as e:
            # in Pydantic v2 il JSON corrotto e' un ValidationError type='json_invalid'
            errors = e.errors()
            if errors and errors[0].get("type") == "json_invalid":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"manifest.json JSON corrotto: {errors[0].get('msg', '')}",
                ) from e
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"manifest.json non valido: {errors[:3]}",
            ) from e

        if manifest.versione_app != VERSIONE_MANIFEST_SUPPORTATA:
            avvisi.append(
                f"versione_app diversa da quella supportata "
                f"({manifest.versione_app} vs {VERSIONE_MANIFEST_SUPPORTATA})"
            )

        # device_id deve coincidere col form field (defense-in-depth)
        if manifest.device_id != device_id:
            avvisi.append(
                f"device_id form ({device_id}) != manifest.device_id "
                f"({manifest.device_id})"
            )

        # tutti i segmenti dichiarati devono esistere come file nel zip
        for seg in manifest.segmenti_video:
            if seg.filename not in nomi_file:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"segmento dichiarato ma mancante: {seg.filename}",
                )

        # eventi.jsonl: opzionale, parsing tollerante
        n_eventi_validi = 0
        n_eventi_corrotti = 0
        if "eventi.jsonl" in nomi_file:
            jsonl_bytes = zf.read("eventi.jsonl")
            for n_riga, linea in enumerate(
                jsonl_bytes.decode("utf-8").splitlines(),
                start=1,
            ):
                if not linea.strip():
                    continue
                try:
                    EventoBundle.model_validate_json(linea)
                    n_eventi_validi += 1
                except (ValidationError, json.JSONDecodeError):
                    n_eventi_corrotti += 1
                    if n_eventi_corrotti <= 5:
                        avvisi.append(f"riga {n_riga} di eventi.jsonl corrotta")

            if n_eventi_corrotti > 5:
                avvisi.append(
                    f"+{n_eventi_corrotti - 5} altre righe corrotte (omesse)"
                )
        else:
            avvisi.append("eventi.jsonl assente: bundle senza eventi BLE")

        # sanity: manifest dichiara n_eventi_ble vs quello che vediamo
        if manifest.n_eventi_ble != n_eventi_validi:
            avvisi.append(
                f"n_eventi_ble dichiarato ({manifest.n_eventi_ble}) != "
                f"contato ({n_eventi_validi})"
            )

        # persistenza: estraiamo in una directory dedicata sotto storage_partite_path
        dir_dest = impostazioni.storage_partite_path / id_partita
        if dir_dest.exists():
            avvisi.append(f"sovrascritta partita esistente: {id_partita}")
            shutil.rmtree(dir_dest)
        dir_dest.mkdir(parents=True, exist_ok=True)

        try:
            zf.extractall(dir_dest)
        except OSError as e:
            shutil.rmtree(dir_dest, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"errore scrittura storage: {e}",
            ) from e

    durata_totale = sum(s.durata_sec for s in manifest.segmenti_video)

    return RispostaImportBundle(
        id_partita=id_partita,
        n_segmenti=len(manifest.segmenti_video),
        n_eventi=n_eventi_validi,
        durata_totale_sec=durata_totale,
        avvisi=avvisi,
    )
