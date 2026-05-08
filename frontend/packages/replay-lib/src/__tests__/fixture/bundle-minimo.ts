/**
 * Bundle replay minimo ma realistico, usato dai test di stato/timeline.
 *
 * 2 giocatori (p0=Alice, p1=Bob), 4 territori (alfa, beta, gamma, delta),
 * sequenza completa: setup → partita_inizio → 2 turni → partita_fine.
 *
 * Le carte di esempio sono coerenti con i territori per dare sostanza ai
 * test su `tris_giocato`.
 */

import type { BundleReplay } from "@risiko/eventi-schema";

export function bundleMinimo(): BundleReplay {
  return {
    schema_version: "1.0",
    partita: {
      id: "partita-test-1",
      data_inizio: "2026-05-08T10:00:00.000Z",
      data_fine: "2026-05-08T10:30:00.000Z",
      luogo: null,
      note: null,
    },
    giocatori: [
      { id: "p0", nome: "Alice", colore: "rosso", ordine_seduta: 1 },
      { id: "p1", nome: "Bob", colore: "blu", ordine_seduta: 2 },
    ],
    eventi: [
      // --- Setup territori (4 territori, 2 a testa, 3 armate ciascuno) ---
      {
        id: "e0",
        ts_evento: "2026-05-08T10:00:01.000Z",
        tipo: "territorio_assegnato_inizio",
        dati: { territorio: "alfa", giocatore_id: "p0", n_armate: 3 },
      },
      {
        id: "e1",
        ts_evento: "2026-05-08T10:00:02.000Z",
        tipo: "territorio_assegnato_inizio",
        dati: { territorio: "beta", giocatore_id: "p0", n_armate: 3 },
      },
      {
        id: "e2",
        ts_evento: "2026-05-08T10:00:03.000Z",
        tipo: "territorio_assegnato_inizio",
        dati: { territorio: "gamma", giocatore_id: "p1", n_armate: 3 },
      },
      {
        id: "e3",
        ts_evento: "2026-05-08T10:00:04.000Z",
        tipo: "territorio_assegnato_inizio",
        dati: { territorio: "delta", giocatore_id: "p1", n_armate: 3 },
      },
      // --- Obiettivi ---
      {
        id: "e4",
        ts_evento: "2026-05-08T10:00:05.000Z",
        tipo: "obiettivo_assegnato",
        dati: { giocatore_id: "p0", obiettivo_id: 1 },
      },
      {
        id: "e5",
        ts_evento: "2026-05-08T10:00:06.000Z",
        tipo: "obiettivo_assegnato",
        dati: { giocatore_id: "p1", obiettivo_id: 2 },
      },
      // --- Partita inizia ---
      {
        id: "e6",
        ts_evento: "2026-05-08T10:00:07.000Z",
        tipo: "partita_inizio",
        dati: { primo_giocatore_id: "p0" },
      },
      // --- Turno 1: p0 piazza, attacca, conquista, sposta, pesca ---
      {
        id: "e7",
        ts_evento: "2026-05-08T10:01:00.000Z",
        tipo: "turno_iniziato",
        dati: { giocatore_id: "p0" },
      },
      {
        id: "e8",
        ts_evento: "2026-05-08T10:01:10.000Z",
        tipo: "armate_piazzate",
        dati: { giocatore_id: "p0", territorio: "alfa", n: 3 },
      },
      {
        id: "e9",
        ts_evento: "2026-05-08T10:01:20.000Z",
        tipo: "attacco_risolto",
        dati: {
          giocatore_id: "p0",
          da: "alfa",
          a: "gamma",
          dadi_attaccante: [6, 6, 6],
          dadi_difensore: [1, 1, 1],
        },
      },
      // gamma a 0 armate dopo l'attacco
      {
        id: "e10",
        ts_evento: "2026-05-08T10:01:25.000Z",
        tipo: "territorio_conquistato",
        dati: { giocatore_id: "p0", territorio: "gamma" },
      },
      {
        id: "e11",
        ts_evento: "2026-05-08T10:01:30.000Z",
        tipo: "armate_spostate",
        dati: { giocatore_id: "p0", da: "alfa", a: "gamma", n: 2 },
      },
      {
        id: "e12",
        ts_evento: "2026-05-08T10:01:40.000Z",
        tipo: "carta_pescata",
        dati: {
          giocatore_id: "p0",
          carta: { territorio: "alfa", simbolo: "fante" },
        },
      },
      {
        id: "e13",
        ts_evento: "2026-05-08T10:01:50.000Z",
        tipo: "turno_finito",
        dati: { giocatore_id: "p0" },
      },
      // --- Turno 2: p1 piazza poco e finisce ---
      {
        id: "e14",
        ts_evento: "2026-05-08T10:02:00.000Z",
        tipo: "turno_iniziato",
        dati: { giocatore_id: "p1" },
      },
      {
        id: "e15",
        ts_evento: "2026-05-08T10:02:10.000Z",
        tipo: "armate_piazzate",
        dati: { giocatore_id: "p1", territorio: "delta", n: 1 },
      },
      {
        id: "e16",
        ts_evento: "2026-05-08T10:02:20.000Z",
        tipo: "turno_finito",
        dati: { giocatore_id: "p1" },
      },
      // --- Partita finisce, p0 vince ---
      {
        id: "e17",
        ts_evento: "2026-05-08T10:30:00.000Z",
        tipo: "partita_fine",
        dati: { vincitore_id: "p0" },
      },
    ],
  };
}
