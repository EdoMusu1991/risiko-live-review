/**
 * Pannello per upload video di una partita.
 *
 * Quando una partita non ha ancora video, mostra un'area drag-drop +
 * file picker. Durante l'upload mostra una barra di progresso. A fine
 * upload chiama `onCaricato` per ricaricare il dettaglio partita.
 */

import { useState, type ChangeEvent, type DragEvent } from "react";
import { Upload, FileVideo } from "lucide-react";

import { apiVideo } from "@/api";
import { ErroreApi } from "@/api";
import { MessaggioErrore } from "./decorativi";

interface ProprietaUploadVideo {
  partitaId: string;
  onCaricato: () => void;
}

export function PannelloUploadVideo({
  partitaId,
  onCaricato,
}: ProprietaUploadVideo) {
  const [progresso, setProgresso] = useState(0);
  const [inUpload, setInUpload] = useState(false);
  const [errore, setErrore] = useState<string | null>(null);
  const [trascinamento, setTrascinamento] = useState(false);

  async function gestisciFile(file: File) {
    setErrore(null);
    setInUpload(true);
    setProgresso(0);
    try {
      await apiVideo.carica(partitaId, file, setProgresso);
      onCaricato();
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi ? e.dettaglio : "Errore durante l'upload";
      setErrore(messaggio);
    } finally {
      setInUpload(false);
    }
  }

  function gestisciInput(evento: ChangeEvent<HTMLInputElement>) {
    const file = evento.target.files?.[0];
    if (file) gestisciFile(file);
  }

  function gestisciDrop(evento: DragEvent) {
    evento.preventDefault();
    setTrascinamento(false);
    const file = evento.dataTransfer.files[0];
    if (file) gestisciFile(file);
  }

  return (
    <div>
      <label
        htmlFor="upload-video"
        onDragOver={(e) => {
          e.preventDefault();
          setTrascinamento(true);
        }}
        onDragLeave={() => setTrascinamento(false)}
        onDrop={gestisciDrop}
        className={`
          block cursor-pointer border-2 border-dashed p-12
          text-center transition-colors
          ${
            trascinamento
              ? "border-scarlatto bg-scarlatto/5"
              : "border-inchiostro/25 hover:border-inchiostro/50"
          }
        `}
      >
        <FileVideo
          size={32}
          className="mx-auto mb-3 text-inchiostro-tenue"
          strokeWidth={1.5}
        />
        <div className="font-display text-xl font-semibold mb-1">
          Carica un video
        </div>
        <div className="text-xs text-inchiostro-tenue mb-4">
          Trascina qui un file MP4/MOV oppure clicca per selezionarlo
        </div>
        <span className="btn-primario inline-flex">
          <Upload size={14} /> Seleziona file
        </span>
        <input
          id="upload-video"
          type="file"
          accept="video/mp4,video/quicktime,video/*"
          className="sr-only"
          onChange={gestisciInput}
          disabled={inUpload}
        />
      </label>

      {inUpload ? (
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs etichetta mb-1">
            <span>Caricamento in corso</span>
            <span className="font-mono num-tab">
              {Math.round(progresso * 100)}%
            </span>
          </div>
          <div className="h-1 bg-inchiostro/10 overflow-hidden">
            <div
              className="h-full bg-scarlatto transition-[width] duration-150"
              style={{ width: `${progresso * 100}%` }}
            />
          </div>
        </div>
      ) : null}

      {errore ? <MessaggioErrore testo={errore} /> : null}
    </div>
  );
}
