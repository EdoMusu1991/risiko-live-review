/**
 * Tipi del dominio "partita" per l'app mobile.
 *
 * Speculari ai modelli backend (`app.modelli.tipi`) ma in italiano-TS.
 * Quando il backend introduce nuovi colori/ruoli, aggiornare qui.
 */

export type ColoreGiocatore =
  | "rosso"
  | "blu"
  | "verde"
  | "giallo"
  | "nero"
  | "viola";

export const COLORI_GIOCATORE: ReadonlyArray<ColoreGiocatore> = [
  "rosso",
  "blu",
  "verde",
  "giallo",
  "nero",
  "viola",
];

export interface Giocatore {
  /** Nome breve per UI (es. "Edo"). */
  nome: string;
  colore: ColoreGiocatore;
  /** Posizione al tavolo (1=primo a sinistra, 2=secondo, ...). */
  ordine_seduta: number;
}

/**
 * Stato corrente della partita in memoria sull'app mobile.
 *
 * Mai persistito — viene buttato giù al `RESET` post-upload.
 */
export interface StatoPartitaInMemoria {
  /** UUID generato sull'app, identifica univocamente questa registrazione. */
  partita_id_locale: string;
  giocatori: Giocatore[];
  luogo: string | null;
  note: string | null;
  /** True se l'utente ha completato il setup e la registrazione può iniziare. */
  pronta: boolean;
}
