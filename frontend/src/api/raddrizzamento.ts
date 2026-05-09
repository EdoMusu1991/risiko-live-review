/**
 * API client per gli endpoint di raddrizzamento prospettico.
 *
 * Endpoint corrispondenti backend: app/routers/raddrizzamento.py + frame.py
 */

import { chiamaApi, cliente } from "./cliente";

export interface StatoRaddrizzamento {
  calibrata: boolean;
  matrice: number[][] | null;
}

export interface RisultatoCalibrazione {
  calibrata: boolean;
  matrice: number[][];
}

export interface RiepilogoBatchRaddrizza {
  n_eventi_totali: number;
  n_riusciti: number;
  n_falliti: number;
  falliti: { evento_id: string; errore: string }[];
}

export const apiRaddrizzamento = {
  /** Stato corrente della calibrazione di raddrizzamento per la partita. */
  stato: (partitaId: string): Promise<StatoRaddrizzamento> =>
    chiamaApi(
      cliente.get<StatoRaddrizzamento>(
        `/partite/${partitaId}/stato-raddrizzamento`,
      ),
    ),

  /**
   * Calibra il raddrizzamento. Usa il frame dell'evento specificato,
   * oppure un offset arbitrario in secondi.
   */
  calibra: (
    partitaId: string,
    opzioni: {
      eventoIdCalibrazione?: string;
      offsetSecCalibrazione?: number;
      forza?: boolean;
    } = {},
  ): Promise<RisultatoCalibrazione> => {
    const params: Record<string, string | number | boolean> = {};
    if (opzioni.eventoIdCalibrazione) {
      params.evento_id_calibrazione = opzioni.eventoIdCalibrazione;
    }
    if (opzioni.offsetSecCalibrazione !== undefined) {
      params.offset_sec_calibrazione = opzioni.offsetSecCalibrazione;
    }
    if (opzioni.forza) params.forza = true;
    return chiamaApi(
      cliente.post<RisultatoCalibrazione>(
        `/partite/${partitaId}/calibra-raddrizzamento`,
        null,
        { params },
      ),
    );
  },

  /** Cancella la calibrazione (forzera' ricalibrazione alla prossima richiesta). */
  cancellaCalibrazione: (partitaId: string): Promise<void> =>
    chiamaApi(
      cliente.delete<void>(
        `/partite/${partitaId}/calibrazione-raddrizzamento`,
      ),
    ),

  /**
   * Pre-popola la cache raddrizzando in batch tutti i frame degli
   * eventi validati della partita.
   */
  raddrizzaTuttiEventi: (
    partitaId: string,
    forza = false,
  ): Promise<RiepilogoBatchRaddrizza> =>
    chiamaApi(
      cliente.post<RiepilogoBatchRaddrizza>(
        `/partite/${partitaId}/raddrizza-tutti-eventi-validati`,
        null,
        { params: forza ? { forza: true } : {} },
      ),
    ),

  /** URL completo del frame raw a un offset arbitrario (per <img src=...>). */
  urlFrameOffset: (
    partitaId: string,
    offsetSec: number,
    chiave: string,
  ): string => {
    const base = cliente.defaults.baseURL ?? "";
    const params = new URLSearchParams({
      offset_sec: String(offsetSec),
      chiave,
    });
    return `${base}/partite/${partitaId}/frame?${params.toString()}`;
  },

  /** URL del frame raw al timestamp di un evento. */
  urlFramePerEvento: (partitaId: string, eventoId: string): string => {
    const base = cliente.defaults.baseURL ?? "";
    return `${base}/partite/${partitaId}/eventi/${eventoId}/frame`;
  },

  /** URL del frame RADDRIZZATO al timestamp di un evento. */
  urlFrameRaddrizzatoPerEvento: (
    partitaId: string,
    eventoId: string,
  ): string => {
    const base = cliente.defaults.baseURL ?? "";
    return `${base}/partite/${partitaId}/eventi/${eventoId}/frame-raddrizzato`;
  },
};
