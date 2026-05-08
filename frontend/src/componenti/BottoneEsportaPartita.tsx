/**
 * Bottone "Esporta" con dropdown a tre opzioni: JSON, HTML, CSV.
 *
 * - JSON: scarica un file `.json` strutturato (per archivio digitale).
 * - HTML: apre un nuovo tab con il report stampabile A4 (per archivio
 *   cartaceo del club).
 * - CSV: scarica un file piatto degli eventi per analytics esterne
 *   (Excel, Google Sheets, pandas).
 *
 * Tutte le opzioni puntano a URL del backend; il browser gestisce il
 * download/apertura nativamente.
 */

import { useEffect, useRef, useState } from "react";
import { Download, FileJson, FileSpreadsheet, Printer } from "lucide-react";

import { apiEsportazione } from "@/api";

interface ProprietaBottoneEsporta {
  partitaId: string;
}

export function BottoneEsportaPartita({ partitaId }: ProprietaBottoneEsporta) {
  const [aperto, setAperto] = useState(false);
  const contenitore = useRef<HTMLDivElement>(null);

  // Click esterno chiude il menu
  useEffect(() => {
    if (!aperto) return;
    function gestisci(evento: MouseEvent) {
      if (
        contenitore.current &&
        !contenitore.current.contains(evento.target as Node)
      ) {
        setAperto(false);
      }
    }
    document.addEventListener("mousedown", gestisci);
    return () => document.removeEventListener("mousedown", gestisci);
  }, [aperto]);

  // Escape chiude il menu
  useEffect(() => {
    if (!aperto) return;
    function gestisci(e: KeyboardEvent) {
      if (e.key === "Escape") setAperto(false);
    }
    document.addEventListener("keydown", gestisci);
    return () => document.removeEventListener("keydown", gestisci);
  }, [aperto]);

  function scaricaJson() {
    window.location.href = apiEsportazione.urlJson(partitaId);
    setAperto(false);
  }

  function apriHtml() {
    window.open(apiEsportazione.urlHtml(partitaId), "_blank", "noopener");
    setAperto(false);
  }

  function scaricaCsv() {
    window.location.href = apiEsportazione.urlCsv(partitaId);
    setAperto(false);
  }

  return (
    <div ref={contenitore} className="relative inline-block">
      <button
        type="button"
        onClick={() => setAperto((v) => !v)}
        className="btn-secondario"
        aria-haspopup="menu"
        aria-expanded={aperto}
      >
        <Download size={14} /> Esporta
      </button>

      {aperto ? (
        <div
          role="menu"
          className="absolute right-0 top-full mt-1 z-20 min-w-[220px] bg-pergamena border border-inchiostro/25 shadow-cartaHover"
        >
          <VoceMenu
            onClick={scaricaJson}
            icona={<FileJson size={14} />}
            titolo="Esporta JSON"
            descrizione="Bundle strutturato per archivio digitale"
          />
          <div className="linea-divisoria" />
          <VoceMenu
            onClick={apriHtml}
            icona={<Printer size={14} />}
            titolo="Esporta HTML"
            descrizione="Report stampabile A4 (apre in nuova scheda)"
          />
          <div className="linea-divisoria" />
          <VoceMenu
            onClick={scaricaCsv}
            icona={<FileSpreadsheet size={14} />}
            titolo="Esporta CSV"
            descrizione="Eventi piatti per Excel/Sheets/analytics"
          />
        </div>
      ) : null}
    </div>
  );
}

function VoceMenu({
  onClick,
  icona,
  titolo,
  descrizione,
}: {
  onClick: () => void;
  icona: React.ReactNode;
  titolo: string;
  descrizione: string;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className="w-full text-left px-3 py-2.5 hover:bg-pergamena-chiara transition-colors flex items-start gap-3"
    >
      <span className="mt-0.5 text-inchiostro-tenue">{icona}</span>
      <span className="flex-1">
        <span className="block font-display font-semibold text-sm text-inchiostro">
          {titolo}
        </span>
        <span className="block text-[10px] text-inchiostro-tenue mt-0.5">
          {descrizione}
        </span>
      </span>
    </button>
  );
}
