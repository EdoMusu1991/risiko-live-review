import { describe, it, expect } from "vitest";

import {
  ADIACENZE,
  CONTINENTI,
  CONTINENTE_DI,
  POSIZIONI,
  TERRITORI_TUTTI,
  sonoAdiacenti,
} from "../layout.js";

describe("layout - struttura", () => {
  it("ci sono 42 territori", () => {
    expect(TERRITORI_TUTTI).toHaveLength(42);
  });

  it("ogni territorio in CONTINENTI ha una POSIZIONE", () => {
    for (const t of TERRITORI_TUTTI) {
      expect(POSIZIONI[t], `manca POSIZIONI[${t}]`).toBeDefined();
    }
  });

  it("ogni territorio in POSIZIONI è in TERRITORI_TUTTI (no orfani)", () => {
    for (const t of Object.keys(POSIZIONI)) {
      expect(TERRITORI_TUTTI, `${t} non è in CONTINENTI`).toContain(t);
    }
  });

  it("CONTINENTE_DI è coerente con CONTINENTI", () => {
    for (const c of CONTINENTI) {
      for (const t of c.territori) {
        expect(CONTINENTE_DI[t]).toBe(c.slug);
      }
    }
  });

  it("ci sono 6 continenti con bonus standard EG", () => {
    expect(CONTINENTI).toHaveLength(6);
    const slugs = CONTINENTI.map((c) => c.slug).sort();
    expect(slugs).toEqual([
      "africa",
      "asia",
      "europa",
      "nord_america",
      "oceania",
      "sud_america",
    ]);
    // Bonus EG: 5+5+7+3+2+2 = 24
    const totale = CONTINENTI.reduce((s, c) => s + c.bonus, 0);
    expect(totale).toBe(24);
  });
});

describe("layout - adiacenze", () => {
  it("nessuna coppia di adiacenze duplicata o auto-riflessiva", () => {
    const visti = new Set<string>();
    for (const [a, b] of ADIACENZE) {
      expect(a).not.toBe(b);
      const k1 = `${a}|${b}`;
      const k2 = `${b}|${a}`;
      expect(visti.has(k1) || visti.has(k2)).toBe(false);
      visti.add(k1);
    }
  });

  it("tutte le adiacenze referenziano territori esistenti", () => {
    for (const [a, b] of ADIACENZE) {
      expect(POSIZIONI[a], `${a} sconosciuto`).toBeDefined();
      expect(POSIZIONI[b], `${b} sconosciuto`).toBeDefined();
    }
  });

  it("sonoAdiacenti è simmetrico", () => {
    for (const [a, b] of ADIACENZE) {
      expect(sonoAdiacenti(a, b)).toBe(true);
      expect(sonoAdiacenti(b, a)).toBe(true);
    }
  });

  it("territori non adiacenti restituiscono false", () => {
    expect(sonoAdiacenti("alaska", "argentina")).toBe(false);
    expect(sonoAdiacenti("madagascar", "giappone")).toBe(false);
  });

  it("ponti intercontinentali noti sono presenti", () => {
    expect(sonoAdiacenti("alaska", "kamchatka")).toBe(true);
    expect(sonoAdiacenti("brasile", "africa_settentrionale")).toBe(true);
    expect(sonoAdiacenti("asia_sudorientale", "indonesia")).toBe(true);
    expect(sonoAdiacenti("europa_meridionale", "egitto")).toBe(true);
  });
});

describe("layout - posizioni nel viewBox", () => {
  it("tutte le posizioni sono dentro il viewBox 1000x680", () => {
    for (const [t, p] of Object.entries(POSIZIONI)) {
      expect(p.x, `${t}.x`).toBeGreaterThanOrEqual(0);
      expect(p.x, `${t}.x`).toBeLessThanOrEqual(1000);
      expect(p.y, `${t}.y`).toBeGreaterThanOrEqual(0);
      expect(p.y, `${t}.y`).toBeLessThanOrEqual(680);
    }
  });
});
