/**
 * Schemi Zod per il payload `dati` degli eventi validati di una partita
 * Risiko classico EG.
 *
 * Traduzione fedele degli schemi Pydantic in `risiko-live-review/backend/
 * app/schemi/dati_eventi.py`. Mantiene gli stessi nomi (italiani) e gli
 * stessi vincoli (min/max, pattern, ecc.) per garantire round-trip
 * compatibility.
 *
 * Tutti gli schemi usano `.strict()` per rifiutare campi non dichiarati,
 * specchio del `extra="forbid"` lato Pydantic.
 */

import { z } from "zod";

// === Setup ===

/**
 * Distribuzione iniziale di un territorio a un giocatore.
 * Avviene prima di PARTITA_INIZIO. I 42 territori devono essere tutti
 * assegnati prima che il motore accetti `inizia_partita()`.
 */
export const SchemaDatiTerritorioAssegnatoInizio = z
  .object({
    territorio: z.string().min(1),
    giocatore_id: z.string().min(1),
    n_armate: z.number().int().min(1),
  })
  .strict();
export type DatiTerritorioAssegnatoInizio = z.infer<
  typeof SchemaDatiTerritorioAssegnatoInizio
>;

/**
 * Assegnazione di un obiettivo a un giocatore. `obiettivo_id` 1-16,
 * stabile nel catalogo `risiko_engine.obiettivi.OBIETTIVI`.
 */
export const SchemaDatiObiettivoAssegnato = z
  .object({
    giocatore_id: z.string().min(1),
    obiettivo_id: z.number().int().min(1).max(16),
  })
  .strict();
export type DatiObiettivoAssegnato = z.infer<
  typeof SchemaDatiObiettivoAssegnato
>;

/** Avvio della partita: il primo giocatore entra in RINFORZO. */
export const SchemaDatiPartitaInizio = z
  .object({
    primo_giocatore_id: z.string().min(1),
  })
  .strict();
export type DatiPartitaInizio = z.infer<typeof SchemaDatiPartitaInizio>;

// === Carte / Tris (fase RINFORZO) ===

/**
 * Serializzazione di una carta del Risiko.
 * - Carte territorio: `territorio` valorizzato + simbolo cannone/fante/cavaliere
 * - Carte jolly: `territorio = null` + simbolo `jolly`
 *
 * NOTA: lo schema permette qualsiasi combinazione (anche territorio + jolly,
 * o territorio null + simbolo non-jolly), specchio del Pydantic. Se servirà
 * validazione cross-field andrà aggiunta con `.refine()` qui e nello schema
 * Python.
 */
export const SchemaDatiCarta = z
  .object({
    territorio: z.string().min(1).nullable(),
    simbolo: z.enum(["cannone", "fante", "cavaliere", "jolly"]),
  })
  .strict();
export type DatiCarta = z.infer<typeof SchemaDatiCarta>;

/** Il giocatore attivo gioca un tris di 3 carte (fase RINFORZO). */
export const SchemaDatiTrisGiocato = z
  .object({
    giocatore_id: z.string().min(1),
    carte: z.array(SchemaDatiCarta).length(3),
  })
  .strict();
export type DatiTrisGiocato = z.infer<typeof SchemaDatiTrisGiocato>;

// === Fase RINFORZO ===

/** Il giocatore attivo piazza N armate su un proprio territorio. */
export const SchemaDatiArmatePiazzate = z
  .object({
    giocatore_id: z.string().min(1),
    territorio: z.string().min(1),
    n: z.number().int().min(1),
  })
  .strict();
export type DatiArmatePiazzate = z.infer<typeof SchemaDatiArmatePiazzate>;

// === Fase ATTACCO ===

/**
 * Un attacco con dadi già lanciati.
 *
 * Sia i dadi attaccante sia quelli difensore sono inclusi: il motore
 * non lancia mai i dadi internamente, gli vengono iniettati. La
 * conquista e lo spostamento minimo automatico sono gestiti dal
 * motore se il difensore va a 0.
 */
export const SchemaDatiAttaccoRisolto = z
  .object({
    giocatore_id: z.string().min(1),
    da: z.string().min(1),
    a: z.string().min(1),
    dadi_attaccante: z
      .array(z.number().int().min(1).max(6))
      .min(1)
      .max(3),
    dadi_difensore: z
      .array(z.number().int().min(1).max(6))
      .min(1)
      .max(3),
  })
  .strict();
export type DatiAttaccoRisolto = z.infer<typeof SchemaDatiAttaccoRisolto>;

// === Fase SPOSTAMENTO ===

/** Spostamento finale di N armate fra due territori adiacenti. */
export const SchemaDatiArmateSpostate = z
  .object({
    giocatore_id: z.string().min(1),
    da: z.string().min(1),
    a: z.string().min(1),
    n: z.number().int().min(1),
  })
  .strict();
export type DatiArmateSpostate = z.infer<typeof SchemaDatiArmateSpostate>;

// === Fine turno / partita ===

/** Il giocatore attivo passa il turno (eventualmente pesca una carta). */
export const SchemaDatiTurnoFinito = z
  .object({
    giocatore_id: z.string().min(1),
  })
  .strict();
export type DatiTurnoFinito = z.infer<typeof SchemaDatiTurnoFinito>;

/**
 * Evento informativo di fine partita. Il motore lo determina
 * automaticamente; questo evento è documentativo.
 */
export const SchemaDatiPartitaFine = z
  .object({
    vincitore_id: z.string().min(1),
  })
  .strict();
export type DatiPartitaFine = z.infer<typeof SchemaDatiPartitaFine>;

// === Eventi "presunti" (no schema Pydantic dedicato lato backend) ===
//
// Questi tipi esistono nell'enum TipoEvento ma non hanno uno schema
// Pydantic dedicato perché vengono o emessi automaticamente dal motore
// in ricostruzione, o usati in modo informativo. Includiamo schemi
// best-guess basati sull'uso effettivo nel codebase.

/**
 * Inizio del turno di un giocatore. Emesso o aggiunto manualmente
 * dall'utente nella review. Non ha schema Pydantic dedicato; payload
 * presunto basato sull'uso nel servizio statistiche.
 */
export const SchemaDatiTurnoIniziato = z
  .object({
    giocatore_id: z.string().min(1),
  })
  .strict();
export type DatiTurnoIniziato = z.infer<typeof SchemaDatiTurnoIniziato>;

/**
 * Conquista di un territorio dopo un attacco vittorioso. Emesso
 * automaticamente dal motore quando il difensore va a 0 armate.
 */
export const SchemaDatiTerritorioConquistato = z
  .object({
    giocatore_id: z.string().min(1),
    territorio: z.string().min(1),
  })
  .strict();
export type DatiTerritorioConquistato = z.infer<
  typeof SchemaDatiTerritorioConquistato
>;

/**
 * Pesca carta a fine turno (se conquista almeno 1 territorio nel
 * turno). Emesso automaticamente dal motore.
 */
export const SchemaDatiCartaPescata = z
  .object({
    giocatore_id: z.string().min(1),
    carta: SchemaDatiCarta,
  })
  .strict();
export type DatiCartaPescata = z.infer<typeof SchemaDatiCartaPescata>;
