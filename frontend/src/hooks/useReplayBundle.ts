/**
 * Hook che carica e valida il bundle replay di una partita.
 *
 * Workflow:
 * 1. Fetcha `/api/partite/{id}/esporta?formato=replay`
 * 2. Parsa la risposta con `parsaBundleReplay` di `@risiko/eventi-schema`
 * 3. Espone `{ bundle, caricamento, errore, ricarica }`
 *
 * La validazione zod runtime cattura drift backend↔frontend: se domani
 * il backend cambia un campo o lo schema, il frontend lo segnala
 * esplicitamente invece di crashare con `undefined` silenzioso.
 *
 * Uso tipico:
 *   const { bundle, caricamento, errore } = useReplayBundle(partitaId);
 *   if (bundle) <RisikoReplayPlayer bundle={bundle} />;
 */

import { useCallback, useEffect, useState } from "react";

import {
  ErroreParsingEventi,
  parsaBundleReplay,
  type BundleReplay,
} from "@risiko/eventi-schema";

import { apiEsportazione } from "@/api";

interface StatoUseReplayBundle {
  bundle: BundleReplay | null;
  caricamento: boolean;
  errore: string | null;
  /** Ricarica forzata (es. dopo aver accettato nuovi eventi). */
  ricarica: () => void;
}

export function useReplayBundle(
  partitaId: string | null,
): StatoUseReplayBundle {
  const [bundle, setBundle] = useState<BundleReplay | null>(null);
  const [caricamento, setCaricamento] = useState(false);
  const [errore, setErrore] = useState<string | null>(null);
  const [contatore, setContatore] = useState(0);

  const ricarica = useCallback(() => {
    setContatore((n) => n + 1);
  }, []);

  useEffect(() => {
    if (partitaId === null) {
      setBundle(null);
      setCaricamento(false);
      setErrore(null);
      return;
    }

    let attivo = true;
    setCaricamento(true);
    setErrore(null);

    fetch(apiEsportazione.urlReplay(partitaId))
      .then(async (resposta) => {
        if (!resposta.ok) {
          throw new Error(
            `Errore ${resposta.status}: ${resposta.statusText}`,
          );
        }
        return resposta.json();
      })
      .then((raw: unknown) => {
        if (!attivo) return;
        // Validazione runtime con zod
        const valido = parsaBundleReplay(raw);
        setBundle(valido);
      })
      .catch((e: unknown) => {
        if (!attivo) return;
        if (e instanceof ErroreParsingEventi) {
          // Schema drift: backend ha emesso qualcosa che zod rifiuta.
          // Mostro i primi dettagli per debug.
          const primoDettaglio = e.dettagli[0];
          const percorso = primoDettaglio
            ? primoDettaglio.percorso.join(".")
            : "?";
          setErrore(
            `Bundle replay non conforme allo schema (${percorso}: ${
              primoDettaglio?.messaggio ?? "n/a"
            }). Possibile drift backend/frontend.`,
          );
        } else if (e instanceof Error) {
          setErrore(e.message);
        } else {
          setErrore("Errore sconosciuto durante il caricamento del bundle replay");
        }
      })
      .finally(() => {
        if (attivo) setCaricamento(false);
      });

    return () => {
      attivo = false;
    };
  }, [partitaId, contatore]);

  return { bundle, caricamento, errore, ricarica };
}
