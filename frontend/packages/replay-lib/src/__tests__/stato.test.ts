import { describe, it, expect } from "vitest";

import {
  applicaEvento,
  calcolaPerdite,
  creaStatoInizialeDaBundle,
  ErroreReplayCorrotto,
} from "../stato.js";
import type { EventoValidato } from "@risiko/eventi-schema";
import { bundleMinimo } from "./fixture/bundle-minimo.js";

// === Helper di costruzione eventi (compatti per i test) =====================

let _eid = 0;
const ev = <T extends EventoValidato["tipo"]>(
  tipo: T,
  dati: Extract<EventoValidato, { tipo: T }>["dati"],
): EventoValidato =>
  ({
    id: `t-${_eid++}`,
    ts_evento: "2026-05-08T10:00:00.000Z",
    tipo,
    dati,
  }) as EventoValidato;

describe("creaStatoInizialeDaBundle", () => {
  it("popola i giocatori dal bundle e lascia territori vuoti", () => {
    const s = creaStatoInizialeDaBundle(bundleMinimo());
    expect(s.giocatori.size).toBe(2);
    expect(s.giocatori.get("p0")?.nome).toBe("Alice");
    expect(s.giocatori.get("p1")?.nome).toBe("Bob");
    expect(s.territori.size).toBe(0);
    expect(s.fase).toBe("setup");
    expect(s.giocatore_di_turno).toBe(null);
    expect(s.vincitore_id).toBe(null);
  });

  it("partita_id e data_inizio dal bundle", () => {
    const s = creaStatoInizialeDaBundle(bundleMinimo());
    expect(s.partita_id).toBe("partita-test-1");
    expect(s.data_inizio).toBe("2026-05-08T10:00:00.000Z");
  });
});

describe("applicaEvento - non muta lo stato originale", () => {
  it("ritorna nuovo stato, originale invariato", () => {
    const s0 = creaStatoInizialeDaBundle(bundleMinimo());
    const territoriPrima = s0.territori.size;
    const s1 = applicaEvento(
      s0,
      ev("territorio_assegnato_inizio", {
        territorio: "alfa",
        giocatore_id: "p0",
        n_armate: 3,
      }),
    );
    expect(s0.territori.size).toBe(territoriPrima); // s0 invariato
    expect(s1.territori.size).toBe(1);
    expect(s1.territori.get("alfa")?.proprietario_id).toBe("p0");
  });
});

describe("applicaEvento - setup", () => {
  it("territorio_assegnato_inizio crea il territorio col proprietario", () => {
    const s = applicaEvento(
      creaStatoInizialeDaBundle(bundleMinimo()),
      ev("territorio_assegnato_inizio", {
        territorio: "alfa",
        giocatore_id: "p0",
        n_armate: 5,
      }),
    );
    const t = s.territori.get("alfa");
    expect(t?.proprietario_id).toBe("p0");
    expect(t?.n_armate).toBe(5);
  });

  it("territorio_assegnato_inizio con giocatore sconosciuto lancia", () => {
    expect(() =>
      applicaEvento(
        creaStatoInizialeDaBundle(bundleMinimo()),
        ev("territorio_assegnato_inizio", {
          territorio: "alfa",
          giocatore_id: "fantasma",
          n_armate: 3,
        }),
      ),
    ).toThrow(ErroreReplayCorrotto);
  });

  it("obiettivo_assegnato imposta l'obiettivo del giocatore", () => {
    const s = applicaEvento(
      creaStatoInizialeDaBundle(bundleMinimo()),
      ev("obiettivo_assegnato", { giocatore_id: "p0", obiettivo_id: 7 }),
    );
    expect(s.giocatori.get("p0")?.obiettivo_id).toBe(7);
  });

  it("partita_inizio cambia fase e imposta primo giocatore", () => {
    const s = applicaEvento(
      creaStatoInizialeDaBundle(bundleMinimo()),
      ev("partita_inizio", { primo_giocatore_id: "p1" }),
    );
    expect(s.fase).toBe("in_corso");
    expect(s.giocatore_di_turno).toBe("p1");
  });
});

describe("applicaEvento - turno", () => {
  it("turno_iniziato imposta giocatore di turno e resetta conquiste", () => {
    let s = creaStatoInizialeDaBundle(bundleMinimo());
    s.conquiste_turno_corrente = ["x"]; // setup artificioso
    s = applicaEvento(s, ev("turno_iniziato", { giocatore_id: "p1" }));
    expect(s.giocatore_di_turno).toBe("p1");
    expect(s.conquiste_turno_corrente).toEqual([]);
    expect(s.ultimo_attacco).toBe(null);
  });

  it("turno_finito è no-op semantico", () => {
    const s0 = creaStatoInizialeDaBundle(bundleMinimo());
    const s1 = applicaEvento(s0, ev("turno_finito", { giocatore_id: "p0" }));
    expect(s1.fase).toBe(s0.fase);
    expect(s1.giocatore_di_turno).toBe(s0.giocatore_di_turno);
  });
});

