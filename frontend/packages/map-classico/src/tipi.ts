/**
 * Tipi specifici della mappa Risiko classico.
 *
 * I tipi `ColoreGiocatore` e `GiocatorePartita` arrivano da
 * `@risiko/eventi-schema`: la mappa li riusa come canonici. `InfoTerritorio`
 * è invece specifico della map-lib (rappresenta lo stato di RENDERING di un
 * territorio, non un evento).
 */

import type { GiocatorePartita } from "@risiko/eventi-schema";

/**
 * Stato di rendering di un singolo territorio sulla mappa.
 *
 * `controllore_id` riferisce un `id` di `GiocatorePartita`. Il consumer deve
 * fornire una lista di giocatori coerente.
 *
 * Nota sul naming: questo è il vocabolario RL ("controllore", "armate"). La
 * `replay-lib` usa `proprietario_id` / `n_armate` per `StatoTerritorio`. Il
 * `RisikoReplayPlayer` (pacchetto `@risiko/replay-player`) si occupa
 * dell'adattamento.
 */
export interface InfoTerritorio {
  controllore_id: string | null;
  armate: number;
}

/**
 * Re-export per ergonomia del consumer.
 */
export type { GiocatorePartita };
