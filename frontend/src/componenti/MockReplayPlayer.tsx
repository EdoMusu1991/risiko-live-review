/**
 * Mock del player replay, usato finché Battle Commander non consegna la
 * sua replay-lib vera.
 *
 * Mostra gli eventi del bundle in una lista navigabile con cursor che si
 * muove con prev/next. Quando arriverà la libreria di BC, basta
 * sostituire questo componente nell'import del `<VisoreReplay>` e tutto
 * il resto continua a funzionare (stesso `BundleReplay` in input).
 *
 * API public attesa (specchio della lib BC futura):
 *   <RisikoReplayPlayer
 *     bundle={...}
 *     onCursorChange={(tsEvento) => ...}  // opzionale, per sync video
 *   />
 */

import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, SkipBack, SkipForward } from "lucide-react";

import type { BundleReplay, EventoValidato } from "@risiko/eventi-schema";

interface ProprietaMockReplayPlayer {
  bundle: BundleReplay;
  /** Callback chiamata a ogni cambio di posizione del cursor. */
  onCursorChange?: (tsEvento: string, indice: number) => void;
}

export function MockReplayPlayer({
  bundle,
  onCursorChange,
}: ProprietaMockReplayPlayer) {
  const [indice, setIndice] = useState(0);

  const eventoCorrente: EventoValidato | null = bundle.eventi[indice] ?? null;
  const totale = bundle.eventi.length;

  // Mappa giocatore_id -> nome per render leggibile
  const nomiPerId = useMemo(() => {
    const m = new Map<string, string>();
    for (const g of bundle.giocatori) m.set(g.id, g.nome);
    return m;
  }, [bundle.giocatori]);

  function vai(nuovoIndice: number) {
    const clamped = Math.max(0, Math.min(totale - 1, nuovoIndice));
    setIndice(clamped);
    const ev = bundle.eventi[clamped];
    if (ev && onCursorChange) onCursorChange(ev.ts_evento, clamped);
  }

  if (totale === 0) {
    return (
      <div className="text-center text-sm text-inchiostro-fioco italic py-8">
        Bundle replay vuoto. Aggiungi eventi alla partita per generare un
        replay riproducibile.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Avviso che è un placeholder */}
      <div className="text-[11px] text-inchiostro-fioco italic border-l-2 border-oro/40 pl-3 py-1">
        Player provvisorio. Quando Battle Commander consegnerà la sua
        replay-lib (scope B/C), questo componente sarà sostituito con il
        viewer mappa completo. Il bundle è già validato secondo lo schema
        condiviso, niente da rifare.
      </div>

      {/* Cursor + controlli */}
      <div className="flex items-center justify-between gap-2 bg-pergamena-scura/40 border border-inchiostro/10 rounded px-3 py-2">
        <div className="flex items-center gap-1">
          <BottoneCursor
            onClick={() => vai(0)}
            disabled={indice === 0}
            label="Inizio"
          >
            <SkipBack className="w-4 h-4" />
          </BottoneCursor>
          <BottoneCursor
            onClick={() => vai(indice - 1)}
            disabled={indice === 0}
            label="Precedente"
          >
            <ChevronLeft className="w-4 h-4" />
          </BottoneCursor>
          <BottoneCursor
            onClick={() => vai(indice + 1)}
            disabled={indice >= totale - 1}
            label="Successivo"
          >
            <ChevronRight className="w-4 h-4" />
          </BottoneCursor>
          <BottoneCursor
            onClick={() => vai(totale - 1)}
            disabled={indice >= totale - 1}
            label="Fine"
          >
            <SkipForward className="w-4 h-4" />
          </BottoneCursor>
        </div>

        <div className="text-xs tabular-nums text-inchiostro-tenue">
          {indice + 1} / {totale}
        </div>
      </div>

      {/* Slider per saltare a un punto qualsiasi */}
      <input
        type="range"
        min={0}
        max={totale - 1}
        value={indice}
        onChange={(e) => vai(Number(e.target.value))}
        className="w-full"
        aria-label="Posizione replay"
      />

      {/* Evento corrente */}
      {eventoCorrente ? (
        <DettaglioEvento evento={eventoCorrente} nomiPerId={nomiPerId} />
      ) : null}
    </div>
  );
}

