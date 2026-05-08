/**
 * Helper di parsing con error reporting strutturato.
 *
 * Pensati per l'uso in Battle Commander: BC riceve un bundle JSON da
 * Risiko Live (o da export utente), e vuole sapere CON PRECISIONE
 * cosa è andato storto se il parsing fallisce, senza avere uno
 * stack-trace cripto-zod in console.
 */

import { z } from "zod";

import {
  SchemaBundleReplay,
  SchemaEventoValidato,
  type BundleReplay,
  type EventoValidato,
} from "./evento.js";

// === Errori di dominio ===

/**
 * Errore di parsing con dettaglio strutturato.
 *
 * `dettagli` è la lista di problemi puntuali sui campi (path + messaggio),
 * utilizzabile per evidenziare in UI quale parte dell'input è sbagliata.
 */
export class ErroreParsingEventi extends Error {
  constructor(
    messaggio: string,
    public readonly dettagli: ReadonlyArray<DettaglioErrore>,
  ) {
    super(messaggio);
    this.name = "ErroreParsingEventi";
  }
}

export interface DettaglioErrore {
  /** Path al campo in errore (es. ["eventi", 3, "dati", "dadi_attaccante"]). */
  percorso: ReadonlyArray<string | number>;
  /** Messaggio human-readable del problema. */
  messaggio: string;
  /** Codice zod del problema (es. "invalid_type", "too_small"). */
  codice: string;
}

function _convertiZodIssues(
  issues: ReadonlyArray<z.ZodIssue>,
): ReadonlyArray<DettaglioErrore> {
  return issues.map((i) => ({
    percorso: i.path,
    messaggio: i.message,
    codice: i.code,
  }));
}

// === Parsing strict (lancia su errore) ===

/**
 * Parsa un singolo evento, lancia `ErroreParsingEventi` su payload non
 * valido. Usa per consumatori che vogliono fail-fast.
 */
export function parsaEvento(raw: unknown): EventoValidato {
  const r = SchemaEventoValidato.safeParse(raw);
  if (!r.success) {
    throw new ErroreParsingEventi(
      `Evento non valido: ${r.error.issues.length} problemi`,
      _convertiZodIssues(r.error.issues),
    );
  }
  return r.data;
}

/**
 * Parsa un bundle completo (partita + giocatori + eventi).
 */
export function parsaBundleReplay(raw: unknown): BundleReplay {
  const r = SchemaBundleReplay.safeParse(raw);
  if (!r.success) {
    throw new ErroreParsingEventi(
      `Bundle replay non valido: ${r.error.issues.length} problemi`,
      _convertiZodIssues(r.error.issues),
    );
  }
  return r.data;
}

// === Parsing tollerante (no throw) ===

export type RisultatoParsing<T> =
  | { success: true; valore: T }
  | { success: false; errore: ErroreParsingEventi };

/**
 * Versione non-throwing di `parsaEvento`. Utile per consumatori che
 * vogliono parsare una lista grossa raccogliendo gli errori invece
 * di interrompersi al primo.
 */
export function parsaEventoSafe(raw: unknown): RisultatoParsing<EventoValidato> {
  const r = SchemaEventoValidato.safeParse(raw);
  if (!r.success) {
    return {
      success: false,
      errore: new ErroreParsingEventi(
        `Evento non valido: ${r.error.issues.length} problemi`,
        _convertiZodIssues(r.error.issues),
      ),
    };
  }
  return { success: true, valore: r.data };
}

/**
 * Parsa una lista di eventi tollerando errori puntuali. Ritorna i
 * validi + lista di errori per indice. Pensato per il modulo replay
 * di BC: se un evento è corrotto, salta quello e continua.
 */
export function parsaListaEventi(raw: ReadonlyArray<unknown>): {
  validi: EventoValidato[];
  scartati: ReadonlyArray<{ indice: number; errore: ErroreParsingEventi }>;
} {
  const validi: EventoValidato[] = [];
  const scartati: { indice: number; errore: ErroreParsingEventi }[] = [];

  for (let i = 0; i < raw.length; i++) {
    const r = parsaEventoSafe(raw[i]);
    if (r.success) {
      validi.push(r.valore);
    } else {
      scartati.push({ indice: i, errore: r.errore });
    }
  }
  return { validi, scartati };
}
