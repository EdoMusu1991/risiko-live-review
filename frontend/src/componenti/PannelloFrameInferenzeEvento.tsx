/**
 * Pannello "Frame inferenze evento" con selettore.
 *
 * Permette all'utente di scegliere un evento validato dal dropdown e
 * vedere il frame raddrizzato corrispondente con sovrapposte le
 * bbox delle inferenze CV.
 *
 * Use case principale: debug singolo evento. "Cosa ha visto la CV
 * sull'evento di attacco al turno 12?"
 */

import { useEffect, useState } from "react";
import { Eye, ImageOff } from "lucide-react";

import { apiEventi, ErroreApi } from "@/api";
import { MessaggioErrore } from "@/componenti/decorativi";
import { VisualizzatoreFrameInferenze } from "@/componenti/VisualizzatoreFrameInferenze";
import type { EventoValidato } from "@/tipi/dominio";

interface ProprietaPannello {
  partitaId: string;
  /**
   * Numero di eventi validati: serve come "trigger" di ricarica.
   * Quando cambia, il pannello ricarica la lista eventi.
   */
  triggerRicarica?: number;
}

export function PannelloFrameInferenzeEvento({
  partitaId,
  triggerRicarica,
}: ProprietaPannello) {
  const [eventi, setEventi] = useState<EventoValidato[]>([]);
  const [eventoSelezionato, setEventoSelezionato] = useState<string>("");
  const [errore, setErrore] = useState<string | null>(null);
  const [caricamento, setCaricamento] = useState(true);

  useEffect(() => {
    let attivo = true;
    setCaricamento(true);
    setErrore(null);
    apiEventi
      .listaValidati(partitaId)
      .then((evs) => {
        if (!attivo) return;
        setEventi(evs);
        // Default: primo evento
        if (evs.length > 0 && eventoSelezionato === "") {
          setEventoSelezionato(evs[0].id);
        }
      })
      .catch((e) => {
        if (attivo) {
          setErrore(
            e instanceof ErroreApi ? e.dettaglio : "Errore caricamento eventi",
          );
        }
      })
      .finally(() => {
        if (attivo) setCaricamento(false);
      });
    return () => {
      attivo = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partitaId, triggerRicarica]);

  if (caricamento && eventi.length === 0) {
    return null;
  }

  if (errore) {
    return (
      <section className="carta p-5 space-y-2">
        <h3 className="etichetta">Frame inferenze evento</h3>
        <MessaggioErrore testo={errore} />
      </section>
    );
  }

  if (eventi.length === 0) {
    // Nessun evento validato: pannello nascosto
    return null;
  }

  const eventoCorrente = eventi.find((e) => e.id === eventoSelezionato);

  return (
    <section className="space-y-3">
      <div className="carta p-4">
        <header className="flex items-center justify-between gap-2 mb-3 flex-wrap">
          <h3 className="etichetta inline-flex items-center gap-2">
            <Eye className="w-3.5 h-3.5" />
            Frame inferenze evento
          </h3>
          <span className="text-xs text-inchiostro-fioco tabular-nums">
            {eventi.length} eventi validati
          </span>
        </header>

        <div className="flex items-center gap-2 flex-wrap">
          <label className="text-xs text-inchiostro-fioco">Evento:</label>
          <select
            value={eventoSelezionato}
            onChange={(e) => setEventoSelezionato(e.target.value)}
            className="flex-1 min-w-0 px-2 py-1 text-sm border border-inchiostro/20 rounded bg-pergamena text-inchiostro"
          >
            {eventi.map((ev) => (
              <option key={ev.id} value={ev.id}>
                {formatTimestamp(ev.ts_evento)} — {ev.tipo}
              </option>
            ))}
          </select>
        </div>

        {eventoCorrente ? (
          <p className="text-[11px] text-inchiostro-fioco mt-2 italic">
            ID:{" "}
            <code className="bg-pergamena-scura/30 px-1 rounded">
              {eventoCorrente.id}
            </code>
          </p>
        ) : null}
      </div>

      {eventoSelezionato ? (
        <VisualizzatoreFrameInferenze
          partitaId={partitaId}
          eventoId={eventoSelezionato}
        />
      ) : (
        <div className="carta p-5 text-center text-inchiostro-fioco italic text-sm">
          <ImageOff className="w-5 h-5 inline mb-2" />
          <br />
          Seleziona un evento per vedere il frame con le inferenze CV.
        </div>
      )}
    </section>
  );
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}
