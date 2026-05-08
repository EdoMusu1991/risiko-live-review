# Installazione fase 2 - Monorepo Risiko Live

Questo zip contiene il monorepo completo `risiko-live/` con:

- 3 pacchetti nuovi: `replay-lib`, `map-classico`, `replay-player`
- Pacchetto esistente `eventi-schema` (config aggiornato a source-only)
- Frontend RL aggiornato per consumare i 4 pacchetti

## Cosa c'è nello zip

```
risiko-live/
├── INSTALLAZIONE.md            ← questo file
├── README.md                   ← panoramica del monorepo
├── package.json                ← npm workspaces, scripts globali
├── tsconfig.base.json          ← config TS condivisa
├── packages/
│   ├── eventi-schema/          (existing, package.json riallineato)
│   ├── replay-lib/             (NUOVO)
│   ├── map-classico/           (NUOVO)
│   └── replay-player/          (NUOVO)
└── frontend/                   (RL frontend, modificato)
    ├── package.json            ← 4 deps workspace (era 1)
    ├── src/componenti/
    │   ├── PlanciaMappa.tsx    ← thin re-export da @risiko/map-classico
    │   └── PannelloReplay.tsx  ← NUOVO: integra RisikoReplayPlayer
    ├── src/pagine/
    │   └── PaginaDettaglioPartita.tsx ← +sezione "Replay scrubabile"
    └── src/tipi/
        └── mappaLayout.ts      ← thin re-export da @risiko/map-classico
```

## Procedura (PowerShell)

```powershell
# 1. Backup (se hai già un risiko-live/ esistente da preservare)
if (Test-Path .\risiko-live) {
  Copy-Item -Recurse .\risiko-live .\risiko-live.bak
}

# 2. Estrarre lo zip
Expand-Archive -Path risiko-live-fase2.zip -DestinationPath . -Force

# 3. Installare (npm workspaces fa il lift di tutto in un colpo)
cd risiko-live
npm install

# 4. Verificare che tutto funzioni
npm run typecheck
npm run test:run

# 5. Avviare il frontend (con backend FastAPI già su :8000)
cd frontend
npm run dev      # → http://localhost:5173
```

## Risultato atteso

```
=== Typecheck ===
packages/eventi-schema        ✓
packages/replay-lib           ✓
packages/map-classico         ✓
packages/replay-player        ✓
frontend                      ✓

=== Test (95/95 verdi) ===
packages/eventi-schema        Tests  28 passed (28)
packages/replay-lib           Tests  50 passed (50)
packages/map-classico         Tests  11 passed (11)
packages/replay-player        Tests   6 passed (6)
```

## Cosa cambia per gli utenti del frontend RL

Dopo l'install, nella pagina di dettaglio partita (con stato_finale
ricostruito) compare una nuova sezione **"Replay scrubabile"** sotto
lo stato finale, contenente:

- Header con data/luogo della partita + fase corrente
- Mappa SVG identica a quella già in uso (è la stessa, promossa a libreria)
- Narrative con descrizione dell'evento corrente
- Scrubber con play/pause/avanti/indietro/inizio/fine + 4 preset velocità

Il replay è **già cablato al PlayerVideo esistente**: spostando il
cursore del replay, il video salta automaticamente all'offset
corrispondente (stesso pattern di PannelloProposteAggregazione).

Il sync **inverso** (video drives replay) è preparato negli hook ma
non ancora cablato — sarà aggiunto in fase C dopo i primi test su
una partita reale.

## Se qualcosa va storto

```powershell
# Roll-back completo
Remove-Item -Recurse .\risiko-live
Move-Item .\risiko-live.bak .\risiko-live

# O rebuild da zero
cd risiko-live
Remove-Item -Recurse node_modules, packages\*\node_modules, frontend\node_modules
npm install
```

## Cosa NON fa questo zip

- **Non tocca il backend FastAPI**. L'endpoint `/api/partite/{id}/esporta?formato=replay` deve già esistere e produrre un `BundleReplay` valido per lo schema v0.1.0. Se non c'è, vedrai "Replay non disponibile" nel pannello.
- **Non integra Battle Commander**. Quel passaggio (rimuovere il vendoring locale di BC e farlo importare dai workspace) è una sessione successiva — richiede di decidere git submodule vs npm registry privato.
- **Non implementa il sync inverso video → replay**. Lo lasciamo per fase C, dopo che hai una partita reale registrata al club da usare come banco di prova.

## Cose da configurare lato backend (per testing locale)

L'endpoint `/api/partite/{id}/esporta?formato=replay` deve restituire un
JSON conforme allo schema `BundleReplay` v1.0. Verifica con:

```bash
curl http://localhost:8000/api/partite/<UUID>/esporta?formato=replay | python -m json.tool
```

Il JSON deve avere campi `schema_version: "1.0"`, `partita.{id, data_inizio, ...}`,
`giocatori: [...]`, `eventi: [...]`. Se manca o ha forma diversa, il pannello
mostra l'errore di Zod con il path del campo problematico.
