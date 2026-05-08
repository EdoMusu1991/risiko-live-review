import { describe, it, expect } from "vitest";

import { creaTimeline, Timeline } from "../timeline.js";
import { bundleMinimo } from "./fixture/bundle-minimo.js";

describe("Timeline - costruzione", () => {
  it("lunghezza = numero eventi nel bundle", () => {
    const t = creaTimeline(bundleMinimo());
    expect(t.lunghezza).toBe(18);
  });

  it("eventoAlIndice ritorna l'evento giusto", () => {
    const t = creaTimeline(bundleMinimo());
    expect(t.eventoAlIndice(0)?.tipo).toBe("territorio_assegnato_inizio");
    expect(t.eventoAlIndice(6)?.tipo).toBe("partita_inizio");
    expect(t.eventoAlIndice(17)?.tipo).toBe("partita_fine");
  });

  it("eventoAlIndice fuori range ritorna null", () => {
    const t = creaTimeline(bundleMinimo());
    expect(t.eventoAlIndice(-1)).toBe(null);
    expect(t.eventoAlIndice(100)).toBe(null);
  });
});

describe("Timeline - statoAlIndice", () => {
  it("idx -1 ritorna lo stato iniziale (giocatori popolati, territori vuoti)", () => {
    const t = creaTimeline(bundleMinimo());
    const s = t.statoAlIndice(-1);
    expect(s.giocatori.size).toBe(2);
    expect(s.territori.size).toBe(0);
    expect(s.fase).toBe("setup");
  });

  it("dopo i 4 territorio_assegnato_inizio (idx=3) i territori sono 4", () => {
    const t = creaTimeline(bundleMinimo());
    const s = t.statoAlIndice(3);
    expect(s.territori.size).toBe(4);
  });

  it("a partita_inizio (idx=6) la fase è in_corso", () => {
    const t = creaTimeline(bundleMinimo());
    const s = t.statoAlIndice(6);
    expect(s.fase).toBe("in_corso");
    expect(s.giocatore_di_turno).toBe("p0");
  });

  it("ultimo indice = stato finale (vincitore p0)", () => {
    const t = creaTimeline(bundleMinimo());
    const s = t.statoAlIndice(t.lunghezza - 1);
    expect(s.fase).toBe("finita");
    expect(s.vincitore_id).toBe("p0");
  });

  it("statoAlIndice fuori range lancia RangeError", () => {
    const t = creaTimeline(bundleMinimo());
    expect(() => t.statoAlIndice(-2)).toThrow(RangeError);
    expect(() => t.statoAlIndice(t.lunghezza)).toThrow(RangeError);
  });

  it("scrubbing forward dà risultati identici a jump diretto", () => {
    const t = creaTimeline(bundleMinimo());
    // Sequenziale 0..N
    const sequenziale = [];
    for (let i = 0; i < t.lunghezza; i++) {
      sequenziale.push(t.statoAlIndice(i));
    }
    // Random access in altro ordine, su nuova istanza
    const t2 = creaTimeline(bundleMinimo());
    const random = [];
    const ordini = [5, 0, 10, 3, 17, 12, 1];
    for (const i of ordini) random.push(t2.statoAlIndice(i));

    for (const i of ordini) {
      const a = sequenziale[i];
      const b = random[ordini.indexOf(i)];
      expect(a?.fase).toBe(b?.fase);
      expect(a?.giocatore_di_turno).toBe(b?.giocatore_di_turno);
      expect(a?.vincitore_id).toBe(b?.vincitore_id);
      expect(a?.territori.size).toBe(b?.territori.size);
    }
  });
});

describe("Timeline - cache LRU", () => {
  it("cache rispetta cacheMaxSize, evict il least recently used", () => {
    const t = new Timeline(bundleMinimo(), { cacheMaxSize: 3 });
    // Forziamo 5 stati distinti
    for (let i = 0; i < 5; i++) t.statoAlIndice(i);
    // La cache interna è privata; testiamo l'effetto: chiedere lo stesso stato
    // dopo gli stati che l'hanno spinto fuori deve riprodurre lo stesso valore.
    const a = t.statoAlIndice(0);
    expect(a.fase).toBe("setup");
  });

  it("resetCache non rompe nulla", () => {
    const t = creaTimeline(bundleMinimo());
    t.statoAlIndice(5);
    t.resetCache();
    const s = t.statoAlIndice(5);
    expect(s).toBeDefined();
  });
});

describe("Timeline - utilities", () => {
  it("indiciTurni trova tutti i turno_iniziato", () => {
    const t = creaTimeline(bundleMinimo());
    const idx = t.indiciTurni();
    // Il bundle minimo ha 2 turno_iniziato
    expect(idx).toHaveLength(2);
    expect(t.eventoAlIndice(idx[0]!)?.tipo).toBe("turno_iniziato");
    expect(t.eventoAlIndice(idx[1]!)?.tipo).toBe("turno_iniziato");
  });

  it("eventiTraIndici ritorna lo slice corretto", () => {
    const t = creaTimeline(bundleMinimo());
    const e = t.eventiTraIndici(7, 13); // primo turno completo
    expect(e).toHaveLength(7);
    expect(e[0]!.tipo).toBe("turno_iniziato");
    expect(e[e.length - 1]!.tipo).toBe("turno_finito");
  });
});
