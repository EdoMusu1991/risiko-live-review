/**
 * Storage locale persistente (MMKV).
 *
 * Conserva la cronologia degli upload tra una sessione e l'altra
 * dell'app. Niente DB SQLite — un singolo MMKV map basta per il volume
 * atteso (decine di partite/anno per club).
 */

import { MMKV } from "react-native-mmkv";

import type { RecordUpload } from "@/tipi";

const STORAGE = new MMKV({ id: "risiko-upload-cronologia" });

const CHIAVE_INDICE = "indice";

/**
 * Salva o aggiorna un record di upload.
 * Idempotente: se esiste già, sovrascrive.
 */
export function salvaRecordUpload(record: RecordUpload): void {
  STORAGE.set(
    chiaveRecord(record.partita_id_locale),
    JSON.stringify(record),
  );
  aggiungiAdIndice(record.partita_id_locale);
}

/** Ritorna tutti i record, ordinati per data registrazione (più recente prima). */
export function leggiTuttiRecordUpload(): RecordUpload[] {
  const indice = leggiIndice();
  const out: RecordUpload[] = [];
  for (const id of indice) {
    const raw = STORAGE.getString(chiaveRecord(id));
    if (!raw) continue;
    try {
      out.push(JSON.parse(raw) as RecordUpload);
    } catch {
      // Corrotto? Ignora. Si potrebbe loggare.
    }
  }
  out.sort((a, b) =>
    b.data_registrazione.localeCompare(a.data_registrazione),
  );
  return out;
}

/** Ritorna un singolo record per id locale, o null se non esiste. */
export function leggiRecordUpload(
  partita_id_locale: string,
): RecordUpload | null {
  const raw = STORAGE.getString(chiaveRecord(partita_id_locale));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as RecordUpload;
  } catch {
    return null;
  }
}

/** Aggiorna alcuni campi di un record esistente. Lancia se non esiste. */
export function aggiornaRecordUpload(
  partita_id_locale: string,
  modifiche: Partial<RecordUpload>,
): RecordUpload {
  const corrente = leggiRecordUpload(partita_id_locale);
  if (!corrente) {
    throw new Error(`Record upload '${partita_id_locale}' non trovato`);
  }
  const aggiornato: RecordUpload = { ...corrente, ...modifiche };
  salvaRecordUpload(aggiornato);
  return aggiornato;
}

/** Elimina un record dalla cronologia (NON elimina il file ZIP sul disco). */
export function eliminaRecordUpload(partita_id_locale: string): void {
  STORAGE.delete(chiaveRecord(partita_id_locale));
  rimuoviDaIndice(partita_id_locale);
}

// === Privati ===

function chiaveRecord(id: string): string {
  return `record:${id}`;
}

function leggiIndice(): string[] {
  const raw = STORAGE.getString(CHIAVE_INDICE);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as string[];
  } catch {
    return [];
  }
}

function aggiungiAdIndice(id: string): void {
  const indice = leggiIndice();
  if (!indice.includes(id)) {
    indice.push(id);
    STORAGE.set(CHIAVE_INDICE, JSON.stringify(indice));
  }
}

function rimuoviDaIndice(id: string): void {
  const indice = leggiIndice().filter((i) => i !== id);
  STORAGE.set(CHIAVE_INDICE, JSON.stringify(indice));
}
