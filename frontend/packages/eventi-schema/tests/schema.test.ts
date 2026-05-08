/**
 * Test del pacchetto schema eventi. Coprono:
 * - Validazione di payload validi per ogni tipo evento
 * - Rigetto di payload invalidi (campi mancanti, fuori range, extra)
 * - Discriminated union (narrowing su `tipo`)
 * - Bundle replay
 * - Helper di parsing tollerante
 */

import { describe, expect, it } from "vitest";

import {
  ErroreParsingEventi,
  parsaBundleReplay,
  parsaEvento,
  parsaEventoSafe,
  parsaListaEventi,
  SchemaBundleReplay,
  SchemaDatiAttaccoRisolto,
  SchemaDatiCarta,
  SchemaDatiTrisGiocato,
  SchemaEventoValidato,
} from "../src/index.js";

// === Helper fixture ===

const TS = "2026-05-07T21:00:00+00:00";

function evento(tipo: string, dati: unknown, id = "ev-1") {
  return { id, partita_id: "p1", ts_evento: TS, tipo, dati };
}

// === Schema dati ===

describe("SchemaDatiAttaccoRisolto", () => {
  it("accetta payload valido 3v2", () => {
    const r = SchemaDatiAttaccoRisolto.safeParse({
      giocatore_id: "g-rosso",
      da: "kamchatka",
      a: "alaska",
      dadi_attaccante: [6, 4, 2],
      dadi_difensore: [5, 3],
    });
    expect(r.success).toBe(true);
  });

  it("rifiuta dadi attaccante vuoti", () => {
    const r = SchemaDatiAttaccoRisolto.safeParse({
      giocatore_id: "g",
      da: "k",
      a: "a",
      dadi_attaccante: [],
      dadi_difensore: [3],
    });
    expect(r.success).toBe(false);
  });

  it("rifiuta più di 3 dadi attaccante", () => {
    const r = SchemaDatiAttaccoRisolto.safeParse({
      giocatore_id: "g",
      da: "k",
      a: "a",
      dadi_attaccante: [1, 2, 3, 4],
      dadi_difensore: [3],
    });
    expect(r.success).toBe(false);
  });

  it("rifiuta valori dadi fuori range 1-6", () => {
    const r = SchemaDatiAttaccoRisolto.safeParse({
      giocatore_id: "g",
      da: "k",
      a: "a",
      dadi_attaccante: [7],
      dadi_difensore: [3],
    });
    expect(r.success).toBe(false);
  });

  it("rifiuta campi extra (.strict)", () => {
    const r = SchemaDatiAttaccoRisolto.safeParse({
      giocatore_id: "g",
      da: "k",
      a: "a",
      dadi_attaccante: [6],
      dadi_difensore: [3],
      campo_inventato: "x",
    });
    expect(r.success).toBe(false);
  });
});

describe("SchemaDatiCarta", () => {
  it("accetta carta territorio cannone", () => {
    expect(
      SchemaDatiCarta.safeParse({
        territorio: "kamchatka",
        simbolo: "cannone",
      }).success,
    ).toBe(true);
  });

  it("accetta jolly con territorio null", () => {
    expect(
      SchemaDatiCarta.safeParse({
        territorio: null,
        simbolo: "jolly",
      }).success,
    ).toBe(true);
  });

  it("rifiuta simbolo invalido", () => {
    expect(
      SchemaDatiCarta.safeParse({
        territorio: "k",
        simbolo: "drago",
      }).success,
    ).toBe(false);
  });
});

describe("SchemaDatiTrisGiocato", () => {
  it("richiede esattamente 3 carte", () => {
    const r = SchemaDatiTrisGiocato.safeParse({
      giocatore_id: "g",
      carte: [
        { territorio: "a", simbolo: "cannone" },
        { territorio: "b", simbolo: "cannone" },
      ],
    });
    expect(r.success).toBe(false);
  });

  it("accetta tris di 3 cannoni", () => {
    const r = SchemaDatiTrisGiocato.safeParse({
      giocatore_id: "g",
      carte: [
        { territorio: "a", simbolo: "cannone" },
        { territorio: "b", simbolo: "cannone" },
        { territorio: "c", simbolo: "cannone" },
      ],
    });
    expect(r.success).toBe(true);
  });

  it("accetta tris misto con jolly", () => {
    const r = SchemaDatiTrisGiocato.safeParse({
      giocatore_id: "g",
      carte: [
        { territorio: "a", simbolo: "cannone" },
        { territorio: "b", simbolo: "fante" },
        { territorio: null, simbolo: "jolly" },
      ],
    });
    expect(r.success).toBe(true);
  });
});

// === Discriminated union ===

describe("SchemaEventoValidato discriminated union", () => {
  it("accetta evento attacco_risolto valido", () => {
    const r = SchemaEventoValidato.safeParse(
      evento("attacco_risolto", {
        giocatore_id: "g",
        da: "k",
        a: "a",
        dadi_attaccante: [6],
        dadi_difensore: [3],
      }),
    );
    expect(r.success).toBe(true);
  });

  it("accetta evento armate_piazzate valido", () => {
    const r = SchemaEventoValidato.safeParse(
      evento("armate_piazzate", {
        giocatore_id: "g",
        territorio: "k",
        n: 5,
      }),
    );
    expect(r.success).toBe(true);
  });

  it("rifiuta tipo evento sconosciuto", () => {
    const r = SchemaEventoValidato.safeParse(
      evento("evento_inventato", {}),
    );
    expect(r.success).toBe(false);
  });

  it("rifiuta payload non corrispondente al tipo", () => {
    // attacco_risolto con dati di armate_piazzate
    const r = SchemaEventoValidato.safeParse(
      evento("attacco_risolto", {
        giocatore_id: "g",
        territorio: "k",
        n: 5,
      }),
    );
    expect(r.success).toBe(false);
  });

  it("preserva narrowing TypeScript dopo parsing", () => {
    const ev = SchemaEventoValidato.parse(
      evento("attacco_risolto", {
        giocatore_id: "g",
        da: "k",
        a: "a",
        dadi_attaccante: [6, 4],
        dadi_difensore: [3],
      }),
    );
    if (ev.tipo === "attacco_risolto") {
      // TypeScript sa che ev.dati è DatiAttaccoRisolto
      expect(ev.dati.dadi_attaccante).toEqual([6, 4]);
      expect(ev.dati.da).toBe("k");
    }
  });
});

