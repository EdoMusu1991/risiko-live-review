/**
 * Timeline navigabile su un BundleReplay.
 *
 * Convenzione indici (importante per il consumer):
 *   - idx = -1     → stato iniziale, post creaStatoInizialeDaBundle, PRE eventi
 *   - idx = 0      → stato DOPO aver applicato l'evento 0
 *   - idx = N-1    → stato DOPO l'ultimo evento (= stato finale partita)
 *
 * Strategia di calcolo:
 *   - Lazy: statoAlIndice(i) ricalcola applicando eventi da 0 a i.
 *   - Cache LRU degli ultimi `cacheMaxSize` stati richiesti.
 *   - Per scrubbing fluido in avanti, parte sempre dallo stato cached più
 *     vicino ≤ idx richiesto e forward-replay solo i mancanti.
 *
 * Per partite reali (~200-500 eventi) e cache di 50, lo scrubbing arbitrario è
 * ben sotto i 16ms anche su hardware modesto. Se in futuro servirà di più, si
 * aggiungono snapshot fissi ogni N eventi.
 */

import { applicaEvento, creaStatoInizialeDaBundle } from "./stato.js";
import type { StatoPartita } from "./stato.js";
import type { BundleReplay, EventoValidato } from "@risiko/eventi-schema";

export interface OpzioniTimeline {
  /** Numero massimo di stati tenuti in cache LRU. Default 50. */
  cacheMaxSize?: number;
}

export class Timeline {
  readonly bundle: BundleReplay;
  readonly lunghezza: number;

  private readonly cacheMaxSize: number;
  private readonly cache: Map<number, StatoPartita>;

  constructor(bundle: BundleReplay, opzioni: OpzioniTimeline = {}) {
    this.bundle = bundle;
    this.lunghezza = bundle.eventi.length;
    this.cacheMaxSize = Math.max(1, opzioni.cacheMaxSize ?? 50);
    this.cache = new Map();
  }

  /**
   * Ritorna lo stato della partita all'indice richiesto.
   *
   * @param idx -1 (pre-eventi) ≤ idx ≤ lunghezza-1
   * @throws RangeError se l'indice è fuori range
   */
  statoAlIndice(idx: number): StatoPartita {
    if (idx < -1 || idx >= this.lunghezza) {
      throw new RangeError(
        `idx fuori range: ${idx} (atteso -1..${this.lunghezza - 1})`,
      );
    }
    if (idx === -1) {
      // Lo stato iniziale è ricostruito ogni volta: è economico (solo i
      // giocatori del bundle) e tenerlo in cache rischierebbe di essere
      // mutato dal consumer.
      return creaStatoInizialeDaBundle(this.bundle);
    }
    const cached = this.cache.get(idx);
    if (cached) {
      // Promuovi l'entry come "recently used" rimettendola in coda.
      this.cache.delete(idx);
      this.cache.set(idx, cached);
      return cached;
    }

    // Trova il più vicino snapshot cached con chiave ≤ idx.
    let prevIdx = -1;
    let prevStato: StatoPartita | null = null;
    for (const [k, v] of this.cache) {
      if (k <= idx && k > prevIdx) {
        prevIdx = k;
        prevStato = v;
      }
    }
    let stato = prevStato ?? creaStatoInizialeDaBundle(this.bundle);
    for (let i = prevIdx + 1; i <= idx; i++) {
      const evento = this.bundle.eventi[i];
      if (!evento) {
        throw new RangeError(`Evento nullo a idx ${i}`);
      }
      stato = applicaEvento(stato, evento);
    }

    this._aggiungiCache(idx, stato);
    return stato;
  }

  /**
   * Ritorna l'evento all'indice (0..lunghezza-1) o null fuori range.
   */
  eventoAlIndice(idx: number): EventoValidato | null {
    if (idx < 0 || idx >= this.lunghezza) return null;
    return this.bundle.eventi[idx] ?? null;
  }

  /**
   * Ritorna gli eventi nell'intervallo `[da, a]` (estremi inclusi). Utile per
   * costruire il narrative di un turno: passa da/a corrispondenti agli eventi
   * tra due `turno_iniziato`.
   *
   * Restituisce array vuoto se `da > a` o se gli indici sono fuori range.
   */
  eventiTraIndici(da: number, a: number): EventoValidato[] {
    if (da > a || da < 0 || a >= this.lunghezza) return [];
    return this.bundle.eventi.slice(da, a + 1);
  }

  /**
   * Trova gli indici degli eventi `turno_iniziato`. Utile per la UI: il
   * consumer può creare uno scrubber "per turno" invece che per evento.
   */
  indiciTurni(): number[] {
    const out: number[] = [];
    for (let i = 0; i < this.lunghezza; i++) {
      if (this.bundle.eventi[i]?.tipo === "turno_iniziato") out.push(i);
    }
    return out;
  }

  /**
   * Pulisce la cache. Utile in caso di consumer che muta lo stato per errore.
   */
  resetCache(): void {
    this.cache.clear();
  }

  // --- Internals ---

  private _aggiungiCache(idx: number, stato: StatoPartita): void {
    if (this.cache.size >= this.cacheMaxSize) {
      // Evict il least recently used (= primo nell'ordine di insertion).
      const firstKey = this.cache.keys().next().value;
      if (firstKey !== undefined) {
        this.cache.delete(firstKey);
      }
    }
    this.cache.set(idx, stato);
  }
}

/**
 * Factory di convenienza.
 */
export function creaTimeline(
  bundle: BundleReplay,
  opzioni?: OpzioniTimeline,
): Timeline {
  return new Timeline(bundle, opzioni);
}
