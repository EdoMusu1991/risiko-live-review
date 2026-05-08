import { describe, it, expect } from "vitest";

import { adattaReplayBc } from "../adapter-bc.js";
import { creaTimeline } from "../timeline.js";
import { parsaBundleReplay } from "@risiko/eventi-schema";
import {
  ORDINE_TERRITORI_TEST,
  replayBcLegacyEsempio,
} from "./fixture/replay-bc-legacy.js";

describe("adattaReplayBc - struttura output", () => {
  it("produce un BundleReplay valido (zod parse passa)", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    expect(() => parsaBundleReplay(bundle)).not.toThrow();
  });

  it("marca il bundle come legacy in note", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    expect(bundle.partita.note).toMatch(/\[bc-legacy\]/);
  });

  it("genera id giocatori stabili p0..pN", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    expect(bundle.giocatori.map((g) => g.id)).toEqual(["p0", "p1"]);
    expect(bundle.giocatori[0]!.nome).toBe("Alice");
    expect(bundle.giocatori[1]!.nome).toBe("Bob");
  });

  it("preserva startedAt e endedAt come ISO 8601", () => {
    const legacy = replayBcLegacyEsempio();
    const bundle = adattaReplayBc(legacy, {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    expect(bundle.partita.data_inizio).toBe(
      new Date(legacy.startedAt).toISOString(),
    );
    expect(bundle.partita.data_fine).toBe(
      new Date(legacy.endedAt!).toISOString(),
    );
  });
});

describe("adattaReplayBc - eventi emessi", () => {
  it("emette territorio_assegnato_inizio per ogni territorio occupato", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    const init = bundle.eventi.filter(
      (e) => e.tipo === "territorio_assegnato_inizio",
    );
    // 6 territori, tutti occupati nel fixture
    expect(init).toHaveLength(6);
  });

  it("emette obiettivo_assegnato per ogni giocatore", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    const obj = bundle.eventi.filter((e) => e.tipo === "obiettivo_assegnato");
    expect(obj).toHaveLength(2);
  });

  it("emette partita_inizio dopo il setup", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    const init = bundle.eventi.findIndex((e) => e.tipo === "partita_inizio");
    expect(init).toBeGreaterThan(0);
  });

  it("attack con conquered=true → attacco_risolto + territorio_conquistato", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    const att = bundle.eventi.findIndex((e) => e.tipo === "attacco_risolto");
    const conq = bundle.eventi.findIndex(
      (e) => e.tipo === "territorio_conquistato",
    );
    expect(att).toBeGreaterThanOrEqual(0);
    expect(conq).toBe(att + 1);
  });

  it("partita_fine con vincitore_id corretto", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    const fine = bundle.eventi.find((e) => e.tipo === "partita_fine");
    expect(fine).toBeDefined();
    if (fine?.tipo === "partita_fine") {
      expect(fine.dati.vincitore_id).toBe("p0");
    }
  });

  it("ogni turno BC produce coppia turno_iniziato/turno_finito", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    const inizi = bundle.eventi.filter((e) => e.tipo === "turno_iniziato");
    const fini = bundle.eventi.filter((e) => e.tipo === "turno_finito");
    // 2 turni non-finali nel fixture (terzo è isFinal)
    expect(inizi).toHaveLength(2);
    expect(fini).toHaveLength(2);
  });
});

describe("adattaReplayBc - round-trip con replay-lib", () => {
  it("il bundle convertito è applicabile dall'inizio alla fine senza errori", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    const t = creaTimeline(bundle);
    expect(() => t.statoAlIndice(t.lunghezza - 1)).not.toThrow();
  });

  it("stato finale: gamma è di p0 (era stata conquistata)", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    const t = creaTimeline(bundle);
    const finale = t.statoAlIndice(t.lunghezza - 1);
    expect(finale.territori.get("gamma")?.proprietario_id).toBe("p0");
  });

  it("stato finale: vincitore p0, fase finita", () => {
    const bundle = adattaReplayBc(replayBcLegacyEsempio(), {
      ordineTerritori: ORDINE_TERRITORI_TEST,
    });
    const t = creaTimeline(bundle);
    const finale = t.statoAlIndice(t.lunghezza - 1);
    expect(finale.fase).toBe("finita");
    expect(finale.vincitore_id).toBe("p0");
  });
});
