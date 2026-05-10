# CHANGELOG v0.33 — Scheduler in-process per cleanup automatico

Continuazione di v0.32. Aggiunge cleanup automatico dei bundle vecchi
non promossi senza dipendenze esterne (no cron Railway).

## Backend

### Nuove dipendenze

- `apscheduler>=3.10.0` (~2 MB, zero dep transitive pesanti)

### Nuove env var

| Var | Default | Descrizione |
|---|---|---|
| `SCHEDULER_ABILITATO` | `false` | Abilita lo scheduler in-process |
| `BUNDLE_CLEANUP_GIORNI` | `30` | Bundle scaduti dopo N giorni vengono cancellati |
| `BUNDLE_CLEANUP_ORA` | `03:00` | Ora del giorno (HH:MM) per il cleanup |

In Railway, settare `SCHEDULER_ABILITATO=true` per abilitare.

### Nuovo modulo: `app/utili/scheduler.py`

`AsyncIOScheduler` di APScheduler integrato nel lifespan di FastAPI.
Il job `_job_cleanup_bundle()` viene schedulato giornalmente all'ora
configurata, chiama `cancella_bundle_vecchi(giorni)` (gia' esistente).

API pubblica:
- `avvia_scheduler()` — chiamata in `lifespan` startup
- `ferma_scheduler()` — chiamata in `lifespan` shutdown
- `stato_scheduler()` — diagnostica per endpoint

### Nuovo endpoint: `GET /api/scheduler`

Ritorna lo stato corrente:
```json
{
  "abilitato": true,
  "in_esecuzione": true,
  "prossima_esecuzione": "2026-05-11T03:00:00+02:00",
  "giorni_cleanup": 30
}
```

### Test

- 9 nuovi test in `tests/test_scheduler.py`
- Suite totale: **381 verdi** (372 baseline + 9 nuovi)
- Ruff pulito

## Frontend

### Pagina Bundle in attesa: pannello "Cleanup automatico"

Aggiunta sezione in fondo alla pagina che mostra:
- Pallino verde/oro/grigio (in_esecuzione / abilitato_non_avviato / disabilitato)
- Testo descrittivo con prossima esecuzione formattata in italiano
- Suggerimento env var se disabilitato

Polling ogni 60 secondi del `/api/scheduler` (silenziosamente fallisce se
backend e' su versione vecchia, niente errore visibile).

### Nuovo client API

`apiScheduler.stato()` → `Promise<StatoScheduler>`

### Build

```
typecheck:  pulito
vite build: 492 kB → 140 kB gzip (+0.5 kB rispetto v0.32)
```

## Setup Railway

1. Push del codice v0.33 sul repo
2. In Railway dashboard, settare le env vars:
   ```
   SCHEDULER_ABILITATO=true
   BUNDLE_CLEANUP_GIORNI=30
   BUNDLE_CLEANUP_ORA=03:00
   ```
3. Redeploy
4. Verifica: `curl https://railway-url/api/scheduler` → `in_esecuzione: true`

## Cosa resta aperto

- **Roboflow scaffold**: directory + script di estrazione frame +
  guideline annotazione. Da fare quando avrai foto vere della plancia
  al club.
- **Pre-loading segmento successivo nel video player**: micro-pausa di
  100-300ms tra segmenti. Quality-of-life, non bloccante.
- **Endpoint POST /api/scheduler/run-now**: chiama manualmente il job
  cleanup senza aspettare il trigger. Utile per testare. 5 minuti di
  lavoro quando serve.
