/**
 * Pannello "Proposte di aggregazione dadi BLE".
 *
 * Mostra le proposte di `attacco_risolto` candidati generate dal
 * backend a partire dagli eventi grezzi `DADI_LANCIATI` di fonte BLE.
 *
 * Ogni proposta è cliccabile:
 * - Click sul timestamp → seek del video alla posizione
 * - "Accetta" → apre form di completamento (giocatore, territori da/a)
 *               e crea l'EventoValidato corrispondente
 * - "Rifiuta" → marca gli eventi grezzi come ignorati (eliminandoli o
 *               flaggandoli, a discrezione del flusso futuro)
 *
 * Per ora il flusso "Accetta" rimanda alla form FormEvento esistente
 * (riutilizzo). Il "Rifiuta" elimina i grezzi.
 */

import { useState } from "react";
import { Sparkles, RefreshCw, ChevronRight, Trash2 } from "lucide-react";

import { apiAggregazione, ErroreApi } from "@/api";
import type {
  PropostaAggregazioneDadi,
  RisultatoAggregazione,
} from "@/api/aggregazione";
import { apiEventi } from "@/api/eventi";
import { MessaggioErrore } from "./decorativi";

interface ProprietaPannelloProposte {
  partitaId: string;
  /** Callback per cercare nel video alla posizione data. */
  onSeek?: (ts: string) => void;
  /**
   * Callback chiamato quando l'utente accetta una proposta.
   * Riceve la proposta completa: il chiamante deve aprire un form
   * per completare i campi mancanti (giocatore, territori) e poi
   * creare l'EventoValidato.
   */
  onAccetta: (proposta: PropostaAggregazioneDadi) => void;
  /** Chiamato dopo "Rifiuta" per ricaricare la lista eventi grezzi. */
  onEventiCambiati?: () => void;
}

