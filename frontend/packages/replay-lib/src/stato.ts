/**
 * Stato della partita durante il replay e funzione pura `applicaEvento`.
 *
 * FILOSOFIA: il replay è un film. La libreria NON valida le regole di gioco —
 * applica solo le conseguenze descritte negli eventi. Se il bundle è incoerente
 * con le regole (es. un attacco con dadi impossibili), la replay-lib produce
 * uno stato anche incoerente. La validazione strutturale è di Zod, quella di
 * regole è del backend RL.
 *
 * UNICA ECCEZIONE: per `attacco_risolto` calcoliamo le perdite dai dadi
 * (regola standard: ordina decrescente, confronta coppie, parità → attaccante
 * perde). È l'unico modo per sapere come aggiornare `n_armate` sui territori.
 * Non è "rivalutare il gameplay": è applicare il significato dichiarato dei
 * dadi tirati.
 */

import type {
  BundleReplay,
  EventoValidato,
  GiocatorePartita,
} from "@risiko/eventi-schema";
import type { DatiCarta } from "@risiko/eventi-schema";

// === Tipi di stato ============================================================

export type ColoreGiocatore = GiocatorePartita["colore"];

export type FasePartita = "setup" | "in_corso" | "finita";

export interface GiocatoreInPartita {
  readonly id: string;
  readonly nome: string;
  readonly colore: ColoreGiocatore;
  readonly ordine_seduta: number;
  obiettivo_id: number | null;
  mano: DatiCarta[];
  eliminato: boolean;
}

export interface StatoTerritorio {
  proprietario_id: string | null;
  n_armate: number;
}

export interface UltimoAttacco {
  da: string;
  a: string;
  giocatore_id: string;
  dadi_attaccante: number[]; // ordinati decrescenti
  dadi_difensore: number[]; // ordinati decrescenti
  perdite_attaccante: number;
  perdite_difensore: number;
}

export interface StatoPartita {
  readonly partita_id: string;
  readonly data_inizio: string;
  data_fine: string | null;
  fase: FasePartita;
  giocatori: Map<string, GiocatoreInPartita>;
  territori: Map<string, StatoTerritorio>;
  giocatore_di_turno: string | null;
  ultimo_attacco: UltimoAttacco | null;
  conquiste_turno_corrente: string[];
  vincitore_id: string | null;
}

// === Errori ===================================================================

export class ErroreReplayCorrotto extends Error {
  constructor(
    messaggio: string,
    public readonly evento?: EventoValidato,
  ) {
    super(messaggio);
    this.name = "ErroreReplayCorrotto";
  }
}

// === Stato iniziale ===========================================================

/**
 * Costruisce uno stato iniziale dal bundle: popola i giocatori, lascia i
 * territori vuoti (verranno popolati da `territorio_assegnato_inizio`).
 *
 * NOTA: lo stato ritornato è "vivo" (Map mutabili). La timeline si occupa di
 * fare snapshot immutabili dove serve. `applicaEvento` non muta lo stato di
 * input.
 */
export function creaStatoInizialeDaBundle(bundle: BundleReplay): StatoPartita {
  const giocatori = new Map<string, GiocatoreInPartita>();
  for (const g of bundle.giocatori) {
    giocatori.set(g.id, {
      id: g.id,
      nome: g.nome,
      colore: g.colore,
      ordine_seduta: g.ordine_seduta,
      obiettivo_id: null,
      mano: [],
      eliminato: false,
    });
  }
  return {
    partita_id: bundle.partita.id,
    data_inizio: bundle.partita.data_inizio,
    data_fine: bundle.partita.data_fine ?? null,
    fase: "setup",
    giocatori,
    territori: new Map(),
    giocatore_di_turno: null,
    ultimo_attacco: null,
    conquiste_turno_corrente: [],
    vincitore_id: null,
  };
}

// === applicaEvento ============================================================

/**
 * Applica un evento allo stato e ritorna un NUOVO stato. Lo stato originale
 * non viene mutato (clone via `structuredClone`).
 *
 * Lancia `ErroreReplayCorrotto` se l'evento referenzia entità non presenti
 * nello stato (giocatore o territorio sconosciuto).
 */
