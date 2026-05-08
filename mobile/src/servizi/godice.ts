/**
 * Servizio per la gestione dei dadi GoDice via Bluetooth Low Energy.
 *
 * Architettura:
 * - `ServizioGoDice` è l'interfaccia astratta consumata dalle schermate
 * - `StubGoDice` è un'implementazione fake che simula dadi e lanci
 *   (utile per dev senza hardware)
 * - `GoDiceBlePlx` (in arrivo) sarà l'implementazione reale via
 *   `react-native-ble-plx`. Wireup in `costruisciGoDice()`.
 *
 * Quando arrivano i dadi fisici, l'implementazione reale richiede:
 * 1. Sniffing del GATT profile (caratteristiche e UUID)
 * 2. Parser dei messaggi del dado (orientation → face value)
 * 3. Gestione disconnect/reconnect/RSSI
 *
 * I dati reali da analizzare arriveranno dopo che Edoardo riceve i 6
 * GoDice e fa lo scan con nRF Connect.
 */

import type {
  ConfigurazioneGoDado,
  DadoConnesso,
  RuoloDado,
} from "@/tipi";
import { etichettaDado } from "@/tipi";

/** Callback chiamato quando un dado nuovo viene trovato durante uno scan. */
export type CallbackDadoScansionato = (dado: {
  ble_id: string;
  nome_advertised: string | null;
  rssi: number;
}) => void;

/** Callback chiamato quando un dado connesso emette un nuovo lancio. */
export type CallbackLancio = (lancio: {
  ble_id: string;
  ruolo: RuoloDado;
  slot: 1 | 2 | 3;
  valore: number;
  ts: Date;
}) => void;

/** Callback per cambi di stato connessione. */
export type CallbackStatoDado = (
  ble_id: string,
  stato: "connesso" | "disconnesso" | "errore",
) => void;

export interface ServizioGoDice {
  /** Avvia uno scan BLE per trovare GoDice nelle vicinanze. */
  avviaScan(callback: CallbackDadoScansionato): Promise<void>;

  /** Ferma lo scan attivo. */
  fermaScan(): Promise<void>;

  /** Connette il dado e lo associa a ruolo+slot. */
  connettiDado(configurazione: ConfigurazioneGoDado): Promise<void>;

  /** Disconnette un dado. */
  disconnettiDado(ble_id: string): Promise<void>;

  /** Ritorna la lista dei dadi attualmente associati. */
  dadiCorrenti(): DadoConnesso[];

  /**
   * Sottoscrive ai lanci dei dadi connessi.
   * Ritorna una funzione di unsubscribe.
   */
  sottoscriviLanci(callback: CallbackLancio): () => void;

  /** Sottoscrive ai cambi di stato connessione. */
  sottoscriviStato(callback: CallbackStatoDado): () => void;

  /** Pulizia generale (chiamare allo unmount o reset). */
  reset(): Promise<void>;
}

/**
 * Implementazione stub per sviluppo senza hardware.
 *
 * Simula 6 dadi virtuali che si "scansionano" istantaneamente, si
 * connettono in 200ms, e tirano valori casuali ogni 5 secondi se
 * abilitati con `_simulaLanciAutomatici`.
 */
export class StubGoDice implements ServizioGoDice {
  private dadi: Map<string, DadoConnesso> = new Map();
  private listenerLancio: Set<CallbackLancio> = new Set();
  private listenerStato: Set<CallbackStatoDado> = new Set();
  private timerSimulazione: ReturnType<typeof setInterval> | null = null;

  async avviaScan(callback: CallbackDadoScansionato): Promise<void> {
    // Simula 6 dadi con MAC fake
    const fakeMac = (i: number) =>
      `AA:BB:${i.toString(16).padStart(2, "0").toUpperCase()}:CC:DD:EE`;

    for (let i = 0; i < 6; i++) {
      // Piccolo delay per simulare il discovery progressivo
      await this.attendi(150 + i * 100);
      callback({
        ble_id: fakeMac(i),
        nome_advertised: `GoDice_${i + 1}`,
        rssi: -45 - i * 3,
      });
    }
  }

  async fermaScan(): Promise<void> {
    // Niente da fare nello stub
  }

  async connettiDado(configurazione: ConfigurazioneGoDado): Promise<void> {
    await this.attendi(200);
    const dado: DadoConnesso = {
      configurazione,
      stato_connessione: "connesso",
      ultimo_valore: null,
      ultimo_aggiornamento: null,
      rssi: -50,
    };
    this.dadi.set(configurazione.ble_id, dado);
    this.emettiStato(configurazione.ble_id, "connesso");
  }

