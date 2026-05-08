/**
 * Layout schematico della mappa Risiko EG.
 *
 * Ogni territorio ha coordinate (x, y) in un viewBox 1000x680, raggruppate
 * per continente. Le posizioni rispettano vagamente la geografia reale ma
 * sono ottimizzate per leggibilità: niente sovrapposizioni, etichette
 * leggibili, raggruppamenti continentali chiari.
 *
 * Ordine alfabetico dei territori dentro ogni continente per facile
 * manutenzione.
 */

export interface PosizioneTerritorio {
  x: number;
  y: number;
}

export type SlugContinente =
  | "nord_america"
  | "sud_america"
  | "europa"
  | "africa"
  | "asia"
  | "oceania";

export interface DefinizioneContinente {
  slug: SlugContinente;
  nome: string;
  bonus: number;
  // Bounding box approssimato per disegnare lo sfondo del continente
  riquadro: { x: number; y: number; larghezza: number; altezza: number };
  // Etichetta titolo dentro il riquadro
  etichetta: { x: number; y: number };
  territori: ReadonlyArray<string>;
}

// Coordinate dei territori (centro tessera) nel viewBox 1000x680
export const POSIZIONI: Readonly<Record<string, PosizioneTerritorio>> = {
  // === NORD AMERICA ===
  alaska: { x: 70, y: 100 },
  territori_nordovest: { x: 180, y: 100 },
  groenlandia: { x: 330, y: 70 },
  alberta: { x: 140, y: 180 },
  ontario: { x: 230, y: 180 },
  quebec: { x: 320, y: 180 },
  stati_occidentali: { x: 150, y: 260 },
  stati_orientali: { x: 250, y: 260 },
  america_centrale: { x: 180, y: 340 },

  // === SUD AMERICA ===
  venezuela: { x: 220, y: 410 },
  brasile: { x: 290, y: 470 },
  peru: { x: 220, y: 490 },
  argentina: { x: 250, y: 580 },

  // === EUROPA ===
  islanda: { x: 440, y: 100 },
  scandinavia: { x: 530, y: 100 },
  gran_bretagna: { x: 440, y: 200 },
  europa_settentrionale: { x: 530, y: 190 },
  ucraina: { x: 620, y: 170 },
  europa_occidentale: { x: 440, y: 280 },
  europa_meridionale: { x: 540, y: 280 },

  // === ASIA ===
  urali: { x: 660, y: 110 },
  siberia: { x: 740, y: 90 },
  jacuzia: { x: 830, y: 90 },
  cita: { x: 770, y: 170 },
  kamchatka: { x: 910, y: 110 },
  mongolia: { x: 830, y: 220 },
  giappone: { x: 940, y: 230 },
  afghanistan: { x: 660, y: 240 },
  medio_oriente: { x: 600, y: 320 },
  india: { x: 720, y: 310 },
  cina: { x: 800, y: 290 },
  asia_sudorientale: { x: 830, y: 380 },

  // === AFRICA ===
  africa_settentrionale: { x: 450, y: 380 },
  egitto: { x: 540, y: 360 },
  africa_orientale: { x: 580, y: 450 },
  congo: { x: 500, y: 480 },
  africa_meridionale: { x: 520, y: 570 },
  madagascar: { x: 620, y: 570 },

  // === OCEANIA ===
  indonesia: { x: 820, y: 470 },
  nuova_guinea: { x: 920, y: 480 },
  australia_occidentale: { x: 850, y: 580 },
  australia_orientale: { x: 940, y: 590 },
};

export const CONTINENTI: ReadonlyArray<DefinizioneContinente> = [
  {
    slug: "nord_america",
    nome: "Nord America",
    bonus: 5,
    riquadro: { x: 20, y: 40, larghezza: 360, altezza: 330 },
    etichetta: { x: 40, y: 60 },
    territori: [
      "alaska",
      "territori_nordovest",
      "groenlandia",
      "alberta",
      "ontario",
      "quebec",
      "stati_occidentali",
      "stati_orientali",
      "america_centrale",
    ],
  },
  {
    slug: "sud_america",
    nome: "Sud America",
    bonus: 2,
    riquadro: { x: 170, y: 380, larghezza: 175, altezza: 240 },
    etichetta: { x: 180, y: 397 },
    territori: ["venezuela", "brasile", "peru", "argentina"],
  },
  {
    slug: "europa",
    nome: "Europa",
    bonus: 5,
    riquadro: { x: 400, y: 60, larghezza: 230, altezza: 250 },
    etichetta: { x: 415, y: 80 },
    territori: [
      "islanda",
      "scandinavia",
      "gran_bretagna",
      "europa_settentrionale",
      "ucraina",
      "europa_occidentale",
      "europa_meridionale",
    ],
  },
  {
    slug: "asia",
    nome: "Asia",
    bonus: 7,
    riquadro: { x: 640, y: 50, larghezza: 340, altezza: 360 },
    etichetta: { x: 660, y: 70 },
    territori: [
      "urali",
      "siberia",
      "jacuzia",
      "cita",
      "kamchatka",
      "mongolia",
      "giappone",
      "afghanistan",
      "medio_oriente",
      "india",
      "cina",
      "asia_sudorientale",
    ],
  },
  {
    slug: "africa",
    nome: "Africa",
    bonus: 3,
    riquadro: { x: 410, y: 330, larghezza: 250, altezza: 290 },
    etichetta: { x: 425, y: 350 },
    territori: [
      "africa_settentrionale",
      "egitto",
      "africa_orientale",
      "congo",
      "africa_meridionale",
      "madagascar",
    ],
  },
  {
    slug: "oceania",
    nome: "Oceania",
    bonus: 2,
    riquadro: { x: 790, y: 430, larghezza: 195, altezza: 200 },
    etichetta: { x: 805, y: 450 },
    territori: [
      "indonesia",
      "nuova_guinea",
      "australia_occidentale",
      "australia_orientale",
    ],
  },
];