// === Sotto-componenti ===

function BottoneCursor({
  onClick,
  disabled,
  label,
  children,
}: {
  onClick: () => void;
  disabled: boolean;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className="p-1.5 rounded text-inchiostro-tenue hover:bg-inchiostro/10 hover:text-inchiostro disabled:opacity-30 disabled:cursor-not-allowed transition"
    >
      {children}
    </button>
  );
}

function DettaglioEvento({
  evento,
  nomiPerId,
}: {
  evento: EventoValidato;
  nomiPerId: Map<string, string>;
}) {
  // Discriminated union → narrowing automatico sul tipo
  const descrizione = (() => {
    switch (evento.tipo) {
      case "territorio_assegnato_inizio": {
        const nome = nomiPerId.get(evento.dati.giocatore_id) ?? "?";
        return `${nome} riceve ${formatTerritorio(evento.dati.territorio)} (${evento.dati.n_armate} armate)`;
      }
      case "obiettivo_assegnato": {
        const nome = nomiPerId.get(evento.dati.giocatore_id) ?? "?";
        return `${nome} riceve l'obiettivo #${evento.dati.obiettivo_id}`;
      }
      case "partita_inizio": {
        const nome = nomiPerId.get(evento.dati.primo_giocatore_id) ?? "?";
        return `Partita iniziata, primo giocatore: ${nome}`;
      }
      case "turno_iniziato": {
        const nome = nomiPerId.get(evento.dati.giocatore_id) ?? "?";
        return `Turno di ${nome}`;
      }
      case "armate_piazzate": {
        const nome = nomiPerId.get(evento.dati.giocatore_id) ?? "?";
        return `${nome} piazza ${evento.dati.n} armate su ${formatTerritorio(evento.dati.territorio)}`;
      }
      case "tris_giocato": {
        const nome = nomiPerId.get(evento.dati.giocatore_id) ?? "?";
        return `${nome} gioca un tris (${evento.dati.carte.length} carte)`;
      }
      case "attacco_risolto": {
        const nome = nomiPerId.get(evento.dati.giocatore_id) ?? "?";
        return `${nome} attacca ${formatTerritorio(evento.dati.a)} da ${formatTerritorio(evento.dati.da)} — dadi ${evento.dati.dadi_attaccante.join(",")} vs ${evento.dati.dadi_difensore.join(",")}`;
      }
      case "territorio_conquistato": {
        const nome = nomiPerId.get(evento.dati.giocatore_id) ?? "?";
        return `${nome} conquista ${formatTerritorio(evento.dati.territorio)}`;
      }
      case "armate_spostate": {
        const nome = nomiPerId.get(evento.dati.giocatore_id) ?? "?";
        return `${nome} sposta ${evento.dati.n} armate da ${formatTerritorio(evento.dati.da)} a ${formatTerritorio(evento.dati.a)}`;
      }
      case "carta_pescata": {
        const nome = nomiPerId.get(evento.dati.giocatore_id) ?? "?";
        const c = evento.dati.carta;
        return `${nome} pesca una carta ${c.simbolo}${c.territorio ? ` (${formatTerritorio(c.territorio)})` : ""}`;
      }
      case "turno_finito": {
        const nome = nomiPerId.get(evento.dati.giocatore_id) ?? "?";
        return `${nome} termina il turno`;
      }
      case "partita_fine": {
        const nome = nomiPerId.get(evento.dati.vincitore_id) ?? "?";
        return `Partita finita, vincitore: ${nome}`;
      }
    }
  })();

  return (
    <div className="bg-pergamena-chiara border border-inchiostro/15 rounded p-3 space-y-1">
      <div className="text-[10px] uppercase tracking-wider text-inchiostro-fioco">
        {evento.tipo}
      </div>
      <div className="text-sm text-inchiostro">{descrizione}</div>
      <div className="text-[10px] text-inchiostro-fioco font-mono">
        {evento.ts_evento}
      </div>
    </div>
  );
}

function formatTerritorio(slug: string): string {
  return slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
