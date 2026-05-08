/**
 * Importatore di bundle replay.
 *
 * Tre canali:
 *   - importaBundleDaOggetto: bundle già parsato come JS object
 *   - importaBundleDaJson:    stringa JSON
 *   - importaBundleDaUrl:     fetch + parse
 *   - importaBundleDaFile:    File API (drag&drop / input)
 *
 * Tutti i canali producono lo stesso `RisultatoImport` con bundle validato e
 * (eventuali) avvisi non bloccanti.
 */

import {
  ErroreParsingEventi,
  parsaBundleReplay,
  type BundleReplay,
} from "@risiko/eventi-schema";

export interface AvvisoImport {
  livello: "info" | "warning";
  messaggio: string;
}

export interface RisultatoImport {
  bundle: BundleReplay;
  avvisi: ReadonlyArray<AvvisoImport>;
}

export class ErroreImport extends Error {
  constructor(
    messaggio: string,
    public readonly causa?: unknown,
  ) {
    super(messaggio);
    this.name = "ErroreImport";
  }
}

// === Da oggetto JS (già parsato) ============================================

/**
 * Valida un bundle già in memoria. Path d'ingresso più semplice.
 *
 * @throws ErroreParsingEventi se la struttura non rispetta lo schema zod
 */
export function importaBundleDaOggetto(raw: unknown): RisultatoImport {
  const bundle = parsaBundleReplay(raw);
  return { bundle, avvisi: rilevaAvvisi(bundle) };
}

// === Da stringa JSON ========================================================

export function importaBundleDaJson(json: string): RisultatoImport {
  let raw: unknown;
  try {
    raw = JSON.parse(json);
  } catch (e) {
    throw new ErroreImport(
      `JSON non parsabile: ${(e as Error).message}`,
      e,
    );
  }
  return importaBundleDaOggetto(raw);
}

// === Da URL =================================================================

/**
 * Carica un bundle via HTTP. Compatibile con l'endpoint Risiko Live
 * `GET /api/partite/{id}/esporta?formato=replay`.
 *
 * @param url    URL completa del bundle
 * @param init   opzionale, passato a fetch (es. headers, signal)
 */
export async function importaBundleDaUrl(
  url: string,
  init?: RequestInit,
): Promise<RisultatoImport> {
  let resp: Response;
  try {
    resp = await fetch(url, init);
  } catch (e) {
    throw new ErroreImport(
      `Fetch fallita: ${(e as Error).message}`,
      e,
    );
  }
  if (!resp.ok) {
    throw new ErroreImport(
      `HTTP ${resp.status} ${resp.statusText} su ${url}`,
    );
  }
  let raw: unknown;
  try {
    raw = await resp.json();
  } catch (e) {
    throw new ErroreImport(
      `Risposta non JSON: ${(e as Error).message}`,
      e,
    );
  }
  return importaBundleDaOggetto(raw);
}

// === Da File (input/drop) ===================================================

/**
 * Carica un bundle da un File browser (drop, input[type=file]).
 *
 * Limite ragionevole: 50MB. Bundle più grandi probabilmente sono corrotti o
 * non sono replay. Configurabile via `maxSize`.
 */
export async function importaBundleDaFile(
  file: File,
  opzioni: { maxSize?: number } = {},
): Promise<RisultatoImport> {
  const maxSize = opzioni.maxSize ?? 50 * 1024 * 1024;
  if (file.size > maxSize) {
    throw new ErroreImport(
      `File troppo grande: ${file.size} byte (max ${maxSize})`,
    );
  }
  let testo: string;
  try {
    testo = await file.text();
  } catch (e) {
    throw new ErroreImport(
      `Lettura file fallita: ${(e as Error).message}`,
      e,
    );
  }
  return importaBundleDaJson(testo);
}

// === Re-export per ergonomia ================================================

export { ErroreParsingEventi };

// === Avvisi non bloccanti ===================================================

/**
 * Rileva problemi non strutturali nel bundle (zod ha già validato la forma).
 * Sono solo segnalazioni: il replay è comunque utilizzabile.
 */
function rilevaAvvisi(bundle: BundleReplay): AvvisoImport[] {
  const avvisi: AvvisoImport[] = [];
  if (bundle.eventi.length === 0) {
    avvisi.push({
      livello: "warning",
      messaggio: "Bundle senza eventi: il replay sarà vuoto.",
    });
  }
  // Marker dell'adapter BC legacy (vedi adapter-bc.ts).
  if (
    bundle.partita.note &&
    bundle.partita.note.includes("[bc-legacy]")
  ) {
    avvisi.push({
      livello: "info",
      messaggio:
        "Replay convertito da formato Battle Commander legacy: alcuni eventi (piazzamento armate per-territorio) sono approssimazioni.",
    });
  }
  return avvisi;
}
