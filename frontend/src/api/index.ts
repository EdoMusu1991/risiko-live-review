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
export { apiClassificaClub, bilancioArmate } from "./classificaClub";
export type {
  ClassificaClub,
  GiocatoreClub,
} from "./classificaClub";
export { apiInferenzeCV } from "./inferenzeCV";
export type {
  AggiornamentoBulkDivergenze,
  DivergenzaInferita,
  InferenzaCV,
  ProblemaInferenza,
  RiepilogoAnalisiBatch,
  RiepilogoDiscrepanze,
  RisoluzioneDivergenza,
  RisultatoBulkDivergenze,
  RisultatoValidazione,
  StatisticheDiscrepanze,
  SuggerimentoEvento,
} from "./inferenzeCV";
export { apiDiagnostica } from "./diagnostica";
export type {
  StatoComponente,
  StatoPipelineCv,
} from "./diagnostica";
export { apiRaddrizzamento } from "./raddrizzamento";
export type {
  RiepilogoBatchRaddrizza,
  RisultatoCalibrazione,
  StatoRaddrizzamento,
} from "./raddrizzamento";
export type { TerritorioInfo, ObiettivoInfo } from "./risorse";
export type {
  SetupAutomaticoRichiesta,
  SetupAutomaticoRisposta,
} from "./setupAutomatico";
export { ErroreApi } from "./cliente";
