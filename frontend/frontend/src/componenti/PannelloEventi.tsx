/**
 * Pannello laterale che mostra gli eventi della partita.
 *
 * Due tab: validati (pronti per il motore) e grezzi (raccolti dal CV/BLE
 * o input manuali, ancora da promuovere).
 *
 * - Click su evento: salta al timestamp video corrispondente.
 * - Per eventi validati: pulsanti edit/elimina (compaiono on-hover).
 * - Pulsanti gestiti via callback passati dalla pagina genitore.
 */

import { useMemo, useState } from "react";
import { format, parseISO } from "date-fns";
import {
  CircleCheck,
  Circle,
  CircleArrowUp,
  Pencil,
  Plus,
  Search,
  SlidersHorizontal,
  Trash2,
  X,
} from "lucide-react";

import type {
  EventoGrezzo,
  EventoValidato,
  GiocatorePartita,
  Video,
} from "@/tipi/dominio";
import { FASI_FILTRO, fasePerTipo, type IdFase } from "@/tipi/costanti";
import {
  eventoCoinvolgeGiocatore,
  eventoCoinvolgeTerritorio,
} from "@/utility/eventiCoinvolti";
import { PallinoColore } from "./decorativi";

type Tab = "validati" | "grezzi";

interface ProprietaPannelloEventi {
  eventiGrezzi: EventoGrezzo[];
  eventiValidati: EventoValidato[];
  /** Giocatori della partita per i filtri colore-giocatore. */
  giocatori: GiocatorePartita[];
  video: Video | null;
  /** Se valorizzato, mostra solo gli eventi che coinvolgono questo territorio. */
  filtroTerritorio?: string | null;
  onPuliciFiltro?: () => void;
  onSaltaSecondo?: (sec: number) => void;
  /** Aggiungi un nuovo evento (modale). Tipologia in base al tab corrente. */
  onAggiungi?: (tipologia: "validato" | "grezzo") => void;
  onModificaValidato?: (evento: EventoValidato) => void;
  onEliminaValidato?: (evento: EventoValidato) => void;
  onModificaGrezzo?: (evento: EventoGrezzo) => void;
  onEliminaGrezzo?: (evento: EventoGrezzo) => void;
  /** Promuove un grezzo a validato (one-click). */
  onPromuoviGrezzo?: (evento: EventoGrezzo) => void;
}

