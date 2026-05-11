# CHANGELOG v0.36 — Dashboard sommario sistema

Continuazione di v0.35. Aggiunge una pagina Dashboard nel frontend che
mostra in colpo d'occhio lo stato del sistema, alimentata da un nuovo
endpoint backend `/api/dashboard/sommario`.

## Backend

### Nuovo endpoint: `GET /api/dashboard/sommario`

Ritorna un sommario aggregato di tutte le metriche del sistema in una
singola chiamata (single round-trip per la dashboard frontend).

Risposta:

```json
{
  "partite": {
    "n_partite_totali": 42,
    "n_partite_ultimo_mese": 8,
    "n_partite_ultima_settimana": 2,
    "n_eventi_totali": 15234,
    "n_video_totali": 168,
    "durata_video_totale_sec": 378000
  },
  "bundle": {
    "n_bundle_in_attesa": 3,
    "dimensione_totale_byte": 8589934592,
    "bundle_piu_vecchio_giorni": 5
  },
  "spazio": {
    "storage_video_byte": 21474836480,
    "storage_frame_byte": 1073741824,
    "storage_partite_byte": 8589934592,
    "totale_byte": 31138512896
  },
  "servizi": {
    "scheduler_abilitato": true,
    "scheduler_in_esecuzione": true,
    "roboflow_configurato": false
  },
  "timestamp": "2026-05-11T14:23:45+00:00"
}
```

### Test

- 5 nuovi test in `tests/test_dashboard.py`
- Suite totale: **389 verdi** (384 baseline + 5 dashboard)
- Ruff pulito

## Frontend

### Nuova pagina `/dashboard`

4 sezioni a card:

1. **Partite** — counts totali/mensili/settimanali, eventi BLE, ore registrate
2. **Bundle in attesa** — count, dimensione, eta del piu' vecchio
3. **Spazio disco** — breakdown video/frame/bundle + totale
4. **Servizi** — pallini verde/grigio per scheduler e Roboflow

Polling automatico ogni 30 secondi.

### Voce di menu

Aggiunta "Dashboard" alla nav bar principale, dopo "Classifica club".

### Build

```
typecheck:  pulito
vite build: 492 kB → 141 kB gzip (+1 kB)
```

## Casi d'uso della Dashboard

1. **Verifica deploy**: dopo un deploy, apri /dashboard per vedere subito
   se servizi sono attivi e nessun bundle e' bloccato.
2. **Monitor spazio**: con storage limitato su Railway, vedere a colpo
   d'occhio quanto e' occupato. Se "Bundle" sale, lanciare cleanup.
3. **Stato pre-torneo**: prima di un evento al club, controllare che
   scheduler sia attivo e Roboflow (se configurato) sia raggiungibile.
4. **Health check sistematico**: alimentazione futura per un monitoring
   esterno (Uptime Kuma, ecc.) che fa GET su /dashboard/sommario.

## Stato sistema dopo v0.36

- Backend: 389/389 test verdi, ruff pulito
- Frontend: typecheck pulito, build 141 KB gzip
- App mobile: bundle `risiko-live-mobile.zip` consegnato (193 test verdi)
- Audit fix v2 applicato
- godice-lib v0.4 con auto-reconnect
- Roboflow scaffold completo

## Cosa resta aperto

- **Autenticazione**: la dashboard e' pubblica, accessibile a chiunque
  abbia l'URL Railway. Se vuoi limitare l'accesso, aggiungere un middleware
  semplice con basic auth (1 ora di lavoro).
- **Grafici storici**: la dashboard mostra solo lo snapshot corrente.
  Aggiungere serie temporali (es. partite/settimana) richiederebbe una
  tabella di telemetria + chart library. Non bloccante.
- **`img_riferimento.jpg`**: ancora da scattare al club per attivare
  pipeline CV.
