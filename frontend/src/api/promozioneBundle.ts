/**
 * Funzioni di accesso al dominio "promozione bundle".
 *
 * Endpoint backend (v0.29):
 * - GET  /api/partite/bundle-disponibili   → lista bundle in storage_partite/
 * - POST /api/partite/da-bundle/{id}       → crea Partita SQL da un bundle
 */

import { chiamaApi, cliente } from "./cliente";

export interface BundleDisponibile {
  id_partita: string;
  ts_inizio: string;
  ts_fine: string;
  n_segmenti: number;
  n_eventi_dichiarati: number;
}

export interface RispostaListaBundle {
  bundle: BundleDisponibile[];
}

export interface RichiestaPromozioneBundle {
  luogo?: string | null;
  note_extra?: string | null;
}

export interface RispostaPromozioneBundle {
  id_partita: string;
  n_video: number;
  n_eventi_importati: number;
  n_eventi_scartati: number;
  avvisi: string[];
}

export const apiPromozioneBundle = {
  async lista(): Promise<RispostaListaBundle> {
    return chiamaApi(
      cliente.get<RispostaListaBundle>("/partite/bundle-disponibili"),
    );
  },

  async promuovi(
    idPartita: string,
    richiesta: RichiestaPromozioneBundle = {},
  ): Promise<RispostaPromozioneBundle> {
    return chiamaApi(
      cliente.post<RispostaPromozioneBundle>(
        `/partite/da-bundle/${idPartita}`,
        richiesta,
      ),
    );
  },

  async scarta(idPartita: string): Promise<void> {
    await chiamaApi(cliente.delete(`/partite/bundle/${idPartita}`));
  },

  async cleanupVecchi(
    olderThanDays: number,
  ): Promise<{ n_cancellati: number; ids_cancellati: string[] }> {
    return chiamaApi(
      cliente.delete<{ n_cancellati: number; ids_cancellati: string[] }>(
        `/partite/bundle?older_than_days=${olderThanDays}`,
      ),
    );
  },
};
