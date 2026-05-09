/**
 * Pannello "Calibrazione raddrizzamento" — UI per gestire la matrice
 * di omografia che raddrizza i frame video.
 *
 * Workflow utente:
 * 1. Carica un video di partita.
 * 2. Verifica stato calibrazione (badge: "calibrata" o "da calibrare").
 * 3. Click "Calibra" → backend estrae frame all'offset 0s e calcola
 *    omografia via SIFT+ORB. Il pannello mostra preview prima/dopo.
 * 4. Se la calibrazione e' insoddisfacente, "Ricalibra" con offset
 *    diverso, oppure "Cancella" per riprovare.
 *
 * Il pannello e' nascosto se la partita non ha video caricato (caso
 * normale per partite vecchie / senza CV).
 */

import { useEffect, useState } from "react";
import {
  Camera,
  CheckCircle,
  Crosshair,
  Loader2,
  RotateCcw,
  Trash2,
} from "lucide-react";

import {
  apiRaddrizzamento,
  ErroreApi,
  type StatoRaddrizzamento,
} from "@/api";
import { MessaggioErrore } from "@/componenti/decorativi";
import { WidgetStatoPipelineCv } from "@/componenti/WidgetStatoPipelineCv";

interface ProprietaPannelloCalibrazione {
  partitaId: string;
  /** Se la partita non ha video, il pannello si nasconde. */
  haVideo: boolean;
}

export function PannelloCalibrazione({
  partitaId,
  haVideo,
}: ProprietaPannelloCalibrazione) {
  const [stato, setStato] = useState<StatoRaddrizzamento | null>(null);
  const [caricamento, setCaricamento] = useState(true);
  const [erroreLoad, setErroreLoad] = useState<string | null>(null);

  const [inCalibrazione, setInCalibrazione] = useState(false);
  const [erroreCalibrazione, setErroreCalibrazione] = useState<string | null>(
    null,
  );

  const [offsetSec, setOffsetSec] = useState(0);

  // Cache-buster per forzare ricarica dei frame dopo ricalibrazione
  const [versioneFrame, setVersioneFrame] = useState(0);

  async function ricaricaStato() {
    setCaricamento(true);
    setErroreLoad(null);
    try {
      const s = await apiRaddrizzamento.stato(partitaId);
      setStato(s);
    } catch (e) {
      setErroreLoad(e instanceof ErroreApi ? e.dettaglio : "Errore caricamento");
    } finally {
      setCaricamento(false);
    }
  }

  useEffect(() => {
    if (haVideo) {
      void ricaricaStato();
    } else {
      setCaricamento(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partitaId, haVideo]);

  if (!haVideo) {
    return null;
  }

  async function calibra() {
    setInCalibrazione(true);
    setErroreCalibrazione(null);
    try {
      await apiRaddrizzamento.calibra(partitaId, {
        offsetSecCalibrazione: offsetSec,
        forza: true,
      });
      setVersioneFrame((v) => v + 1);
      await ricaricaStato();
    } catch (e) {
      setErroreCalibrazione(
        e instanceof ErroreApi ? e.dettaglio : "Errore calibrazione",
      );
    } finally {
      setInCalibrazione(false);
    }
  }

  async function cancella() {
    if (!stato?.calibrata) return;
    if (!confirm("Cancellare la calibrazione attuale?")) return;
    try {
      await apiRaddrizzamento.cancellaCalibrazione(partitaId);
      setVersioneFrame((v) => v + 1);
      await ricaricaStato();
    } catch (e) {
      setErroreCalibrazione(
        e instanceof ErroreApi ? e.dettaglio : "Errore cancellazione",
      );
    }
  }

  if (caricamento) {
    return (
      <section className="carta p-5">
        <h3 className="etichetta">Calibrazione raddrizzamento</h3>
        <div className="flex items-center gap-2 text-inchiostro-fioco py-3">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Caricamento…</span>
        </div>
      </section>
    );
  }

  if (erroreLoad) {
    return (
      <section className="carta p-5 space-y-3">
        <h3 className="etichetta">Calibrazione raddrizzamento</h3>
        <MessaggioErrore testo={erroreLoad} />
      </section>
    );
  }

  return (
    <section className="carta p-5 space-y-4">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="etichetta inline-flex items-center gap-2">
          <Crosshair className="w-3.5 h-3.5" />
          Calibrazione raddrizzamento
        </h3>
        <div className="flex items-center gap-2 flex-wrap">
          <BadgeCalibrazione stato={stato} />
          <WidgetStatoPipelineCv />
        </div>
      </header>

      <Controlli
        offsetSec={offsetSec}
        onOffsetCambia={setOffsetSec}
        inCalibrazione={inCalibrazione}
        calibrata={stato?.calibrata ?? false}
        onCalibra={calibra}
        onCancella={cancella}
      />

      {erroreCalibrazione ? (
        <MessaggioErrore testo={erroreCalibrazione} />
      ) : null}

      {stato?.calibrata ? (
        <Anteprima
          partitaId={partitaId}
          offsetSec={offsetSec}
          versione={versioneFrame}
        />
      ) : (
        <p className="text-xs text-inchiostro-fioco italic">
          La partita non e' calibrata. La pipeline CV non puo' produrre
          frame raddrizzati finche' non lanci la calibrazione.
        </p>
      )}

      {stato?.matrice ? <DettagliMatrice matrice={stato.matrice} /> : null}
    </section>
  );
}

// === Sotto-componenti ===

function BadgeCalibrazione({ stato }: { stato: StatoRaddrizzamento | null }) {
  if (stato === null) return null;
  if (stato.calibrata) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-bottiglia bg-bottiglia/10 px-2 py-0.5 rounded">
        <CheckCircle className="w-3 h-3" />
        calibrata
      </span>
    );
  }
  return (
    <span className="text-xs text-bronzo bg-bronzo/10 px-2 py-0.5 rounded">
      da calibrare
    </span>
  );
}

