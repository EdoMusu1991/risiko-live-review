/**
 * Modale per il workflow "evento aggiunto" smart.
 *
 * Quando l'utente clicca "evento aggiunto" su una divergenza, invece
 * di marcare semplicemente la risoluzione, apriamo questa modale che:
 * 1. Chiama POST suggerisci-evento
 * 2. Mostra il candidato (tipo + dati + commento + confidence)
 * 3. Permette modifica manuale di JSON dati
 * 4. Click "Crea evento" → POST /eventi-validati + PATCH risoluzione
 *    a "evento_aggiunto"
 *
 * Eliminato: l'utente puo' anche solo marcare risoluzione senza creare
 * l'evento (link "Salta creazione").
 */

import { useEffect, useState } from "react";
import { Loader2, Plus, Sparkles, X } from "lucide-react";

import {
  apiEventi,
  apiInferenzeCV,
  ErroreApi,
  type DivergenzaInferita,
  type SuggerimentoEvento,
} from "@/api";
import { MessaggioErrore } from "@/componenti/decorativi";
import type { TipoEvento } from "@/tipi/dominio";

interface ProprietaModale {
  partitaId: string;
  divergenza: DivergenzaInferita;
  onChiudi: () => void;
  /** Chiamata dopo successo (per ricarica della lista). */
  onCompletato: () => void;
}

export function ModaleEventoAggiunto({
  partitaId,
  divergenza,
  onChiudi,
  onCompletato,
}: ProprietaModale) {
  const [suggerimento, setSuggerimento] = useState<SuggerimentoEvento | null>(
    null,
  );
  const [caricamento, setCaricamento] = useState(true);
  const [errore, setErrore] = useState<string | null>(null);

  const [tipoEvento, setTipoEvento] = useState<string>("");
  const [datiTesto, setDatiTesto] = useState<string>("{}");
  const [inSalvataggio, setInSalvataggio] = useState(false);

  useEffect(() => {
    apiInferenzeCV
      .suggerisciEvento(partitaId, divergenza.id)
      .then((s) => {
        setSuggerimento(s);
        setTipoEvento(s.tipo ?? "");
        setDatiTesto(JSON.stringify(s.dati ?? {}, null, 2));
      })
      .catch((e) => {
        setErrore(
          e instanceof ErroreApi ? e.dettaglio : "Errore suggerimento",
        );
      })
      .finally(() => setCaricamento(false));
  }, [partitaId, divergenza.id]);

  async function creaEvento() {
    setInSalvataggio(true);
    setErrore(null);
    try {
      const dati = JSON.parse(datiTesto);
      // Crea evento al timestamp della divergenza (now se non disponibile)
      const ts = new Date().toISOString();
      await apiEventi.creaValidato(partitaId, {
        ts_evento: ts,
        tipo: tipoEvento as TipoEvento,
        dati,
        validato_da: "review-cv",
      });
      // Marca divergenza come "evento_aggiunto"
      await apiInferenzeCV.aggiornaDivergenza(
        partitaId,
        divergenza.id,
        "evento_aggiunto",
        `Evento creato dal pannello CV (${tipoEvento})`,
      );
      onCompletato();
      onChiudi();
    } catch (e) {
      if (e instanceof SyntaxError) {
        setErrore(`JSON non valido: ${e.message}`);
      } else if (e instanceof ErroreApi) {
        setErrore(e.dettaglio);
      } else {
        setErrore("Errore imprevisto");
      }
    } finally {
      setInSalvataggio(false);
    }
  }

  async function saltaCreazione() {
    setInSalvataggio(true);
    setErrore(null);
    try {
      await apiInferenzeCV.aggiornaDivergenza(
        partitaId,
        divergenza.id,
        "evento_aggiunto",
        "Evento gia' presente o gestito altrove (skip).",
      );
      onCompletato();
      onChiudi();
    } catch (e) {
      setErrore(e instanceof ErroreApi ? e.dettaglio : "Errore");
    } finally {
      setInSalvataggio(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-inchiostro/40 flex items-center justify-center p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onChiudi();
      }}
    >
      <div className="bg-pergamena rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        <header className="px-5 py-3 border-b border-inchiostro/10 flex items-center justify-between">
          <h2 className="font-display text-lg text-inchiostro inline-flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Aggiungi evento mancante
          </h2>
          <button
            type="button"
            onClick={onChiudi}
            className="p-1 hover:bg-inchiostro/5 rounded text-inchiostro-fioco"
          >
            <X className="w-4 h-4" />
          </button>
        </header>

        <div className="px-5 py-4 overflow-y-auto flex-1 space-y-4">
          <DescriDivergenza divergenza={divergenza} />

          {caricamento ? (
            <div className="flex items-center gap-2 text-inchiostro-fioco py-4">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-sm">
                Calcolo suggerimento dal backend…
              </span>
            </div>
          ) : null}

          {errore ? <MessaggioErrore testo={errore} /> : null}

          {suggerimento ? (
            <Suggerimento
              suggerimento={suggerimento}
              tipoEvento={tipoEvento}
              datiTesto={datiTesto}
              onTipoCambia={setTipoEvento}
              onDatiCambia={setDatiTesto}
            />
          ) : null}
        </div>

        <footer className="px-5 py-3 border-t border-inchiostro/10 flex items-center justify-between gap-2 flex-wrap">
          <button
            type="button"
            onClick={saltaCreazione}
            disabled={inSalvataggio}
            className="text-xs text-inchiostro-fioco underline-offset-2 hover:underline disabled:opacity-50"
          >
            Salta creazione (marca solo come risolta)
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onChiudi}
              disabled={inSalvataggio}
              className="btn-secondario"
            >
              Annulla
            </button>
            <button
              type="button"
              onClick={creaEvento}
              disabled={inSalvataggio || tipoEvento === ""}
              className="btn-primario disabled:opacity-50"
            >
              {inSalvataggio ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Plus className="w-3.5 h-3.5" />
              )}
              Crea evento + risolvi
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}

