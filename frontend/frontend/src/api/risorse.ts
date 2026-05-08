/**
 * Client API per le risorse statiche del motore Risiko.
 *
 * Cache-friendly lato client: i 42 territori e i 16 obiettivi non
 * cambiano mai. Idealmente caricati una volta sola per sessione.
 */

import { chiamaApi, cliente } from "./cliente";

export interface TerritorioInfo {
  nome: string;
  continente: string;
  adiacenti: string[];
}

export interface ObiettivoInfo {
  id: number;
  nome: string;
  immagine: string;
  territori_richiesti: string[];
}

export const apiRisorse = {
  async territori(): Promise<TerritorioInfo[]> {
    return chiamaApi(cliente.get<TerritorioInfo[]>("/risorse/territori"));
  },

  async obiettivi(): Promise<ObiettivoInfo[]> {
    return chiamaApi(cliente.get<ObiettivoInfo[]>("/risorse/obiettivi"));
  },
};
