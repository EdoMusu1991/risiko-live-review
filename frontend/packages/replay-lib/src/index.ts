/**
 * @risiko/replay-lib
 *
 * Modulo replay agnostico al framework. Consuma BundleReplay (schema
 * `@risiko/eventi-schema`) e fornisce:
 *   - StatoPartita derivato turno per turno (`stato.ts`)
 *   - Timeline navigabile per scrubbing (`timeline.ts`)
 *   - Importatori da file/URL/oggetto/JSON (`importatore.ts`)
 *   - Adapter dal formato Battle Commander legacy (`adapter-bc.ts`)
 *   - React layer opzionale (`react/`) per chi vuole un wrapper pronto.
 *
 * Esempio uso minimo (non-React):
 *
 * ```ts
 * import { creaTimeline, importaBundleDaJson } from "@risiko/replay-lib";
 *
 * const { bundle } = importaBundleDaJson(jsonString);
 * const t = creaTimeline(bundle);
 * console.log(t.lunghezza);
 * const stato = t.statoAlIndice(t.lunghezza - 1); // stato finale
 * ```
 */

// Schema (re-export per ergonomia: chi usa replay-lib non ha bisogno di
// importare separatamente da @risiko/eventi-schema)
export * from "@risiko/eventi-schema";

// Stato + applicazione eventi
export {
  applicaEvento,
  creaStatoInizialeDaBundle,
  ErroreReplayCorrotto,
  calcolaPerdite,
} from "./stato.js";
export type {
  StatoPartita,
  StatoTerritorio,
  GiocatoreInPartita,
  ColoreGiocatore,
  FasePartita,
  UltimoAttacco,
} from "./stato.js";

// Timeline
export { Timeline, creaTimeline } from "./timeline.js";
export type { OpzioniTimeline } from "./timeline.js";

// Importatori
export {
  importaBundleDaOggetto,
  importaBundleDaJson,
  importaBundleDaUrl,
  importaBundleDaFile,
  ErroreImport,
} from "./importatore.js";
export type { RisultatoImport, AvvisoImport } from "./importatore.js";

// Adapter BC legacy
export { adattaReplayBc } from "./adapter-bc.js";
export type { ReplayBcLegacy, OpzioniAdapter } from "./adapter-bc.js";
