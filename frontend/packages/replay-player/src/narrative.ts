/**
 * Generazione di testo italiano descrittivo per ogni evento del bundle,
 * con risoluzione dei nomi giocatori dallo stato corrente.
 *
 * I testi sono brevi (1 frase), pensati per stare in una riga di narrative
 * sotto la mappa. Scope possibile in futuro: i18n vero, font specifici,
 * markup per highlight (territori cliccabili nel narrative ecc.).
 */

import type { EventoValidato } from "@risiko/eventi-schema";
import type { StatoPartita } from "@risiko/replay-lib";

export function narrativeEvento(
  evento: EventoValidato,
  stato: StatoPartita,
): string {
  const nome = (id: string): string =>
    stato.giocatori.get(id)?.nome ?? id;
  const territorio = (slug: string): string =>
    slug.replace(/_/g, " ");

  switch (evento.tipo) {
    case "territorio_assegnato_inizio": {
      const { giocatore_id, territorio: t, n_armate } = evento.dati;
      return `${nome(giocatore_id)} riceve ${territorio(t)} (${n_armate} armate iniziali).`;
    }
    case "obiettivo_assegnato": {
      return `Obiettivo assegnato a ${nome(evento.dati.giocatore_id)}.`;
    }
    case "partita_inizio": {
      return `La partita inizia. Primo turno a ${nome(evento.dati.primo_giocatore_id)}.`;
    }
    case "turno_iniziato": {
      return `Inizia il turno di ${nome(evento.dati.giocatore_id)}.`;
    }
    case "turno_finito": {
      return `${nome(evento.dati.giocatore_id)} chiude il suo turno.`;
    }
    case "armate_piazzate": {
      const { giocatore_id, territorio: t, n } = evento.dati;
      return `${nome(giocatore_id)} piazza ${n} ${n === 1 ? "armata" : "armate"} su ${territorio(t)}.`;
    }
    case "tris_giocato": {
      const { giocatore_id, carte } = evento.dati;
      const simboli = carte.map((c) => c.simbolo).join(" + ");
      return `${nome(giocatore_id)} gioca un tris (${simboli}).`;
    }
    case "attacco_risolto": {
      const { giocatore_id, da, a, dadi_attaccante, dadi_difensore } =
        evento.dati;
      return `${nome(giocatore_id)} attacca da ${territorio(da)} verso ${territorio(a)}: ${dadi_attaccante.join("-")} vs ${dadi_difensore.join("-")}.`;
    }
    case "territorio_conquistato": {
      const { giocatore_id, territorio: t } = evento.dati;
      return `${nome(giocatore_id)} conquista ${territorio(t)}.`;
    }
    case "armate_spostate": {
      const { giocatore_id, da, a, n } = evento.dati;
      return `${nome(giocatore_id)} sposta ${n} ${n === 1 ? "armata" : "armate"} da ${territorio(da)} a ${territorio(a)}.`;
    }
    case "carta_pescata": {
      const { giocatore_id, carta } = evento.dati;
      const desc = carta.territorio
        ? `${territorio(carta.territorio)} (${carta.simbolo})`
        : carta.simbolo;
      return `${nome(giocatore_id)} pesca una carta: ${desc}.`;
    }
    case "partita_fine": {
      return `Partita conclusa. Vince ${nome(evento.dati.vincitore_id)}.`;
    }
  }
}
