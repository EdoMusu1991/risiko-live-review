/**
 * Tipi TypeScript del dominio Risiko Live Review.
 *
 * Speculari agli schemi Pydantic del backend (`app/schemi/*.py`).
 * Quando il backend cambia, aggiornare a mano qui (in futuro:
 * generazione automatica da OpenAPI).
 */

// === Enum ===

export type StatoReview =
  | "grezza"
  | "in_review"
  | "validata"
  | "archiviata";

export type ColoreGiocatore =
  | "rosso"
  | "blu"
  | "verde"
  | "giallo"
  | "nero"
  | "viola";

export type FonteEvento =
  | "dado_ble"
  | "qr_retro_carta"
  | "qr_fronte_carta"
  | "cv_automatico"
  | "input_manuale";

export type TipoEvento =
  | "partita_inizio"
  | "partita_fine"
  | "territorio_assegnato_inizio"
  | "obiettivo_assegnato"
  | "turno_iniziato"
  | "turno_finito"
  | "armate_piazzate"
  | "tris_giocato"
  | "dadi_lanciati"
  | "attacco_risolto"
  | "territorio_conquistato"
  | "armate_spostate"
  | "carta_pescata"
  | "mazzo_rigirato"
  | "cv_pesca_rilevata"
  | "cv_tris_rilevato"
  | "cv_movimento_carri"
  | "nota";

export type FaseTurno =
  | "pre_partita"
  | "rinforzo"
  | "attacco"
  | "spostamento"
  | "fine_partita";

// === Giocatori ===

export interface GiocatorePartita {
  id: string;
  nome: string;
  colore: ColoreGiocatore;
  ordine_seduta: number;
}

export interface GiocatorePartitaCreazione {
  nome: string;
  colore: ColoreGiocatore;
  ordine_seduta: number;
}

// === Video ===

export interface Video {
  id: string;
  nome_originale: string;
  ts_inizio: string;
  durata_sec: number;
  codec: string | null;
  risoluzione: string | null;
  dimensione_byte: number;
  data_caricamento: string;
}

// === Eventi ===

export interface EventoGrezzo {
  id: string;
  partita_id: string;
  ts_evento: string;
  tipo: TipoEvento;
  fonte: FonteEvento;
  confidenza: number;
  dati: Record<string, unknown>;
  validato: boolean;
  data_creazione: string;
}

export interface EventoGrezzoCreazione {
  ts_evento: string;
  tipo: TipoEvento;
  fonte?: FonteEvento;
  confidenza?: number;
  dati?: Record<string, unknown>;
}

export interface EventoGrezzoAggiornamento {
  ts_evento?: string;
  tipo?: TipoEvento;
  fonte?: FonteEvento;
  confidenza?: number;
  dati?: Record<string, unknown>;
}

export interface EventoValidato {
  id: string;
  partita_id: string;
  ts_evento: string;
  tipo: TipoEvento;
  dati: Record<string, unknown>;
  evento_grezzo_id: string | null;
  validato_da: string;
  data_creazione: string;
}

// === Tipi tipizzati derivati dallo schema zod condiviso ===
//
// Per nuove feature che vogliono narrowing TS automatico sul payload
// `dati` di ogni evento, importare questi al posto di `EventoValidato`
// (che ha `dati: Record<string, unknown>`).
//
// Esempio: nel visore replay, switch su `ev.tipo === "attacco_risolto"`
// fa narrowing su `ev.dati.dadi_attaccante: number[]`.
//
// Source of truth: `packages/eventi-schema/src/`. Il backend Pydantic
// è la SSOT semantica; lo schema zod è la traduzione TS verificata via
// test di round-trip.
export type {
  BundleReplay,
  DatiArmatePiazzate,
  DatiArmateSpostate,
  DatiAttaccoRisolto,
  DatiCarta,
  DatiCartaPescata,
  DatiObiettivoAssegnato,
  DatiPartitaFine,
  DatiPartitaInizio,
  DatiTerritorioAssegnatoInizio,
  DatiTerritorioConquistato,
  DatiTrisGiocato,
  DatiTurnoFinito,
  DatiTurnoIniziato,
  EventoValidato as EventoValidatoTipato,
  GiocatorePartita as GiocatorePartitaSchema,
} from "@risiko/eventi-schema";

export interface EventoValidatoCreazione {
  ts_evento: string;
  tipo: TipoEvento;
  dati?: Record<string, unknown>;
  evento_grezzo_id?: string | null;
  validato_da?: string;
}

export interface EventoValidatoAggiornamento {
  ts_evento?: string;
  tipo?: TipoEvento;
  dati?: Record<string, unknown>;
  validato_da?: string;
}

// === Partite ===

export interface PartitaSommario {
  id: string;
  data_inizio: string;
  data_fine: string | null;
  luogo: string | null;
  stato_review: StatoReview;
  data_creazione: string;
}

export interface PartitaDettaglio {
  id: string;
  data_inizio: string;
  data_fine: string | null;
  luogo: string | null;
  note: string | null;
  stato_review: StatoReview;
  data_creazione: string;
  data_aggiornamento: string;
  giocatori: GiocatorePartita[];
  video: Video[];
}

export interface PartitaCreazione {
  data_inizio: string;
  luogo?: string | null;
  note?: string | null;
  giocatori: GiocatorePartitaCreazione[];
}

export interface PartitaAggiornamento {
  data_inizio?: string;
  data_fine?: string | null;
  luogo?: string | null;
  note?: string | null;
  stato_review?: StatoReview;
}

// === Stato ricostruito ===

export interface InfoTerritorio {
  nome: string;
  controllore_id: string | null;
  armate: number;
}

export interface InfoGiocatoreSnapshot {
  player_id: string;
  colore: ColoreGiocatore;
  nome: string;
  eliminato: boolean;
}

export interface StatoPartitaSnapshot {
  fase_corrente: FaseTurno;
  turno: number;
  giocatore_attivo_id: string | null;
  vincitore_id: string | null;
  armate_da_piazzare: number;
  tris_giocato_questo_turno: boolean;
  spostamento_effettuato: boolean;
  territori_conquistati_nel_turno: string[];
  giocatori: InfoGiocatoreSnapshot[];
  territori: Record<string, InfoTerritorio>;
  conteggio_mani: Record<string, number>;
  snapshot_mazzo: Record<string, number>;
}

export interface ErroreRicostruzione {
  evento_validato_id: string;
  posizione_nella_sequenza: number;
  tipo_evento: string;
  ts_evento: string;
  classe_errore: string;
  messaggio: string;
}

export interface RisultatoRicostruzione {
  partita_id: string;
  successo: boolean;
  n_eventi_totali: number;
  n_eventi_applicati: number;
  n_errori: number;
  errori: ErroreRicostruzione[];
  stato_finale: StatoPartitaSnapshot | null;
  data_ricostruzione: string;
}
