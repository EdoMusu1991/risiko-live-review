# CHANGELOG v0.34 — ClientCVRoboflow implementato

Continuazione di v0.33. Il backend ora supporta inferenze CV reali via
Roboflow API, oltre che il mock esistente.

## Backend

### `ClientCVRoboflow` ora funzionante

Il metodo `inferisci(percorso_frame_raddrizzato)` ora:
1. Apre il file frame in modalita' binaria
2. Chiama POST a `{endpoint}?api_key=...&confidence=...&overlap=...&format=json`
3. Parsa il JSON di Roboflow:
   - `predictions[*]` con `x`, `y`, `width`, `height` (centro bbox)
   - Convertito a top-left per coerenza con `DetectionCV.bbox`
   - `class` (string) parsata via `_parsa_classe_default` o callable custom
4. Ritorna `list[DetectionCV]` con `territorio=None` (mappato downstream)

Convenzione classe Roboflow: `<colore>_<tipo>_<n_armate>`. Esempi:
- `rosso_carro_piccolo_3`
- `blu_carro_grande_2`

Classi non parsabili: detection comunque tornata ma con campi semantici
`None`/`0`. Il `ServizioCV` puo' filtrarle o conservarle per debug.

### Nuove env vars

| Var | Default | Descrizione |
|---|---|---|
| `ROBOFLOW_API_KEY` | `""` | API key Roboflow (vuota = usa mock) |
| `ROBOFLOW_ENDPOINT` | `""` | URL completo modello (es. `https://detect.roboflow.com/risiko/3`) |
| `ROBOFLOW_CONFIDENCE_MIN` | `0.5` | Soglia confidence per filtrare detection |
| `ROBOFLOW_IOU_MIN` | `0.5` | IoU threshold per NMS |

### Selezione automatica client

`_crea_servizio_cv()` ora controlla le env e istanzia:
- `ClientCVRoboflow` se `ROBOFLOW_API_KEY` E `ROBOFLOW_ENDPOINT` sono settate
- `ClientCVMock` altrimenti (dev/test, default)

### Stato test

- 383 verdi (-1 placeholder + 3 nuovi su `ClientCVRoboflow`)
- Test usano `monkeypatch` su `httpx.AsyncClient.post` per simulare
  risposta Roboflow → niente call reale all'API nei test
- Test coperti:
  - parsing predictions ben formate
  - detection con classe non parsabile (campi semantici None)
  - errore 404 → `ClientCVError`
  - parser default su 7 casi limite

## Scaffold Roboflow (zip separato)

`roboflow-scaffold.zip` (11 KB) — workflow completo per passare dal
mock al modello reale:

- `docs/GUIDELINE_ANNOTAZIONE.md` — regole per annotare la plancia
  (convenzioni classi, casi limite, target #frame)
- `script/estrai_frame_per_roboflow.py` — scarica frame dal backend
  Railway, ogni N secondi, in cartella locale (idempotente)
- `script/upload_a_roboflow.py` — upload bulk a Roboflow via API, con
  split train/valid/test automatico (70/20/10), tagging batch
- `README.md` — workflow end-to-end in 9 fasi (registra partita → train
  modello → deploy)

## Stato sistema dopo v0.34

Edoardo puo' ora:
1. Registrare partite sull'app mobile (con tutte le patch + audit)
2. Caricarle sul backend Railway
3. Promuoverle a Partita SQL via UI /bundle
4. Estrarre frame da /api/partite/<id>/video/<vid>/frame-raddrizzato
5. Uploadarle su Roboflow per annotazione
6. Annotare con la convenzione `<colore>_<tipo>_<n>`
7. Allenare il modello v1
8. Settare le env Roboflow su Railway
9. Riprocessare le partite → discrepanze CV reali invece di mock

## Cosa resta aperto

- **`img_riferimento.jpg`**: foto canonica plancia vuota dall'alto per
  raddrizzamento. Da scattare al club. 5 minuti di lavoro.
- **Mapping `bbox → territorio`**: codice in `ServizioCV.mappa_bbox_a_territorio`
  da calibrare con coordinate dei territori sulla `img_riferimento.jpg`
  (file JSON con bounding box per ogni territorio). 2 ore di lavoro
  manuale una volta.
- **Pre-loading segmento video successivo nel player**: quality-of-life.
- **Endpoint `POST /api/scheduler/run-now`**: forza esecuzione cleanup
  per testare. 5 minuti.
