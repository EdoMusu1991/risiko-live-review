/**
 * Tipi per la cronologia degli upload.
 *
 * Persistiti in MMKV. Permettono all'utente di vedere lo stato di ogni
 * tentativo di invio (in coda, in corso, riuscito, fallito).
 */

export type StatoUpload =
  | "in_coda"          // bundle pronto sul telefono, in attesa di invio
  | "in_corso"         // upload in corso
  | "completato"       // server ha accettato, partita_id ricevuto
  | "fallito"          // errore di rete o server, riprovabile
  | "scartato";        // bundle eliminato dall'utente

export interface RecordUpload {
  /** UUID locale generato sull'app, persistente. */
  partita_id_locale: string;
  /** Path completo del file ZIP sul filesystem del telefono. */
  bundle_path: string;
  /** Dimensione del bundle in byte. */
  bundle_dimensione_byte: number;
  /** Quando è stata creata la registrazione (ISO 8601). */
  data_registrazione: string;
  /** Durata della registrazione (sec). */
  durata_sec: number;
  /** Numero di eventi BLE catturati. */
  n_eventi: number;
  /** Numero di giocatori. */
  n_giocatori: number;
  /** Stato corrente nel ciclo di upload. */
  stato: StatoUpload;
  /** Messaggio di errore se `stato == "fallito"`. */
  errore: string | null;
  /** UUID della partita sul server, ricevuto a upload completato. */
  partita_id_server: string | null;
  /** Timestamp ISO ultimo tentativo. */
  ultimo_tentativo: string | null;
  /** Numero di tentativi fatti (incrementa a ogni retry). */
  n_tentativi: number;
}
