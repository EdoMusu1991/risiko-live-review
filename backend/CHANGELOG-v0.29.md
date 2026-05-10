# CHANGELOG v0.29 — promozione bundle mobile a Partita SQL

Continuazione di v0.28. Risolve la "decisione architetturale aperta": ora il
backend integra il flusso bundle mobile (M14, storage filesystem) con il
flusso review SQL completo.

## Cosa e' cambiato

### Nuovo: `POST /api/partite/da-bundle/{id_partita}`

Promuove un bundle gia' caricato da `storage_partite/<id>/` a record SQL
`Partita` + `Video[]` + `EventoGrezzo[]`. Solo dopo questa promozione il
flusso review (aggregazione, ricostruzione, discrepanze CV) puo' partire.

Body opzionale (`application/json`):
```json
{"luogo": "Il Gufo - Roma", "note_extra": "Torneo serale"}
```

Risposta 201:
```json
{
  "id_partita": "...",
  "n_video": 2,
  "n_eventi_importati": 142,
  "n_eventi_scartati": 3,
  "avvisi": ["..."]
}
```

Errori:
- 404: bundle non trovato in `storage_partite/`
- 400: manifest mancante o corrotto
- 409: Partita SQL gia' esistente con quell'id (idempotenza)

### Nuovo: `GET /api/partite/bundle-disponibili`

Lista i bundle in `storage_partite/` non ancora promossi. Utile per la UI
del backend (lista "in attesa di review").

Risposta:
```json
{
  "bundle": [
    {
      "id_partita": "abc-123",
      "ts_inizio": "2026-05-12T20:00:00+02:00",
      "ts_fine": "2026-05-12T22:30:00+02:00",
      "n_segmenti": 15,
      "n_eventi_dichiarati": 142
    }
  ]
}
```

Ordinato per `ts_inizio` decrescente (piu' recente prima).

### Mapping bundle → SQL

| Bundle | SQL |
|---|---|
| `manifest.versione_app` | annotato in `Partita.note` |
| `manifest.device_id` | annotato in `Partita.note` |
| `manifest.ts_inizio_registrazione` | `Partita.data_inizio` |
| `manifest.ts_fine_registrazione` | `Partita.data_fine` |
| `manifest.segmenti_video[i]` | record `Video` separato (uno per segmento, NO concatenazione ffmpeg) |
| `eventi.jsonl` riga | `EventoGrezzo` |
| `evento.fonte` | mappato: `dado_ble`→DADO_BLE, `manuale`→INPUT_MANUALE, `sistema`→INPUT_MANUALE |
| `evento.tipo` | validato vs enum `TipoEvento`; tipi sconosciuti scartati con warning |

I file mp4 vengono **spostati** (non copiati) da `storage_partite/<id>/` a
`storage_video/<id>__<filename>`. Dopo la promozione la cartella bundle
viene rimossa: i video sono nel DB+filesystem, gli eventi nel DB.

### Nuovo file di sorgenti

- `app/servizi/promozione_bundle_servizio.py` — logica di promozione
- `app/routers/promozione_bundle.py` — 2 endpoint
- `app/schemi/promozione_bundle.py` — schemi Pydantic richiesta/risposta

### Modifiche `app/main.py`

Il router `promozione_bundle` deve essere registrato **prima** di `partite`
nel `include_router` perche' `/partite/bundle-disponibili` altrimenti
verrebbe catturato da `/partite/{id_partita}` come `id="bundle-disponibili"`.

### Stato test

```
353 baseline (v0.28)
+13 test_promozione_bundle.py
───
366 passed in 10.10s
```

## Flusso end-to-end ora chiuso

```
[App mobile iPhone]
   │ registra video 2.5h + ascolta BLE 6 dadi
   │ produce bundle.zip (manifest.json + segmenti + eventi.jsonl)
   ▼
[POST /api/import/bundle-mobile]   ← M14 (v0.28)
   │ deposita in storage_partite/<id>/
   │ NESSUN record SQL, solo filesystem
   ▼
[storage_partite/<id>/]
   │ in attesa di promozione (puo' restare giorni)
   ▼
[GET /api/partite/bundle-disponibili]   ← v0.29
   │ UI vede la lista
   ▼
[POST /api/partite/da-bundle/<id>]      ← v0.29
   │ crea Partita SQL + Video[] + EventoGrezzo[]
   │ sposta mp4 in storage_video/
   │ rimuove storage_partite/<id>/
   ▼
[Flusso review esistente: aggregazione → ricostruzione → CV → discrepanze]
```

## Esempio uso da curl

```bash
# 1. (app mobile) upload bundle
curl -F bundle=@bundle.zip -F device_id=iphone-1 -F id_partita=p-001 \
  https://risiko-scores.up.railway.app/api/import/bundle-mobile

# 2. (operatore) lista bundle in attesa
curl https://risiko-scores.up.railway.app/api/partite/bundle-disponibili

# 3. (operatore) promuove a Partita
curl -X POST -H "Content-Type: application/json" \
  -d '{"luogo": "Il Gufo - Roma", "note_extra": "Torneo serale"}' \
  https://risiko-scores.up.railway.app/api/partite/da-bundle/p-001

# 4. (operatore) ora la Partita esiste nel flusso review SQL
curl https://risiko-scores.up.railway.app/api/partite/p-001
# → {id, data_inizio, data_fine, luogo, note, video[], stato_review, ...}
```

## Cosa restera' aperto

- **Cancellazione bundle non promossi** per cleanup automatico
  (`storage_partite/` puo' accumularsi). Suggerimento futuro: cron job
  che cancella bundle > 30 giorni non promossi, o endpoint
  `DELETE /api/partite/bundle/{id}`.
- **Streaming concatenato dei segmenti video** lato player frontend
  (HTML5 `<video>` con MediaSource Extensions o `hls.js` per playlist
  m3u8 generata dal backend). Non urgente: il review-player puo'
  mostrare i segmenti in lista e l'operatore navigare tra essi.