// === Sotto-componenti ===

function DescriDivergenza({ divergenza: d }: { divergenza: DivergenzaInferita }) {
  const segno = d.valore_cv > d.valore_motore ? "+" : "−";
  return (
    <div className="bg-pergamena-scura/30 rounded p-3 text-sm">
      <div className="etichetta mb-1">Divergenza da risolvere</div>
      <div className="text-inchiostro">
        <strong className="capitalize">{d.territorio.replace(/_/g, " ")}</strong>
        {" "}
        <span className="text-inchiostro-fioco">({d.colore})</span>:
        motore vede{" "}
        <strong className="tabular-nums">{d.valore_motore}</strong> armate,
        CV ne vede{" "}
        <strong className="tabular-nums">{d.valore_cv}</strong>
        {" "}
        <span className="text-scarlatto tabular-nums">
          ({segno}
          {d.delta_assoluto})
        </span>
      </div>
    </div>
  );
}

function Suggerimento({
  suggerimento,
  tipoEvento,
  datiTesto,
  onTipoCambia,
  onDatiCambia,
}: {
  suggerimento: SuggerimentoEvento;
  tipoEvento: string;
  datiTesto: string;
  onTipoCambia: (t: string) => void;
  onDatiCambia: (s: string) => void;
}) {
  const conf = suggerimento.confidence_suggerimento;
  const confColore =
    conf >= 0.7
      ? "text-bottiglia"
      : conf >= 0.5
        ? "text-bronzo"
        : "text-scarlatto";

  return (
    <div className="space-y-3">
      <div className="bg-bottiglia/5 border border-bottiglia/20 rounded p-3 text-sm space-y-1">
        <div className="inline-flex items-center gap-1 text-bottiglia">
          <Sparkles className="w-3.5 h-3.5" />
          <strong>Suggerimento del backend</strong>
          <span className={`text-xs ${confColore}`}>
            (confidence {(conf * 100).toFixed(0)}%)
          </span>
        </div>
        <p className="text-inchiostro-tenue text-xs italic">
          {suggerimento.commento}
        </p>
      </div>

      <div>
        <label className="etichetta block mb-1">Tipo evento</label>
        <select
          value={tipoEvento}
          onChange={(e) => onTipoCambia(e.target.value)}
          className="w-full px-2 py-1.5 border border-inchiostro/20 rounded bg-pergamena text-inchiostro"
        >
          <option value="">— scegli un tipo —</option>
          <option value="armate_piazzate">armate_piazzate</option>
          <option value="armate_spostate">armate_spostate</option>
          <option value="attacco_risolto">attacco_risolto</option>
          <option value="territorio_conquistato">territorio_conquistato</option>
          <option value="carta_pescata">carta_pescata</option>
          <option value="tris_giocato">tris_giocato</option>
          <option value="nota">nota</option>
        </select>
      </div>

      <div>
        <label className="etichetta block mb-1">Dati evento (JSON)</label>
        <textarea
          value={datiTesto}
          onChange={(e) => onDatiCambia(e.target.value)}
          rows={6}
          className="w-full px-2 py-1.5 border border-inchiostro/20 rounded bg-pergamena text-inchiostro font-mono text-xs tabular-nums"
          spellCheck={false}
        />
        <p className="text-[10px] text-inchiostro-fioco italic mt-1">
          Modifica i campi se servono aggiustamenti (es. specificare il
          territorio destinazione su un attacco/spostamento).
        </p>
      </div>
    </div>
  );
}
