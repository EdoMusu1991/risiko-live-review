/**
 * @risiko/eventi-schema — schema condiviso degli eventi di partita Risiko.
 *
 * Pacchetto consumato da:
 * - **Battle Commander**: modulo replay, per validare eventi in arrivo
 *   da Risiko Live o da partite native BC esportate
 * - **Risiko Live Review**: frontend, per validazione type-safe degli
 *   eventi ricevuti dal backend FastAPI
 */

export * from "./dati.js";
export * from "./evento.js";
export * from "./parsing.js";
