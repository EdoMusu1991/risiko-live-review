/**
 * Tipi del dominio "GoDice" — i dadi BLE.
 *
 * Filosofia 6-dadi:
 * - 3 dadi associati al ruolo "attaccante", slot 1/2/3
 * - 3 dadi associati al ruolo "difensore", slot 1/2/3
 *
 * I dadi NON sono associati ai giocatori: stanno fissi al centro del
 * tavolo. Quando attacca un giocatore, prende i 3 dadi attaccante.
 * Quando difende, prende i 3 dadi difensore.
 *
 * Ragioni di questa scelta:
 * - 6 dadi al posto di 12 → costo dimezzato (~80€ invece di 160€)
 * - In Risiko il massimo è 3v3 → 6 dadi sono sufficienti
 * - I dadi non vanno scambiati ogni turno (semplicità operativa)
 */

export type RuoloDado = "attaccante" | "difensore";

export interface ConfigurazioneGoDado {
  /** MAC address Bluetooth del GoDice. */
  ble_id: string;
  ruolo: RuoloDado;
  /** Slot 1, 2 o 3 entro il proprio ruolo. */
  slot: 1 | 2 | 3;
  /** Nome amichevole per l'UI (es. "Att-1"). Generato automaticamente. */
  etichetta: string;
}

export type StatoConnessioneDado =
  | "non_associato"
  | "in_scan"
  | "connesso"
  | "disconnesso"
  | "errore";

export interface DadoConnesso {
  configurazione: ConfigurazioneGoDado;
  stato_connessione: StatoConnessioneDado;
  /** Ultimo valore letto, se mai. */
  ultimo_valore: number | null;
  /** Timestamp ultima lettura, se mai. */
  ultimo_aggiornamento: string | null;
  /** RSSI (potenza segnale) quando disponibile. */
  rssi: number | null;
}

/** Genera l'etichetta umana standard per un dado. */
export function etichettaDado(ruolo: RuoloDado, slot: 1 | 2 | 3): string {
  return ruolo === "attaccante" ? `Att-${slot}` : `Dif-${slot}`;
}