// Reverse map per rapido lookup territorio → continente
export const CONTINENTE_DI: Readonly<Record<string, SlugContinente>> =
  Object.fromEntries(
    CONTINENTI.flatMap((c) => c.territori.map((t) => [t, c.slug])),
  );

/**
 * Coppie di territori adiacenti (per disegnare le linee di confine).
 *
 * Modellate sulla mappa Risiko EG; ogni coppia è elencata una sola volta
 * (es. solo "alaska-alberta", non anche il reciproco).
 *
 * Le 3 connessioni "intercontinentali" sono inclusi:
 *   - alaska ↔ kamchatka (ponte di Bering)
 *   - africa_settentrionale ↔ europa_occidentale e ↔ europa_meridionale
 *   - asia_sudorientale ↔ indonesia
 *   - argentina ↔ africa_meridionale (no, in EG non c'è)
 */
export const ADIACENZE: ReadonlyArray<readonly [string, string]> = [
  // Nord America
  ["alaska", "territori_nordovest"],
  ["alaska", "alberta"],
  ["alaska", "kamchatka"],
  ["territori_nordovest", "alberta"],
  ["territori_nordovest", "ontario"],
  ["territori_nordovest", "groenlandia"],
  ["groenlandia", "ontario"],
  ["groenlandia", "quebec"],
  ["groenlandia", "islanda"],
  ["alberta", "ontario"],
  ["alberta", "stati_occidentali"],
  ["ontario", "quebec"],
  ["ontario", "stati_occidentali"],
  ["ontario", "stati_orientali"],
  ["quebec", "stati_orientali"],
  ["stati_occidentali", "stati_orientali"],
  ["stati_occidentali", "america_centrale"],
  ["stati_orientali", "america_centrale"],
  ["america_centrale", "venezuela"],
  // Sud America
  ["venezuela", "brasile"],
  ["venezuela", "peru"],
  ["brasile", "peru"],
  ["brasile", "argentina"],
  ["brasile", "africa_settentrionale"],
  ["peru", "argentina"],
  // Europa
  ["islanda", "scandinavia"],
  ["islanda", "gran_bretagna"],
  ["gran_bretagna", "scandinavia"],
  ["gran_bretagna", "europa_settentrionale"],
  ["gran_bretagna", "europa_occidentale"],
  ["scandinavia", "europa_settentrionale"],
  ["scandinavia", "ucraina"],
  ["europa_settentrionale", "ucraina"],
  ["europa_settentrionale", "europa_occidentale"],
  ["europa_settentrionale", "europa_meridionale"],
  ["ucraina", "europa_meridionale"],
  ["ucraina", "urali"],
  ["ucraina", "afghanistan"],
  ["ucraina", "medio_oriente"],
  ["europa_occidentale", "europa_meridionale"],
  ["europa_occidentale", "africa_settentrionale"],
  ["europa_meridionale", "africa_settentrionale"],
  ["europa_meridionale", "egitto"],
  ["europa_meridionale", "medio_oriente"],
  // Africa
  ["africa_settentrionale", "egitto"],
  ["africa_settentrionale", "africa_orientale"],
  ["africa_settentrionale", "congo"],
  ["egitto", "africa_orientale"],
  ["egitto", "medio_oriente"],
  ["africa_orientale", "congo"],
  ["africa_orientale", "africa_meridionale"],
  ["africa_orientale", "madagascar"],
  ["africa_orientale", "medio_oriente"],
  ["congo", "africa_meridionale"],
  ["africa_meridionale", "madagascar"],
  // Asia
  ["urali", "siberia"],
  ["urali", "afghanistan"],
  ["urali", "cina"],
  ["siberia", "jacuzia"],
  ["siberia", "cita"],
  ["siberia", "mongolia"],
  ["siberia", "cina"],
  ["jacuzia", "cita"],
  ["jacuzia", "kamchatka"],
  ["cita", "mongolia"],
  ["cita", "kamchatka"],
  ["kamchatka", "mongolia"],
  ["kamchatka", "giappone"],
  ["mongolia", "giappone"],
  ["mongolia", "cina"],
  ["afghanistan", "medio_oriente"],
  ["afghanistan", "india"],
  ["afghanistan", "cina"],
  ["medio_oriente", "india"],
  ["india", "cina"],
  ["india", "asia_sudorientale"],
  ["cina", "asia_sudorientale"],
  ["asia_sudorientale", "indonesia"],
  // Oceania
  ["indonesia", "nuova_guinea"],
  ["indonesia", "australia_occidentale"],
  ["nuova_guinea", "australia_orientale"],
  ["nuova_guinea", "australia_occidentale"],
  ["australia_occidentale", "australia_orientale"],
];

// Lookup veloce per controllare se due territori sono adiacenti
const setAdiacenze = new Set(
  ADIACENZE.flatMap(([a, b]) => [`${a}|${b}`, `${b}|${a}`]),
);
export function sonoAdiacenti(a: string, b: string): boolean {
  return setAdiacenze.has(`${a}|${b}`);
}

/**
 * Lista di tutti i 42 territori, derivata dall'ordine alfabetico per
 * continente di `CONTINENTI`.
 */
export const TERRITORI_TUTTI: ReadonlyArray<string> = CONTINENTI.flatMap(
  (c) => c.territori,
);