export function applicaEvento(
  stato: StatoPartita,
  evento: EventoValidato,
): StatoPartita {
  const s = clonaStato(stato);

  switch (evento.tipo) {
    // --- Setup ---

    case "territorio_assegnato_inizio": {
      const { territorio, giocatore_id, n_armate } = evento.dati;
      esigiGiocatore(s, giocatore_id, evento);
      s.territori.set(territorio, { proprietario_id: giocatore_id, n_armate });
      return s;
    }

    case "obiettivo_assegnato": {
      const { giocatore_id, obiettivo_id } = evento.dati;
      const g = esigiGiocatore(s, giocatore_id, evento);
      g.obiettivo_id = obiettivo_id;
      return s;
    }

    case "partita_inizio": {
      const { primo_giocatore_id } = evento.dati;
      esigiGiocatore(s, primo_giocatore_id, evento);
      s.fase = "in_corso";
      s.giocatore_di_turno = primo_giocatore_id;
      return s;
    }

    // --- Turno ---

    case "turno_iniziato": {
      const { giocatore_id } = evento.dati;
      esigiGiocatore(s, giocatore_id, evento);
      s.giocatore_di_turno = giocatore_id;
      s.conquiste_turno_corrente = [];
      s.ultimo_attacco = null;
      return s;
    }

    case "turno_finito": {
      // No-op semantico: lasciamo lo stato come è. Il prossimo turno_iniziato
      // (o partita_fine) sposterà giocatore_di_turno.
      return s;
    }

    // --- Rinforzo ---

    case "armate_piazzate": {
      const { giocatore_id, territorio, n } = evento.dati;
      esigiGiocatore(s, giocatore_id, evento);
      const t = esigiTerritorio(s, territorio, evento);
      t.n_armate += n;
      return s;
    }

    case "tris_giocato": {
      const { giocatore_id, carte } = evento.dati;
      const g = esigiGiocatore(s, giocatore_id, evento);
      // Rimuove 3 carte: una corrispondenza per ciascuna delle carte giocate.
      // Match per (territorio, simbolo); per i jolly serve solo simbolo.
      for (const c of carte) {
        const idx = trovaIndiceCarta(g.mano, c);
        if (idx < 0) {
          throw new ErroreReplayCorrotto(
            `Tris: carta non in mano a ${giocatore_id}: ${JSON.stringify(c)}`,
            evento,
          );
        }
        g.mano.splice(idx, 1);
      }
      return s;
    }

    // --- Attacco ---

    case "attacco_risolto": {
      const { giocatore_id, da, a, dadi_attaccante, dadi_difensore } =
        evento.dati;
      esigiGiocatore(s, giocatore_id, evento);
      const tDa = esigiTerritorio(s, da, evento);
      const tA = esigiTerritorio(s, a, evento);

      const dadiAtt = [...dadi_attaccante].sort((x, y) => y - x);
      const dadiDif = [...dadi_difensore].sort((x, y) => y - x);
      const { perdite_att, perdite_dif } = calcolaPerdite(dadiAtt, dadiDif);

      // Clamp difensivo: l'evento è dichiarativo, ma lo stato non ammette
      // n_armate negative.
      tDa.n_armate = Math.max(0, tDa.n_armate - perdite_att);
      tA.n_armate = Math.max(0, tA.n_armate - perdite_dif);

      s.ultimo_attacco = {
        da,
        a,
        giocatore_id,
        dadi_attaccante: dadiAtt,
        dadi_difensore: dadiDif,
        perdite_attaccante: perdite_att,
        perdite_difensore: perdite_dif,
      };
      return s;
    }

    case "territorio_conquistato": {
      const { giocatore_id, territorio } = evento.dati;
      esigiGiocatore(s, giocatore_id, evento);
      const t = esigiTerritorio(s, territorio, evento);
      const proprietarioPrecedente = t.proprietario_id;
      t.proprietario_id = giocatore_id;
      // Tracciamento conquiste del turno (per logica pesca carta).
      s.conquiste_turno_corrente.push(territorio);
      // Eventuale eliminazione del precedente proprietario: vero se non possiede
      // più alcun territorio dopo la conquista.
      if (proprietarioPrecedente && proprietarioPrecedente !== giocatore_id) {
        const restanti = contaTerritori(s, proprietarioPrecedente);
        if (restanti === 0) {
          const eliminato = s.giocatori.get(proprietarioPrecedente);
          if (eliminato) eliminato.eliminato = true;
        }
      }
      return s;
    }

    // --- Spostamento ---

    case "armate_spostate": {
      const { giocatore_id, da, a, n } = evento.dati;
      esigiGiocatore(s, giocatore_id, evento);
      const tDa = esigiTerritorio(s, da, evento);
      const tA = esigiTerritorio(s, a, evento);
      tDa.n_armate = Math.max(0, tDa.n_armate - n);
      tA.n_armate += n;
      return s;
    }

    // --- Pesca ---

    case "carta_pescata": {
      const { giocatore_id, carta } = evento.dati;
      const g = esigiGiocatore(s, giocatore_id, evento);
      g.mano.push(carta);
      return s;
    }

    // --- Fine ---

    case "partita_fine": {
      const { vincitore_id } = evento.dati;
      esigiGiocatore(s, vincitore_id, evento);
      s.fase = "finita";
      s.vincitore_id = vincitore_id;
      s.data_fine = evento.ts_evento;
      return s;
    }
  }
}