export function PannelloProposteAggregazione({
  partitaId,
  onSeek,
  onAccetta,
  onEventiCambiati,
}: ProprietaPannelloProposte) {
  const [risultato, setRisultato] = useState<RisultatoAggregazione | null>(
    null,
  );
  const [caricamento, setCaricamento] = useState(false);
  const [errore, setErrore] = useState<string | null>(null);
  const [sogliaSecondi, setSogliaSecondi] = useState(3);

  async function richiedi() {
    setErrore(null);
    setCaricamento(true);
    try {
      const r = await apiAggregazione.proponi(partitaId, sogliaSecondi);
      setRisultato(r);
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi
          ? e.dettaglio
          : "Errore durante la richiesta di aggregazione";
      setErrore(messaggio);
    } finally {
      setCaricamento(false);
    }
  }

  async function rifiuta(proposta: PropostaAggregazioneDadi) {
    if (
      !window.confirm(
        `Eliminare i ${proposta.eventi_grezzi_id.length} eventi grezzi di questa proposta? Non potranno essere recuperati.`,
      )
    ) {
      return;
    }
    try {
      // Elimina tutti gli eventi grezzi del cluster in una sola
      // chiamata atomica (un round-trip invece di N).
      await apiEventi.eliminaGrezziBatch(partitaId, proposta.eventi_grezzi_id);
      // Ricarica le proposte rimanenti e notifica il padre
      await richiedi();
      onEventiCambiati?.();
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi
          ? e.dettaglio
          : "Errore durante l'eliminazione degli eventi grezzi";
      setErrore(messaggio);
    }
  }

  /**
   * Elimina TUTTI gli eventi grezzi di TUTTE le proposte in un colpo
   * solo. Utile quando l'utente decide che i dadi BLE sono compromessi
   * e vuole ricominciare la review manuale degli attacchi da zero.
   */
  async function rifiutaTutte() {
    if (!risultato || risultato.proposte.length === 0) return;
    const tuttiIds = risultato.proposte.flatMap((p) => p.eventi_grezzi_id);
    if (
      !window.confirm(
        `Eliminare TUTTE le ${risultato.proposte.length} proposte (${tuttiIds.length} eventi grezzi)? Non potranno essere recuperati.`,
      )
    ) {
      return;
    }
    try {
      await apiEventi.eliminaGrezziBatch(partitaId, tuttiIds);
      await richiedi();
      onEventiCambiati?.();
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi
          ? e.dettaglio
          : "Errore durante l'eliminazione batch";
      setErrore(messaggio);
    }
  }

  return (
    <div className="border border-inchiostro/15 bg-pergamena-chiara">
      {/* Intestazione */}
      <div className="px-4 py-3 border-b border-inchiostro/15 bg-pergamena flex items-center gap-3">
        <Sparkles className="w-4 h-4 text-scarlatto" />
        <h3 className="font-serif text-sm font-medium uppercase tracking-wider">
          Proposte aggregazione BLE
        </h3>
        <div className="ml-auto flex items-center gap-2">
          <label className="text-xs text-inchiostro-tenue">
            Gap max{" "}
            <input
              type="number"
              min={0.1}
              max={60}
              step={0.5}
              value={sogliaSecondi}
              onChange={(e) =>
                setSogliaSecondi(Math.max(0.1, Number(e.target.value)))
              }
              className="w-14 px-1 py-0.5 bg-pergamena border border-inchiostro/20 text-xs font-mono"
            />{" "}
            sec
          </label>
          <button
            onClick={richiedi}
            disabled={caricamento}
            className="px-3 py-1 text-xs bg-scarlatto text-pergamena-chiara hover:bg-scarlatto/90 disabled:opacity-50 transition-colors flex items-center gap-1.5"
          >
            <RefreshCw
              className={`w-3 h-3 ${caricamento ? "animate-spin" : ""}`}
            />
            {caricamento ? "Calcolo…" : "Calcola"}
          </button>
        </div>
      </div>

      {/* Stato vuoto */}
      {!risultato && !caricamento && !errore && (
        <div className="px-4 py-6 text-center text-sm text-inchiostro-tenue italic">
          Premi <span className="font-medium">Calcola</span> per analizzare gli
          eventi BLE non validati e ottenere proposte di attacchi risolti.
        </div>
      )}

      {errore && (
        <div className="px-4 py-3">
          <MessaggioErrore testo={errore} />
        </div>
      )}

      {/* Riepilogo */}
      {risultato && (
        <div className="px-4 py-2 bg-pergamena/50 border-b border-inchiostro/10 text-xs text-inchiostro-tenue flex items-center justify-between gap-3">
          <div>
            {risultato.n_eventi_grezzi_analizzati === 0 ? (
              <>Nessun evento BLE non validato da raggruppare.</>
            ) : (
              <>
                Analizzati <strong>{risultato.n_eventi_grezzi_analizzati}</strong>{" "}
                eventi BLE → <strong>{risultato.n_proposte}</strong> proposte
                generate.
              </>
            )}
          </div>
          {risultato.proposte.length > 1 ? (
            <button
              type="button"
              onClick={rifiutaTutte}
              className="text-xs text-scarlatto hover:text-scarlatto-scuro underline-offset-2 hover:underline transition"
              title="Elimina TUTTE le proposte in un colpo solo (utile se i dadi BLE sono compromessi)"
            >
              Rifiuta tutte ({risultato.proposte.length})
            </button>
          ) : null}
        </div>
      )}

      {/* Lista proposte */}
      {risultato && risultato.proposte.length > 0 && (
        <ul className="divide-y divide-inchiostro/10">
          {risultato.proposte.map((p, i) => (
            <ListaProposta
              key={`${p.ts_inizio}-${i}`}
              proposta={p}
              onSeek={onSeek}
              onAccetta={onAccetta}
              onRifiuta={rifiuta}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

interface ProprietaListaProposta {
  proposta: PropostaAggregazioneDadi;
  onSeek?: (ts: string) => void;
  onAccetta: (proposta: PropostaAggregazioneDadi) => void;
  onRifiuta: (proposta: PropostaAggregazioneDadi) => void;
}

function ListaProposta({
  proposta: p,
  onSeek,
  onAccetta,
  onRifiuta,
}: ProprietaListaProposta) {
  const ora = new Date(p.ts_inizio).toLocaleTimeString("it-IT", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const durataMs =
    new Date(p.ts_fine).getTime() - new Date(p.ts_inizio).getTime();

  // Soglie di colore confidenza (tipografia editoriale: niente badge tondi)
  const colorConfidenza =
    p.confidenza >= 0.9
      ? "text-foresta"
      : p.confidenza >= 0.5
        ? "text-inchiostro"
        : "text-scarlatto";

  return (
    <li className="px-4 py-3 hover:bg-pergamena/40 transition-colors">
      <div className="flex items-start gap-3">
        {/* Timestamp cliccabile */}
        <button
          onClick={() => onSeek?.(p.ts_inizio)}
          className="font-mono text-xs text-inchiostro-tenue hover:text-scarlatto transition-colors mt-0.5 shrink-0"
          title="Vai al video a questo punto"
        >
          {ora}
        </button>

        {/* Contenuto principale */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-3 flex-wrap">
            {/* Dadi attaccante */}
            <span className="text-sm">
              <span className="text-inchiostro-tenue text-xs uppercase tracking-wider mr-1.5">
                Att
              </span>
              {p.dadi_attaccante.length > 0 ? (
                <span className="font-mono font-medium">
                  {p.dadi_attaccante.join(" · ")}
                </span>
              ) : (
                <span className="text-inchiostro-tenue italic">—</span>
              )}
            </span>

            <span className="text-inchiostro/30">vs</span>

            {/* Dadi difensore */}
            <span className="text-sm">
              <span className="text-inchiostro-tenue text-xs uppercase tracking-wider mr-1.5">
                Dif
              </span>
              {p.dadi_difensore.length > 0 ? (
                <span className="font-mono font-medium">
                  {p.dadi_difensore.join(" · ")}
                </span>
              ) : (
                <span className="text-inchiostro-tenue italic">—</span>
              )}
            </span>

            {/* Confidenza */}
            <span className={`text-xs ml-auto ${colorConfidenza}`}>
              {Math.round(p.confidenza * 100)}%
            </span>
          </div>

          {/* Note di clustering */}
          {p.note.length > 0 && (
            <ul className="mt-1.5 space-y-0.5">
              {p.note.map((n, i) => (
                <li
                  key={i}
                  className="text-xs text-scarlatto/80 flex items-start gap-1.5"
                >
                  <span className="text-scarlatto/40">•</span>
                  <span>{n}</span>
                </li>
              ))}
            </ul>
          )}

          {/* Meta */}
          <div className="mt-1 text-xs text-inchiostro-tenue/80">
            {p.eventi_grezzi_id.length} eventi BLE
            {durataMs > 100 && <> · finestra {(durataMs / 1000).toFixed(1)}s</>}
          </div>
        </div>

        {/* Azioni */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => onRifiuta(p)}
            className="p-1.5 text-inchiostro-tenue hover:text-scarlatto transition-colors"
            title="Rifiuta proposta (elimina eventi grezzi)"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => onAccetta(p)}
            className="px-3 py-1 text-xs bg-inchiostro text-pergamena-chiara hover:bg-scarlatto transition-colors flex items-center gap-1"
            title="Accetta proposta (apri form completamento)"
          >
            Accetta
            <ChevronRight className="w-3 h-3" />
          </button>
        </div>
      </div>
    </li>
  );
}
