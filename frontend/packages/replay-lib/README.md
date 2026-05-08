# @risiko/replay-lib

Replay engine condiviso. Consuma `BundleReplay` (`@risiko/eventi-schema`) e
produce uno `StatoPartita` navigabile per ogni indice della timeline.

## Cosa fa

- Valida un bundle JSON con Zod (via `@risiko/eventi-schema`)
- Costruisce uno `StatoPartita` applicando eventi uno alla volta, in modo puro
- Espone una `Timeline` navigabile per scrubbing in avanti/indietro con cache LRU
- Layer React opzionale (`useReplay`, `PlayerReplay`) — render-prop based, nessun vincolo di stile
- Adapter dal formato replay BC vecchio (lossy, marcato)

## Cosa NON fa

- **Non rivaluta le regole di gameplay**. Il replay è un film: applichiamo le
  conseguenze degli eventi (perdite ai dadi, cambi proprietario) ma non
  controlliamo se la mossa era legale.
- Non disegna mappe — è agnostica alla UI. Per la mappa Risiko classico EG
  vedi `@risiko/map-classico`. Per il viewer "out of the box" che combina
  entrambi, vedi `@risiko/replay-player`.
- Non fa I/O da localStorage o IndexedDB. Riceve i bundle dal chiamante.

## Uso

### Minimo (non-React)

```ts
import { creaTimeline, importaBundleDaUrl } from "@risiko/replay-lib";

const { bundle, avvisi } = await importaBundleDaUrl(
  `/api/partite/${partitaId}/esporta?formato=replay`,
);
for (const a of avvisi) console.log(a.livello, a.messaggio);

const timeline = creaTimeline(bundle);
const stato = timeline.statoAlIndice(timeline.lunghezza - 1); // stato finale
for (const [id, t] of stato.territori) {
  console.log(`${id}: ${t.proprietario_id} (${t.n_armate} armate)`);
}
```

### Hook React

```tsx
import { useReplay } from "@risiko/replay-lib/react";

function CustomViewer({ bundle }) {
  const r = useReplay(bundle);
  return (
    <>
      <MyMap stato={r.stato} />
      <button onClick={r.indietro}>◀</button>
      <button onClick={r.togglePlay}>{r.inPlay ? "⏸" : "▶"}</button>
      <button onClick={r.avanti}>▶</button>
    </>
  );
}
```

### Conversione di replay BC legacy

Per i replay BC nel vecchio formato (snapshot per turno):

```ts
import { adattaReplayBc, creaTimeline } from "@risiko/replay-lib";

const bundle = adattaReplayBc(legacy, {
  ordineTerritori: TERRITORI_BC, // array di id territori nello stesso ordine di territoriesFlat
});
const timeline = creaTimeline(bundle);
```

L'adapter è marcato con `[bc-legacy]` in `bundle.partita.note`. L'importatore
mostra un avviso al consumer per segnalare la perdita di fedeltà su:
dadi attacco, carte tris, distribuzione rinforzi per-territorio.

## Convenzioni

### Indici timeline

| `idx` | Significato |
|---|---|
| `-1` | Stato iniziale (giocatori popolati, territori vuoti, fase=setup) |
| `0` | Stato dopo l'evento 0 |
| `lunghezza-1` | Stato finale (post-ultimo evento) |

### Identità

- Giocatori: stringa `id` (lo schema RL usa stringhe; l'adapter BC genera `p0`, `p1`, ecc.)
- Territori: stringa nome. La libreria non valida che corrispondano a una mappa specifica — quello è competenza del consumer.

### Naming carte

Vocabolario canonico dello schema: `fante` / `cavaliere` / `cannone` / `jolly`.

## Test

```bash
npm run test:run    # 50 test
npm run typecheck   # tsc --noEmit
```

## Limitazioni note dell'adapter BC legacy

I replay BC vecchi non tracciano:
- Dadi grezzi degli attacchi (solo le perdite)
- Le 3 carte specifiche di un tris (solo il bonus)
- La distribuzione per-territorio dei rinforzi (solo il totale)
- I move post-conquista e finali (omessi)

L'adapter ricostruisce eventi sintaticamente coerenti col bundle, marcandoli
nel campo note. I replay BC nuovi (post-aggiornamento del recorder, fase
successiva) saranno fedeli.
