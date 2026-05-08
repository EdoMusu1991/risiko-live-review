import { describe, it, expect } from "vitest";

import { narrativeEvento } from "../narrative.js";
import { creaStatoInizialeDaBundle } from "@risiko/replay-lib";
import type { EventoValidato, BundleReplay } from "@risiko/eventi-schema";

const bundleMin: BundleReplay = {
  schema_version: "1.0",
  partita: {
    id: "p1",
    data_inizio: "2026-01-01T00:00:00.000Z",
    data_fine: null,
    luogo: null,
    note: null,
  },
  giocatori: [
    { id: "p0", nome: "Alice", colore: "rosso", ordine_seduta: 1 },
    { id: "p1", nome: "Bob", colore: "blu", ordine_seduta: 2 },
  ],
  eventi: [],
};

const stato = creaStatoInizialeDaBundle(bundleMin);

const ev = <T extends EventoValidato["tipo"]>(
  tipo: T,
  dati: Extract<EventoValidato, { tipo: T }>["dati"],
): EventoValidato =>
  ({
    id: "test",
    ts_evento: "2026-01-01T00:00:00.000Z",
    tipo,
    dati,
  }) as EventoValidato;

describe("narrativeEvento", () => {
  it("turno_iniziato: usa il nome del giocatore", () => {
    const e = ev("turno_iniziato", { giocatore_id: "p0" });
    expect(narrativeEvento(e, stato)).toBe("Inizia il turno di Alice.");
  });

  it("attacco_risolto: include territori e dadi", () => {
    const e = ev("attacco_risolto", {
      giocatore_id: "p0",
      da: "alaska",
      a: "kamchatka",
      dadi_attaccante: [6, 5],
      dadi_difensore: [3],
    });
    const t = narrativeEvento(e, stato);
    expect(t).toContain("Alice");
    expect(t).toContain("alaska");
    expect(t).toContain("kamchatka");
    expect(t).toContain("6-5");
    expect(t).toContain("3");
  });

  it("armate_piazzate: singolare/plurale", () => {
    const e1 = ev("armate_piazzate", {
      giocatore_id: "p0",
      territorio: "alaska",
      n: 1,
    });
    expect(narrativeEvento(e1, stato)).toContain("1 armata");
    const e2 = ev("armate_piazzate", {
      giocatore_id: "p0",
      territorio: "alaska",
      n: 5,
    });
    expect(narrativeEvento(e2, stato)).toContain("5 armate");
  });

  it("partita_fine: nomina il vincitore", () => {
    const e = ev("partita_fine", { vincitore_id: "p1" });
    expect(narrativeEvento(e, stato)).toContain("Bob");
  });

  it("territorio_conquistato: replace underscore con spazio", () => {
    const e = ev("territorio_conquistato", {
      giocatore_id: "p0",
      territorio: "africa_settentrionale",
    });
    const t = narrativeEvento(e, stato);
    expect(t).toContain("africa settentrionale");
    expect(t).not.toContain("africa_settentrionale");
  });

  it("tutti i 12 tipi evento producono una stringa non vuota", () => {
    const tipiCampione: EventoValidato[] = [
      ev("territorio_assegnato_inizio", {
        territorio: "alaska",
        giocatore_id: "p0",
        n_armate: 3,
      }),
      ev("obiettivo_assegnato", { giocatore_id: "p0", obiettivo_id: 1 }),
      ev("partita_inizio", { primo_giocatore_id: "p0" }),
      ev("turno_iniziato", { giocatore_id: "p0" }),
      ev("turno_finito", { giocatore_id: "p0" }),
      ev("armate_piazzate", {
        giocatore_id: "p0",
        territorio: "alaska",
        n: 3,
      }),
      ev("tris_giocato", {
        giocatore_id: "p0",
        carte: [
          { territorio: null, simbolo: "fante" },
          { territorio: null, simbolo: "fante" },
          { territorio: null, simbolo: "fante" },
        ],
      }),
      ev("attacco_risolto", {
        giocatore_id: "p0",
        da: "alaska",
        a: "kamchatka",
        dadi_attaccante: [6],
        dadi_difensore: [1],
      }),
      ev("territorio_conquistato", {
        giocatore_id: "p0",
        territorio: "kamchatka",
      }),
      ev("armate_spostate", {
        giocatore_id: "p0",
        da: "alaska",
        a: "kamchatka",
        n: 2,
      }),
      ev("carta_pescata", {
        giocatore_id: "p0",
        carta: { territorio: "alaska", simbolo: "cavaliere" },
      }),
      ev("partita_fine", { vincitore_id: "p0" }),
    ];
    for (const e of tipiCampione) {
      const t = narrativeEvento(e, stato);
      expect(t.length).toBeGreaterThan(0);
    }
  });
});
