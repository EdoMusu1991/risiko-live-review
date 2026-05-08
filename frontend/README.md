# risiko-live (monorepo)

Monorepo che contiene Risiko Live Review (frontend) e i pacchetti
condivisi del dominio Risiko classico EG (schema eventi, replay engine,
mappa, viewer player).

## Struttura

```
risiko-live/
├── packages/
│   ├── eventi-schema/          Schema condiviso degli eventi (Zod)
│   ├── replay-lib/             Replay engine (StatoPartita, Timeline)
│   ├── map-classico/           Mappa SVG editoriale + dati strutturali
│   └── replay-player/          Viewer "out of the box" (replay-lib + mappa)
├── frontend/                   Risiko Live Review frontend (React + Vite)
├── tsconfig.base.json
├── package.json                npm workspaces
└── README.md
```

## Dipendenze tra i pacchetti

```
                                      eventi-schema
                                     /             \
                                  replay-lib    map-classico
                                     \             /
                                      replay-player
                                            |
                                       frontend RL
```

`eventi-schema` è il pacchetto fondamentale, source-of-truth per gli
schemi Zod. Mirror del backend FastAPI/Pydantic.

## Setup

```bash
# dalla root del monorepo
npm install      # installa tutti i workspace in un colpo solo

# test e typecheck globali
npm run test:run
npm run typecheck

# o per pacchetto specifico
cd packages/replay-lib && npm run test:run
```

## Frontend

```bash
cd frontend
npm run dev      # localhost:5173, proxy /api → :8000 (FastAPI)
npm run build    # tsc -b && vite build
```

Il frontend consuma 4 pacchetti workspace:
- `@risiko/eventi-schema` per i tipi Zod (validation lato client)
- `@risiko/map-classico` per la mappa (PlanciaMappa.tsx ne è un thin wrapper)
- `@risiko/replay-lib` per il motore replay (transitivo via replay-player)
- `@risiko/replay-player` per il viewer completo

Il `RisikoReplayPlayer` è integrato in `PaginaDettaglioPartita.tsx` come
nuova sezione, sotto lo stato finale ricostruito. Si attiva quando la
ricostruzione ha prodotto un `stato_finale` (= la partita è almeno
parzialmente ricostruibile).

## Pacchetti

| Nome | Versione | Test | Descrizione |
|---|---|---|---|
| `@risiko/eventi-schema` | 0.1.0 | 28 | Zod schemas, fonte unica per il dominio eventi |
| `@risiko/replay-lib` | 0.1.0 | 50 | StatoPartita, Timeline, importatori, adapter BC |
| `@risiko/map-classico` | 0.1.0 | 11 | Mappa SVG + dati strutturali (42 territori) |
| `@risiko/replay-player` | 0.1.0 | 6 | Wrapper RisikoReplayPlayer + narrative |

Totale 95 test verdi. Typecheck stretto pulito.

## Integrazione esterna (Battle Commander)

Battle Commander (repo separato) consumerà gli stessi pacchetti via:

- **Git submodule** del monorepo, importando `risiko-live/packages/`, oppure
- **npm registry privato** quando i pacchetti saranno pubblicati

Per ora BC usa una copia vendored di `@risiko/replay-lib` (sessione
precedente). Sostituibile con un import workspace al prossimo refactor.

## Workspaces e versioning

I pacchetti sono `private: true` e usano `"*"` come version specifier
nelle dipendenze incrociate. npm workspaces risolve i link interni
automaticamente.

Per pubblicare su npm: rimuovere `private: true`, aggiungere `"build": "tsc"`,
generare `dist/` e cambiare `main`/`types`/`exports` per puntare al build.
Il setup attuale è source-only (no build step) per lo sviluppo veloce
intra-monorepo.

## Stack frontend

- React 18 + Vite 5 + TypeScript 5.5
- Tailwind 3
- @tanstack/react-query 5
- React Router 6
- date-fns 4
- lucide-react

## Stack pacchetti

- TypeScript 5.6
- Zod 3
- Vitest 2
- React 18 (peer dependency dei pacchetti UI: map-classico, replay-lib/react, replay-player)
