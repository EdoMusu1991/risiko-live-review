# CHANGELOG v0.28 — patch backend M14, M17, M19, M20

Patch derivate dal lavoro dell'app mobile (chat parallela). Tutte le 4
patch sono additive, nessuna regressione sui 303 test esistenti.

## Cosa e' cambiato

### M14 — Bundle mobile con `segmenti_video[]`

Nuovo endpoint **`POST /api/import/bundle-mobile`** che accetta lo schema
nuovo del bundle prodotto dall'app mobile (Vision Camera ruota il
segmento video ogni 10min, quindi il manifest contiene una lista di
segmenti).

- Modello Pydantic: `app/schemi/bundle_mobile.py`
- Router: `app/routers/import_bundle_mobile.py`
- Storage: `impostazioni.storage_partite_path` (default `./storage_partite`,
  override via env `STORAGE_PARTITE_PATH` su Railway con volume persistente)
- Limite: 5 GB → 413
- Validazione tollerante: righe `eventi.jsonl` corrotte sono warning, non errore
- 15 test verdi in `tests/test_import_bundle_mobile.py`

**L'endpoint legacy** `POST /api/import/bundle-mobile-legacy` resta in
piedi (era `bundle-mobile` prima di questa patch) e mantiene il flusso
SQL completo (crea record `Partita`, processa eventi → `EventoGrezzo`).
Cosi' nessuna funzionalita' esistente e' rotta.

**Decisione architetturale aperta**: M14 NON crea record SQL. Lo storage
e' solo filesystem. Quando l'app mobile manda un bundle, ottieni una
cartella `storage_partite/<id_partita>/` con `manifest.json`, segmenti
mp4, e `eventi.jsonl`, ma niente record nel DB. Il flusso review
SQL→aggregazione→ricostruzione→CV richiede una `Partita` SQL: dovrai
decidere se M14 deve creare la `Partita` direttamente, o se serve un
secondo endpoint "promuovi bundle a partita SQL" da chiamare quando
inizia la review.

### M17 — Health/version

- `GET /api/health` → `{status, timestamp ISO UTC, uptime_sec}` per Railway
  uptime monitoring
- `GET /api/version` → legge `APP_VERSION` e `APP_COMMIT` da env, fallback
  `"dev"` / `null`. Include anche `python` e `fastapi` version.
- 6 test verdi in `tests/test_health.py`

### M19 — Logging strutturato + RequestId

- `app/utili/logging_setup.py`: formatter JSON line-per-line con
  `ts`/`level`/`logger`/`msg`/`extra`/`request_id`. Idempotente.
- `app/middleware/request_id.py`: middleware che assegna UUID v4 a ogni
  richiesta (riusa `X-Request-ID` se presente), propaga via context var,
  aggiunge l'header alla response, logga `request inizio/fine` con
  method/path/status.
- `configura_logging()` chiamato all'avvio in `lifespan`.
- 20 test verdi in `tests/test_logging_setup.py` + `tests/test_request_id.py`

### M20 — Error handler globale + CORS expose_headers

- `app/middleware/error_handler.py`: `@app.exception_handler(Exception)`
  cattura le eccezioni non-HTTPException → 500 JSON con
  `{errore, request_id, tipo}` e header `X-Request-ID`.
- CORS aggiornato con `expose_headers=["X-Request-ID"]` per permettere
  ai client browser di leggere l'header dalla response.
- 9 test verdi in `tests/test_error_handler.py`

## Stato test (cumulativo)

```
303 baseline pre-patch
+10 test_import_bundle.py legacy aggiornati al nuovo path
 +6 test_health.py                          (M17)
+11 test_logging_setup.py                   (M19)
 +9 test_request_id.py                      (M19)
 +9 test_error_handler.py                   (M20)
+15 test_import_bundle_mobile.py            (M14)
───
353 passed in 11.22s
```

## Variabili d'ambiente nuove

| Var | Default | Note |
|-----|---------|------|
| `APP_VERSION` | `"dev"` | Esposta da `GET /api/version` |
| `APP_COMMIT` | `null` | Esposta da `GET /api/version` |
| `STORAGE_PARTITE_PATH` | `./storage_partite` | Cartella di destinazione M14 bundle |
| `CORS_ORIGINS` (gia' esistente) | `["http://localhost:5173", "http://localhost:3000"]` | Aggiungere produzione (es. URL Railway frontend) |

## Deploy Railway — checklist

1. Push del branch al repo `risiko-webapp`
2. Su Railway, settare nelle variabili:
   - `APP_VERSION=v0.28`
   - `APP_COMMIT=$RAILWAY_GIT_COMMIT_SHA`
   - `STORAGE_PARTITE_PATH=/data/partite` (con volume montato su `/data`)
   - `CORS_ORIGINS=["https://risiko-scores.up.railway.app", "http://localhost:5173"]`
3. Aggiungere volume persistente in Railway (almeno 50 GB per ~10 partite)
4. Redeploy → verificare `GET /api/health` risponde 200 e `GET /api/version`
   mostra il commit
5. App mobile: l'URL upload e' `https://<railway>/api/import/bundle-mobile`,
   payload multipart con `bundle`, `device_id`, `id_partita`
