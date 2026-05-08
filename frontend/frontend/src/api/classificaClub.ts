/**
 * API client per la classifica del club (aggregazione cross-partita).
 *
 * Endpoint costoso (O(N_partite x N_eventi)) ma ricalcolato a ogni
 * chiamata, niente cache server-side. Per UI: chiamare on-demand
 * (es. apertura pagina) e mostrare loading.
 */

import { chiamaApi, cliente } from "./cliente";

export interface GiocatoreClub {
  nome: string;
  nome_normalizzato: string;
  n_partite: number;
  n_attacchi_totali: number;
  n_difese_totali: number;
  armate_inflitte_attaccando_tot: number;
  armate_perse_attaccando_tot: number;
  armate_inflitte_difendendo_tot: number;
  armate_perse_difendendo_tot: number;
  n_territori_conquistati_tot: number;
  n_carte_pescate_tot: number;
  n_tris_giocati_tot: number;
  n_dadi_lanciati_tot: number;
  media_dadi_globale: number | null;
}

export interface ClassificaClub {
  n_partite_totali: number;
  n_partite_con_eventi: number;
  n_giocatori_distinti: number;
  durata_totale_sec: number;
  n_attacchi_totali: number;
  giocatori: GiocatoreClub[];
}

/** Calcola bilancio armate per un giocatore. Equivalente alla `@property` Python. */
export function bilancioArmate(g: GiocatoreClub): number {
  return (
    g.armate_inflitte_attaccando_tot +
    g.armate_inflitte_difendendo_tot -
    g.armate_perse_attaccando_tot -
    g.armate_perse_difendendo_tot
  );
}

export const apiClassificaClub = {
  ottieni: (): Promise<ClassificaClub> =>
    chiamaApi(cliente.get<ClassificaClub>("/club/classifica")),
};
