/**
 * Pannello "Linter inferenze CV": validazione cross-check delle
 * inferenze rispetto al motore di gioco.
 *
 * Mostra:
 * - Conteggio errori e warning come badge
 * - Lista problemi raggruppati per codice (espandibile)
 * - Bottone "Cancella inferenza" per ogni inferenza problematica
 *
 * Si nasconde se non ci sono inferenze CV nel DB.
 */

import { useEffect, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Trash2,
} from "lucide-react";

import {
  apiInferenzeCV,
  ErroreApi,
  type ProblemaInferenza,
  type RisultatoValidazione,
} from "@/api";
import { MessaggioErrore } from "@/componenti/decorativi";

interface ProprietaProps {
  partitaId: string;
  /** Trigger ricarica (es. cambio numero inferenze). */
  triggerRicarica?: number;
}

export function PannelloLinterInferenze({
  partitaId,
  triggerRicarica = 0,
}: ProprietaProps) {
  const [risultato, setRisultato] = useState<RisultatoValidazione | null>(null);
  const [caricamento, setCaricamento] = useState(true);
  const [errore, setErrore] = useState<string | null>(null);
  const [aperto, setAperto] = useState(false);
  const [versione, setVersione] = useState(0);

  useEffect(() => {
    let attivo = true;
    setCaricamento(true);
    setErrore(null);
    apiInferenzeCV
      .validaInferenze(partitaId)
      .then((r) => {
        if (attivo) setRisultato(r);
      })
      .catch((e) => {
        if (attivo) {
          setErrore(e instanceof ErroreApi ? e.dettaglio : "Errore");
        }
      })
      .finally(() => {
        if (attivo) setCaricamento(false);
      });
    return () => {
      attivo = false;
    };
  }, [partitaId, triggerRicarica, versione]);

  async function cancellaInferenza(inferenzaId: string) {
    if (!confirm("Cancellare questa inferenza?")) return;
    try {
      await apiInferenzeCV.cancellaInferenza(partitaId, inferenzaId);
      setVersione((v) => v + 1);
    } catch (e) {
      setErrore(e instanceof ErroreApi ? e.dettaglio : "Errore cancellazione");
    }
  }

  if (caricamento && risultato === null) {
    return null;
  }

  if (errore !== null) {
    return (
      <section className="carta p-5 space-y-2">
        <h3 className="etichetta">Linter inferenze</h3>
        <MessaggioErrore testo={errore} />
      </section>
    );
  }

  if (risultato === null || risultato.n_inferenze === 0) {
    return null;
  }

  const tutto_ok = risultato.n_problemi === 0;

  return (
    <section className="carta p-4">
      <button
        type="button"
        onClick={() => setAperto((v) => !v)}
        className="w-full flex items-center justify-between gap-2 text-left"
      >
        <div className="flex items-center gap-2">
          <h3 className="etichetta inline-flex items-center gap-2">
            {tutto_ok ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-bottiglia" />
            ) : (
              <AlertCircle className="w-3.5 h-3.5 text-scarlatto" />
            )}
            Linter inferenze CV
          </h3>
          <span className="text-xs text-inchiostro-fioco">
            ({risultato.n_inferenze} totali)
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {risultato.n_error > 0 ? (
            <span className="px-1.5 py-0.5 bg-scarlatto/10 text-scarlatto rounded inline-flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              {risultato.n_error} errori
            </span>
          ) : null}
          {risultato.n_warning > 0 ? (
            <span className="px-1.5 py-0.5 bg-bronzo/10 text-bronzo rounded inline-flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />
              {risultato.n_warning} avvisi
            </span>
          ) : null}
          {tutto_ok ? (
            <span className="text-bottiglia text-xs">tutto ok</span>
          ) : null}
          <ChevronDown
            className={`w-3.5 h-3.5 transition-transform ${
              aperto ? "rotate-180" : ""
            }`}
          />
        </div>
      </button>

      {aperto && !tutto_ok ? (
        <div className="mt-3 space-y-2">
          {!risultato.territori_validi_disponibili ? (
            <p className="text-xs text-inchiostro-fioco italic">
              ⓘ Snapshot motore non disponibile — il check sui territori
              esistenti e' stato saltato. Ricostruisci la partita per il
              controllo completo.
            </p>
          ) : null}

          <ListaProblemi
            problemi={risultato.problemi}
            onCancellaInferenza={cancellaInferenza}
          />

          {risultato.troncato ? (
            <p className="text-xs text-inchiostro-fioco italic">
              ⓘ Lista troncata a 200 problemi. Risolvi i piu' gravi e
              riesegui la validazione.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

// === Sotto-componenti ===

function ListaProblemi({
  problemi,
  onCancellaInferenza,
}: {
  problemi: ProblemaInferenza[];
  onCancellaInferenza: (inferenzaId: string) => void;
}) {
  // Raggruppa per codice
  const perCodice = new Map<string, ProblemaInferenza[]>();
  for (const p of problemi) {
    const lista = perCodice.get(p.codice) ?? [];
    lista.push(p);
    perCodice.set(p.codice, lista);
  }

  return (
    <div className="space-y-2">
      {Array.from(perCodice.entries()).map(([codice, lista]) => (
        <details
          key={codice}
          className="border border-inchiostro/10 rounded p-2 bg-pergamena-scura/20"
        >
          <summary className="cursor-pointer text-xs hover:text-inchiostro flex items-center gap-1.5">
            {lista[0].severita === "error" ? (
              <AlertCircle className="w-3 h-3 text-scarlatto" />
            ) : (
              <AlertTriangle className="w-3 h-3 text-bronzo" />
            )}
            <code className="font-mono text-[11px]">{codice}</code>
            <span className="text-inchiostro-fioco">
              ({lista.length} occorrenze)
            </span>
          </summary>
          <ul className="mt-2 space-y-1 text-[11px]">
            {lista.slice(0, 20).map((p) => (
              <li
                key={p.inferenza_id}
                className="flex items-start gap-2 py-1 border-t border-inchiostro/5"
              >
                <code className="text-inchiostro-fioco font-mono flex-shrink-0">
                  {p.inferenza_id.slice(0, 8)}
                </code>
                <span className="flex-1 text-inchiostro-tenue">
                  {p.descrizione}
                </span>
                <button
                  type="button"
                  onClick={() => onCancellaInferenza(p.inferenza_id)}
                  className="text-inchiostro-fioco hover:text-scarlatto p-0.5 flex-shrink-0"
                  title="Cancella questa inferenza"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </li>
            ))}
            {lista.length > 20 ? (
              <li className="text-inchiostro-fioco italic px-2">
                + altri {lista.length - 20} casi
              </li>
            ) : null}
          </ul>
        </details>
      ))}
    </div>
  );
}
