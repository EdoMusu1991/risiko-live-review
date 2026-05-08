/**
 * Layout schematico della mappa Risiko EG — adesso un re-export di
 * `@risiko/map-classico`.
 *
 * I dati strutturali (POSIZIONI, CONTINENTI, ADIACENZE, sonoAdiacenti) sono
 * stati promossi a libreria workspace condivisa fra Risiko Live e
 * Battle Commander. Questo file resta come ponte di compatibilità per i
 * consumer interni di RL.
 */

export {
  POSIZIONI,
  CONTINENTI,
  CONTINENTE_DI,
  ADIACENZE,
  TERRITORI_TUTTI,
  sonoAdiacenti,
  type PosizioneTerritorio,
  type DefinizioneContinente,
  type SlugContinente,
} from "@risiko/map-classico";
