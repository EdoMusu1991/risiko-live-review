/**
 * API client per gli endpoint diagnostici del backend.
 *
 * Endpoint corrispondenti: app/routers/diagnostica.py
 */

import { chiamaApi, cliente } from "./cliente";

export interface StatoComponente {
  disponibile: boolean;
  nome: string;
  dettaglio: string | null;
}

export interface StatoPipelineCv {
  ffmpeg: StatoComponente;
  opencv: StatoComponente;
  immagine_riferimento: StatoComponente;
  client_cv: StatoComponente;
  pronto: boolean;
  livello_pronto: "completo" | "parziale" | "non_pronto";
}

export const apiDiagnostica = {
  /** Stato dei prerequisiti della pipeline CV. */
  statoPipelineCv: (): Promise<StatoPipelineCv> =>
    chiamaApi(
      cliente.get<StatoPipelineCv>("/diagnostica/pipeline-cv"),
    ),
};

export interface StatoScheduler {
  abilitato: boolean;
  in_esecuzione: boolean;
  prossima_esecuzione: string | null;
  giorni_cleanup: number;
}

export const apiScheduler = {
  /** Stato dello scheduler in-process (cleanup automatico bundle). */
  async stato(): Promise<StatoScheduler> {
    return chiamaApi(cliente.get<StatoScheduler>("/scheduler"));
  },
};
