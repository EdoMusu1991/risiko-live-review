/**
 * Funzioni per ricostruzione partita via risiko_engine.
 */

import { chiamaApi, cliente } from "./cliente";
import type { RisultatoRicostruzione } from "@/tipi/dominio";

export const apiRicostruzione = {
  async ricostruisci(partitaId: string): Promise<RisultatoRicostruzione> {
    return chiamaApi(
      cliente.post<RisultatoRicostruzione>(
        `/partite/${partitaId}/ricostruisci`,
      ),
    );
  },

  async statoFinale(partitaId: string): Promise<RisultatoRicostruzione | null> {
    try {
      return await chiamaApi(
        cliente.get<RisultatoRicostruzione>(
          `/partite/${partitaId}/stato-finale`,
        ),
      );
    } catch (errore) {
      // 404 = non ancora ricostruita (caso normale, non un vero errore)
      if (
        errore !== null &&
        typeof errore === "object" &&
        "status" in errore &&
        errore.status === 404
      ) {
        return null;
      }
      throw errore;
    }
  },
};
