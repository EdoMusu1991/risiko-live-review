/**
 * Costanti del dominio Risiko, parallele a quelle del motore Python.
 *
 * Questi valori sono "fissi" per natura del gioco — la mappa Risiko EG ha
 * sempre 42 territori e 16 obiettivi. Quando l'engine cambierà queste
 * liste, aggiornare a mano.
 */

import type { TipoEvento } from "./dominio";

// === 42 territori canonici, ordinati alfabeticamente per UX dei select ===

export const TERRITORI: ReadonlyArray<string> = [
  "afghanistan",
  "africa_meridionale",
  "africa_orientale",
  "africa_settentrionale",
  "alaska",
  "alberta",
  "america_centrale",
  "argentina",
  "asia_sudorientale",
  "australia_occidentale",
  "australia_orientale",
  "brasile",
  
  "cina",
  "cita",
  "congo",
  "egitto",
  "europa_meridionale",
  "europa_occidentale",
  "europa_settentrionale",
  "giappone",
  "gran_bretagna",
  "groenlandia",
  "india",
  "indonesia",
  "islanda",
  "jacuzia",
  "kamchatka",
  "madagascar",
  "medio_oriente",
  "mongolia",
  "nuova_guinea",
  "ontario",
  "peru",
  "quebec",
  "scandinavia",
  "siberia",
  "stati_orientali",
  "stati_occidentali",
  "territori_nordovest",
  "ucraina",
  "urali",
  "venezuela",
] as const;

export interface Obiettivo {
  id: number;
  nome: string;
}

// I 16 obiettivi del Risiko classico EG, in ordine canonico.
export const OBIETTIVI: ReadonlyArray<Obiettivo> = [
  { id: 1, nome: "Letto" },
  { id: 2, nome: "Elefante" },
  { id: 3, nome: "Ciclista" },
  { id: 4, nome: "Giraffa" },
  { id: 5, nome: "Granchio" },
  { id: 6, nome: "Formula 1" },
  { id: 7, nome: "Befana" },
  { id: 8, nome: "Elvis" },
  { id: 9, nome: "Dromedario con mosca" },
  { id: 10, nome: "Piovra" },
  { id: 11, nome: "Lupo siberiana" },
  { id: 12, nome: "Tappeto" },
  { id: 13, nome: "Guerra fredda" },
  { id: 14, nome: "Motorino" },
  { id: 15, nome: "Aragosta e pesciolino" },
  { id: 16, nome: "Locomotiva" },
] as const;

// === Tipi di evento applicabili al motore (vedi backend dispatcher) ===

export interface DefinizioneTipo {
  tipo: TipoEvento;
  etichetta: string;
  /** True se il motore può applicarlo direttamente (form dedicato disponibile). */
  applicabile: boolean;
  /** Se applicabile, fase tipica di occorrenza (per ordinare il select). */
  faseTipica?: "setup" | "rinforzo" | "attacco" | "spostamento" | "fine_turno" | "altro";
}

export const TIPI_EVENTO: ReadonlyArray<DefinizioneTipo> = [
  // Setup
  {
    tipo: "territorio_assegnato_inizio",
    etichetta: "Territorio assegnato (setup)",
    applicabile: true,
    faseTipica: "setup",
  },
  {
    tipo: "obiettivo_assegnato",
    etichetta: "Obiettivo assegnato",
    applicabile: true,
    faseTipica: "setup",
  },
  {
    tipo: "partita_inizio",
    etichetta: "Partita iniziata",
    applicabile: true,
    faseTipica: "setup",
  },
  // Rinforzo
  {
    tipo: "armate_piazzate",
    etichetta: "Armate piazzate",
    applicabile: true,
    faseTipica: "rinforzo",
  },
  {
    tipo: "tris_giocato",
    etichetta: "Tris giocato",
    applicabile: true,
    faseTipica: "rinforzo",
  },
  // Attacco
  {
    tipo: "attacco_risolto",
    etichetta: "Attacco risolto",
    applicabile: true,
    faseTipica: "attacco",
  },
  // Spostamento
  {
    tipo: "armate_spostate",
    etichetta: "Armate spostate",
    applicabile: true,
    faseTipica: "spostamento",
  },
  // Fine turno
  {
    tipo: "turno_finito",
    etichetta: "Turno finito",
    applicabile: true,
    faseTipica: "fine_turno",
  },
  // Informativi
  {
    tipo: "partita_fine",
    etichetta: "Partita finita (info)",
    applicabile: true,
    faseTipica: "altro",
  },
  {
    tipo: "nota",
    etichetta: "Nota libera",
    applicabile: false,
    faseTipica: "altro",
  },
] as const;

// === Simboli carta ===

export const SIMBOLI_CARTA = ["cannone", "fante", "cavaliere", "jolly"] as const;
export type SimboloCarta = (typeof SIMBOLI_CARTA)[number];

// === Helper di lookup ===

/** Ritorna la fase tipica di un tipo evento, o "altro" se non mappato. */
export function fasePerTipo(
  tipo: TipoEvento,
): NonNullable<DefinizioneTipo["faseTipica"]> {
  return (
    TIPI_EVENTO.find((t) => t.tipo === tipo)?.faseTipica ?? "altro"
  );
}

/** Categorie disponibili per i filtri (in ordine canonico). */
export const FASI_FILTRO = [
  { id: "setup", etichetta: "Setup" },
  { id: "rinforzo", etichetta: "Rinforzo" },
  { id: "attacco", etichetta: "Attacco" },
  { id: "spostamento", etichetta: "Spostamento" },
  { id: "fine_turno", etichetta: "Fine turno" },
  { id: "altro", etichetta: "Altro" },
] as const satisfies ReadonlyArray<{
  id: NonNullable<DefinizioneTipo["faseTipica"]>;
  etichetta: string;
}>;

export type IdFase = (typeof FASI_FILTRO)[number]["id"];
