/**
 * API client per le inferenze CV e le divergenze CV ↔ motore.
 *
 * Endpoint corrispondenti backend: app/routers/inferenze_cv.py
 *
 * Uso tipico nel frontend:
 *   const riepilogo = await apiInferenzeCV.listaDiscrepanze(partitaId);
 *   for (const d of riepilogo.divergenze) { ... }
 */

import { chiamaApi, cliente } from "./cliente";

export type RisoluzioneDivergenza =
  | "aperta"
  | "accettata_motore"
  | "accettata_cv"
  | "evento_aggiunto";

export interface InferenzaCV {
  id: string;
  partita_id: string;
  evento_validato_id: string | null;
  modello_versione: string;
  territorio: string | null;
  colore: string | null;
  tipo_pedina_dominante: string | null;
  n_armate_stimate: number;
  bbox: [number, number, number, number];
  confidence: number;
  scomposizione: Record<string, unknown>[];
  frame_hash: string | null;
  creata_il: string;
}

export interface DivergenzaInferita {
  id: string;
  partita_id: string;
  evento_validato_id: string | null;
  territorio: string;
  colore: string;
  valore_motore: number;
  valore_cv: number;
  confidence_cv: number;
  delta_assoluto: number;
  inferenze_correlate: string[];
  risoluzione: RisoluzioneDivergenza;
  note: string | null;
  creata_il: string;
  aggiornata_il: string;
}

export interface RiepilogoDiscrepanze {
  n_divergenze_totali: number;
  n_aperte: number;
  n_risolte: number;
  delta_max: number;
  divergenze: DivergenzaInferita[];
}

export const apiInferenzeCV = {
  /** Lista delle inferenze CV per la partita (filtrabili). */
  lista: (
    partitaId: string,
    opzioni: { eventoValidatoId?: string; modelloVersione?: string } = {},
  ): Promise<InferenzaCV[]> => {
    const params: Record<string, string> = {};
    if (opzioni.eventoValidatoId) params.evento_validato_id = opzioni.eventoValidatoId;
    if (opzioni.modelloVersione) params.modello_versione = opzioni.modelloVersione;
    return chiamaApi(
      cliente.get<InferenzaCV[]>(`/partite/${partitaId}/inferenze-cv`, {
        params,
      }),
    );
  },

  /**
   * Lancia il calcolo delle divergenze CV ↔ motore. Persiste i risultati
   * come `DivergenzaInferita` con risoluzione="aperta". Le divergenze
   * preesistenti vengono cancellate.
   */
  calcolaDiscrepanze: (
    partitaId: string,
    modelloVersione?: string,
  ): Promise<RiepilogoDiscrepanze> => {
    const params: Record<string, string> = {};
    if (modelloVersione) params.modello_versione = modelloVersione;
    return chiamaApi(
      cliente.post<RiepilogoDiscrepanze>(
        `/partite/${partitaId}/calcola-discrepanze`,
        null,
        { params },
      ),
    );
  },

  /**
   * Calcola divergenze evento-per-evento (snapshot intermedi del motore).
   * Le inferenze con `evento_validato_id` vengono confrontate con lo
   * stato motore subito DOPO quell'evento. Piu' preciso di
   * `calcolaDiscrepanze` per pipeline CV legate a singoli eventi.
   */
  calcolaDiscrepanzePerEvento: (
    partitaId: string,
    modelloVersione?: string,
  ): Promise<RiepilogoDiscrepanze> => {
    const params: Record<string, string> = {};
    if (modelloVersione) params.modello_versione = modelloVersione;
    return chiamaApi(
      cliente.post<RiepilogoDiscrepanze>(
        `/partite/${partitaId}/calcola-discrepanze-per-evento`,
        null,
        { params },
      ),
    );
  },

  /** Lista divergenze gia' calcolate. */
  listaDiscrepanze: (
    partitaId: string,
    soloAperte = false,
  ): Promise<RiepilogoDiscrepanze> =>
    chiamaApi(
      cliente.get<RiepilogoDiscrepanze>(`/partite/${partitaId}/discrepanze`, {
        params: soloAperte ? { solo_aperte: true } : {},
      }),
    ),

  /** Aggiorna la risoluzione di una divergenza (review umana). */
  aggiornaDivergenza: (
    partitaId: string,
    divergenzaId: string,
    risoluzione: RisoluzioneDivergenza,
    note?: string,
  ): Promise<DivergenzaInferita> =>
    chiamaApi(
      cliente.patch<DivergenzaInferita>(
        `/partite/${partitaId}/discrepanze/${divergenzaId}`,
        { risoluzione, note: note ?? null },
      ),
    ),

  /** Statistiche aggregate sulle divergenze (per dashboard/grafici). */
  statisticheDiscrepanze: (
    partitaId: string,
  ): Promise<StatisticheDiscrepanze> =>
    chiamaApi(
      cliente.get<StatisticheDiscrepanze>(
        `/partite/${partitaId}/discrepanze/statistiche`,
      ),
    ),

  /** Cancella una singola inferenza CV (per pulizia mirata da UI). */
  cancellaInferenza: (
    partitaId: string,
    inferenzaId: string,
  ): Promise<void> =>
    chiamaApi(
      cliente.delete<void>(
        `/partite/${partitaId}/inferenze-cv/${inferenzaId}`,
      ),
    ),

  /**
   * Chiede al backend di suggerire un evento candidato per risolvere
   * una divergenza. Euristica: delta positivo → ARMATE_PIAZZATE,
   * delta negativo → ARMATE_SPOSTATE.
   */
  suggerisciEvento: (
    partitaId: string,
    divergenzaId: string,
  ): Promise<SuggerimentoEvento> =>
    chiamaApi(
      cliente.get<SuggerimentoEvento>(
        `/partite/${partitaId}/discrepanze/${divergenzaId}/suggerisci-evento`,
      ),
    ),

  /**
   * Aggiorna in batch la risoluzione di piu' divergenze che soddisfano
   * i filtri specificati.
   */
  aggiornaDivergenzeBulk: (
    partitaId: string,
    body: AggiornamentoBulkDivergenze,
  ): Promise<RisultatoBulkDivergenze> =>
    chiamaApi(
      cliente.post<RisultatoBulkDivergenze>(
        `/partite/${partitaId}/discrepanze/aggiorna-bulk`,
        body,
      ),
    ),

  /**
   * Valida le inferenze CV (linter semantico): controlla territori
   * inesistenti, colori non assegnati a giocatori, valori fuori range.
   */
  validaInferenze: (
    partitaId: string,
    modelloVersione?: string,
  ): Promise<RisultatoValidazione> => {
    const params: Record<string, string> = {};
    if (modelloVersione) params.modello_versione = modelloVersione;
    return chiamaApi(
      cliente.get<RisultatoValidazione>(
        `/partite/${partitaId}/inferenze-cv/validazione`,
        { params },
      ),
    );
  },

  /** URL completo per scaricare il CSV delle divergenze. */
  urlEsportaCsv: (partitaId: string, soloAperte = false): string => {
    const base = cliente.defaults.baseURL ?? "";
    const params = new URLSearchParams();
    if (soloAperte) params.set("solo_aperte", "true");
    const qs = params.toString();
    return `${base}/partite/${partitaId}/discrepanze/esporta-csv${
      qs ? "?" + qs : ""
    }`;
  },

  /**
   * Pipeline CV completa per UN evento: estrai frame → raddrizza →
   * inferisci → persisti. Richiede calibrazione preventiva.
   */
  analizzaEvento: (
    partitaId: string,
    eventoId: string,
    forzaRaddrizzamento = false,
  ): Promise<InferenzaCV[]> =>
    chiamaApi(
      cliente.post<InferenzaCV[]>(
        `/partite/${partitaId}/eventi/${eventoId}/analizza-cv`,
        null,
        { params: forzaRaddrizzamento ? { forza_raddrizzamento: true } : {} },
      ),
    ),

  /**
   * Pipeline CV per TUTTI gli eventi della partita. Ritorna riepilogo
   * (n_riusciti, n_falliti, n_inferenze_totali, falliti).
   */
  analizzaTuttiEventi: (
    partitaId: string,
    forzaRaddrizzamento = false,
  ): Promise<RiepilogoAnalisiBatch> =>
    chiamaApi(
      cliente.post<RiepilogoAnalisiBatch>(
        `/partite/${partitaId}/analizza-tutti-eventi-cv`,
        null,
        { params: forzaRaddrizzamento ? { forza_raddrizzamento: true } : {} },
      ),
    ),
};

