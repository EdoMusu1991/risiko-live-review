/**
 * Funzioni di accesso al dominio Partite.
 */

import { chiamaApi, cliente } from "./cliente";
import type {
  PartitaAggiornamento,
  PartitaCreazione,
  PartitaDettaglio,
  PartitaSommario,
  StatoReview,
} from "@/tipi/dominio";

export interface ParametriListaPartite {
  offset?: number;
  limite?: number;
  stato?: StatoReview;
}

export const apiPartite = {
  async lista(
    parametri: ParametriListaPartite = {},
  ): Promise<PartitaSommario[]> {
    return chiamaApi(
      cliente.get<PartitaSommario[]>("/partite", { params: parametri }),
    );
  },

  async crea(dati: PartitaCreazione): Promise<PartitaDettaglio> {
    return chiamaApi(cliente.post<PartitaDettaglio>("/partite", dati));
  },

  async dettaglio(id: string): Promise<PartitaDettaglio> {
    return chiamaApi(cliente.get<PartitaDettaglio>(`/partite/${id}`));
  },

  async aggiorna(
    id: string,
    dati: PartitaAggiornamento,
  ): Promise<PartitaDettaglio> {
    return chiamaApi(cliente.patch<PartitaDettaglio>(`/partite/${id}`, dati));
  },

  async elimina(id: string): Promise<void> {
    await chiamaApi(cliente.delete<void>(`/partite/${id}`));
  },

  async setupAutomatico(
    id: string,
    parametri: SetupAutomaticoRichiesta = {},
  ): Promise<SetupAutomaticoRisposta> {
    return chiamaApi(
      cliente.post<SetupAutomaticoRisposta>(
        `/partite/${id}/setup-automatico`,
        parametri,
      ),
    );
  },
};

export interface SetupAutomaticoRichiesta {
  primo_giocatore_id?: string | null;
  seed?: number | null;
}

export interface SetupAutomaticoRisposta {
  n_territori_assegnati: number;
  n_obiettivi_assegnati: number;
  primo_giocatore_id: string;
  armate_per_giocatore: number;
  seed_usato: number;
}
