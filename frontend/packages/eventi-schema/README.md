# @risiko/eventi-schema

Schema Zod condiviso degli eventi di partita Risiko classico EG. Pacchetto consumato da:

- **Battle Commander** (modulo replay): valida eventi in arrivo da Risiko Live o da partite native BC esportate
- **Risiko Live Review** (frontend): validazione type-safe degli eventi ricevuti dal backend FastAPI

Source of truth: gli schemi Pydantic in `risiko-live-review/backend/app/schemi/dati_eventi.py`. Le costanti italiane sono mantenute identiche per garantire round-trip compatibility.

## Installazione

Pacchetto privato. Da git submodule, npm workspace, o copia diretta della cartella.

```bash
npm install zod  # peer dependency
```

## Uso da Battle Commander (caso replay)

```ts
import {
  SchemaBundleReplay,
  parsaBundleReplay,
  ErroreParsingEventi,
  type EventoValidato,
} from "@risiko/eventi-schema";

// 1. BC riceve un JSON dall'utente (o da API Risiko Live)
const jsonGrezzo = await fetch("/replay-bundle.json").then((r) => r.json());

// 2. Validazione strutturata
try {
  const bundle = parsaBundleReplay(jsonGrezzo);
  // bundle.giocatori, bundle.eventi sono ora type-safe
  for (const ev of bundle.eventi) {
    switch (ev.tipo) {
      case "attacco_risolto":
        // TS sa che ev.dati ha dadi_attaccante: number[]
        animaAttacco(ev.dati);
        break;
      case "armate_piazzate":
        animaPiazzamento(ev.dati);
        break;
      // ... discriminated union esaustiva
    }
  }
} catch (e) {
  if (e instanceof ErroreParsingEventi) {
    // e.dettagli ha [{ percorso, messaggio, codice }, ...]
    console.error("Bundle invalido:", e.dettagli);
  }
}
```

## Uso da Risiko Live frontend

```ts
import { SchemaEventoValidato } from "@risiko/eventi-schema";

// Sostituisce i tipi TS scritti a mano in src/tipi/dominio.ts
const eventi = await apiEventi.listaValidati(partitaId);
const eventiValidati = eventi.map((e) => SchemaEventoValidato.parse(e));
// → validazione runtime + tipi TS narrowing automatico
```

## Tipi evento coperti

12 tipi di `EventoValidato` (più 5 schemi `Dati*` riutilizzati):

| Tipo evento | Fase | Schema dati |
|---|---|---|
| `territorio_assegnato_inizio` | setup | `DatiTerritorioAssegnatoInizio` |
| `obiettivo_assegnato` | setup | `DatiObiettivoAssegnato` |
| `partita_inizio` | setup | `DatiPartitaInizio` |
| `turno_iniziato` | turno | `DatiTurnoIniziato` * |
| `armate_piazzate` | rinforzo | `DatiArmatePiazzate` |
| `tris_giocato` | rinforzo | `DatiTrisGiocato` (3× `DatiCarta`) |
| `attacco_risolto` | attacco | `DatiAttaccoRisolto` |
| `territorio_conquistato` | attacco | `DatiTerritorioConquistato` * |
| `armate_spostate` | spostamento | `DatiArmateSpostate` |
| `carta_pescata` | fine turno | `DatiCartaPescata` * |
| `turno_finito` | fine turno | `DatiTurnoFinito` |
| `partita_fine` | fine | `DatiPartitaFine` |

\* Questi 3 tipi non hanno schema Pydantic dedicato lato backend RL (sono o derivati automaticamente dal motore, o solo informativi). Lo schema Zod qui è basato sull'uso effettivo nel codebase. Se servirà ufficializzarli sarà semplice aggiungere lo schema Pydantic mirror lato backend.

## Vincoli importanti

- Tutti gli schemi `.strict()`: rifiutano campi extra. Specchio del `extra="forbid"` Pydantic.
- `partita_id` opzionale negli eventi: in alcuni contesti (replay bundle) è dentro la partita stessa, non serve ripeterlo per evento.
- `ts_evento` deve essere ISO 8601 con timezone offset (es. `2026-05-07T21:00:00+00:00` o `...Z`).
- Dadi sempre `1..6`, `1..3` quantità. Carte sempre 3 nel tris.
- Giocatori sempre 2-6 nel bundle replay.

## Helper di parsing

Tre livelli di tolleranza:

```ts
// Strict: lancia su errore (per fail-fast)
const ev = parsaEvento(raw);

// Safe: ritorna { success, valore | errore } (no throw)
const r = parsaEventoSafe(raw);
if (r.success) { ... } else { console.error(r.errore.dettagli); }

// Tollerante per liste: separa validi da scartati con indici
const { validi, scartati } = parsaListaEventi(rawArray);
// scartati: [{ indice: number, errore: ErroreParsingEventi }, ...]
```

## Test

```bash
npm test           # vitest run
npm run test:watch
npm run typecheck
npm run build      # tsc → dist/
```

28 test verdi. Coprono validazione di ogni schema dati, discriminated union narrowing, bundle replay, helper di parsing tollerante.

## Roadmap

- [ ] Tradurre `DatiCarta`, `DatiTrisGiocato` in BC (oggi probabilmente differente)
- [ ] Ufficializzare schemi Pydantic per `TurnoIniziato`, `TerritorioConquistato`, `CartaPescata` lato backend RL (rimuovere asterischi)
- [ ] Considerare submodule git o npm workspace dopo prima integrazione reale BC↔RL

## Versioning

`schema_version` esposto nel `BundleReplay` per evolvere il formato senza rompere bundle vecchi. Attualmente `1.0`. Una nuova major version richiederà adapter espliciti nel modulo replay BC.
