/**
 * Client HTTP centralizzato per il backend FastAPI.
 *
 * In sviluppo le chiamate a `/api/...` passano per il proxy Vite
 * (configurato in `vite.config.ts`) verso `localhost:8000`.
 */

import axios, { AxiosError } from "axios";

export const cliente = axios.create({
  baseURL: "/api",
  timeout: 30_000,
  headers: {
    "Content-Type": "application/json",
  },
});

/**
 * Errore HTTP con il messaggio del backend già estratto.
 *
 * Il backend restituisce errori in formato `{ detail: string }`.
 * Questa classe normalizza l'accesso al messaggio.
 */
export class ErroreApi extends Error {
  constructor(
    public readonly status: number,
    public readonly dettaglio: string,
    public readonly causa?: AxiosError,
  ) {
    super(dettaglio);
    this.name = "ErroreApi";
  }
}

/**
 * Wrapper che converte ogni AxiosError in `ErroreApi` con messaggio
 * leggibile per l'utente.
 */
export async function chiamaApi<T>(
  promessa: Promise<{ data: T }>,
): Promise<T> {
  try {
    const risposta = await promessa;
    return risposta.data;
  } catch (errore) {
    if (errore instanceof AxiosError) {
      const status = errore.response?.status ?? 0;
      const dettaglio =
        errore.response?.data?.detail ??
        errore.response?.statusText ??
        errore.message ??
        "Errore di rete";
      throw new ErroreApi(
        status,
        typeof dettaglio === "string" ? dettaglio : JSON.stringify(dettaglio),
        errore,
      );
    }
    throw errore;
  }
}
