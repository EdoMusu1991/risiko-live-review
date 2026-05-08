/**
 * Costruzione del bundle ZIP da inviare al server.
 *
 * Layout prodotto:
 * ```
 * risiko-partita-{uuid}.zip
 * ├── manifest.json
 * ├── video.mp4         (rinominato dal nome originale)
 * └── eventi.jsonl
 * ```
 *
 * Tutti i percorsi sono nella sandbox dell'app (RNFS DocumentDirectoryPath).
 * Il bundle viene salvato e restituito; il file video originale e il
 * jsonl temporaneo sono lasciati nella cartella `temp/<partita_id>/`
 * fino a che l'utente non conferma l'invio o cancella la partita.
 */

import RNFS from "react-native-fs";
import { zip } from "react-native-zip-archive";

import type {
  Manifest,
  RigaEventoJsonl,
  Giocatore,
  ManifestDevice,
  ManifestGoDice,
} from "@/tipi";
import { creaManifestBase } from "@/tipi";

import type { RisultatoRegistrazione } from "./registratore";

export interface ParametriBundle {
  partita_id_locale: string;
  giocatori: Giocatore[];
  luogo: string | null;
  note: string | null;
  device: ManifestDevice;
  godice: ManifestGoDice;
  registrazione: RisultatoRegistrazione;
  /** Eventi BLE già raccolti (in ordine cronologico). */
  eventi: RigaEventoJsonl[];
}

export interface BundleProdotto {
  /** Path del file ZIP finale. */
  zip_path: string;
  /** Dimensione del bundle in byte. */
  zip_dimensione_byte: number;
  /** Manifest che è stato scritto dentro lo ZIP (utile per UI riepilogo). */
  manifest: Manifest;
}

const NOME_VIDEO_DENTRO_ZIP = "video.mp4";
const NOME_EVENTI_DENTRO_ZIP = "eventi.jsonl";
const NOME_MANIFEST = "manifest.json";

/**
 * Cartella radice per i file di lavoro durante il build.
 * Strutturata per partita: `temp/<partita_id_locale>/`.
 */
function cartellaTemp(partita_id_locale: string): string {
  return `${RNFS.DocumentDirectoryPath}/temp/${partita_id_locale}`;
}

/**
 * Costruisce il bundle ZIP completo.
 *
 * Side effects:
 * - Crea `temp/<partita_id>/` con i 3 file
 * - Sposta il video dalla sua posizione originale alla cartella temp
 * - Zippa la cartella in `bundle/risiko-partita-<id>.zip`
 * - Lascia la cartella temp e il bundle finale sul disco
 */
export async function costruisciBundle(
  parametri: ParametriBundle,
): Promise<BundleProdotto> {
  const tempDir = cartellaTemp(parametri.partita_id_locale);
  await assicuraDir(tempDir);

  // 1. Sposta (o copia) il video dentro temp/ con nome canonico
  const videoPath = `${tempDir}/${NOME_VIDEO_DENTRO_ZIP}`;
  await RNFS.moveFile(parametri.registrazione.file_path, videoPath);

  // 2. Scrivi eventi.jsonl
  const eventiPath = `${tempDir}/${NOME_EVENTI_DENTRO_ZIP}`;
  const jsonlContent =
    parametri.eventi.map((e) => JSON.stringify(e)).join("\n") +
    (parametri.eventi.length > 0 ? "\n" : "");
  await RNFS.writeFile(eventiPath, jsonlContent, "utf8");

  // 3. Costruisci e scrivi manifest.json
  const manifest = creaManifestBase({
    partita_id_locale: parametri.partita_id_locale,
    device: parametri.device,
    registrazione: {
      ts_inizio: parametri.registrazione.ts_inizio.toISOString(),
      ts_fine: parametri.registrazione.ts_fine.toISOString(),
      durata_sec: parametri.registrazione.durata_sec,
      video_file: NOME_VIDEO_DENTRO_ZIP,
      // SHA256 calcolato dopo lo spostamento del file (opzionale, costoso).
      video_sha256: null,
      video_dimensione_byte: parametri.registrazione.dimensione_byte,
    },
    godice: parametri.godice,
    eventi: {
      n_eventi_totali: parametri.eventi.length,
      eventi_file: NOME_EVENTI_DENTRO_ZIP,
    },
    giocatori: parametri.giocatori,
    luogo: parametri.luogo,
    note: parametri.note,
  });

  const manifestPath = `${tempDir}/${NOME_MANIFEST}`;
  await RNFS.writeFile(manifestPath, JSON.stringify(manifest, null, 2), "utf8");

  // 4. Zippa la cartella in `bundle/`
  const bundleDir = `${RNFS.DocumentDirectoryPath}/bundle`;
  await assicuraDir(bundleDir);
  const zipPath = `${bundleDir}/risiko-partita-${parametri.partita_id_locale}.zip`;

  // Se esiste già (retry), eliminalo prima
  if (await RNFS.exists(zipPath)) {
    await RNFS.unlink(zipPath);
  }
  await zip(tempDir, zipPath);

  const stat = await RNFS.stat(zipPath);

  return {
    zip_path: zipPath,
    zip_dimensione_byte: Number(stat.size),
    manifest,
  };
}

/**
 * Elimina il bundle e i file temporanei di una partita.
 *
 * Da chiamare quando l'utente conferma l'eliminazione o dopo upload
 * andato a buon fine + utente che svuota la cronologia.
 */
export async function eliminaBundle(partita_id_locale: string): Promise<void> {
  const tempDir = cartellaTemp(partita_id_locale);
  if (await RNFS.exists(tempDir)) {
    await RNFS.unlink(tempDir);
  }
  const zipPath = `${RNFS.DocumentDirectoryPath}/bundle/risiko-partita-${partita_id_locale}.zip`;
  if (await RNFS.exists(zipPath)) {
    await RNFS.unlink(zipPath);
  }
}

async function assicuraDir(path: string): Promise<void> {
  if (!(await RNFS.exists(path))) {
    await RNFS.mkdir(path);
  }
}
