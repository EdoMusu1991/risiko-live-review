/**
 * Pannello replay: carica il bundle dall'endpoint
 * `/api/partite/{id}/esporta?formato=replay` e monta il `RisikoReplayPlayer`
 * di `@risiko/replay-player`.
 *
 * Integrazione con le altre parti di RL:
 *   - `onCursorChange`: pronto per il sync video (scope C). Per ora logga
 *     solo un counter di chiamate.
 *   - `onTerritorioClick`: filtro eventi per territorio. Cablato al setter
 *     esposto dal genitore.
 *
 * Stato di errore: l'endpoint può non essere disponibile per partite non
 * validate. Mostriamo un avviso non bloccante.
 */

import { useEffect, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

import {
  RisikoReplayPlayer,
  importaBundleDaUrl,
  type BundleReplay,
  type RiferimentoRisikoReplayPlayer,
} from "@risiko/replay-player";

import { apiEsportazione } from "@/api";
import { useRef } from "react";

interface ProprietaPannelloReplay {
  partitaId: string;
  /**
   * Slug del territorio attualmente filtrato nei pannelli laterali.
   * Mostrato come alone scarlatto sulla mappa.
   */
  territorioSelezionato?: string | null;
  /** Click su territorio nella mappa: usato per filtrare gli eventi laterali. */
  onClickTerritorio?: (nome: string) => void;
  /**
   * Callback per il sync esterno con il PlayerVideo. Riceve l'ISO 8601
   * dell'evento corrente; il consumer lo converte in offset secondi e
   * chiama `videoRef.current.saltaA(...)`.
   *
   * Per ora opzionale: se non passato, il replay funziona standalone.
   * In fase C verrà cablato al PlayerVideo già presente in
   * PaginaDettaglioPartita.
   */
  onCursorChange?: (ts_evento: string | null) => void;
  /**
   * Riferimento esposto al genitore per il controllo imperativo (es. il
   * video drives il replay, oppure pulsanti "Vai a inizio turno X" da
   * un pannello esterno).
   */
  controllerRef?: React.MutableRefObject<RiferimentoRisikoReplayPlayer | null>;
}

export function PannelloReplay({
  partitaId,
  territorioSelezionato,
  onClickTerritorio,
  onCursorChange,
  controllerRef,
}: ProprietaPannelloReplay) {
  const [bundle, setBundle] = useState<BundleReplay | null>(null);
  const [stato, setStato] = useState<"caricamento" | "ok" | "errore">(
    "caricamento",
  );
  const [messaggioErrore, setMessaggioErrore] = useState<string | null>(null);
  const [avvisi, setAvvisi] = useState<ReadonlyArray<string>>([]);
  const refInterno = useRef<RiferimentoRisikoReplayPlayer | null>(null);
  const refDaUsare = controllerRef ?? refInterno;

  useEffect(() => {
    let annullato = false;
    setStato("caricamento");
    setBundle(null);
    setMessaggioErrore(null);
    setAvvisi([]);

    importaBundleDaUrl(apiEsportazione.urlReplay(partitaId))
      .then((risultato) => {
        if (annullato) return;
        setBundle(risultato.bundle);
        setAvvisi(risultato.avvisi.map((a) => a.messaggio));
        setStato("ok");
      })
      .catch((errore: unknown) => {
        if (annullato) return;
        const messaggio =
          errore instanceof Error ? errore.message : String(errore);
        setMessaggioErrore(messaggio);
        setStato("errore");
      });

    return () => {
      annullato = true;
    };
  }, [partitaId]);

  if (stato === "caricamento") {
    return (
      <div className="bg-pergamena-chiara border border-inchiostro/15 p-6 flex items-center justify-center gap-3 min-h-[400px]">
        <Loader2 className="animate-spin text-inchiostro-tenue" size={18} />
        <span className="text-inchiostro-tenue text-sm">
          Caricamento del replay…
        </span>
      </div>
    );
  }

  if (stato === "errore" || !bundle) {
    return (
      <div className="bg-pergamena-chiara border border-inchiostro/15 p-6 flex items-start gap-3">
        <AlertTriangle className="text-scarlatto mt-0.5" size={18} />
        <div className="text-sm">
          <div className="font-display font-semibold text-inchiostro mb-1">
            Replay non disponibile
          </div>
          <div className="text-inchiostro-tenue">
            {messaggioErrore ??
              "Il bundle replay non è ancora generabile per questa partita. Solitamente è disponibile dopo la validazione."}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {avvisi.length > 0 ? (
        <div className="bg-pergamena-chiara border border-inchiostro/15 p-3 text-xs text-inchiostro-tenue space-y-1">
          {avvisi.map((m, i) => (
            <div key={i} className="flex items-start gap-2">
              <span className="text-scarlatto mt-0.5">·</span>
              <span>{m}</span>
            </div>
          ))}
        </div>
      ) : null}

      <RisikoReplayPlayer
        ref={refDaUsare}
        bundle={bundle}
        territorioSelezionato={territorioSelezionato ?? null}
        onTerritorioClick={onClickTerritorio}
        onCursorChange={(ts_evento) => onCursorChange?.(ts_evento)}
      />
    </div>
  );
}
