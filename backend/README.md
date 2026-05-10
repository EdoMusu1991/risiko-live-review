# Risiko Live Review — Backend

Backend FastAPI per la review e validazione di partite Risiko.

## Requisiti

- Python 3.12+
- (opzionale) Docker Desktop per Postgres

## Setup rapido (SQLite, no Docker)

Per partire subito senza Docker, usa SQLite. Su PowerShell Windows:

```powershell
cd backend

# Crea ambiente virtuale
python -m venv .venv
.venv\Scripts\Activate.ps1

# Installa dipendenze
pip install -e ".[dev]"

# Copia file env
Copy-Item .env.example .env

# Avvia il server
uvicorn app.main:app --reload
```

Il server gira su <http://localhost:8000>. Documentazione interattiva su <http://localhost:8000/docs>.

## Setup con Postgres (Docker)

Più realistico per ambiente che simula produzione:

```powershell
# Avvia Postgres + Adminer
cd ..
docker-compose up -d

# Modifica backend/.env e usa:
# RISIKO_DATABASE_URL=postgresql+asyncpg://risiko:risiko_dev_password@localhost:5432/risiko_review

cd backend
uvicorn app.main:app --reload
```

Adminer (interfaccia DB web) gira su <http://localhost:8080>.

## Test

```powershell
pytest                    # tutti i test
pytest tests/test_partite.py -v   # un singolo file
pytest -k "crea_partita" -v       # filtra per nome
```

I test usano SQLite in-memory, sono indipendenti dal DB di sviluppo.

## Lint e type check

```powershell
ruff check .              # lint
ruff check . --fix        # autofix
mypy app                  # type check (strict)
```

## Struttura del codice

```
backend/
├── app/
│   ├── main.py              # entry point FastAPI
│   ├── configurazione/      # settings + DB connection
│   ├── modelli/             # SQLAlchemy ORM
│   ├── schemi/              # Pydantic v2 (request/response + dati eventi + snapshot)
│   ├── routers/             # endpoint API (partite, eventi, video, ricostruzione)
│   ├── servizi/             # business logic (incl. ricostruzione via risiko_engine)
│   └── storage/             # gestione filesystem video + ffprobe
├── risiko_engine/           # motore regole Risiko (copia da Fase 1)
├── tests/                   # pytest
├── alembic/                 # migrazioni DB (TBD)
└── pyproject.toml
```

## API endpoints disponibili (v0.3)

### Partite

- `POST /api/partite` — crea nuova partita
- `GET /api/partite` — lista partite (paginata, filtrabile per stato)
- `GET /api/partite/{id}` — dettaglio partita
- `PATCH /api/partite/{id}` — aggiorna metadata
- `DELETE /api/partite/{id}` — elimina partita (con cleanup video filesystem + snapshot)
- `POST /api/partite/{id}/setup-automatico` ⭐ NUOVO in v0.6 — distribuzione automatica territori/obiettivi/partita_inizio

### Eventi grezzi

- `POST /api/partite/{id}/eventi-grezzi` — aggiungi evento grezzo singolo
- `POST /api/partite/{id}/eventi-grezzi/batch` — upload batch
- `GET /api/partite/{id}/eventi-grezzi` — lista (con filtro `solo_non_validati`)
- `DELETE /api/partite/{id}/eventi-grezzi/{eid}` — elimina evento

### Eventi validati

- `POST /api/partite/{id}/eventi-validati` — promuovi grezzo o crea manuale
- `POST /api/partite/{id}/eventi-validati/batch` ⭐ NUOVO in v0.6 — inserimento atomico di N eventi (es. setup automatico)
- `GET /api/partite/{id}/eventi-validati` — lista
- `PATCH /api/partite/{id}/eventi-validati/{eid}` ⭐ NUOVO in v0.5 — modifica un evento (ts/tipo/dati/validato_da)
- `DELETE /api/partite/{id}/eventi-validati/{eid}` ⭐ NUOVO in v0.5 — elimina un evento

### Risorse statiche ⭐ NUOVO in v0.6

- `GET /api/risorse/territori` — lista 42 territori canonici con adiacenze e continente
- `GET /api/risorse/obiettivi` — lista 16 obiettivi del Risiko classico EG

### Video

- `POST /api/partite/{id}/video` — upload video (multipart, streaming, max 10 GB default)
- `GET /api/partite/{id}/video` — lista video di una partita
- `GET /api/partite/{id}/video/{vid}` — metadata video
- `GET /api/partite/{id}/video/{vid}/stream` — streaming con supporto **HTTP Range** (seekable)
- `DELETE /api/partite/{id}/video/{vid}` — elimina video (DB + filesystem)

### Ricostruzione partita ⭐ NUOVO in v0.3

- `POST /api/partite/{id}/ricostruisci` — applica gli eventi validati al motore `risiko_engine` per produrre lo stato finale
- `GET /api/partite/{id}/stato-finale` — ritorna l'ultimo snapshot ricostruito

### Health

- `GET /` — info API
- `GET /healthz` — health check

## Dipendenze esterne

### ffprobe (richiesto per upload video)

Il backend usa `ffprobe` (parte di FFmpeg) per estrarre i metadata
(durata, codec, risoluzione, ts_creazione) dai video caricati.

**Installazione su Windows:**

```powershell
# Opzione 1: winget (Windows 10/11)
winget install ffmpeg

# Opzione 2: scoop
scoop install ffmpeg

# Opzione 3: download manuale
# https://www.gyan.dev/ffmpeg/builds/ → release essentials
# Scompatta e aggiungi /bin al PATH
```

Verifica:
```powershell
ffprobe -version
```

Se ffprobe non è disponibile, l'endpoint upload risponde 500 con messaggio chiaro.

## Motore regole (`risiko_engine`)

Il backend include il pacchetto `risiko_engine/` come **sotto-package
self-contained**, copiato dal repo Fase 1.

Funzionalità coperte dalla ricostruzione (v0.3):
- 9 applicatori `TipoEvento → metodo MotorePartita`: territorio_assegnato_inizio, obiettivo_assegnato, partita_inizio, armate_piazzate, tris_giocato, attacco_risolto, armate_spostate, turno_finito.
- **Transizioni di fase implicite**: l'utente non deve creare eventi finti per `passa_a_attacco`/`passa_a_spostamento`. Il dispatcher li chiama automaticamente quando serve.
- **Error recovery**: gli eventi che falliscono (payload invalido, azione illegale, tipo non supportato) sono registrati nella lista `errori` della risposta, ma non bloccano il resto della ricostruzione.
- **Idempotenza**: ogni `POST /ricostruisci` sostituisce lo snapshot precedente. Stessi eventi → stesso stato finale.

Per modifiche al motore, lavorare sul repo Fase 1 separato e ricopiare
la cartella `risiko_engine/` qui dentro.

## Roadmap immediata

- ✅ Setup base, modelli, endpoint CRUD partite/eventi (v0.1)
- ✅ Upload video con metadata extraction via ffprobe (v0.2)
- ✅ Streaming video con HTTP Range (seekable nel browser)
- ✅ Endpoint ricostruzione partita via `risiko_engine` (v0.3)
- ✅ PATCH/DELETE eventi validati per editor interattivo (v0.5)
- ✅ Setup automatico partita (regole EG, distribuzione round-robin, seed riproducibile) (v0.6)
- ⬜ Migrazioni Alembic
- ⬜ WebSocket per broadcast eventi (UI live)
- ⬜ Promozione grezzo → validato dalla UI
