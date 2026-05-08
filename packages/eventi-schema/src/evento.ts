/**
 * Evento di partita: discriminated union sul campo `tipo`.
 *
 * Specchio dell'enum `TipoEvento` lato backend Python. Ogni variante
 * è abbinata al suo schema dati corrispondente, garantendo type
 * safety completa sul payload.
 *
 * Uso tipico (replay di Battle Commander):
 *
 * ```ts
 * import { SchemaEventoValidato, type EventoValidato } from "@risiko/eventi-schema";
 *
 * const eventi: EventoValidato[] = jsonGrezzo.map(parseEvento);
 *
 * function parseEvento(raw: unknown): EventoValidato {
 *   const r = SchemaEventoValidato.safeParse(raw);
 *   if (!r.success) throw new Error(`Evento non valido: ${r.error.message}`);
 *   return r.data;
 * }
 *
 * // Switch esaustivo type-safe
 * for (const e of eventi) {
 *   switch (e.tipo) {
 *     case "attacco_risolto":
 *       e.dati.dadi_attaccante; // typed: number[]
 *       break;
 *     case "armate_piazzate":
 *       e.dati.n; // typed: number
 *       break;
 *     // ...
 *   }
 * }
 * ```
 */

import { z } from "zod";

import {
  SchemaDatiArmatePiazzate,
  SchemaDatiArmateSpostate,
  SchemaDatiAttaccoRisolto,
  SchemaDatiCartaPescata,
  SchemaDatiObiettivoAssegnato,
  SchemaDatiPartitaFine,
  SchemaDatiPartitaInizio,
  SchemaDatiTerritorioAssegnatoInizio,
  SchemaDatiTerritorioConquistato,
  SchemaDatiTrisGiocato,
  SchemaDatiTurnoFinito,
  SchemaDatiTurnoIniziato,
} from "./dati.js";

// === Enum tipi ===

/**
 * Tipi di evento osservabili durante una partita. Specchio di
 * `app.modelli.tipi.TipoEvento` lato backend Python.
 *
 * NOTA: `dadi_lanciati` esiste nell'enum backend ma è solo per
 * `EventoGrezzo` (singolo dado BLE), non per `EventoValidato`.
 * Non lo includo qui perché lo schema rappresenta solo gli eventi
 * applicabili al motore o validi per il replay.
 */
export const SchemaTipoEvento = z.enum([
  "partita_inizio",
  "partita_fine",
  "territorio_assegnato_inizio",
  "obiettivo_assegnato",
  "turno_iniziato",
  "turno_finito",
  "armate_piazzate",
  "tris_giocato",
  "attacco_risolto",
  "territorio_conquistato",
  "armate_spostate",
  "carta_pescata",
]);
export type TipoEvento = z.infer<typeof SchemaTipoEvento>;

// === Metadati comuni di EventoValidato ===

/**
 * Campi comuni di tutti gli EventoValidato (oltre `tipo` e `dati`).
 *
 * `partita_id` opzionale perché in alcuni contesti (es. export per
 * replay) l'evento è già "dentro" il bundle della partita e non serve
 * ripeterlo.
 */
const SchemaMetadatiEvento = z.object({
  id: z.string().min(1),
  partita_id: z.string().min(1).optional(),
  ts_evento: z.string().datetime({ offset: true }),
  evento_grezzo_id: z.string().nullable().optional(),
  validato_da: z.string().optional(),
});

// === Discriminated union ===

/**
 * Evento Validato come arriva dal backend RL. Discriminated union su
 * `tipo`: TypeScript fa type narrowing automatico nei branch.
 */
export const SchemaEventoValidato = z.discriminatedUnion("tipo", [
  SchemaMetadatiEvento.extend({
    tipo: z.literal("territorio_assegnato_inizio"),
    dati: SchemaDatiTerritorioAssegnatoInizio,
  }),
  SchemaMetadatiEvento.extend({
    tipo: z.literal("obiettivo_assegnato"),
    dati: SchemaDatiObiettivoAssegnato,
  }),
  SchemaMetadatiEvento.extend({
    tipo: z.literal("partita_inizio"),
    dati: SchemaDatiPartitaInizio,
  }),
  SchemaMetadatiEvento.extend({
    tipo: z.literal("turno_iniziato"),
    dati: SchemaDatiTurnoIniziato,
  }),
  SchemaMetadatiEvento.extend({
    tipo: z.literal("armate_piazzate"),
    dati: SchemaDatiArmatePiazzate,
  }),
  SchemaMetadatiEvento.extend({
    tipo: z.literal("tris_giocato"),
    dati: SchemaDatiTrisGiocato,
  }),
  SchemaMetadatiEvento.extend({
    tipo: z.literal("attacco_risolto"),
    dati: SchemaDatiAttaccoRisolto,
  }),
  SchemaMetadatiEvento.extend({
    tipo: z.literal("territorio_conquistato"),
    dati: SchemaDatiTerritorioConquistato,
  }),
  SchemaMetadatiEvento.extend({
    tipo: z.literal("armate_spostate"),
    dati: SchemaDatiArmateSpostate,
  }),
  SchemaMetadatiEvento.extend({
    tipo: z.literal("carta_pescata"),
    dati: SchemaDatiCartaPescata,
  }),
  SchemaMetadatiEvento.extend({
    tipo: z.literal("turno_finito"),
    dati: SchemaDatiTurnoFinito,
  }),
  SchemaMetadatiEvento.extend({
    tipo: z.literal("partita_fine"),
    dati: SchemaDatiPartitaFine,
  }),
]);
export type EventoValidato = z.infer<typeof SchemaEventoValidato>;

// === Bundle replay (stream completo per BC) ===

/**
 * Schema del giocatore in una partita (sufficiente per il replay).
 */
export const SchemaGiocatorePartita = z.object({
  id: z.string().min(1),
  nome: z.string().min(1),
  colore: z.enum(["rosso", "blu", "verde", "giallo", "nero", "viola"]),
  ordine_seduta: z.number().int().min(1).max(6),
});
export type GiocatorePartita = z.infer<typeof SchemaGiocatorePartita>;

/**
 * Bundle completo per replay di una partita.
 *
 * Questo è il formato che Risiko Live esporta per Battle Commander.
 * BC riceve questo JSON, lo valida con `SchemaBundleReplay.parse(...)`,
 * e ottiene una struttura type-safe pronta per essere consumata dal
 * suo modulo replay.
 */
export const SchemaBundleReplay = z.object({
  schema_version: z.literal("1.0"),
  partita: z.object({
    id: z.string().min(1),
    data_inizio: z.string().datetime({ offset: true }),
    data_fine: z.string().datetime({ offset: true }).nullable(),
    luogo: z.string().nullable().optional(),
    note: z.string().nullable().optional(),
  }),
  giocatori: z.array(SchemaGiocatorePartita).min(2).max(6),
  eventi: z.array(SchemaEventoValidato),
});
export type BundleReplay = z.infer<typeof SchemaBundleReplay>;
