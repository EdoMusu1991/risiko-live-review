/**
 * @risiko/map-classico
 *
 * Mappa Risiko classico EG: 42 territori, 6 continenti, adiacenze.
 * Fornisce sia i dati strutturali (POSIZIONI, CONTINENTI, ADIACENZE) sia
 * il componente React `MappaRisikoClassico` per il rendering.
 *
 * Stile editoriale (pergamena, scarlatto, Fraunces+JetBrainsMono+InterTight),
 * stili inline (no Tailwind dependency), zero CSS esterni.
 */

// Tipi
export type {
  GiocatorePartita,
  InfoTerritorio,
} from "./tipi.js";
export type { ColoreGiocatore } from "@risiko/eventi-schema";

// Dati strutturali
export {
  POSIZIONI,
  CONTINENTI,
  CONTINENTE_DI,
  ADIACENZE,
  TERRITORI_TUTTI,
  sonoAdiacenti,
} from "./layout.js";
export type {
  PosizioneTerritorio,
  DefinizioneContinente,
  SlugContinente,
} from "./layout.js";

// Componente
export { MappaRisikoClassico } from "./MappaRisikoClassico.js";
export type { PropsMappaRisikoClassico } from "./MappaRisikoClassico.js";
