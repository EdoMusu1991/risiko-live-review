/**
 * Client API per il setup automatico di una partita.
 *
 * Genera in transazione tutti gli eventi di setup (42 territori, N
 * obiettivi, partita_inizio) applicando le regole Risiko EG.
 */

import { chiamaApi, cliente } from "./cliente";

export interface SetupAutomaticoRichiesta {
  /** Chi inizia. Default backend: giocatore con ordine_seduta=1. */
  primo_giocatore_id?: string | null;
  /** Seed per riproducibilità. Default: random. */
  seed?: number | null;
}

export interface SetupAutomaticoRisposta {
  n_territori_assegnati: number;
  n_obiettivi_assegnati: number;
  primo_giocatore_id: string;
  armate_per_giocatore: number;
  seed_usato: number;
}

export const apiSetupAutomatico = {
  async esegui(
    partitaId: string,
    parametri: SetupAutomaticoRichiesta = {},
  ): Promise<SetupAutomaticoRisposta> {
    return chiamaApi(
      cliente.post<SetupAutomaticoRisposta>(
        `/partite/${partitaId}/setup-automatico`,
        parametri,
      ),
    );
  },
};
