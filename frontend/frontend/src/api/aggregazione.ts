/**
 * Funzioni di accesso al dominio Aggregazione: proposte di
 * raggruppamento eventi BLE → attacchi risolti candidati.
 */

import { chiamaApi, cliente } from "./cliente";
import type { EventoValidato } from "../tipi/dominio";

export interface PropostaAggregazioneDadi {
  ts_inizio: string;
  ts_fine: string;
  dadi_attaccante: number[];
  dadi_difensore: number[];
  eventi_grezzi_id: string[];
  confidenza: number;
  note: string[];
}

export interface RisultatoAggregazione {
  n_eventi_grezzi_analizzati: number;
  n_proposte: number;
  proposte: PropostaAggregazioneDadi[];
}

/**
 * Body per accettare una proposta di aggregazione e creare un
 * EventoValidato di tipo `attacco_risolto`.
 *
 * I dadi sono modificabili rispetto alla proposta originale:
 * l'utente può correggere a mano un valore se vede che il sensore
 * BLE ha letto male un dado caduto storto.
 */
export interface AccettaPropostaPayload {
  eventi_grezzi_id: string[];
  giocatore_id: string;
  da: string; // codice territorio attaccante
  a: string; // codice territorio difensore
  dadi_attaccante: number[];
  dadi_difensore: number[];
  ts_evento?: string;
  validato_da?: string;
}

export const apiAggregazione = {
  /**
   * Richiede al backend di proporre aggregazioni di eventi BLE
   * non ancora validati per la partita data.
   *
   * @param partitaId id della partita
   * @param sogliaGapSecondi gap massimo (sec) tra eventi consecutivi
   *                         dello stesso cluster. Default 3s.
   */
  proponi: (
    partitaId: string,
    sogliaGapSecondi?: number,
  ): Promise<RisultatoAggregazione> =>
    chiamaApi(
      cliente.post<RisultatoAggregazione>(
        `/partite/${partitaId}/proponi-aggregazioni-dadi`,
        null,
        sogliaGapSecondi !== undefined
          ? { params: { soglia_gap_secondi: sogliaGapSecondi } }
          : undefined,
      ),
    ),

  /**
   * Accetta una proposta promuovendola a `EventoValidato` di tipo
   * `attacco_risolto`. Marca tutti gli eventi grezzi citati come
   * validati: spariranno dalle proposte successive.
   */
  accetta: (
    partitaId: string,
    payload: AccettaPropostaPayload,
  ): Promise<EventoValidato> =>
    chiamaApi(
      cliente.post<EventoValidato>(
        `/partite/${partitaId}/accetta-aggregazione-dadi`,
        payload,
      ),
    ),
};
