/**
 * Visualizzatore del frame raddrizzato per un evento, con sovrapposte
 * le bbox delle inferenze CV.
 *
 * Usato come pannello di dettaglio quando l'utente vuole vedere "cosa
 * ha visto la CV" su un frame specifico, per debug della pipeline.
 *
 * Tre stati:
 * 1. Nessun frame raddrizzato → invita a calibrare/analizzare
 * 2. Frame disponibile, niente inferenze → mostra solo l'immagine
 * 3. Frame + inferenze → overlay bbox cliccabili con tooltip
 */

import { useEffect, useState } from "react";
import { Loader2, MousePointerClick } from "lucide-react";

import {
  apiInferenzeCV,
  apiRaddrizzamento,
  ErroreApi,
  type InferenzaCV,
} from "@/api";
import { MessaggioErrore } from "@/componenti/decorativi";

interface ProprietaVisualizzatore {
  partitaId: string;
  eventoId: string;
}

const COLORI_BBOX: Record<string, string> = {
  rosso: "#c4453a",
  blu: "#3a5fc4",
  verde: "#2d7a4f",
  giallo: "#c4a73a",
  nero: "#2a2a2a",
  viola: "#7a3ac4",
};

export function VisualizzatoreFrameInferenze({
  partitaId,
  eventoId,
}: ProprietaVisualizzatore) {
  const [inferenze, setInferenze] = useState<InferenzaCV[]>([]);
  const [caricamento, setCaricamento] = useState(true);
  const [errore, setErrore] = useState<string | null>(null);
  const [selezionata, setSelezionata] = useState<InferenzaCV | null>(null);

  useEffect(() => {
    let attivo = true;
    setCaricamento(true);
    setErrore(null);
    setSelezionata(null);
    apiInferenzeCV
      .lista(partitaId, { eventoValidatoId: eventoId })
      .then((r) => {
        if (attivo) setInferenze(r);
      })
      .catch((e) => {
        if (attivo) {
          setErrore(
            e instanceof ErroreApi ? e.dettaglio : "Errore caricamento",
          );
        }
      })
      .finally(() => {
        if (attivo) setCaricamento(false);
      });
    return () => {
      attivo = false;
    };
  }, [partitaId, eventoId]);

  const urlFrame = apiRaddrizzamento.urlFrameRaddrizzatoPerEvento(
    partitaId,
    eventoId,
  );

  return (
    <section className="carta p-5 space-y-3">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="etichetta">Frame raddrizzato + inferenze CV</h3>
        <span className="text-xs text-inchiostro-fioco tabular-nums">
          {inferenze.length} detection
        </span>
      </header>

      {caricamento ? (
        <div className="flex items-center gap-2 text-inchiostro-fioco py-3">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Caricamento inferenze…</span>
        </div>
      ) : null}

      {errore ? <MessaggioErrore testo={errore} /> : null}

      <FrameConBbox
        urlFrame={urlFrame}
        inferenze={inferenze}
        selezionata={selezionata}
        onSelezionaInferenza={setSelezionata}
      />

      {selezionata ? (
        <DettaglioInferenza inferenza={selezionata} />
      ) : inferenze.length > 0 ? (
        <p className="text-xs text-inchiostro-fioco italic inline-flex items-center gap-1">
          <MousePointerClick className="w-3 h-3" />
          Click su una bbox per i dettagli
        </p>
      ) : null}
    </section>
  );
}

// === Sotto-componenti ===

function FrameConBbox({
  urlFrame,
  inferenze,
  selezionata,
  onSelezionaInferenza,
}: {
  urlFrame: string;
  inferenze: InferenzaCV[];
  selezionata: InferenzaCV | null;
  onSelezionaInferenza: (inf: InferenzaCV | null) => void;
}) {
  const [dimensioniFrame, setDimensioniFrame] = useState<
    { w: number; h: number } | null
  >(null);
  const [errore, setErrore] = useState(false);

  if (errore) {
    return (
      <div className="rounded border border-inchiostro/10 bg-pergamena-scura/20 p-6 text-center">
        <p className="text-sm text-inchiostro-fioco italic">
          Frame raddrizzato non disponibile. Calibra la partita e lancia
          "Analizza CV" nel pannello discrepanze.
        </p>
      </div>
    );
  }

  return (
    <div className="relative rounded border border-inchiostro/10 bg-inchiostro/5 overflow-hidden">
      <img
        src={urlFrame}
        alt="Frame raddrizzato"
        className="w-full h-auto block"
        onLoad={(e) => {
          const img = e.currentTarget as HTMLImageElement;
          setDimensioniFrame({
            w: img.naturalWidth,
            h: img.naturalHeight,
          });
        }}
        onError={() => setErrore(true)}
      />
      {dimensioniFrame !== null
        ? inferenze.map((inf) => (
            <Bbox
              key={inf.id}
              inferenza={inf}
              dimensioniFrame={dimensioniFrame}
              selezionata={selezionata?.id === inf.id}
              onClick={() =>
                onSelezionaInferenza(
                  selezionata?.id === inf.id ? null : inf,
                )
              }
            />
          ))
        : null}
    </div>
  );
}