describe("applicaEvento - rinforzo", () => {
  it("armate_piazzate aggiunge armate al territorio", () => {
    let s = creaStatoInizialeDaBundle(bundleMinimo());
    s = applicaEvento(
      s,
      ev("territorio_assegnato_inizio", {
        territorio: "alfa",
        giocatore_id: "p0",
        n_armate: 3,
      }),
    );
    s = applicaEvento(
      s,
      ev("armate_piazzate", {
        giocatore_id: "p0",
        territorio: "alfa",
        n: 5,
      }),
    );
    expect(s.territori.get("alfa")?.n_armate).toBe(8);
  });

  it("armate_piazzate su territorio sconosciuto lancia", () => {
    const s = creaStatoInizialeDaBundle(bundleMinimo());
    expect(() =>
      applicaEvento(
        s,
        ev("armate_piazzate", {
          giocatore_id: "p0",
          territorio: "inesistente",
          n: 1,
        }),
      ),
    ).toThrow(ErroreReplayCorrotto);
  });

  it("tris_giocato rimuove le 3 carte dalla mano (match per territorio+simbolo)", () => {
    let s = creaStatoInizialeDaBundle(bundleMinimo());
    // Aggiungo 4 carte alla mano di p0
    const g = s.giocatori.get("p0")!;
    g.mano.push(
      { territorio: "alfa", simbolo: "fante" },
      { territorio: "beta", simbolo: "fante" },
      { territorio: "gamma", simbolo: "fante" },
      { territorio: "delta", simbolo: "cavaliere" },
    );
    s = applicaEvento(
      s,
      ev("tris_giocato", {
        giocatore_id: "p0",
        carte: [
          { territorio: "alfa", simbolo: "fante" },
          { territorio: "beta", simbolo: "fante" },
          { territorio: "gamma", simbolo: "fante" },
        ],
      }),
    );
    const mano = s.giocatori.get("p0")!.mano;
    expect(mano).toHaveLength(1);
    expect(mano[0]?.territorio).toBe("delta");
  });

  it("tris_giocato con carta non in mano lancia", () => {
    const s0 = creaStatoInizialeDaBundle(bundleMinimo());
    expect(() =>
      applicaEvento(
        s0,
        ev("tris_giocato", {
          giocatore_id: "p0",
          carte: [
            { territorio: "alfa", simbolo: "fante" },
            { territorio: "beta", simbolo: "fante" },
            { territorio: null, simbolo: "jolly" },
          ],
        }),
      ),
    ).toThrow(ErroreReplayCorrotto);
  });
});

