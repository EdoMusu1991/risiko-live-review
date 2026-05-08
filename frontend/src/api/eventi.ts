/**
 * Funzioni di accesso al dominio Eventi (grezzi e validati).
 */

import { chiamaApi, cliente } from "./cliente";
import type {
  EventoGrezzo,
  EventoGrezzoAggiornamento,
  EventoGrezzoCreazione,
  EventoValidato,
  EventoValidatoAggiornamento,
  EventoValidatoCreazione,
} from "@/tipi/dominio";

export const apiEventi = {
  // === Eventi grezzi ===

  async listaGrezzi(
    partitaId: string,
    soloNonValidati = false,
  ): Promise<EventoGrezzo[]> {
    return chiamaApi(
      cliente.get<EventoGrezzo[]>(
        `/partite/${partitaId}/eventi-grezzi`,
        { params: { solo_non_validati: soloNonValidati } },
      ),
    );
  },

  async aggiungiGrezzo(
    partitaId: string,
    dati: EventoGrezzoCreazione,
  ): Promise<EventoGrezzo> {
    return chiamaApi(
      cliente.post<EventoGrezzo>(
        `/partite/${partitaId}/eventi-grezzi`,
        dati,
      ),
    );
  },

  async aggiungiGrezziBatch(
    partitaId: string,
    eventi: EventoGrezzoCreazione[],
  ): Promise<EventoGrezzo[]> {
    return chiamaApi(
      cliente.post<EventoGrezzo[]>(
        `/partite/${partitaId}/eventi-grezzi/batch`,
        { eventi },
      ),
    );
  },

  async aggiornaGrezzo(
    partitaId: string,
    eventoId: string,
    dati: EventoGrezzoAggiornamento,
  ): Promise<EventoGrezzo> {
    return chiamaApi(
      cliente.patch<EventoGrezzo>(
        `/partite/${partitaId}/eventi-grezzi/${eventoId}`,
        dati,
      ),
    );
  },

  async eliminaGrezzo(partitaId: string, eventoId: string): Promise<void> {
    await chiamaApi(
      cliente.delete<void>(`/partite/${partitaId}/eventi-grezzi/${eventoId}`),
    );
  },

  /**
   * Elimina N eventi grezzi atomicamente. Usato dal flusso "rifiuta
   * proposta" per scartare tutti i dadi BLE di un cluster in un colpo
   * solo invece di N delete sequenziali.
   *
   * Ritorna il numero effettivamente cancellati (può essere < di
   * `eventoIds.length` se alcuni ID non esistevano).
   */
  async eliminaGrezziBatch(
    partitaId: string,
    eventoIds: string[],
  ): Promise<number> {
    const risultato = await chiamaApi(
      cliente.post<{ n_eliminati: number }>(
        `/partite/${partitaId}/eventi-grezzi/elimina-batch`,
        { evento_ids: eventoIds },
      ),
    );
    return risultato.n_eliminati;
  },

  // === Eventi validati ===

  async listaValidati(partitaId: string): Promise<EventoValidato[]> {
    return chiamaApi(
      cliente.get<EventoValidato[]>(`/partite/${partitaId}/eventi-validati`),
    );
  },

  async creaValidato(
    partitaId: string,
    dati: EventoValidatoCreazione,
  ): Promise<EventoValidato> {
    return chiamaApi(
      cliente.post<EventoValidato>(
        `/partite/${partitaId}/eventi-validati`,
        dati,
      ),
    );
  },

  async aggiornaValidato(
    partitaId: string,
    eventoId: string,
    dati: EventoValidatoAggiornamento,
  ): Promise<EventoValidato> {
    return chiamaApi(
      cliente.patch<EventoValidato>(
        `/partite/${partitaId}/eventi-validati/${eventoId}`,
        dati,
      ),
    );
  },

  async eliminaValidato(partitaId: string, eventoId: string): Promise<void> {
    await chiamaApi(
      cliente.delete<void>(
        `/partite/${partitaId}/eventi-validati/${eventoId}`,
      ),
    );
  },
};
