# Scripts di sviluppo e manutenzione

Questo è un drawer di script Python usabili durante lo sviluppo e
operations. Non fanno parte del servizio runtime (non sono importati
da `app/`).

## seed_demo_ble.py

Popola il DB con una partita demo + giocatori + eventi BLE plausibili,
così puoi testare il flusso UI di review delle proposte di aggregazione
**senza dover passare dall'app mobile** (che non esiste ancora).

### Uso

Avvia prima il backend in dev (es. `uvicorn app.main:app --reload`),
poi in un altro terminale:

```bash
# Da /backend
python scripts/seed_demo_ble.py
```

Output:

```
✓ Partita seed creata: id=…, 3 giocatori, 3 attacchi → 10 eventi BLE grezzi

============================================================
FRONTEND URL (default Vite dev server):
  http://localhost:5173/partite/63ca4e27-…
============================================================
```

Apri l'URL e dovresti vedere:
- Partita "Il Gufo · Roma (DEMO)" con 3 giocatori (Edoardo/Marco/Alice)
- Pannello "Proposte aggregazione dadi BLE" con 3 proposte:
  1. Attacco pulito 3v3 (confidenza 1.0)
  2. Attacco 2v1 (confidenza 1.0)
  3. Attacco 1v0 (confidenza 0.5, anomalia "nessun dado difensore")

Click "Accetta" su una proposta → si apre `ModaleAccettaProposta`,
compili giocatore + territori + dadi, conferma → la proposta sparisce
dalla lista e compare un nuovo `EventoValidato` di tipo `attacco_risolto`
nel pannello eventi.

**Bonus**: dopo aver accettato almeno una proposta, il `PannelloStatistiche`
sotto lo stato finale si auto-popola mostrando metriche per giocatore
(numero attacchi, dadi tirati, conquiste, perdite/vincite armate) e
totali partita (n_turni, durata, n_attacchi).

### Idempotenza

Lo script è idempotente: se trovi una partita con `note="Demo BLE Seed"`,
la riusa. Per ricreare da zero usa `--reset`.

```bash
# Riusa la stessa partita seed (no-op se già presente)
python scripts/seed_demo_ble.py

# Elimina e ricrea (utile dopo aver "consumato" tutte le proposte)
python scripts/seed_demo_ble.py --reset

# Solo 1 attacco invece di 3
python scripts/seed_demo_ble.py --reset --n-attacchi 1
```

### Configurazione DB

Il seed scrive sul DB configurato dalle stesse env vars usate dal
backend (`RISIKO_DATABASE_URL`). In sviluppo locale di solito è
SQLite o un Postgres docker-compose; non puntare mai questo script
verso un DB di produzione.

## verifica_e2e.py

Smoke test diverso: costruisce un bundle ZIP "realistico" e lo invia
a `POST /api/import/bundle-mobile` per verificare che l'endpoint
import funzioni. Lanciare con `python verifica_e2e.py`.

A differenza del seed, questo va attraverso l'API HTTP, quindi il
backend deve essere già attivo su `localhost:8000`.

## genera_bundle_esempio.py

Genera un bundle replay (JSON conforme a `@risiko/eventi-schema`
`BundleReplay`) usabile come fixture per test:

- Test di Battle Commander quando integra il modulo replay
- Test del frontend RL quando avrà il visore replay
- Smoke test del contratto cross-system

### Uso

```bash
# Default output: ./bundle-replay-esempio.json
python scripts/genera_bundle_esempio.py

# Output custom (es. aggiornare fixture del pacchetto zod)
python scripts/genera_bundle_esempio.py \
  ../packages/eventi-schema/fixtures/bundle-replay-esempio.json
```

Lo script costruisce un DB SQLite in-memory dedicato (non tocca quello
configurato), simula una partita 3 giocatori con setup automatico + 5
turni con rinforzi/attacchi/conquiste, ed esporta il bundle. Output
deterministico (seed RNG = 42).

Output di esempio (variabile per stati casuali):

```
Bundle scritto: bundle-replay-esempio.json
  schema_version: 1.0
  giocatori: 3
  eventi: 69
  per tipo:
    armate_piazzate: 5
    attacco_risolto: 6
    obiettivo_assegnato: 3
    partita_inizio: 1
    territorio_assegnato_inizio: 42
    territorio_conquistato: 2
    turno_finito: 5
    turno_iniziato: 5
```
