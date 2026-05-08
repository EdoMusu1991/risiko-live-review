/**
 * Tema visuale dell'app mobile.
 *
 * Speculare al tema "cartografia editoriale" del frontend web ma
 * adattato a touch:
 * - System fonts (San Francisco / Roboto) per leggibilità mobile
 * - Spaziature più ampie per dita
 * - Stessa palette colori (pergamena, inchiostro, scarlatto)
 */

import { Platform } from "react-native";

export const colori = {
  pergamena: "#f4ede0",
  pergamenaChiara: "#faf6ec",
  pergamenaScura: "#ebe1cd",
  inchiostro: "#1a1614",
  inchiostroTenue: "#5c5147",
  inchiostroFioco: "#8a7d70",
  scarlatto: "#b8332a",
  scarlattoChiaro: "#d24a3f",
  navale: "#1f3552",
  bottiglia: "#2c4a36",
  oro: "#a8782a",

  // Linee e divisori
  linea: "rgba(26, 22, 20, 0.12)",
  lineaForte: "rgba(26, 22, 20, 0.30)",

  // Status
  successo: "#2c4a36",
  attenzione: "#a8782a",
  errore: "#b8332a",

  // Colori dei giocatori
  giocatoreRosso: "#b8332a",
  giocatoreBlu: "#1f3552",
  giocatoreVerde: "#2c4a36",
  giocatoreGiallo: "#c8902b",
  giocatoreNero: "#1a1614",
  giocatoreViola: "#5e2d56",
} as const;

export const tipografia = {
  /** Font system per body — ottimo su iOS/Android. */
  fontSans: Platform.select({
    ios: "System",
    android: "Roboto",
    default: "System",
  }),
  /** Font monospaced per timestamp e numeri. */
  fontMono: Platform.select({
    ios: "Menlo",
    android: "monospace",
    default: "monospace",
  }),
  /** Font serif per titoli importanti. */
  fontSerif: Platform.select({
    ios: "Georgia",
    android: "serif",
    default: "serif",
  }),
} as const;

export const spazi = {
  xs: 4,
  s: 8,
  m: 16,
  l: 24,
  xl: 32,
  xxl: 48,
} as const;

export const raggi = {
  niente: 0,
  piccolo: 4,
  medio: 8,
  grande: 16,
} as const;

/** Mappa nome colore giocatore (string) → colore CSS. */
export function coloreDaColoreGiocatore(
  nome: import("@/tipi").ColoreGiocatore,
): string {
  switch (nome) {
    case "rosso":
      return colori.giocatoreRosso;
    case "blu":
      return colori.giocatoreBlu;
    case "verde":
      return colori.giocatoreVerde;
    case "giallo":
      return colori.giocatoreGiallo;
    case "nero":
      return colori.giocatoreNero;
    case "viola":
      return colori.giocatoreViola;
  }
}
