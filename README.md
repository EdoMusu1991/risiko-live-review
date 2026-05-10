# Risiko Live Review

Sistema per registrare, importare e revisionare partite di Risiko classico
giocate al club. Genera dataset strutturato + replay + statistiche aggregate.

## Architettura

```
DURANTE PARTITA (al club, no internet)
═══════════════════════════════════════
Singola app mobile (iOS+Android) su iPhone appeso al soffitto
  ├── Registra MP4 con AVCaptureSession
  ├── Ascolta BLE 6 GoDice (3 attaccante + 3 difensore, ROLI non giocatori)
  └── Tutto timestampato sullo stesso device

DOPO PARTITA (a casa, con internet)
═══════════════════════════════════════
App esporta bundle ZIP → upload a server (es. Railway)
  └── Backend processa: import → proposte aggregazione → review umana
       └── Frontend web: review eventi + ricostruzione partita + statistiche
```

## Pipeline dati end-to-end

```
1. App mobile registra al club
   └── bundle.zip = manifest.json + video.mp4 + eventi.jsonl
                            ↓
2. POST /api/import/bundle-mobile
   └── Crea Partita + Video + N EventoGrezzo (DADI_LANCIATI/DADO_BLE)
                            ↓
3. UI web: Pannello "Proposte aggregazione"
   └── POST /api/partite/{id}/proponi-aggregazioni-dadi
       Cluster temporale: 3 dadi att + 2 dif vicini = 1 proposta
                            ↓
4. Utente clicca "Accetta" → ModaleAccettaProposta
   └── Sceglie giocatore + territori da/a, corregge dadi se serve
                            ↓
5. POST /api/partite/{id}/accetta-aggregazione-dadi
   └── Crea EventoValidato (ATTACCO_RISOLTO)
       Marca EventoGrezzo citati come validato=true
                            ↓
6. POST /api/partite/{id}/ricostruisci
   └── risiko_engine applica eventi → StatoPartitaRicostruito
                            ↓
7. UI mostra plancia SVG + statistiche aggregate
```

## Componenti

### `backend/` — FastAPI service
Stack: Python 3.12, FastAPI, SQLAlchemy 2 async, Pydantic v2, Postgres
(prod) / SQLite (test), Alembic, ffprobe per metadata video.

**Routers**: `partite`, `eventi`, `video`, `ricostruzione`, `risorse`,
`esportazione`, `import_bundle`, `aggregazione`, `statistiche`,
`validazione`, `classifica_club`, `frame`, `raddrizzamento`,
`inferenze_cv`.

**Servizi (logica pura/quasi-pura)**: `partita_servizio`,
`setup_automatico_servizio` (genera 46 eventi setup),
`import_bundle_servizio`, `aggregazione_dadi_servizio` (clustering +
accetta), `ricostruzione_servizio` (wrap risiko_engine),
`statistiche_partita_servizio`, `validazione_coerenza_servizio`,
`classifica_club_servizio` (aggregazione cross-partita),
`esportazione_servizio`, `video_servizio`,
`estrazione_frame_servizio` (ffmpeg per CV), `raddrizzamento_servizio`
(OpenCV per CV), `discrepanze_servizio` (algoritmo CV ↔ motore puro).

**253 test verdi**, ruff + mypy strict puliti, deploy Railway pronto
(Dockerfile multi-stage + entrypoint Alembic + 2 migrazioni). Vedi
`backend/README.md`.

### Pipeline CV pronta (modello esterno)

Il backend espone gli step preparatori per il riconoscimento via
computer vision:

1. **Estrazione frame**: dato un video di partita, estrae il frame
   corrispondente al timestamp di ogni evento BLE (cache su disco).
   Endpoint: `GET /api/partite/{id}/eventi/{ev}/frame`.
2. **Raddrizzamento prospettico**: calibra una matrice di omografia
   per la partita (1 sola volta), poi applica il warp ai frame estratti
   per ottenere la "vista canonica" della plancia, in cui le pedine
   hanno scala stabile.
   Endpoint: `POST /api/partite/{id}/calibra-raddrizzamento`,
   `GET /api/partite/{id}/eventi/{ev}/frame-raddrizzato`,
   `POST /api/partite/{id}/raddrizza-tutti-eventi-validati`.
3. **Schema dati inferenze CV**: tabelle `InferenzaCV` (con bbox,
   confidence, scomposizione, modello_versione) e `DivergenzaInferita`
   (CV ↔ motore). Una pipeline esterna popola `InferenzaCV` via
   `POST /api/partite/{id}/inferenze-cv` (batch atomico).
