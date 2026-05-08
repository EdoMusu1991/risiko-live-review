/**
 * Upload del bundle ZIP al backend.
 *
 * Usa `fetch` nativo con `FormData` (multipart/form-data). Per file
 * molto grandi, in futuro si può passare a `RNFS.uploadFiles` che
 * supporta upload in background su iOS.
 */

import RNFS from "react-native-fs";

import { configurazione } from "@/configurazione";

export interface RispostaUpload {
  partita_id: string;
  n_giocatori: number;
  n_eventi_grezzi_creati: number;
  n_eventi_scartati: number;
  durata_video_sec: number;
  dimensione_video_byte: number;
  note: string[];
}

export class ErroreUpload extends Error {
  constructor(
    public readonly status: number,
    public readonly dettaglio: string,
  ) {
    super(dettaglio);
    this.name = "ErroreUpload";
  }
}

/**
 * Carica il bundle al backend.
 *
 * Lancia `ErroreUpload` con dettaglio leggibile in caso di errore.
 * Su rete instabile, il chiamante gestisce il retry (l'app uploader
 * non ritenta automaticamente per evitare di sovraccaricare il server
 * in caso di errori 4xx).
 */
export async function caricaBundle(
  zipPath: string,
  onProgresso?: (frazione: number) => void,
): Promise<RispostaUpload> {
  if (!(await RNFS.exists(zipPath))) {
    throw new ErroreUpload(0, `File bundle non trovato: ${zipPath}`);
  }

  const url = `${configurazione.backend_url}/api/import/bundle-mobile`;

  // Usiamo `RNFS.uploadFiles` invece di `fetch` per avere il progresso
  // di upload e supporto background (iOS) "gratis".
  const risultato = await RNFS.uploadFiles({
    toUrl: url,
    method: "POST",
    files: [
      {
        name: "file",
        filename: nomeFileDaPath(zipPath),
        filepath: zipPath,
        filetype: "application/zip",
      },
    ],
    progress: (progresso) => {
      if (onProgresso) {
        onProgresso(progresso.totalBytesSent / progresso.totalBytesExpectedToSend);
      }
    },
  }).promise;

  if (risultato.statusCode < 200 || risultato.statusCode >= 300) {
    let dettaglio = `HTTP ${risultato.statusCode}`;
    try {
      const corpo = JSON.parse(risultato.body);
      if (typeof corpo.detail === "string") {
        dettaglio = corpo.detail;
      }
    } catch {
      // body non JSON, mantieni dettaglio default
    }
    throw new ErroreUpload(risultato.statusCode, dettaglio);
  }

  const risposta = JSON.parse(risultato.body) as RispostaUpload;
  return risposta;
}

function nomeFileDaPath(path: string): string {
  const idx = path.lastIndexOf("/");
  return idx === -1 ? path : path.slice(idx + 1);
}
