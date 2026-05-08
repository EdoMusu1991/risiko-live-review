/**
 * Adapter dal formato replay legacy di Battle Commander al BundleReplay
 * canonico.
 *
 * LIMITAZIONI (lossy by design):
 *   - I dadi degli attacchi non sono salvati nel formato BC: ne sintetizziamo
 *     di plausibili che producono le perdite dichiarate.
 *   - Le carte di un tris non sono salvate: ne emettiamo 3 fittizie coerenti
 *     col `kind` (uguali/diversi) se disponibile, altrimenti 3 fanti.
 *   - La carta pescata non è salvata: ne emettiamo una fittizia `jolly`.
 *   - Il piazzamento rinforzi è aggregato (`total`), non per-territorio:
 *     emettiamo un singolo `armate_piazzate` su un territorio del giocatore.
 *   - Spostamento post-conquista non tracciato: lo omettiamo.
 *   - Obiettivi: BC salva solo description testuali. Emettiamo
 *     `obiettivo_assegnato` con id 1..16 ciclato (placeholder, non semantico).
 *
 * Il bundle prodotto è MARCATO via `partita.note` con il prefisso
 * `[bc-legacy]`. L'importatore lo riconosce e mostra un avviso al consumer.
 *
 * Per i replay GENERATI dopo la migrazione del recorder BC (fase 2 del
 * refactor), questo adapter andrà sostituito da uno fedele.
 */

import type {
  BundleReplay,
  EventoValidato,
  GiocatorePartita,
} from "@risiko/eventi-schema";
import type { DatiCarta } from "@risiko/eventi-schema";

// === Tipi del formato BC legacy ============================================

/** Evento generico nel formato BC: discriminator è il campo `k`. */
type EventoBcLegacy =
  | {
      k: "attack";
      from?: string;
      to?: string;
      f?: number;
      t?: number;
      attackerIdx: number;
      defenderIdx: number;
      conquered: boolean;
      atkLoss: number;
      defLoss: number;
    }
  | {
      k: "tris";
      playerIdx: number;
      bonus: number;
      kind?: "uguali" | "diversi";
      base?: number;
      bonusTerritori?: number;
    }
  | { k: "card"; playerIdx: number }
  | { k: "reinforce"; playerIdx: number; total: number }
  | {
      k: "move";
      from?: string;
      to?: string;
      f?: number;
      t?: number;
      armies: number;
    };

/** Singolo turno nel formato BC. */
interface TurnoBcLegacy {
  turn: number;
  currentPlayer: number;
  territoriesFlat: number[];
  events: EventoBcLegacy[];
  isFinal?: boolean;
}

/** Player nel formato BC: l'identità è l'INDICE nell'array. */
interface PlayerBcLegacy {
  name: string;
  color: string;
  type: "human" | "ai" | string;
}

/** Replay BC legacy completo (output di `replay/replay.js`). */
export interface ReplayBcLegacy {
  version: number;
  startedAt: number;
  endedAt: number | null;
  players: PlayerBcLegacy[];
  missions: string[];
  turns: TurnoBcLegacy[];
  winnerIdx: number | null;
  winnerReason: "mission" | "domination" | string | null;
}

// === Configurazione adapter ================================================

export interface OpzioniAdapter {
  /**
   * ID stabile della partita. Se non passato, generiamo da startedAt.
   * Quando l'adapter viene usato in produzione, il chiamante dovrebbe
   * passare un id già calcolato (es. cuid del Game lato server).
   */
  partita_id?: string;
  /**
   * Lista degli id territori nell'ordine di `territoriesFlat`. Necessaria
   * per espandere i `f`/`t` numerici negli eventi e per emettere
   * `territorio_assegnato_inizio`.
   *
   * Convenzione: ordine identico a `TERRITORIES` di BC. Il chiamante
   * (App.jsx, ReplayScreen) lo passa esplicitamente.
   */
  ordineTerritori: ReadonlyArray<string>;
}

// === Mapping giocatori =====================================================