function Controlli({
  offsetSec,
  onOffsetCambia,
  inCalibrazione,
  calibrata,
  onCalibra,
  onCancella,
}: {
  offsetSec: number;
  onOffsetCambia: (n: number) => void;
  inCalibrazione: boolean;
  calibrata: boolean;
  onCalibra: () => void;
  onCancella: () => void;
}) {
  return (
    <div className="flex items-end gap-3 flex-wrap">
      <div>
        <label className="text-[10px] uppercase tracking-wider text-inchiostro-fioco mb-1 block">
          Offset sec (frame di calibrazione)
        </label>
        <input
          type="number"
          min={0}
          step={1}
          value={offsetSec}
          onChange={(e) => onOffsetCambia(Number(e.target.value))}
          className="w-24 px-2 py-1 border border-inchiostro/20 rounded bg-pergamena text-inchiostro tabular-nums"
        />
      </div>
      <button
        type="button"
        onClick={onCalibra}
        disabled={inCalibrazione}
        className="btn-primario disabled:opacity-50"
      >
        {inCalibrazione ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : calibrata ? (
          <RotateCcw className="w-3.5 h-3.5" />
        ) : (
          <Crosshair className="w-3.5 h-3.5" />
        )}
        {calibrata ? "Ricalibra" : "Calibra"}
      </button>
      {calibrata ? (
        <button
          type="button"
          onClick={onCancella}
          className="btn-secondario text-scarlatto"
          title="Cancella la matrice di omografia"
        >
          <Trash2 className="w-3.5 h-3.5" />
          Cancella
        </button>
      ) : null}
    </div>
  );
}

function Anteprima({
  partitaId,
  offsetSec,
  versione,
}: {
  partitaId: string;
  offsetSec: number;
  versione: number;
}) {
  const urlRaw = `${apiRaddrizzamento.urlFrameOffset(
    partitaId,
    offsetSec,
    "anteprima-calibrazione",
  )}&v=${versione}`;

  return (
    <div className="space-y-2">
      <div className="text-[10px] uppercase tracking-wider text-inchiostro-fioco">
        Anteprima frame raw a {offsetSec}s
      </div>
      <div className="rounded border border-inchiostro/10 bg-pergamena-scura/20 overflow-hidden">
        <img
          key={versione}
          src={urlRaw}
          alt={`Frame raw offset ${offsetSec}s`}
          className="w-full h-auto block"
          onError={(e) => {
            // Se il frame non esiste, nascondi l'immagine
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
      </div>
      <p className="text-[11px] text-inchiostro-fioco italic">
        <Camera className="w-3 h-3 inline mr-1" />
        Per vedere il frame raddrizzato, vai sul singolo evento e usa
        l'endpoint <code>/eventi/{"{id}"}/frame-raddrizzato</code> oppure
        lancia "Analizza CV" nel pannello discrepanze.
      </p>
    </div>
  );
}

function DettagliMatrice({ matrice }: { matrice: number[][] }) {
  return (
    <details className="text-[11px] text-inchiostro-fioco">
      <summary className="cursor-pointer hover:text-inchiostro">
        Matrice di omografia (3×3)
      </summary>
      <pre className="mt-2 p-2 bg-pergamena-scura/30 rounded overflow-x-auto tabular-nums">
        {matrice
          .map((riga) =>
            riga.map((v) => v.toFixed(4).padStart(10)).join(" "),
          )
          .join("\n")}
      </pre>
    </details>
  );
}