  async disconnettiDado(ble_id: string): Promise<void> {
    const dado = this.dadi.get(ble_id);
    if (dado) {
      this.dadi.set(ble_id, {
        ...dado,
        stato_connessione: "disconnesso",
      });
      this.emettiStato(ble_id, "disconnesso");
    }
  }

  dadiCorrenti(): DadoConnesso[] {
    return Array.from(this.dadi.values());
  }

  sottoscriviLanci(callback: CallbackLancio): () => void {
    this.listenerLancio.add(callback);
    return () => {
      this.listenerLancio.delete(callback);
    };
  }

  sottoscriviStato(callback: CallbackStatoDado): () => void {
    this.listenerStato.add(callback);
    return () => {
      this.listenerStato.delete(callback);
    };
  }

  async reset(): Promise<void> {
    this.fermaSimulazione();
    this.dadi.clear();
    this.listenerLancio.clear();
    this.listenerStato.clear();
  }

  // === Helpers di sviluppo ===

  /**
   * Inietta un lancio simulato. Utile in test e demo.
   * Non disponibile nell'implementazione reale.
   */
  iniettaLancioSimulato(args: {
    ble_id: string;
    valore: number;
  }): void {
    const dado = this.dadi.get(args.ble_id);
    if (!dado) return;

    const ts = new Date();
    this.dadi.set(args.ble_id, {
      ...dado,
      ultimo_valore: args.valore,
      ultimo_aggiornamento: ts.toISOString(),
    });

    for (const cb of this.listenerLancio) {
      cb({
        ble_id: args.ble_id,
        ruolo: dado.configurazione.ruolo,
        slot: dado.configurazione.slot,
        valore: args.valore,
        ts,
      });
    }
  }

  /**
   * Avvia una simulazione automatica: ogni dado connesso lancia un
   * valore casuale ogni `intervalloMs` millisecondi.
   */
  avviaSimulazioneLanciAutomatici(intervalloMs = 5000): void {
    this.fermaSimulazione();
    this.timerSimulazione = setInterval(() => {
      const connessi = this.dadiCorrenti().filter(
        (d) => d.stato_connessione === "connesso",
      );
      for (const d of connessi) {
        const valore = 1 + Math.floor(Math.random() * 6);
        this.iniettaLancioSimulato({
          ble_id: d.configurazione.ble_id,
          valore,
        });
      }
    }, intervalloMs);
  }

  fermaSimulazione(): void {
    if (this.timerSimulazione !== null) {
      clearInterval(this.timerSimulazione);
      this.timerSimulazione = null;
    }
  }

  // === Privati ===

  private emettiStato(
    ble_id: string,
    stato: "connesso" | "disconnesso" | "errore",
  ): void {
    for (const cb of this.listenerStato) {
      cb(ble_id, stato);
    }
  }

  private attendi(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// === Helper costruzione configurazione ===

/** Crea le 6 configurazioni canoniche (3 attaccante + 3 difensore). */
export function configurazioniCanoniche(
  ble_id_attaccante: [string, string, string],
  ble_id_difensore: [string, string, string],
): ConfigurazioneGoDado[] {
  const out: ConfigurazioneGoDado[] = [];
  for (let i = 0; i < 3; i++) {
    const slot = (i + 1) as 1 | 2 | 3;
    out.push({
      ble_id: ble_id_attaccante[i]!,
      ruolo: "attaccante",
      slot,
      etichetta: etichettaDado("attaccante", slot),
    });
  }
  for (let i = 0; i < 3; i++) {
    const slot = (i + 1) as 1 | 2 | 3;
    out.push({
      ble_id: ble_id_difensore[i]!,
      ruolo: "difensore",
      slot,
      etichetta: etichettaDado("difensore", slot),
    });
  }
  return out;
}

// === Factory ===

let istanzaCorrente: ServizioGoDice | null = null;

/**
 * Factory che ritorna l'implementazione corrente.
 *
 * In dev: stub con dadi virtuali.
 * In produzione (futuro): switch automatico a `GoDiceBlePlx` quando
 * disponibile.
 */
export function ottieniServizioGoDice(): ServizioGoDice {
  if (!istanzaCorrente) {
    istanzaCorrente = new StubGoDice();
  }
  return istanzaCorrente;
}

/** Per i test: forza una specifica implementazione. */
export function impostaServizioGoDicePerTest(servizio: ServizioGoDice): void {
  istanzaCorrente = servizio;
}
