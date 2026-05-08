/**
 * Servizio di registrazione video.
 *
 * Astrazione sopra `react-native-vision-camera`. Anche qui due
 * implementazioni:
 * - `StubRegistratore`: simula start/stop senza camera reale,
 *   produce un file fittizio. Per dev senza Mac/dispositivo.
 * - `RegistratoreVisionCamera`: implementazione reale (in arrivo
 *   quando avremo iPhone+Mac o Android collegato).
 *
 * Convenzione importante: il `ts_inizio` e `ts_fine` ritornati dal
 * servizio condividono lo stesso clock dei lanci BLE — è il `Date.now()`
 * del telefono. Questa coincidenza di clock è la ragione architetturale
 * per cui app mobile è single-device (vs il vecchio setup con tablet
 * separato che richiedeva sincronizzazione NTP).
 */

import RNFS from "react-native-fs";

export interface RisultatoRegistrazione {
  /** Path completo del file video sul filesystem del telefono. */
  file_path: string;
  /** Filename "logico" (senza path), usato nel manifest. */
  nome_file: string;
  ts_inizio: Date;
  ts_fine: Date;
  durata_sec: number;
  dimensione_byte: number;
  /** Codec usato dalla camera. */
  codec: string | null;
  /** Risoluzione, es: "1920x1080". */
  risoluzione: string | null;
}

export interface ServizioRegistratore {
  /**
   * Verifica e richiede i permessi camera + microfono.
   * Ritorna true se concessi.
   */
  verificaPermessi(): Promise<boolean>;

  /** Avvia la registrazione. Solleva se non c'è permesso o camera. */
  avviaRegistrazione(): Promise<void>;

  /**
   * Termina la registrazione corrente. Ritorna il file prodotto.
   *
   * Solleva se non c'era una registrazione attiva.
   */
  fermaRegistrazione(): Promise<RisultatoRegistrazione>;

  /** True se sta registrando in questo momento. */
  inRegistrazione(): boolean;

  /** Pulizia (chiamare allo unmount). */
  reset(): Promise<void>;
}

/** Stub: simula la registrazione senza usare la camera. */
export class StubRegistratore implements ServizioRegistratore {
  private registrando = false;
  private tsInizio: Date | null = null;

  async verificaPermessi(): Promise<boolean> {
    return true;
  }

  async avviaRegistrazione(): Promise<void> {
    if (this.registrando) {
      throw new Error("Registrazione già in corso");
    }
    this.registrando = true;
    this.tsInizio = new Date();
  }

  async fermaRegistrazione(): Promise<RisultatoRegistrazione> {
    if (!this.registrando || this.tsInizio === null) {
      throw new Error("Nessuna registrazione attiva");
    }
    const tsFine = new Date();
    const durataSec = (tsFine.getTime() - this.tsInizio.getTime()) / 1000;

    // Crea un file "fake" sul filesystem del telefono.
    // Su un device reale il path è ` ${RNFS.DocumentDirectoryPath}/...`.
    const nomeFile = `registrazione-${Date.now()}.mp4`;
    const filePath = `${RNFS.DocumentDirectoryPath}/${nomeFile}`;

    const contenutoFake = "FAKE_MP4_PLACEHOLDER";
    await RNFS.writeFile(filePath, contenutoFake, "utf8");
    const stat = await RNFS.stat(filePath);

    this.registrando = false;
    const risultato: RisultatoRegistrazione = {
      file_path: filePath,
      nome_file: nomeFile,
      ts_inizio: this.tsInizio,
      ts_fine: tsFine,
      durata_sec: durataSec,
      dimensione_byte: Number(stat.size),
      codec: "h264",
      risoluzione: "1920x1080",
    };
    this.tsInizio = null;
    return risultato;
  }

  inRegistrazione(): boolean {
    return this.registrando;
  }

  async reset(): Promise<void> {
    if (this.registrando) {
      try {
        await this.fermaRegistrazione();
      } catch {
        // ignore
      }
    }
    this.registrando = false;
    this.tsInizio = null;
  }
}

// === Factory ===

let istanzaCorrente: ServizioRegistratore | null = null;

export function ottieniRegistratore(): ServizioRegistratore {
  if (!istanzaCorrente) {
    istanzaCorrente = new StubRegistratore();
  }
  return istanzaCorrente;
}

export function impostaRegistratorePerTest(s: ServizioRegistratore): void {
  istanzaCorrente = s;
}