/** Riepilogo del batch analisi-cv. */
export interface RiepilogoAnalisiBatch {
  n_eventi_totali: number;
  n_riusciti: number;
  n_falliti: number;
  n_inferenze_totali: number;
  modello_versione: string;
  falliti: { evento_id: string; errore: string }[];
}

/** Statistiche aggregate sulle divergenze (per dashboard). */
export interface StatisticheDiscrepanze {
  n_totali: number;
  distribuzione_delta: Record<string, number>;
  per_risoluzione: Record<string, number>;
  top_territori: { territorio: string; delta_totale: number }[];
  per_colore: Record<string, number>;
  confidence_media: number;
}

/** Suggerimento di evento candidato per risolvere una divergenza. */
export interface SuggerimentoEvento {
  tipo: string | null;
  dati: Record<string, unknown>;
  commento: string;
  confidence_suggerimento: number;
  divergenza_id?: string;
}

/** Body per aggiornamento bulk delle divergenze. */
export interface AggiornamentoBulkDivergenze {
  risoluzione: RisoluzioneDivergenza;
  note?: string | null;
  delta_minimo?: number | null;
  delta_massimo?: number | null;
  territorio?: string | null;
  colore?: string | null;
  solo_aperte?: boolean;
}

/** Risposta dell'aggiornamento bulk. */
export interface RisultatoBulkDivergenze {
  n_aggiornate: number;
  risoluzione_applicata: string;
}

/** Singolo problema rilevato dal linter inferenze. */
export interface ProblemaInferenza {
  codice: string;
  severita: "error" | "warning";
  inferenza_id: string;
  descrizione: string;
}

/** Risultato della validazione cross-check inferenze. */
export interface RisultatoValidazione {
  n_inferenze: number;
  n_problemi: number;
  n_error: number;
  n_warning: number;
  territori_validi_disponibili: boolean;
  problemi: ProblemaInferenza[];
  troncato: boolean;
}