/**
 * Colori assegnati per ordine di seduta (ignoriamo i colori BC esadecimali:
 * lo schema RL ha un enum chiuso e qui scegliamo deterministicamente).
 */
const COLORI_PER_ORDINE: ReadonlyArray<GiocatorePartita["colore"]> = [
  "rosso",
  "blu",
  "verde",
  "giallo",
  "nero",
  "viola",
];

function idDaIdx(idx: number): string {
  return `p${idx}`;
}

// === Conversione principale ================================================

/**
 * Converte un replay BC legacy in BundleReplay validato.
 */
export function adattaReplayBc(
  legacy: ReplayBcLegacy,
  opzioni: OpzioniAdapter,
): BundleReplay {
  const { ordineTerritori } = opzioni;
  if (legacy.players.length === 0) {
    throw new Error("adattaReplayBc: replay senza giocatori");
  }
  if (legacy.turns.length === 0) {
    throw new Error("adattaReplayBc: replay senza turni");
  }

  const giocatori: GiocatorePartita[] = legacy.players.map((p, i) => ({
    id: idDaIdx(i),
    nome: p.name,
    // L'enum non ha "Arancio"/"Rosa" di BC: assegniamo per ordine.
    colore: COLORI_PER_ORDINE[i] ?? "nero",
    ordine_seduta: i + 1,
  }));

  const partita_id =
    opzioni.partita_id ?? `bc-${legacy.startedAt}`;

  const eventi = generaEventi(legacy, ordineTerritori, giocatori);

  return {
    schema_version: "1.0",
    partita: {
      id: partita_id,
      data_inizio: msAIso(legacy.startedAt),
      data_fine: legacy.endedAt ? msAIso(legacy.endedAt) : null,
      luogo: null,
      note: "[bc-legacy] Replay convertito da formato Battle Commander v1: dadi attacco, carte di tris, carte pescate e distribuzione rinforzi sono ricostruiti.",
    },
    giocatori,
    eventi,
  };
}

// === Generazione eventi ====================================================

function generaEventi(
  legacy: ReplayBcLegacy,
  ordineTerritori: ReadonlyArray<string>,
  giocatori: ReadonlyArray<GiocatorePartita>,
): EventoValidato[] {
  const out: EventoValidato[] = [];
  const startMs = legacy.startedAt;
  let stepMs = 0;
  const tsProssimo = (): string => {
    stepMs += 1000;
    return msAIso(startMs + stepMs);
  };
  let idCounter = 0;
  const idProssimo = (): string => `bc-legacy-${idCounter++}`;

  // --- Setup iniziale: territorio_assegnato_inizio dal primo snapshot ---
  const primoTurno = legacy.turns[0];
  if (!primoTurno) {
    throw new Error("adattaReplayBc: turno iniziale mancante");
  }
  const flat = primoTurno.territoriesFlat;
  for (let i = 0; i < ordineTerritori.length; i++) {
    const owner = flat[i * 2];
    const armies = flat[i * 2 + 1];
    const nome = ordineTerritori[i];
    if (owner === undefined || armies === undefined || !nome) continue;
    if (owner < 0 || armies < 1) continue; // territorio non assegnato
    out.push({
      id: idProssimo(),
      ts_evento: tsProssimo(),
      tipo: "territorio_assegnato_inizio",
      dati: {
        territorio: nome,
        giocatore_id: idDaIdx(owner),
        n_armate: armies,
      },
    });
  }

  // --- Obiettivi (placeholder ciclico, BC salva solo description) ---
  for (let i = 0; i < giocatori.length; i++) {
    const g = giocatori[i];
    if (!g) continue;
    out.push({
      id: idProssimo(),
      ts_evento: tsProssimo(),
      tipo: "obiettivo_assegnato",
      dati: {
        giocatore_id: g.id,
        obiettivo_id: ((i % 16) + 1) as number,
      },
    });
  }

  // --- partita_inizio ---
  out.push({
    id: idProssimo(),
    ts_evento: tsProssimo(),
    tipo: "partita_inizio",
    dati: { primo_giocatore_id: idDaIdx(primoTurno.currentPlayer) },
  });

  // --- Turni: per ciascun turno non-finale emetto turno_iniziato + eventi + turno_finito ---
  for (let ti = 0; ti < legacy.turns.length; ti++) {
    const turno = legacy.turns[ti];
    if (!turno) continue;
    if (turno.isFinal) continue; // turno finale è solo snapshot, niente eventi

    const giocatore_id = idDaIdx(turno.currentPlayer);

    out.push({
      id: idProssimo(),
      ts_evento: tsProssimo(),
      tipo: "turno_iniziato",
      dati: { giocatore_id },
    });

    for (const ev of turno.events) {
      espandiEvento(ev, ordineTerritori, idProssimo, tsProssimo).forEach((e) =>
        out.push(e),
      );
    }

    out.push({
      id: idProssimo(),
      ts_evento: tsProssimo(),
      tipo: "turno_finito",
      dati: { giocatore_id },
    });
  }

  // --- partita_fine ---
  if (
    typeof legacy.winnerIdx === "number" &&
    legacy.winnerIdx >= 0 &&
    legacy.winnerIdx < legacy.players.length
  ) {
    out.push({
      id: idProssimo(),
      ts_evento: tsProssimo(),
      tipo: "partita_fine",
      dati: { vincitore_id: idDaIdx(legacy.winnerIdx) },
    });
  }

  return out;
}

