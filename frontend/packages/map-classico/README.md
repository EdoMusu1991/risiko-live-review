# @risiko/map-classico

Mappa Risiko classico EG come libreria. Estratta dal componente `PlanciaMappa`
di Risiko Live Review v0.1, promossa a workspace condiviso fra Risiko Live e
Battle Commander.

## Cosa contiene

**Dati strutturali** (puri, senza dipendenze):

- `POSIZIONI`: 42 territori → `{x, y}` su viewBox 1000×680
- `CONTINENTI`: 6 continenti con bonus, riquadro, etichetta, lista territori
- `CONTINENTE_DI`: lookup territorio → continente
- `ADIACENZE`: 65 coppie (intercontinentali incluse)
- `TERRITORI_TUTTI`: lista flat dei 42 territori
- `sonoAdiacenti(a, b)`: helper di lookup

**Componente React**:

- `MappaRisikoClassico`: SVG schematico self-contained, stile editoriale
  (pergamena, scarlatto, Fraunces+JetBrainsMono+InterTight). Stili inline,
  zero dipendenze CSS esterne.

## Uso

```tsx
import { MappaRisikoClassico, type InfoTerritorio } from "@risiko/map-classico";

const territori: Record<string, InfoTerritorio> = {
  alaska: { controllore_id: "p0", armate: 5 },
  kamchatka: { controllore_id: "p1", armate: 3 },
  // ...
};

const giocatori = [
  { id: "p0", nome: "Alice", colore: "rosso", ordine_seduta: 1 },
  { id: "p1", nome: "Bob", colore: "blu", ordine_seduta: 2 },
];

<MappaRisikoClassico
  territori={territori}
  giocatori={giocatori}
  territorioSelezionato="alaska"        // alone scarlatto pulsante
  onClickTerritorio={(nome) => alert(nome)}
  mostraLegenda                          // legenda giocatori sotto
/>
```

## API

```ts
interface PropsMappaRisikoClassico {
  territori: Record<string, InfoTerritorio>;
  giocatori: ReadonlyArray<GiocatorePartita>;
  territorioSelezionato?: string | null;
  onClickTerritorio?: (nome: string) => void;
  mostraLegenda?: boolean;  // default true
}

interface InfoTerritorio {
  controllore_id: string | null;  // riferisce GiocatorePartita.id
  armate: number;
}
```

`GiocatorePartita` e `ColoreGiocatore` sono importati da
`@risiko/eventi-schema` (riusati come canonici).

## Naming territori

Italiano standard EG (snake_case): `alaska`, `territori_nordovest`,
`groenlandia`, ..., `australia_orientale`. Lista completa in `TERRITORI_TUTTI`.

I nomi corrispondono a quelli emessi dal backend RL nei campi `territorio`
degli eventi. Il consumer è responsabile di garantire questa coerenza.

## Naming carte

Coerente con `@risiko/eventi-schema`: `fante` / `cavaliere` / `cannone` /
`jolly`. Il pacchetto non disegna carte, ma usa lo stesso vocabolario quando
serve referenziare simboli.

## Test

```bash
npm run test:run    # 9 test su coerenza dati strutturali (42 territori,
                    # bonus EG totale 24, ponti intercontinentali, ecc.)
```
