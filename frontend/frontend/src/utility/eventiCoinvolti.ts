/**
 * Utility per analizzare gli eventi e capire quali territori coinvolgono.
 *
 * Usata per:
 * - Filtrare la lista eventi per un territorio selezionato sulla mappa.
 * - Evidenziare sulla mappa i territori coinvolti dall'evento corrente
 *   sotto al cursore.
 *
 * Lo schema dei `dati` di ogni evento è documentato nel motore Python.
 * Qui leggiamo difensivamente i campi noti, ignorando il resto.
 */

import type { EventoGrezzo, EventoValidato } from "@/tipi/dominio";

interface DatiEventoLetti {
  territori: ReadonlySet<string>;
  giocatori: ReadonlySet<string>;
}

/** Ritorna i territori e giocatori coinvolti dall'evento. */
export function leggiCoinvolti(
  evento: EventoValidato | EventoGrezzo,
): DatiEventoLetti {
  const territori = new Set<string>();
  const giocatori = new Set<string>();
  const d = evento.dati;

  // Territori singoli
  if (typeof d.territorio === "string") territori.add(d.territorio);
  if (typeof d.da === "string") territori.add(d.da);
  if (typeof d.a === "string") territori.add(d.a);

  // Tris: array di carte con territorio (può essere null per i jolly)
  if (Array.isArray(d.carte)) {
    for (const c of d.carte) {
      if (
        c !== null &&
        typeof c === "object" &&
        "territorio" in c &&
        typeof c.territorio === "string"
      ) {
        territori.add(c.territorio);
      }
    }
  }

  // Giocatori
  if (typeof d.giocatore_id === "string") giocatori.add(d.giocatore_id);
  if (typeof d.primo_giocatore_id === "string") {
    giocatori.add(d.primo_giocatore_id);
  }
  if (typeof d.vincitore_id === "string") giocatori.add(d.vincitore_id);

  return { territori, giocatori };
}

/** True se l'evento riguarda il territorio specificato. */
export function eventoCoinvolgeTerritorio(
  evento: EventoValidato | EventoGrezzo,
  slugTerritorio: string,
): boolean {
  return leggiCoinvolti(evento).territori.has(slugTerritorio);
}

/** True se l'evento riguarda il giocatore specificato. */
export function eventoCoinvolgeGiocatore(
  evento: EventoValidato | EventoGrezzo,
  giocatoreId: string,
): boolean {
  return leggiCoinvolti(evento).giocatori.has(giocatoreId);
}
