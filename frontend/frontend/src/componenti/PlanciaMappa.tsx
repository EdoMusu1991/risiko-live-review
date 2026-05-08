/**
 * Plancia mappa di RL — adesso un thin re-export di `@risiko/map-classico`.
 *
 * Il componente è stato promosso a libreria workspace condivisa fra
 * Risiko Live e Battle Commander. L'implementazione è identica
 * byte-per-byte a quella che era qui in v0.1; questo file resta come
 * ponte per non rompere i 2 import esistenti in `PannelloStatoFinale.tsx`.
 *
 * Per il viewer replay completo (mappa + scrubber + autoplay + sync
 * video hooks) vedi `@risiko/replay-player` e il suo `RisikoReplayPlayer`.
 */

export {
  MappaRisikoClassico as PlanciaMappa,
  type PropsMappaRisikoClassico as ProprietaPlanciaMappa,
} from "@risiko/map-classico";