export function PannelloEventi({
  eventiGrezzi,
  eventiValidati,
  giocatori,
  video,
  filtroTerritorio,
  onPuliciFiltro,
  onSaltaSecondo,
  onAggiungi,
  onModificaValidato,
  onEliminaValidato,
  onModificaGrezzo,
  onEliminaGrezzo,
  onPromuoviGrezzo,
}: ProprietaPannelloEventi) {
  const [tab, setTab] = useState<Tab>("validati");

  // Stato filtri locali (sessione, non persistiti)
  const [filtriEspansi, setFiltriEspansi] = useState(false);
  const [filtroGiocatori, setFiltroGiocatori] = useState<ReadonlySet<string>>(
    new Set(),
  );
  const [filtroFasi, setFiltroFasi] = useState<ReadonlySet<IdFase>>(new Set());
  const [testoCerca, setTestoCerca] = useState("");

  const filtroAttivoGiocatore = filtroGiocatori.size > 0;
  const filtroAttivoFase = filtroFasi.size > 0;
  const filtroAttivoCerca = testoCerca.trim().length > 0;
  const nFiltriExtra =
    (filtroAttivoGiocatore ? 1 : 0) +
    (filtroAttivoFase ? 1 : 0) +
    (filtroAttivoCerca ? 1 : 0);

  function azzeraFiltri() {
    setFiltroGiocatori(new Set());
    setFiltroFasi(new Set());
    setTestoCerca("");
    onPuliciFiltro?.();
  }

  function applicaFiltri<T extends EventoValidato | EventoGrezzo>(
    eventi: T[],
  ): T[] {
    let out = eventi;

    if (filtroTerritorio) {
      out = out.filter((e) =>
        eventoCoinvolgeTerritorio(e, filtroTerritorio),
      );
    }

    if (filtroAttivoGiocatore) {
      out = out.filter((e) =>
        Array.from(filtroGiocatori).some((gid) =>
          eventoCoinvolgeGiocatore(e, gid),
        ),
      );
    }

    if (filtroAttivoFase) {
      out = out.filter((e) => filtroFasi.has(fasePerTipo(e.tipo)));
    }

    if (filtroAttivoCerca) {
      const ago = testoCerca.trim().toLowerCase();
      out = out.filter((e) => {
        if (e.tipo.toLowerCase().includes(ago)) return true;
        const json = JSON.stringify(e.dati).toLowerCase();
        return json.includes(ago);
      });
    }

    return out;
  }

  const validatiVisualizzati = useMemo(
    () => applicaFiltri(eventiValidati),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      eventiValidati,
      filtroTerritorio,
      filtroGiocatori,
      filtroFasi,
      testoCerca,
    ],
  );
  const grezziVisualizzati = useMemo(
    () => applicaFiltri(eventiGrezzi),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      eventiGrezzi,
      filtroTerritorio,
      filtroGiocatori,
      filtroFasi,
      testoCerca,
    ],
  );

  const conteggi = useMemo(
    () => ({
      validati: validatiVisualizzati.length,
      grezzi: grezziVisualizzati.length,
      grezziDaValidare: grezziVisualizzati.filter((e) => !e.validato).length,
    }),
    [grezziVisualizzati, validatiVisualizzati],
  );

  return (
    <section className="flex flex-col h-full">
      {/* Banner filtro territorio attivo (selezionato dalla mappa) */}
      {filtroTerritorio ? (
        <div className="px-3 py-2 bg-scarlatto/[0.06] border-b border-scarlatto/30 flex items-center justify-between gap-2">
          <div className="text-xs">
            <span className="etichetta-rossa">Territorio:</span>{" "}
            <span className="font-display font-semibold capitalize">
              {filtroTerritorio.replace(/_/g, " ")}
            </span>
          </div>
          {onPuliciFiltro ? (
            <button
              type="button"
              onClick={onPuliciFiltro}
              className="p-1 hover:text-scarlatto transition-colors"
              aria-label="Rimuovi filtro territorio"
              title="Rimuovi filtro territorio"
            >
              <X size={14} />
            </button>
          ) : null}
        </div>
      ) : null}

      {/* Barra filtri (collassabile) */}
      <BarraFiltri
        espansa={filtriEspansi}
        onToggle={() => setFiltriEspansi((v) => !v)}
        nFiltriAttivi={nFiltriExtra}
        giocatori={giocatori}
        filtroGiocatori={filtroGiocatori}
        onCambiaGiocatori={setFiltroGiocatori}
        filtroFasi={filtroFasi}
        onCambiaFasi={setFiltroFasi}
        testoCerca={testoCerca}
        onCambiaTestoCerca={setTestoCerca}
        onAzzera={
          nFiltriExtra > 0 || filtroTerritorio ? azzeraFiltri : undefined
        }
      />

      <div className="flex items-stretch border-b border-inchiostro/15">
        <BottoneTab
          attivo={tab === "validati"}
          onClick={() => setTab("validati")}
          conteggio={conteggi.validati}
        >
          Validati
        </BottoneTab>
        <BottoneTab
          attivo={tab === "grezzi"}
          onClick={() => setTab("grezzi")}
          conteggio={conteggi.grezzi}
          conteggioRosso={conteggi.grezziDaValidare}
        >
          Grezzi
        </BottoneTab>
        {onAggiungi ? (
          <button
            type="button"
            onClick={() => onAggiungi(tab === "validati" ? "validato" : "grezzo")}
            className="px-3 border-l border-inchiostro/15 text-inchiostro-tenue hover:text-scarlatto hover:bg-pergamena-chiara transition-colors"
            aria-label="Aggiungi evento"
            title={`Aggiungi evento ${tab}`}
          >
            <Plus size={16} />
          </button>
        ) : null}
      </div>

      <div className="flex-1 overflow-y-auto">
        {tab === "validati" ? (
          <ListaEventiValidati
            eventi={validatiVisualizzati}
            video={video}
            onSaltaSecondo={onSaltaSecondo}
            onModifica={onModificaValidato}
            onElimina={onEliminaValidato}
          />
        ) : (
          <ListaEventiGrezzi
            eventi={grezziVisualizzati}
            video={video}
            onSaltaSecondo={onSaltaSecondo}
            onModifica={onModificaGrezzo}
            onElimina={onEliminaGrezzo}
            onPromuovi={onPromuoviGrezzo}
          />
        )}
      </div>
    </section>
  );
}