4. **Algoritmo discrepanze**: `POST /api/partite/{id}/calcola-discrepanze`
   confronta lo stato motore (da `StatoPartitaRicostruito`) con le
   inferenze CV e produce divergenze ordinate per delta_assoluto.
5. **Review umana**: `GET /api/partite/{id}/discrepanze` ritorna le
   divergenze; `PATCH /api/partite/{id}/discrepanze/{div_id}` permette
   all'operatore di risolverle (`accettata_motore`, `accettata_cv`,
   `evento_aggiunto`).

OpenCV è dipendenza **opzionale**: si installa con
`pip install -e ".[cv]"`. Se non installato, gli endpoint di
raddrizzamento ritornano 503 con messaggio chiaro; il resto del backend
funziona invariato.

Il modello CV vero (Roboflow / YOLO / RT-DETR) è in addestramento in
una conversazione separata. Quando sarà pronto, l'integrazione richiede
solo un nuovo servizio `cv_servizio.py` che:
- Consuma i frame raddrizzati dagli endpoint sopra
- Chiama l'API Roboflow (o esegue inferenza locale)
- POSTa le inferenze al backend RL via `/inferenze-cv`
- Triggera `/calcola-discrepanze`

Tutto il resto (cache, schema, algoritmo, review) è già pronto e
testato.

### `frontend/` — React app
Stack: React 18, Vite, TypeScript strict, Tailwind 3, React Router v6.

Estetica "cartografia editoriale": pergamena + inchiostro + scarlatto,
font Fraunces + Inter Tight + JetBrains Mono.

Pagine: `ListaPartite`, `NuovaPartita`, `DettaglioPartita`.

Componenti chiave: `PlayerVideo` (HTTP Range scrubber), `PannelloEventi`
(filtri multi-dim), `PannelloProposteAggregazione`, `ModaleAccettaProposta`,
`PannelloStatistiche`, `PlanciaMappa` (SVG 42 territori), `FormEvento`.

Build production ~106 KB JS gzip + 6 KB CSS gzip. Vedi `frontend/README.md`.

### `risiko-godice-lib/` — Libreria TS
Cross-platform (web/Node/RN), parsing protocollo BLE GoDice + adapter
pattern (mock + RN/Web da implementare). 37 test verdi.

**Stato**: costanti del protocollo basate su API pubblica + ipotesi
ragionevoli. UUID, header byte e mappatura XYZ→faccia da **calibrare con
BLE sniffing** quando arriveranno i dadi reali. Vedi `../risiko-godice-lib/README.md`.

### `mobile/` — App React Native (scaffold)
Stack: RN 0.75 bare, TS strict, vision-camera, ble-plx, mmkv, zip-archive.

**Stato**: tipi domain, servizi (godice/registratore/bundleBuilder/
uploader/storageLocale stubbati), `SchermataSetup` completata.
Mancano 3 schermate + navigazione root. Build iOS richiede Mac
(in cloud o fisico). Vedi `mobile/README.md`.

### `packages/eventi-schema/` — Schema Zod condiviso
Schema TS dei 12 tipi di evento (discriminated union) + bundle replay,
verificato via round-trip Python→JSON→zod. Consumato dal frontend RL
(via `file:` dependency) e da Battle Commander (per il modulo replay).
29 test verdi. Vedi `packages/README.md`.

## Stato componenti