// === Bundle replay ===

describe("SchemaBundleReplay", () => {
  it("accetta bundle minimo (no eventi, 2 giocatori)", () => {
    const r = SchemaBundleReplay.safeParse({
      schema_version: "1.0",
      partita: {
        id: "p1",
        data_inizio: TS,
        data_fine: null,
      },
      giocatori: [
        {
          id: "g1",
          nome: "Edo",
          colore: "rosso",
          ordine_seduta: 1,
        },
        {
          id: "g2",
          nome: "Marco",
          colore: "blu",
          ordine_seduta: 2,
        },
      ],
      eventi: [],
    });
    expect(r.success).toBe(true);
  });

  it("rifiuta partita con 1 giocatore", () => {
    const r = SchemaBundleReplay.safeParse({
      schema_version: "1.0",
      partita: { id: "p1", data_inizio: TS, data_fine: null },
      giocatori: [
        { id: "g1", nome: "Solo", colore: "rosso", ordine_seduta: 1 },
      ],
      eventi: [],
    });
    expect(r.success).toBe(false);
  });

  it("rifiuta schema_version sbagliato", () => {
    const r = SchemaBundleReplay.safeParse({
      schema_version: "2.0",
      partita: { id: "p1", data_inizio: TS, data_fine: null },
      giocatori: [
        { id: "g1", nome: "A", colore: "rosso", ordine_seduta: 1 },
        { id: "g2", nome: "B", colore: "blu", ordine_seduta: 2 },
      ],
      eventi: [],
    });
    expect(r.success).toBe(false);
  });
});

// === Helper di parsing ===

describe("parsaEvento (throw)", () => {
  it("ritorna evento valido", () => {
    const ev = parsaEvento(
      evento("turno_finito", { giocatore_id: "g" }),
    );
    expect(ev.tipo).toBe("turno_finito");
  });

  it("lancia ErroreParsingEventi su input invalido con dettagli", () => {
    expect(() => parsaEvento({ tipo: "invalido" })).toThrow(
      ErroreParsingEventi,
    );
    try {
      parsaEvento({ tipo: "invalido" });
    } catch (e) {
      const err = e as ErroreParsingEventi;
      expect(err.dettagli.length).toBeGreaterThan(0);
      expect(err.dettagli[0]?.percorso).toBeDefined();
      expect(err.dettagli[0]?.codice).toBeDefined();
    }
  });
});

describe("parsaEventoSafe (no throw)", () => {
  it("success=true per evento valido", () => {
    const r = parsaEventoSafe(
      evento("partita_inizio", { primo_giocatore_id: "g1" }),
    );
    expect(r.success).toBe(true);
  });

  it("success=false con errore strutturato per evento invalido", () => {
    const r = parsaEventoSafe({ tipo: "x" });
    expect(r.success).toBe(false);
    if (!r.success) {
      expect(r.errore).toBeInstanceOf(ErroreParsingEventi);
      expect(r.errore.dettagli.length).toBeGreaterThan(0);
    }
  });
});

describe("parsaListaEventi (tollerante)", () => {
  it("separa validi da scartati con indici", () => {
    const lista = [
      evento("turno_finito", { giocatore_id: "g" }, "ev-1"),
      { tipo: "invalido" }, // mancano metadati e dati
      evento("partita_inizio", { primo_giocatore_id: "g" }, "ev-3"),
    ];
    const r = parsaListaEventi(lista);
    expect(r.validi).toHaveLength(2);
    expect(r.scartati).toHaveLength(1);
    expect(r.scartati[0]?.indice).toBe(1);
  });

  it("ritorna tutto valido se nulla è rotto", () => {
    const r = parsaListaEventi([
      evento("turno_finito", { giocatore_id: "g" }),
    ]);
    expect(r.validi).toHaveLength(1);
    expect(r.scartati).toHaveLength(0);
  });

  it("lista vuota → tutto vuoto", () => {
    const r = parsaListaEventi([]);
    expect(r.validi).toEqual([]);
    expect(r.scartati).toEqual([]);
  });
});

describe("parsaBundleReplay", () => {
  it("ritorna bundle parsato", () => {
    const b = parsaBundleReplay({
      schema_version: "1.0",
      partita: { id: "p1", data_inizio: TS, data_fine: null },
      giocatori: [
        { id: "g1", nome: "A", colore: "rosso", ordine_seduta: 1 },
        { id: "g2", nome: "B", colore: "blu", ordine_seduta: 2 },
      ],
      eventi: [
        evento("partita_inizio", { primo_giocatore_id: "g1" }),
      ],
    });
    expect(b.giocatori).toHaveLength(2);
    expect(b.eventi).toHaveLength(1);
  });

  it("lancia su bundle invalido", () => {
    expect(() => parsaBundleReplay({ schema_version: "1.0" })).toThrow(
      ErroreParsingEventi,
    );
  });
});