// === Espansione singolo evento BC → 1+ eventi RL ===========================

function espandiEvento(
  ev: EventoBcLegacy,
  ordineTerritori: ReadonlyArray<string>,
  idProssimo: () => string,
  tsProssimo: () => string,
): EventoValidato[] {
  switch (ev.k) {
    case "attack": {
      const da = idTerritorio(ev, "from", "f", ordineTerritori);
      const a = idTerritorio(ev, "to", "t", ordineTerritori);
      if (!da || !a) return []; // dati incompleti, salto
      const dadi = sintetizzaDadi(ev.atkLoss, ev.defLoss);
      const eventi: EventoValidato[] = [
        {
          id: idProssimo(),
          ts_evento: tsProssimo(),
          tipo: "attacco_risolto",
          dati: {
            giocatore_id: idDaIdx(ev.attackerIdx),
            da,
            a,
            dadi_attaccante: dadi.att,
            dadi_difensore: dadi.dif,
          },
        },
      ];
      if (ev.conquered) {
        eventi.push({
          id: idProssimo(),
          ts_evento: tsProssimo(),
          tipo: "territorio_conquistato",
          dati: {
            giocatore_id: idDaIdx(ev.attackerIdx),
            territorio: a,
          },
        });
      }
      return eventi;
    }

    case "tris": {
      const carte = sintetizzaTris(ev.kind);
      // Per coerenza con applicaEvento: emetto 3 carta_pescata fittizie
      // immediatamente prima del tris, in modo che le carte siano "in mano"
      // al giocatore. È un altro pezzo di lossy: il replay legacy non sa
      // né quando né cosa il giocatore ha pescato.
      const eventiTris: EventoValidato[] = [];
      for (const c of carte) {
        eventiTris.push({
          id: idProssimo(),
          ts_evento: tsProssimo(),
          tipo: "carta_pescata",
          dati: {
            giocatore_id: idDaIdx(ev.playerIdx),
            carta: c,
          },
        });
      }
      eventiTris.push({
        id: idProssimo(),
        ts_evento: tsProssimo(),
        tipo: "tris_giocato",
        dati: {
          giocatore_id: idDaIdx(ev.playerIdx),
          carte,
        },
      });
      return eventiTris;
    }

    case "card": {
      return [
        {
          id: idProssimo(),
          ts_evento: tsProssimo(),
          tipo: "carta_pescata",
          dati: {
            giocatore_id: idDaIdx(ev.playerIdx),
            carta: { territorio: null, simbolo: "jolly" },
          },
        },
      ];
    }

    case "reinforce": {
      // Emetto un singolo armate_piazzate con territorio fittizio.
      // Il consumer vede il totale corretto, ma non sa la distribuzione.
      // Uso il primo territorio dell'ordine come placeholder: la sostituzione
      // semantica è impossibile senza informazioni aggiuntive.
      const placeholder = ordineTerritori[0];
      if (!placeholder) return [];
      return [
        {
          id: idProssimo(),
          ts_evento: tsProssimo(),
          tipo: "armate_piazzate",
          dati: {
            giocatore_id: idDaIdx(ev.playerIdx),
            territorio: placeholder,
            n: ev.total,
          },
        },
      ];
    }

    case "move": {
      const da = idTerritorio(ev, "from", "f", ordineTerritori);
      const a = idTerritorio(ev, "to", "t", ordineTerritori);
      if (!da || !a) return [];
      // BC non sa il giocatore_id del move: lo deduciamo dal contesto?
      // No — non possiamo qui (single-event). Useremo l'attaccante più
      // recente o lasceremo vuoto. Per ora: stringa fittizia, segnalata.
      // Meglio: il move BC è SEMPRE del giocatore di turno. Nel formato BC
      // non è esplicito, ma il chiamante può infilare il currentPlayer del
      // turno corrente nel callback. Per semplicità, omettiamo questo
      // evento se non c'è altro modo: la perdita è limitata.
      // SCELTA: lo emettiamo con giocatore_id derivato dal turno (gestito
      // nel chiamante), oppure lo skippiamo. Qui scegliamo skip e annotiamo.
      // → il move legacy diventa un'informazione persa.
      return [];
    }
  }
}

