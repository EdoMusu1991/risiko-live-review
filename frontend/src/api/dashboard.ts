/**
 * Client per l'endpoint /api/dashboard/sommario.
 *
 * Schema identico alla risposta del backend `app/routers/dashboard.py`.
 */

import { chiamaApi, cliente } from "./cliente";

export interface StatistichePartite {
  n_partite_totali: number;
  n_partite_ultimo_mese: number;
  n_partite_ultima_settimana: number;
  n_eventi_totali: number;
  n_video_totali: number;
  durata_video_totale_sec: number;
}

export interface StatisticheBundle {
  n_bundle_in_attesa: number;
  dimensione_totale_byte: number;
  bundle_piu_vecchio_giorni: number | null;
}

export interface StatisticheSpazio {
  storage_video_byte: number;
  storage_frame_byte: number;
  storage_partite_byte: number;
  totale_byte: number;
}

export interface StatoServizi {
  scheduler_abilitato: boolean;
  scheduler_in_esecuzione: boolean;
  roboflow_configurato: boolean;
}

export interface SommarioDashboard {
  partite: StatistichePartite;
  bundle: StatisticheBundle;
  spazio: StatisticheSpazio;
  servizi: StatoServizi;
  timestamp: string;
}

export const apiDashboard = {
  async sommario(): Promise<SommarioDashboard> {
    return chiamaApi(cliente.get<SommarioDashboard>("/dashboard/sommario"));
  },
};
