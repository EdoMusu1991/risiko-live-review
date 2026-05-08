/**
 * API client per le statistiche aggregate di una partita.
 *
 * Le statistiche sono calcolate al volo lato backend dagli
 * `EventoValidato` esistenti. Non sono persistite — ogni chiamata
 * ricalcola.
 */

import { chiamaApi, cliente } from "./cliente";
import type { ColoreGiocatore } from "../tipi/dominio";

export interface StatisticheGiocatore {
  giocatore_id: string;
  nome: string;
  colore: ColoreGiocatore;

  // Attacco
  n_attacchi: number;
  armate_perse_attaccando: number;
  armate_inflitte_attaccando: number;
  n_dadi_lanciati: number;
  media_dadi_lanciati: number | null;

  // Conquista
  n_territori_conquistati: number;

  // Difesa (popolato solo se il motore di gioco riesce a ricostruire)
  n_difese: number;
  armate_perse_difendendo: number;
  armate_inflitte_difendendo: number;

  // Rinforzo
  n_armate_piazzate_totali: number;
  n_tris_giocati: number;
  n_carte_pescate: number;
}

export interface StatistichePartita {
  partita_id: string;
  n_eventi_validati: number;
  durata_sec: number | null;
  n_turni: number;
  n_attacchi_totali: number;
  statistiche_giocatori: StatisticheGiocatore[];
}

export const apiStatistiche = {
  /**
   * Calcola e ritorna le statistiche aggregate della partita.
   *
   * Ogni chiamata ricalcola dagli EventoValidato presenti, quindi
   * dopo aver aggiunto/modificato eventi vale la pena ri-fetchare.
   */
  ottieni: (partitaId: string): Promise<StatistichePartita> =>
    chiamaApi(
      cliente.get<StatistichePartita>(`/partite/${partitaId}/statistiche`),
    ),
};
