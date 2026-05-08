/**
 * @risiko/replay-player
 *
 * Wrapper "out of the box" che combina @risiko/replay-lib + @risiko/map-classico
 * in un viewer replay completo, con scrubber/autoplay/narrative integrati.
 *
 * Esposto come componente React unico: `RisikoReplayPlayer`.
 *
 * Re-export di valore: useReplay (per consumer che vogliono comporre
 * customizzato senza rinunciare alla map-lib).
 */

export {
  RisikoReplayPlayer,
} from "./RisikoReplayPlayer.js";
export type {
  PropsRisikoReplayPlayer,
  RiferimentoRisikoReplayPlayer,
} from "./RisikoReplayPlayer.js";

export { narrativeEvento } from "./narrative.js";

// Re-export utili per consumer che vogliono il pacchetto come unica entry
export { useReplay } from "@risiko/replay-lib/react";
export type {
  ReplayController,
  OpzioniUseReplay,
} from "@risiko/replay-lib/react";

export {
  importaBundleDaUrl,
  importaBundleDaJson,
  importaBundleDaOggetto,
  importaBundleDaFile,
} from "@risiko/replay-lib";
export type {
  StatoPartita,
  GiocatoreInPartita,
  StatoTerritorio,
  RisultatoImport,
} from "@risiko/replay-lib";

export type {
  BundleReplay,
  EventoValidato,
  GiocatorePartita,
  ColoreGiocatore,
} from "@risiko/eventi-schema";
