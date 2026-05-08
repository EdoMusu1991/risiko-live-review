/**
 * API client per la validazione di coerenza degli eventi di una partita.
 *
 * Diverso dalla ricostruzione: NON applica gli eventi al motore (non
 * crea snapshot), si limita a rilevare problemi di coerenza in un
 * colpo solo. Pensato per essere chiamato prima di "Ricostruisci"
 * per dare all'utente una checklist di problemi da correggere.
 */

import { chiamaApi, cliente } from "./cliente";

export type SeveritaProblema = "errore" | "avviso";

export type CodiceProblema =
  | "attacco_territori_non_adiacenti"
  | "attacco_da_territorio_non_posseduto"
  | "attacco_su_territorio_proprio"
  | "attacco_difensore_inesistente"
  | "doppio_turno_iniziato"
  | "evento_fuori_ordine_temporale"
  | "giocatore_id_inesistente"
  | "territorio_inesistente"
  | "armate_piazzate_su_territorio_altrui"
  | "spostamento_territori_non_adiacenti";

export interface ProblemaCoerenza {
  severita: SeveritaProblema;
  codice: CodiceProblema;
  messaggio: string;
  evento_id: string | null;
  posizione: number | null;
}

export interface RisultatoValidazioneCoerenza {
  n_eventi_analizzati: number;
  n_errori: number;
  n_avvisi: number;
  problemi: ProblemaCoerenza[];
}

export const apiValidazione = {
  /** Verifica problemi di coerenza degli eventi validati. */
  valida: (partitaId: string): Promise<RisultatoValidazioneCoerenza> =>
    chiamaApi(
      cliente.get<RisultatoValidazioneCoerenza>(
        `/partite/${partitaId}/valida-coerenza`,
      ),
    ),
};
