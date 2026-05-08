/**
 * Schemi del bundle ZIP che l'app produce.
 *
 * **Contratto stabile** con il backend (`app.servizi.import_bundle_servizio`).
 * Modificare con cura. Versione corrente: `1.0`.
 *
 * Bundle layout:
 * ```
 * risiko-partita-{uuid}.zip
 * ├── manifest.json
 * ├── video.mp4
 * └── eventi.jsonl
 * ```
 */

import type { Giocatore, ColoreGiocatore } from "./partita";
import type { RuoloDado } from "./godice";

export const SCHEMA_VERSION_BUNDLE = "1.0";

// === Manifest ===

export interface ManifestDevice {
  /** Es: "iPhone 11", "Galaxy S24". */
  modello: string;
  /** Es: "iOS 17.4", "Android 14". */
  os: string;
  /** Versione dell'app mobile. Da `package.json`. */
  app_version: string;
}

export interface ManifestRegistrazione {
  /** Timestamp ISO 8601 con timezone. Inizio registrazione. */
  ts_inizio: string;
  ts_fine: string;
  durata_sec: number;
  /** Filename relativo dentro lo ZIP (default `video.mp4`). */
  video_file: string;
  /** SHA256 hex del video (lowercase). Null se non calcolato. */
  video_sha256: string | null;
  video_dimensione_byte: number;
}

export interface ManifestGoDice {
  n_dadi_attaccante: number;
  n_dadi_difensore: number;
  /** MAC address dei dadi attaccante in ordine slot 1, 2, 3. */
  ble_id_attaccante: string[];
  ble_id_difensore: string[];
}

export interface ManifestEventi {
  n_eventi_totali: number;
  /** Filename relativo dentro lo ZIP (default `eventi.jsonl`). */
  eventi_file: string;
}

export interface ManifestGiocatore {
  nome: string;
  colore: ColoreGiocatore;
  ordine_seduta: number;
}

/** Manifest completo — root del file `manifest.json`. */
export interface Manifest {
  schema_version: string;
  partita_id_locale: string;
  luogo: string | null;
  note: string | null;
  device: ManifestDevice;
  registrazione: ManifestRegistrazione;
  godice: ManifestGoDice;
  eventi: ManifestEventi;
  giocatori: ManifestGiocatore[];
}

// === Eventi (righe del file eventi.jsonl) ===

/**
 * Tipi di evento che l'app può loggare.
 *
 * Per ora il backend importa solo `dado_lanciato`. Gli altri sono
 * riservati a estensioni future (per ora vengono scartati silenziosamente
 * nel backend).
 */
export type TipoEventoBle =
  | "dado_lanciato"
  | "dado_collegato"
  | "dado_disconnesso"
  | "connessione_persa"
  | "stop_registrazione";

export interface EventoDadoLanciato {
  ts: string;
  tipo: "dado_lanciato";
  ble_id: string;
  ruolo: RuoloDado;
  slot: 1 | 2 | 3;
  /** Numero da 1 a 6 letto dal GoDice. Null se la lettura è ambigua. */
  valore: number | null;
}

export interface EventoDadoStato {
  ts: string;
  tipo: "dado_collegato" | "dado_disconnesso" | "connessione_persa";
  ble_id: string;
  ruolo: RuoloDado;
  slot: 1 | 2 | 3;
}

export interface EventoStopRegistrazione {
  ts: string;
  tipo: "stop_registrazione";
  motivo: "manuale" | "errore_camera" | "batteria_bassa" | "altro";
}

export type RigaEventoJsonl =
  | EventoDadoLanciato
  | EventoDadoStato
  | EventoStopRegistrazione;

// === Helper ===

/** Crea un manifest base con tutti i campi obbligatori. */
export function creaManifestBase(args: {
  partita_id_locale: string;
  device: ManifestDevice;
  registrazione: ManifestRegistrazione;
  godice: ManifestGoDice;
  eventi: ManifestEventi;
  giocatori: Giocatore[];
  luogo: string | null;
  note: string | null;
}): Manifest {
  return {
    schema_version: SCHEMA_VERSION_BUNDLE,
    partita_id_locale: args.partita_id_locale,
    luogo: args.luogo,
    note: args.note,
    device: args.device,
    registrazione: args.registrazione,
    godice: args.godice,
    eventi: args.eventi,
    giocatori: args.giocatori.map((g) => ({
      nome: g.nome,
      colore: g.colore,
      ordine_seduta: g.ordine_seduta,
    })),
  };
}