// === Sintesi dadi ==========================================================

/**
 * Genera dadi attaccante/difensore plausibili che producono le perdite
 * dichiarate. La risoluzione (regola standard) è deterministica una volta
 * fissati i dadi ordinati: questo metodo ricostruisce coppie compatibili.
 *
 * Regola: ordino decrescente, confronto coppie, parità → attaccante perde.
 *
 * Strategia:
 *   - perdite totali ≤ 3 (dadi attaccante 1..3, dadi difensore 1..3)
 *   - num_coppie = atkLoss + defLoss
 *   - per ogni coppia: se attaccante deve perdere, dado_att=1, dado_dif=6;
 *     se difensore deve perdere, dado_att=6, dado_dif=1
 */
function sintetizzaDadi(
  atkLoss: number,
  defLoss: number,
): { att: number[]; dif: number[] } {
  const att: number[] = [];
  const dif: number[] = [];
  for (let i = 0; i < defLoss; i++) {
    att.push(6);
    dif.push(1);
  }
  for (let i = 0; i < atkLoss; i++) {
    att.push(1);
    dif.push(6);
  }
  // Se totale è 0 (caso anomalo), fornisco un confronto minimo plausibile.
  if (att.length === 0) {
    att.push(1);
    dif.push(6);
  }
  // Clamp ai range schema (1..3 per array length)
  while (att.length > 3) att.pop();
  while (dif.length > 3) dif.pop();
  return { att, dif };
}

// === Sintesi tris ==========================================================

function sintetizzaTris(kind: "uguali" | "diversi" | undefined): DatiCarta[] {
  if (kind === "diversi") {
    return [
      { territorio: null, simbolo: "fante" },
      { territorio: null, simbolo: "cavaliere" },
      { territorio: null, simbolo: "cannone" },
    ];
  }
  // default: 3 uguali (fante)
  return [
    { territorio: null, simbolo: "fante" },
    { territorio: null, simbolo: "fante" },
    { territorio: null, simbolo: "fante" },
  ];
}

// === Helper ================================================================

function idTerritorio<
  E extends { from?: string; to?: string; f?: number; t?: number },
>(
  ev: E,
  campoString: "from" | "to",
  campoIdx: "f" | "t",
  ordineTerritori: ReadonlyArray<string>,
): string | null {
  const diretto = ev[campoString];
  if (diretto) return diretto;
  const idx = ev[campoIdx];
  if (typeof idx === "number") {
    return ordineTerritori[idx] ?? null;
  }
  return null;
}

function msAIso(ms: number): string {
  return new Date(ms).toISOString();
}
