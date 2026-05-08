/**
 * Hook minimale per gestire chiamate API async con stati
 * loading/error/data. Più leggero di TanStack Query, sufficiente per
 * il flusso review (no caching aggressivo richiesto).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ErroreApi } from "@/api";

export interface StatoRichiesta<T> {
  dato: T | null;
  inCaricamento: boolean;
  errore: ErroreApi | Error | null;
  ricarica: () => Promise<void>;
}

export function useRichiestaApi<T>(
  esegui: () => Promise<T>,
  dipendenze: ReadonlyArray<unknown>,
): StatoRichiesta<T> {
  const [dato, setDato] = useState<T | null>(null);
  const [inCaricamento, setInCaricamento] = useState(true);
  const [errore, setErrore] = useState<ErroreApi | Error | null>(null);

  // Manteniamo un ref alla "esegui" più recente, così la funzione di
  // ricarica non ricrea l'effect ad ogni render.
  const eseguiRef = useRef(esegui);
  eseguiRef.current = esegui;

  const ricarica = useCallback(async () => {
    setInCaricamento(true);
    setErrore(null);
    try {
      const risultato = await eseguiRef.current();
      setDato(risultato);
    } catch (e) {
      setErrore(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setInCaricamento(false);
    }
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    ricarica();
  }, dipendenze);

  return { dato, inCaricamento, errore, ricarica };
}