// === Helper interni ===========================================================

/**
 * Clona profondamente lo stato. `structuredClone` gestisce nativamente Map.
 * Disponibile in Node 17+ e in tutti i browser moderni.
 */
function clonaStato(stato: StatoPartita): StatoPartita {
  return structuredClone(stato);
}

function esigiGiocatore(
  s: StatoPartita,
  id: string,
  ev: EventoValidato,
): GiocatoreInPartita {
  const g = s.giocatori.get(id);
  if (!g) {
    throw new ErroreReplayCorrotto(
      `Giocatore sconosciuto: "${id}" (evento ${ev.tipo})`,
      ev,
    );
  }
  return g;
}

function esigiTerritorio(
  s: StatoPartita,
  id: string,
  ev: EventoValidato,
): StatoTerritorio {
  const t = s.territori.get(id);
  if (!t) {
    throw new ErroreReplayCorrotto(
      `Territorio sconosciuto: "${id}" (evento ${ev.tipo})`,
      ev,
    );
  }
  return t;
}

function contaTerritori(s: StatoPartita, giocatore_id: string): number {
  let n = 0;
  for (const t of s.territori.values()) {
    if (t.proprietario_id === giocatore_id) n++;
  }
  return n;
}

/**
 * Risoluzione perdite ai dadi (regola standard Risiko, identica EG e torneo):
 * dadi ordinati decrescenti, confronto coppie su `min(att.length, dif.length)`,
 * parità → l'attaccante perde.
 */
export function calcolaPerdite(
  attOrdinati: number[],
  difOrdinati: number[],
): { perdite_att: number; perdite_dif: number } {
  let perdite_att = 0;
  let perdite_dif = 0;
  const coppie = Math.min(attOrdinati.length, difOrdinati.length);
  for (let i = 0; i < coppie; i++) {
    if (attOrdinati[i] > difOrdinati[i]) perdite_dif++;
    else perdite_att++;
  }
  return { perdite_att, perdite_dif };
}

/**
 * Trova l'indice della prima carta in `mano` che corrisponde a `cercata`.
 * Match per (territorio, simbolo): i jolly hanno territorio=null e simbolo=jolly.
 * Ritorna -1 se non trovata.
 */
function trovaIndiceCarta(mano: DatiCarta[], cercata: DatiCarta): number {
  for (let i = 0; i < mano.length; i++) {
    const c = mano[i];
    if (!c) continue;
    if (c.territorio === cercata.territorio && c.simbolo === cercata.simbolo) {
      return i;
    }
  }
  return -1;
}
