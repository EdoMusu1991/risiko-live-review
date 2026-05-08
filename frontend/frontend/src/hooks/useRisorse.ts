/**
 * Cache one-shot per le risorse statiche del motore (territori, obiettivi).
 *
 * Caricamento lazy: si carica al primo uso, poi viene riutilizzato senza
 * chiamare di nuovo l'API. I 42 territori e i 16 obiettivi non cambiano,
 * quindi una cache di sessione è più che sufficiente.
 */

import { useEffect, useState } from "react";
import {
  apiRisorse,
  type ObiettivoInfo,
  type TerritorioInfo,
} from "@/api";

let cacheTerritori: TerritorioInfo[] | null = null;
let promessaTerritori: Promise<TerritorioInfo[]> | null = null;

let cacheObiettivi: ObiettivoInfo[] | null = null;
let promessaObiettivi: Promise<ObiettivoInfo[]> | null = null;

export function useTerritori(): {
  territori: TerritorioInfo[] | null;
  inCaricamento: boolean;
} {
  const [stato, setStato] = useState<{
    dati: TerritorioInfo[] | null;
    inCaricamento: boolean;
  }>(() => ({
    dati: cacheTerritori,
    inCaricamento: cacheTerritori === null,
  }));

  useEffect(() => {
    if (cacheTerritori !== null) return;

    let annullato = false;
    if (!promessaTerritori) {
      promessaTerritori = apiRisorse.territori();
    }
    promessaTerritori
      .then((dati) => {
        cacheTerritori = dati;
        if (!annullato) setStato({ dati, inCaricamento: false });
      })
      .catch(() => {
        promessaTerritori = null;
        if (!annullato) setStato({ dati: null, inCaricamento: false });
      });

    return () => {
      annullato = true;
    };
  }, []);

  return { territori: stato.dati, inCaricamento: stato.inCaricamento };
}

export function useObiettivi(): {
  obiettivi: ObiettivoInfo[] | null;
  inCaricamento: boolean;
} {
  const [stato, setStato] = useState<{
    dati: ObiettivoInfo[] | null;
    inCaricamento: boolean;
  }>(() => ({
    dati: cacheObiettivi,
    inCaricamento: cacheObiettivi === null,
  }));

  useEffect(() => {
    if (cacheObiettivi !== null) return;

    let annullato = false;
    if (!promessaObiettivi) {
      promessaObiettivi = apiRisorse.obiettivi();
    }
    promessaObiettivi
      .then((dati) => {
        cacheObiettivi = dati;
        if (!annullato) setStato({ dati, inCaricamento: false });
      })
      .catch(() => {
        promessaObiettivi = null;
        if (!annullato) setStato({ dati: null, inCaricamento: false });
      });

    return () => {
      annullato = true;
    };
  }, []);

  return { obiettivi: stato.dati, inCaricamento: stato.inCaricamento };
}
