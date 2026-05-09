/**
 * Modale "Visore replay" — host del player replay.
 *
 * Architettura: questo componente NON contiene la logica del player.
 * Riceve il `bundle` validato dall'hook `useReplayBundle` e lo passa a
 * un componente `playerComponent` come prop. Quando Battle Commander
 * consegnerà la sua replay-lib (scope B/C), basterà cambiare l'import
 * del player nel chiamante — questo componente resta identico.
 *
 * In attesa della lib BC, il default è `MockReplayPlayer` che mostra
 * gli eventi in lista navigabile.
 */

import { ComponentType } from "react";
import { Loader2, X } from "lucide-react";

import type { BundleReplay } from "@risiko/eventi-schema";

import { MockReplayPlayer } from "./MockReplayPlayer";
import { MessaggioErrore } from "./decorativi";
import { useReplayBundle } from "@/hooks/useReplayBundle";

/**
 * Contratto del componente player replay. Pensato per essere
 * implementato sia dal mock attuale sia dalla replay-lib di BC.
 */
export interface ProprietaReplayPlayer {
  bundle: BundleReplay;
  /** Callback chiamata a ogni cambio di posizione. Per sync con video. */
  onCursorChange?: (tsEvento: string, indice: number) => void;
}

interface ProprietaVisoreReplay {
  partitaId: string;
  /** Callback per chiusura modale. */
  onChiudi: () => void;
  /**
   * Componente player. Default = `MockReplayPlayer` (placeholder).
   * Quando arriverà la replay-lib di BC, il chiamante passa qui il
   * `RisikoReplayPlayer` di BC senza toccare questo componente.
   */
  playerComponent?: ComponentType<ProprietaReplayPlayer>;
}

export function VisoreReplay({
  partitaId,
  onChiudi,
  playerComponent: Player = MockReplayPlayer,
}: ProprietaVisoreReplay) {
  const { bundle, caricamento, errore } = useReplayBundle(partitaId);

  return (
    <div
      className="fixed inset-0 z-50 bg-inchiostro/40 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      onClick={onChiudi}
    >
      <div
        className="bg-pergamena border border-inchiostro/20 shadow-cartaHover w-full max-w-3xl max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="flex items-center justify-between px-5 py-4 border-b border-inchiostro/15 flex-shrink-0">
          <div>
            <h2 className="font-display text-lg text-inchiostro">
              Replay partita
            </h2>
            {bundle ? (
              <p className="text-xs text-inchiostro-fioco mt-0.5">
                {bundle.giocatori.length} giocatori · {bundle.eventi.length}{" "}
                eventi
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onChiudi}
            className="p-1.5 rounded text-inchiostro-tenue hover:bg-inchiostro/10 hover:text-inchiostro transition"
            aria-label="Chiudi visore replay"
          >
            <X className="w-5 h-5" />
          </button>
        </header>

        {/* Contenuto scrollabile */}
        <div className="overflow-y-auto p-5">
          {caricamento ? (
            <div className="flex items-center justify-center gap-2 text-inchiostro-fioco py-12">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-sm">Caricamento bundle replay…</span>
            </div>
          ) : null}

          {errore ? (
            <div className="space-y-3">
              <MessaggioErrore testo={errore} />
              <p className="text-[11px] text-inchiostro-fioco italic">
                Suggerimento: se il messaggio cita "drift backend/frontend",
                prova a ricostruire il pacchetto{" "}
                <code className="font-mono">@risiko/eventi-schema</code> e
                ricaricare la pagina.
              </p>
            </div>
          ) : null}

          {bundle ? <Player bundle={bundle} /> : null}
        </div>
      </div>
    </div>
  );
}