| Componente | Stato | Test |
|---|---|---|
| Backend pipeline import→aggregazione→accetta→ricostruzione | ✅ completo | 253 |
| Backend statistiche aggregate (attacco + difesa via motore) | ✅ completo | (incl.) |
| Backend validatore coerenza eventi pre-ricostruzione | ✅ completo | (incl.) |
| Backend export bundle replay per Battle Commander | ✅ completo | (incl.) |
| Backend classifica club cross-partita | ✅ completo | (incl.) |
| Backend export CSV per analytics esterne | ✅ completo | (incl.) |
| Backend elimina eventi grezzi batch atomico | ✅ completo | (incl.) |
| Backend estrazione frame da video (ffmpeg + cache) | ✅ completo | (incl.) |
| Backend raddrizzamento prospettico (OpenCV opzionale) | ✅ completo | (incl.) |
| Backend schema InferenzaCV + DivergenzaInferita | ✅ completo | (incl.) |
| Backend algoritmo discrepanze CV ↔ motore | ✅ completo | (incl.) |
| Backend endpoint review divergenze | ✅ completo | (incl.) |
| Frontend pannello validazione | ✅ completo | typecheck OK |
| Frontend pagina classifica club | ✅ completo | typecheck OK |
| Frontend rifiuta proposte batch + "rifiuta tutte" | ✅ completo | typecheck OK |
| Pacchetto `@risiko/eventi-schema` (zod) | ✅ completo | 29 |
| Backend deploy Railway-ready | ✅ Dockerfile + Alembic | — |
| Frontend review eventi + plancia + esportazione | ✅ completo | typecheck OK |
| Frontend modale accetta proposta BLE | ✅ completo | — |
| Frontend dashboard statistiche | ✅ completo | — |
| Seed demo testing senza app mobile | ✅ completo | 7 |
| Libreria GoDice (TS) | 🟡 ipotesi protocollo | 37 |
| App mobile React Native | 🟡 scaffold parziale | 0 |
| Calibrazione protocollo BLE GoDice | ❌ aspetta dadi fisici | — |
| Sprint 3 — replay con Battle Commander integrato | ❌ blocca su fix tris BC | — |
| Sprint 5 — CV su Roboflow/YOLO | ❌ rinviato post-MVP | — |

## Decisioni architettoniche chiave

**Postgres-only in produzione, SQLite per i test**: i test usano SQLite
in-memory per velocità (~5s per 165 test). Le migrazioni Alembic sono
testate solo su Postgres. Compromesso accettato perché business logic
non usa feature Postgres-specifiche.

**Storage video filesystem locale, non R2/S3**: Railway non ha disco
persistente — i video si perdono al redeploy. Per i primi test reali al
club è OK; quando servirà persistenza vera aggiungeremo R2 (Sprint 5+).
Lo `StorageVideo` è già wrappato in modo da poter aggiungere il backend
S3 senza toccare la business logic.

**Singola app mobile, no Raspberry Pi**: decisione presa dopo l'analisi
"camera + manual confirm" vs "load cells per territorio". L'iPhone al
soffitto registra video + ascolta BLE — un dispositivo, no rete al club,
no streaming live. Hardware ~80€ totali (6 GoDice).

**6 dadi associati a ruoli, non a giocatori**: 3 attaccante + 3 difensore.
Chi attacca prende i dadi attaccante, chi difende prende i difensore.
Questo permette di non duplicare hardware per ogni giocatore.

**CV non al 100% automatica**: il valore del sistema è BLE + regole +
review umana, non automazione totale. Il vero output è dataset + replay +
analytics, non un arbitro AI.

**Cross-platform mobile da subito (RN bare)**: né solo iOS né Expo. RN
bare permette accesso completo a vision-camera + ble-plx senza vincoli
Expo, e copre Android per futuri membri del club.

**Replay = Battle Commander integrato come libreria**: BC è un progetto
separato di Edoardo (clone Risiko in React). Verrà integrato nel frontend
review come "visore" con identità visuale propria. Bloccato finché BC
non risolve il bug tris.

## Quick start dev locale

```bash
# 1. Pacchetto condiviso (richiesto prima del frontend)
cd packages/eventi-schema
npm install
npm run build

# 2. Backend
cd ../../backend
pip install -e .
uvicorn app.main:app --reload  # http://localhost:8000

# 3. Frontend (altro terminale)
cd ../frontend
npm install
npm run dev  # http://localhost:5173

# 4. (opzionale) Popola dati demo per testare il flusso UI senza app mobile
cd ../backend
python scripts/seed_demo_ble.py
# → stampa l'URL della partita demo
```

## Schema bundle mobile (contratto stabile)

```
risiko-partita-{uuid}.zip
├── manifest.json      schema_version 1.0
├── video.mp4          MP4 H.264 (iPhone AVCaptureSession)
└── eventi.jsonl       una riga per pacchetto BLE
```

Vedi `mobile/docs/schema-bundle.md` per i campi completi.

## Roadmap

- ✅ Sprint 1: backend deploy-ready + import bundle endpoint
- 🟡 Sprint 2: scaffold app RN (parziale; aspetta Mac in cloud)
- ❌ Sprint 3: replay BC integrato (aspetta fix tris BC)
- ❌ Sprint 4: test reale al club con dadi GoDice fisici
- ❌ Sprint 5: CV (Roboflow / YOLO) per riconoscimento carri/carte
