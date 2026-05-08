/**
 * Barrel di tutti gli API client. Facilita gli import dai consumatori.
 */

export { apiPartite } from "./partite";
export { apiEventi } from "./eventi";
export { apiVideo } from "./video";
export { apiRicostruzione } from "./ricostruzione";
export { apiRisorse } from "./risorse";
export { apiSetupAutomatico } from "./setupAutomatico";
export { apiEsportazione } from "./esportazione";
export { apiAggregazione } from "./aggregazione";
export type {
  PropostaAggregazioneDadi,
  RisultatoAggregazione,
} from "./aggregazione";
export { apiStatistiche } from "./statistiche";
export type {
  StatisticheGiocatore,
  StatistichePartita,
} from "./statistiche";
export { apiValidazione } from "./validazione";
export type {
  CodiceProblema,
  ProblemaCoerenza,
  RisultatoValidazioneCoerenza,
  SeveritaProblema,
} from "./validazione";
export type { TerritorioInfo, ObiettivoInfo } from "./risorse";
export type {
  SetupAutomaticoRichiesta,
  SetupAutomaticoRisposta,
} from "./setupAutomatico";
export { ErroreApi } from "./cliente";