describe("applicaEvento - attacco", () => {
  function setupAttacco() {
    let s = creaStatoInizialeDaBundle(bundleMinimo());
    s = applicaEvento(
      s,
      ev("territorio_assegnato_inizio", {
        territorio: "alfa",
        giocatore_id: "p0",
        n_armate: 4,
      }),
    );
    s = applicaEvento(
      s,
      ev("territorio_assegnato_inizio", {
        territorio: "gamma",
        giocatore_id: "p1",
        n_armate: 3,
      }),
    );
    return s;
  }

  it("attacco_risolto applica perdite secondo regola standard", () => {
    let s = setupAttacco();
    s = applicaEvento(
      s,
      ev("attacco_risolto", {
        giocatore_id: "p0",
        da: "alfa",
        a: "gamma",
        dadi_attaccante: [6, 5, 4],
        dadi_difensore: [3, 2],
      }),
    );
    // Coppie: (6 vs 3) → dif perde, (5 vs 2) → dif perde. Dado att 4 scartato.
    expect(s.territori.get("alfa")?.n_armate).toBe(4); // 0 perdite
    expect(s.territori.get("gamma")?.n_armate).toBe(1); // 2 perdite
    expect(s.ultimo_attacco?.perdite_difensore).toBe(2);
    expect(s.ultimo_attacco?.perdite_attaccante).toBe(0);
  });

  it("attacco_risolto con parità: attaccante perde", () => {
    let s = setupAttacco();
    s = applicaEvento(
      s,
      ev("attacco_risolto", {
        giocatore_id: "p0",
        da: "alfa",
        a: "gamma",
        dadi_attaccante: [3],
        dadi_difensore: [3],
      }),
    );
    expect(s.territori.get("alfa")?.n_armate).toBe(3); // -1
    expect(s.territori.get("gamma")?.n_armate).toBe(3); // 0
  });

  it("attacco_risolto: clamp a 0 se le perdite supererebbero le armate", () => {
    let s = setupAttacco();
    // Forzo armate basse sul difensore
    const t = s.territori.get("gamma")!;
    t.n_armate = 1;
    s = applicaEvento(
      s,
      ev("attacco_risolto", {
        giocatore_id: "p0",
        da: "alfa",
        a: "gamma",
        dadi_attaccante: [6, 5],
        dadi_difensore: [1, 1],
      }),
    );
    expect(s.territori.get("gamma")?.n_armate).toBe(0); // clamp
  });

  it("territorio_conquistato cambia proprietario e traccia conquista", () => {
    let s = setupAttacco();
    s = applicaEvento(
      s,
      ev("territorio_conquistato", {
        giocatore_id: "p0",
        territorio: "gamma",
      }),
    );
    expect(s.territori.get("gamma")?.proprietario_id).toBe("p0");
    expect(s.conquiste_turno_corrente).toContain("gamma");
  });

  it("territorio_conquistato che elimina il giocatore: imposta eliminato=true", () => {
    let s = creaStatoInizialeDaBundle(bundleMinimo());
    // p1 ha solo gamma, viene conquistato.
    s = applicaEvento(
      s,
      ev("territorio_assegnato_inizio", {
        territorio: "alfa",
        giocatore_id: "p0",
        n_armate: 3,
      }),
    );
    s = applicaEvento(
      s,
      ev("territorio_assegnato_inizio", {
        territorio: "gamma",
        giocatore_id: "p1",
        n_armate: 1,
      }),
    );
    s = applicaEvento(
      s,
      ev("territorio_conquistato", {
        giocatore_id: "p0",
        territorio: "gamma",
      }),
    );
    expect(s.giocatori.get("p1")?.eliminato).toBe(true);
    expect(s.giocatori.get("p0")?.eliminato).toBe(false);
  });
});

describe("applicaEvento - spostamento", () => {
  it("armate_spostate sposta n armate fra territori", () => {
    let s = creaStatoInizialeDaBundle(bundleMinimo());
    s = applicaEvento(
      s,
      ev("territorio_assegnato_inizio", {
        territorio: "alfa",
        giocatore_id: "p0",
        n_armate: 5,
      }),
    );
    s = applicaEvento(
      s,
      ev("territorio_assegnato_inizio", {
        territorio: "beta",
        giocatore_id: "p0",
        n_armate: 1,
      }),
    );
    s = applicaEvento(
      s,
      ev("armate_spostate", {
        giocatore_id: "p0",
        da: "alfa",
        a: "beta",
        n: 3,
      }),
    );
    expect(s.territori.get("alfa")?.n_armate).toBe(2);
    expect(s.territori.get("beta")?.n_armate).toBe(4);
  });
});

describe("applicaEvento - pesca", () => {
  it("carta_pescata aggiunge la carta in mano", () => {
    let s = creaStatoInizialeDaBundle(bundleMinimo());
    s = applicaEvento(
      s,
      ev("carta_pescata", {
        giocatore_id: "p0",
        carta: { territorio: "alfa", simbolo: "fante" },
      }),
    );
    const mano = s.giocatori.get("p0")!.mano;
    expect(mano).toHaveLength(1);
    expect(mano[0]).toEqual({ territorio: "alfa", simbolo: "fante" });
  });
});

describe("applicaEvento - fine partita", () => {
  it("partita_fine imposta vincitore, fase=finita, data_fine", () => {
    let s = creaStatoInizialeDaBundle(bundleMinimo());
    const evento = ev("partita_fine", { vincitore_id: "p0" });
    // Forziamo un ts_evento specifico
    (evento as { ts_evento: string }).ts_evento = "2026-05-08T11:00:00.000Z";
    s = applicaEvento(s, evento);
    expect(s.fase).toBe("finita");
    expect(s.vincitore_id).toBe("p0");
    expect(s.data_fine).toBe("2026-05-08T11:00:00.000Z");
  });
});

describe("calcolaPerdite", () => {
  it("3 vs 2 con tutti gli attaccanti vincenti", () => {
    expect(calcolaPerdite([6, 6, 6], [1, 1])).toEqual({
      perdite_att: 0,
      perdite_dif: 2,
    });
  });
  it("2 vs 2 con parità su entrambi i lati", () => {
    expect(calcolaPerdite([5, 3], [5, 3])).toEqual({
      perdite_att: 2,
      perdite_dif: 0,
    });
  });
  it("3 vs 1: scarta i dadi extra dell'attaccante", () => {
    expect(calcolaPerdite([6, 5, 4], [6])).toEqual({
      perdite_att: 1,
      perdite_dif: 0,
    });
  });
});
