/**
 * Configurazione runtime dell'app.
 *
 * Per ora hardcoded. In produzione: via `react-native-config` che legge
 * da `.env` al build time, oppure da `MMKV` per impostazioni runtime
 * modificabili dall'utente.
 */

import { Platform } from "react-native";

export interface Configurazione {
  /** URL del backend Risiko Live Review. */
  backend_url: string;
  /** Versione dell'app per il manifest. */
  app_version: string;
  /** Modello e OS del telefono per il manifest. */
  modello_device: string;
  os_device: string;
}

// In produzione, queste verranno popolate da react-native-config / .env
export const configurazione: Configurazione = {
  backend_url: "http://localhost:8000",
  app_version: "0.1.0",
  modello_device: Platform.select({
    ios: "iPhone",
    android: "Android",
    default: "Unknown",
  }),
  os_device: `${Platform.OS} ${Platform.Version}`,
};

/**
 * Permette di sovrascrivere il backend_url runtime (es. quando l'utente
 * lo cambia dalle impostazioni dell'app).
 */
export function impostaBackendUrl(url: string): void {
  // Trim trailing slash per evitare doppie barre.
  configurazione.backend_url = url.replace(/\/$/, "");
}
