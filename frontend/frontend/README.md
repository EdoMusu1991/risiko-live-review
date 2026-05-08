# Risiko Live Review — Frontend

Frontend React per la review e validazione di partite Risiko.

## Requisiti

- Node.js 20 o superiore
- Backend FastAPI in esecuzione su `localhost:8000` (vedi `backend/`)

## Setup rapido

Su PowerShell Windows:

```powershell
cd frontend

# Installa dipendenze
npm install

# Avvia il dev server (proxy automatico verso il backend)
npm run dev
```

Il dev server gira su <http://localhost:5173>. Tutte le chiamate a `/api/*`
vengono inoltrate al backend FastAPI tramite il proxy Vite (configurato in
`vite.config.ts`).

## Comandi

```powershell
npm run dev       # dev server con HMR
npm run build     # type-check + build di produzione
npm run lint      # solo type-check (alias di `tsc -b --noEmit`)
npm run preview   # serve la build di produzione localmente
```

## Stack

- **React 18** con StrictMode + TypeScript strict
- **Vite 5** come bundler/dev server
- **Tailwind CSS 3.4** con palette piatta personalizzata
- **React Router DOM 6** per il routing client
- **axios** per HTTP, con `ErroreApi` normalizzato
- **date-fns** per formattazione date
- **lucide-react** per le icone (no emoji)

## Struttura

```
frontend/
├── src/
│   ├── main.tsx                   # entry point React
│   ├── App.tsx                    # router top-level
│   ├── api/                       # client HTTP per ogni dominio
│   │   ├── cliente.ts             # axios + ErroreApi
│   │   ├── partite.ts
│   │   ├── eventi.ts
│   │   ├── video.ts
│   │   └── ricostruzione.ts
│   ├── tipi/dominio.ts            # types speculari agli schemi Pydantic
│   ├── hooks/useRichiestaApi.ts   # hook loading/error/data
│   ├── componenti/
│   │   ├── Layout.tsx             # header editoriale + footer
│   │   ├── decorativi.tsx         # PallinoColore, BadgeStato, MessaggioErrore, StatoVuoto
│   │   ├── PlayerVideo.tsx        # HTML5 video con HTTP Range + scrubber
│   │   ├── PannelloUploadVideo.tsx
│   │   ├── PannelloEventi.tsx     # tabs validati/grezzi sincronizzati al video
│   │   └── PannelloStatoFinale.tsx
│   ├── pagine/
│   │   ├── PaginaListaPartite.tsx
│   │   ├── PaginaNuovaPartita.tsx
│   │   └── PaginaDettaglioPartita.tsx
│   └── stili/globali.css          # Tailwind + classi custom (.btn-primario, .carta, ecc.)
├── public/favicon.svg
├── index.html                     # carica Fraunces, Inter Tight, JetBrains Mono da Google Fonts
├── tailwind.config.js
├── vite.config.ts                 # proxy /api → localhost:8000
└── package.json
```

## Estetica

Direzione: **cartografia editoriale**.

Pensa a una vecchia mappa Risiko incorniciata in una rivista architettonica
italiana. Pergamena calda, inchiostro scuro, accenti rosso scarlatto come
unico colore dominante. Tipografia editoriale (Fraunces serif per i display,
Inter Tight per il body, JetBrains Mono per i timestamp). Nessun rounded
eccessivo, nessun gradiente viola. Bordi sottili come linee cartografiche.

Palette principale:
- `pergamena` `#f4ede0` — background
- `inchiostro` `#1a1614` — testo
- `scarlatto` `#b8332a` — unico accento
- 6 colori giocatori Risiko

## Convenzioni di codice

- **Tutto in italiano**: variabili, componenti, file, props, eccezioni.
  Coerente col backend.
- **TypeScript strict**: `noUnusedLocals`, `noUnusedParameters`,
  `noUncheckedIndexedAccess` tutti attivi.
- **Componenti funzionali**: nessuna classe, hook quando serve stato.
- **API tipata end-to-end**: i types in `src/tipi/dominio.ts` rispecchiano
  gli schemi Pydantic. Quando il backend cambia, aggiornare a mano (in
  futuro: generazione automatica da OpenAPI).

## Roadmap immediata

- ✅ Lista partite, creazione, dettaglio (v0.4)
- ✅ Player video con HTTP Range + scrubber custom
- ✅ Pannello eventi con sync timeline → video
- ✅ Visualizzazione stato finale ricostruito
- ✅ Editor eventi interattivo: form dinamico per 9 tipi, modifica, elimina, shortcut "N" (v0.5)
- ✅ Bottone setup automatico partita (genera 45 eventi con un click) (v0.6)
- ✅ Plancia SVG schematica con territori, adiacenze e bonus continenti (v0.7)
- ✅ Click-su-territorio per filtrare eventi sulla mappa (v0.8)
- ⬜ Promozione grezzo → validato dalla UI
- ⬜ Pannello statistiche partita (recharts)
- ⬜ Shortcut tastiera J/K/L per scrubbing video