function Bbox({
  inferenza,
  dimensioniFrame,
  selezionata,
  onClick,
}: {
  inferenza: InferenzaCV;
  dimensioniFrame: { w: number; h: number };
  selezionata: boolean;
  onClick: () => void;
}) {
  const [x, y, w, h] = inferenza.bbox;
  // Le bbox sono in coordinate del frame raddrizzato (pixel originali).
  // Le scaliamo a percentuale per il rendering responsive.
  const sx = (x / dimensioniFrame.w) * 100;
  const sy = (y / dimensioniFrame.h) * 100;
  const sw = (w / dimensioniFrame.w) * 100;
  const sh = (h / dimensioniFrame.h) * 100;

  const colore = inferenza.colore
    ? COLORI_BBOX[inferenza.colore] ?? "#888"
    : "#888";

  // Spessore variabile in base a confidence (2-4px)
  const spessore = 2 + Math.round(inferenza.confidence * 2);

  return (
    <button
      type="button"
      onClick={onClick}
      className="absolute transition-all hover:opacity-100 focus:outline-none"
      style={{
        left: `${sx}%`,
        top: `${sy}%`,
        width: `${sw}%`,
        height: `${sh}%`,
        border: `${spessore}px solid ${colore}`,
        backgroundColor: selezionata ? `${colore}30` : "transparent",
        opacity: selezionata ? 1 : 0.7,
        boxShadow: selezionata ? `0 0 0 2px ${colore}` : undefined,
      }}
      title={`${inferenza.territorio ?? "?"} ${inferenza.colore ?? "?"} (${
        inferenza.n_armate_stimate
      }) ${(inferenza.confidence * 100).toFixed(0)}%`}
    >
      <span
        className="absolute -top-5 left-0 text-[10px] px-1 rounded font-mono whitespace-nowrap text-pergamena"
        style={{ backgroundColor: colore }}
      >
        {inferenza.n_armate_stimate}
      </span>
    </button>
  );
}

function DettaglioInferenza({ inferenza: inf }: { inferenza: InferenzaCV }) {
  return (
    <div className="rounded border border-inchiostro/10 bg-pergamena-scura/20 p-3 text-xs space-y-1.5">
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        <div>
          <span className="etichetta">Territorio</span>
          <div className="text-inchiostro">
            {inf.territorio ?? <em>(non riconosciuto)</em>}
          </div>
        </div>
        <div>
          <span className="etichetta">Colore</span>
          <div className="text-inchiostro">
            {inf.colore ?? <em>(non riconosciuto)</em>}
          </div>
        </div>
        <div>
          <span className="etichetta">Tipo dominante</span>
          <div className="text-inchiostro">
            {inf.tipo_pedina_dominante ?? "—"}
          </div>
        </div>
        <div>
          <span className="etichetta">N armate stimate</span>
          <div className="text-inchiostro tabular-nums">
            {inf.n_armate_stimate}
          </div>
        </div>
        <div>
          <span className="etichetta">Confidence</span>
          <div className="text-inchiostro tabular-nums">
            {(inf.confidence * 100).toFixed(1)}%
          </div>
        </div>
        <div>
          <span className="etichetta">Bbox (px)</span>
          <div className="text-inchiostro tabular-nums font-mono">
            {inf.bbox.join(", ")}
          </div>
        </div>
      </div>

      <div>
        <span className="etichetta">Modello</span>{" "}
        <code className="bg-pergamena px-1 rounded">
          {inf.modello_versione}
        </code>
      </div>

      {inf.scomposizione.length > 0 ? (
        <details>
          <summary className="cursor-pointer hover:text-inchiostro etichetta">
            Scomposizione ({inf.scomposizione.length} sub-detection)
          </summary>
          <pre className="mt-1 overflow-x-auto text-[10px] tabular-nums">
            {JSON.stringify(inf.scomposizione, null, 2)}
          </pre>
        </details>
      ) : null}
    </div>
  );
}