function BottoneTab({
  attivo,
  onClick,
  conteggio,
  conteggioRosso,
  children,
}: {
  attivo: boolean;
  onClick: () => void;
  conteggio: number;
  conteggioRosso?: number;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        flex-1 px-4 py-3 text-xs uppercase tracking-widest
        border-b-2 transition-colors
        ${
          attivo
            ? "border-scarlatto text-inchiostro font-semibold"
            : "border-transparent text-inchiostro-tenue hover:text-inchiostro"
        }
      `}
    >
      <span>{children}</span>
      <span className="ml-2 font-mono num-tab text-inchiostro-fioco">
        ({conteggio})
      </span>
      {conteggioRosso && conteggioRosso > 0 ? (
        <span className="ml-1 font-mono num-tab text-scarlatto font-semibold">
          +{conteggioRosso}
        </span>
      ) : null}
    </button>
  );
}

function ListaEventiValidati({
  eventi,
  video,
  onSaltaSecondo,
  onModifica,
  onElimina,
}: {
  eventi: EventoValidato[];
  video: Video | null;
  onSaltaSecondo?: (sec: number) => void;
  onModifica?: (e: EventoValidato) => void;
  onElimina?: (e: EventoValidato) => void;
}) {
  if (eventi.length === 0) {
    return (
      <div className="p-6 text-center etichetta">
        Nessun evento validato.
      </div>
    );
  }

  return (
    <ul className="divide-y divide-inchiostro/10">
      {eventi.map((evento, i) => (
        <RigaEventoValidato
          key={evento.id}
          numero={i + 1}
          evento={evento}
          video={video}
          onSaltaSecondo={onSaltaSecondo}
          onModifica={onModifica}
          onElimina={onElimina}
        />
      ))}
    </ul>
  );
}

function ListaEventiGrezzi({
  eventi,
  video,
  onSaltaSecondo,
  onModifica,
  onElimina,
  onPromuovi,
}: {
  eventi: EventoGrezzo[];
  video: Video | null;
  onSaltaSecondo?: (sec: number) => void;
  onModifica?: (e: EventoGrezzo) => void;
  onElimina?: (e: EventoGrezzo) => void;
  onPromuovi?: (e: EventoGrezzo) => void;
}) {
  if (eventi.length === 0) {
    return (
      <div className="p-6 text-center etichetta">
        Nessun evento grezzo raccolto.
      </div>
    );
  }

  return (
    <ul className="divide-y divide-inchiostro/10">
      {eventi.map((evento, i) => (
        <RigaEventoGrezzo
          key={evento.id}
          numero={i + 1}
          evento={evento}
          video={video}
          onSaltaSecondo={onSaltaSecondo}
          onModifica={onModifica}
          onElimina={onElimina}
          onPromuovi={onPromuovi}
        />
      ))}
    </ul>
  );
}

function RigaEventoValidato({
  numero,
  evento,
  video,
  onSaltaSecondo,
  onModifica,
  onElimina,
}: {
  numero: number;
  evento: EventoValidato;
  video: Video | null;
  onSaltaSecondo?: (sec: number) => void;
  onModifica?: (e: EventoValidato) => void;
  onElimina?: (e: EventoValidato) => void;
}) {
  const offsetSec = useOffsetVideo(evento.ts_evento, video);
  const cliccabileTitolo = offsetSec !== null && onSaltaSecondo !== undefined;

  return (
    <li className="px-3 py-2.5 group transition-colors hover:bg-inchiostro/[0.03]">
      <div className="flex items-baseline gap-2 mb-0.5">
        <span className="font-mono text-[10px] text-inchiostro-fioco num-tab">
          {String(numero).padStart(3, "0")}
        </span>
        <CircleCheck size={12} className="text-bottiglia shrink-0" />
        <span
          className={`font-sans text-sm font-semibold flex-1 truncate ${
            cliccabileTitolo ? "cursor-pointer hover:text-scarlatto" : ""
          }`}
          onClick={() => {
            if (cliccabileTitolo && offsetSec !== null) {
              onSaltaSecondo!(offsetSec);
            }
          }}
        >
          {evento.tipo.replace(/_/g, " ")}
        </span>
        {offsetSec !== null ? (
          <span className="font-mono text-[10px] text-scarlatto num-tab">
            {formatoTempoBreve(offsetSec)}
          </span>
        ) : null}
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          {onModifica ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onModifica(evento);
              }}
              className="p-1 hover:text-scarlatto transition-colors"
              aria-label="Modifica evento"
              title="Modifica"
            >
              <Pencil size={12} />
            </button>
          ) : null}
          {onElimina ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onElimina(evento);
              }}
              className="p-1 hover:text-scarlatto transition-colors"
              aria-label="Elimina evento"
              title="Elimina"
            >
              <Trash2 size={12} />
            </button>
          ) : null}
        </div>
      </div>
      <DettaglioEvento ts={evento.ts_evento} dati={evento.dati} />
    </li>
  );
}

function RigaEventoGrezzo({
  numero,
  evento,
  video,
  onSaltaSecondo,
  onModifica,
  onElimina,
  onPromuovi,
}: {
  numero: number;
  evento: EventoGrezzo;
  video: Video | null;
  onSaltaSecondo?: (sec: number) => void;
  onModifica?: (e: EventoGrezzo) => void;
  onElimina?: (e: EventoGrezzo) => void;
  onPromuovi?: (e: EventoGrezzo) => void;
}) {
  const offsetSec = useOffsetVideo(evento.ts_evento, video);
  const cliccabile = offsetSec !== null && onSaltaSecondo !== undefined;

  return (
    <li
      className={`
        px-3 py-2.5 group transition-colors
        ${cliccabile ? "cursor-pointer hover:bg-inchiostro/[0.03]" : ""}
        ${!evento.validato ? "bg-pergamena-chiara/50" : ""}
      `}
      onClick={() => {
        if (cliccabile && offsetSec !== null) onSaltaSecondo!(offsetSec);
      }}
    >
      <div className="flex items-baseline gap-2 mb-0.5">
        <span className="font-mono text-[10px] text-inchiostro-fioco num-tab">
          {String(numero).padStart(3, "0")}
        </span>
        {evento.validato ? (
          <CircleCheck size={12} className="text-inchiostro-fioco shrink-0" />
        ) : (
          <Circle size={12} className="text-oro shrink-0" />
        )}
        <span className="font-sans text-sm font-semibold flex-1 truncate">
          {evento.tipo.replace(/_/g, " ")}
        </span>
        {offsetSec !== null ? (
          <span className="font-mono text-[10px] text-scarlatto num-tab">
            {formatoTempoBreve(offsetSec)}
          </span>
        ) : null}
        {/* Azioni hover */}
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          {onPromuovi && !evento.validato ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onPromuovi(evento);
              }}
              className="p-1 text-inchiostro-tenue hover:text-bottiglia transition-colors"
              aria-label="Promuovi a validato"
              title="Promuovi a validato"
            >
              <CircleArrowUp size={13} />
            </button>
          ) : null}
          {onModifica ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onModifica(evento);
              }}
              className="p-1 text-inchiostro-tenue hover:text-scarlatto transition-colors"
              aria-label="Modifica"
            >
              <Pencil size={13} />
            </button>
          ) : null}
          {onElimina ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onElimina(evento);
              }}
              className="p-1 text-inchiostro-tenue hover:text-scarlatto transition-colors"
              aria-label="Elimina"
            >
              <Trash2 size={13} />
            </button>
          ) : null}
        </div>
      </div>
      <DettaglioEvento
        ts={evento.ts_evento}
        dati={evento.dati}
        fonte={evento.fonte}
      />
    </li>
  );
}

function DettaglioEvento({
  ts,
  dati,
  fonte,
}: {
  ts: string;
  dati: Record<string, unknown>;
  fonte?: string;
}) {
  return (
    <>
      <div className="flex items-center gap-2 text-xs text-inchiostro-tenue ml-6">
        <span className="font-mono num-tab">
          {format(parseISO(ts), "HH:mm:ss")}
        </span>
        {fonte ? (
          <>
            <span className="text-inchiostro-fioco">·</span>
            <span className="font-mono text-[10px]">{fonte}</span>
          </>
        ) : null}
      </div>
      {Object.keys(dati).length > 0 ? (
        <div className="ml-6 mt-1 font-mono text-[10px] text-inchiostro-fioco truncate">
          {JSON.stringify(dati)}
        </div>
      ) : null}
    </>
  );
}

function useOffsetVideo(tsEvento: string, video: Video | null): number | null {
  return useMemo(() => {
    if (!video) return null;
    const tsEv = parseISO(tsEvento).getTime();
    const tsInizio = parseISO(video.ts_inizio).getTime();
    const off = (tsEv - tsInizio) / 1000;
    if (off < 0 || off > video.durata_sec + 5) return null;
    return off;
  }, [video, tsEvento]);
}

function formatoTempoBreve(secondiTotali: number): string {
  const minuti = Math.floor(secondiTotali / 60);
  const secondi = Math.floor(secondiTotali % 60);
  return `${String(minuti).padStart(2, "0")}:${String(secondi).padStart(2, "0")}`;
}

// === Barra filtri ===

function BarraFiltri({
  espansa,
  onToggle,
  nFiltriAttivi,
  giocatori,
  filtroGiocatori,
  onCambiaGiocatori,
  filtroFasi,
  onCambiaFasi,
  testoCerca,
  onCambiaTestoCerca,
  onAzzera,
}: {
  espansa: boolean;
  onToggle: () => void;
  nFiltriAttivi: number;
  giocatori: GiocatorePartita[];
  filtroGiocatori: ReadonlySet<string>;
  onCambiaGiocatori: (s: ReadonlySet<string>) => void;
  filtroFasi: ReadonlySet<IdFase>;
  onCambiaFasi: (s: ReadonlySet<IdFase>) => void;
  testoCerca: string;
  onCambiaTestoCerca: (t: string) => void;
  onAzzera?: () => void;
}) {
  function alternaGiocatore(id: string) {
    const nuovo = new Set(filtroGiocatori);
    if (nuovo.has(id)) nuovo.delete(id);
    else nuovo.add(id);
    onCambiaGiocatori(nuovo);
  }

  function alternaFase(id: IdFase) {
    const nuovo = new Set(filtroFasi);
    if (nuovo.has(id)) nuovo.delete(id);
    else nuovo.add(id);
    onCambiaFasi(nuovo);
  }

  return (
    <div className="border-b border-inchiostro/10">
      {/* Header sempre visibile */}
      <div className="px-3 py-2 flex items-center gap-2">
        <button
          type="button"
          onClick={onToggle}
          className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-widest text-inchiostro-tenue hover:text-inchiostro transition-colors"
        >
          <SlidersHorizontal size={12} />
          Filtri
          {nFiltriAttivi > 0 ? (
            <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 bg-scarlatto text-pergamena text-[10px] font-mono num-tab">
              {nFiltriAttivi}
            </span>
          ) : null}
        </button>
        <div className="flex-1" />
        {onAzzera ? (
          <button
            type="button"
            onClick={onAzzera}
            className="text-[10px] uppercase tracking-widest text-inchiostro-tenue hover:text-scarlatto transition-colors"
          >
            Azzera
          </button>
        ) : null}
      </div>

      {/* Pannello espanso */}
      {espansa ? (
        <div className="px-3 pb-3 space-y-3">
          {/* Filtro giocatori */}
          <div>
            <div className="etichetta mb-1.5">Giocatori</div>
            <div className="flex flex-wrap gap-1">
              {giocatori
                .slice()
                .sort((a, b) => a.ordine_seduta - b.ordine_seduta)
                .map((g) => {
                  const attivo = filtroGiocatori.has(g.id);
                  return (
                    <button
                      key={g.id}
                      type="button"
                      onClick={() => alternaGiocatore(g.id)}
                      className={`
                        inline-flex items-center gap-1.5 px-2 py-1 text-xs font-sans
                        border transition-colors
                        ${
                          attivo
                            ? "border-inchiostro bg-inchiostro text-pergamena"
                            : "border-inchiostro/25 hover:border-inchiostro/50"
                        }
                      `}
                      title={`${attivo ? "Rimuovi" : "Aggiungi"} ${g.nome}`}
                    >
                      <PallinoColore
                        colore={g.colore}
                        classeDimensione="w-2.5 h-2.5"
                      />
                      <span>{g.nome}</span>
                    </button>
                  );
                })}
            </div>
          </div>

          {/* Filtro fasi */}
          <div>
            <div className="etichetta mb-1.5">Fasi</div>
            <div className="flex flex-wrap gap-1">
              {FASI_FILTRO.map((f) => {
                const attivo = filtroFasi.has(f.id);
                return (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => alternaFase(f.id)}
                    className={`
                      px-2 py-1 text-xs font-sans border transition-colors
                      ${
                        attivo
                          ? "border-scarlatto bg-scarlatto/10 text-scarlatto"
                          : "border-inchiostro/25 hover:border-inchiostro/50"
                      }
                    `}
                  >
                    {f.etichetta}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Search testuale */}
          <div>
            <div className="etichetta mb-1.5">Cerca nei dati</div>
            <div className="relative">
              <Search
                size={12}
                className="absolute left-2 top-1/2 -translate-y-1/2 text-inchiostro-fioco"
              />
              <input
                type="text"
                value={testoCerca}
                onChange={(e) => onCambiaTestoCerca(e.target.value)}
                placeholder="Es: alaska, attacco, jolly…"
                className="campo-testo pl-7 py-1.5 text-xs font-sans"
              />
              {testoCerca ? (
                <button
                  type="button"
                  onClick={() => onCambiaTestoCerca("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-inchiostro-fioco hover:text-scarlatto"
                  aria-label="Pulisci ricerca"
                >
                  <X size={12} />
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
