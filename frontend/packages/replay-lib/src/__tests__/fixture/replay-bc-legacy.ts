/**
 * Replay BC legacy realistico per testare l'adapter `adattaReplayBc`.
 *
 * 2 giocatori, 6 territori, 2 turni, 1 attacco con conquista, 1 tris, 1 move.
 */

import type { ReplayBcLegacy } from "../../adapter-bc.js";

export const ORDINE_TERRITORI_TEST = [
  "alfa",
  "beta",
  "gamma",
  "delta",
  "epsilon",
  "zeta",
];

export function replayBcLegacyEsempio(): ReplayBcLegacy {
  return {
    version: 1,
    startedAt: 1715166000000, // 2024-05-08
    endedAt: 1715167800000,
    players: [
      { name: "Alice", color: "#c0392b", type: "human" },
      { name: "Bob", color: "#2563a8", type: "ai" },
    ],
    missions: ["Conquista 24 territori", "Africa + America del Sud"],
    turns: [
      {
        turn: 1,
        currentPlayer: 0,
        // Setup: alfa, beta a p0; gamma, delta a p1; epsilon, zeta a p0
        // (3 armate ciascuno per p0, 1 a p1)
        territoriesFlat: [
          0, 3, // alfa: p0, 3
          0, 3, // beta: p0, 3
          1, 1, // gamma: p1, 1
          1, 1, // delta: p1, 1
          0, 3, // epsilon: p0, 3
          0, 3, // zeta: p0, 3
        ],
        events: [
          { k: "reinforce", playerIdx: 0, total: 4 },
          {
            k: "attack",
            f: 0, // alfa
            t: 2, // gamma
            attackerIdx: 0,
            defenderIdx: 1,
            conquered: true,
            atkLoss: 0,
            defLoss: 1,
          },
          { k: "card", playerIdx: 0 },
        ],
      },
      {
        turn: 2,
        currentPlayer: 1,
        territoriesFlat: [
          0, 3, // alfa
          0, 3, // beta
          0, 1, // gamma (conquistata)
          1, 1, // delta
          0, 3, // epsilon
          0, 3, // zeta
        ],
        events: [
          { k: "tris", playerIdx: 1, bonus: 6, kind: "uguali" },
          { k: "reinforce", playerIdx: 1, total: 9 },
          { k: "move", f: 3, t: 3, armies: 1 }, // delta→delta no-op
        ],
      },
      // Snapshot finale (isFinal): nessun evento, solo il diff territori.
      {
        turn: 3,
        currentPlayer: -1,
        territoriesFlat: [
          0, 3,
          0, 3,
          0, 1,
          1, 10,
          0, 3,
          0, 3,
        ],
        events: [],
        isFinal: true,
      },
    ],
    winnerIdx: 0,
    winnerReason: "domination",
  };
}
