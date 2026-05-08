/**
 * Pannello "Statistiche partita".
 *
 * Mostra metriche aggregate calcolate dal backend dagli EventoValidato:
 * - Per giocatore: attacchi, conquiste, carte, dadi lanciati, perdite
 * - Globali: durata, n turni, n attacchi totali
 *
 * Refresh manuale con bottone (l'utente lo aggiorna dopo aver
 * accettato proposte o aggiunto eventi). Niente auto-fetch live per
 * non sovraccaricare il backend.
 */

import { useCallback, useEffect, useState } from "react";
import { BarChart3, RefreshCw, Trophy } from "lucide-react";

import {
  apiStatistiche,
  ErroreApi,
  type StatistichePartita,
  type StatisticheGiocatore,
} from "@/api";

import { MessaggioErrore, PallinoColore } from "./decorativi";

interface ProprietaPannelloStatistiche {
  partitaId: string;
  /** Trigger per ricarica automatica (incrementa quando cambiano gli eventi). */
  triggerRicarica?: number;
}

export function PannelloStatistiche({
  partitaId,
  triggerRicarica,
}: ProprietaPannelloStatistiche) {
  const [stat, setStat] = useState<StatistichePartita | null>(null);
  const [caricamento, setCaricamento] = useState(false);
  const [errore, setErrore] = useState<string | null>(null);

  const richiedi = useCallback(async () => {
    setErrore(null);
    setCaricamento(true);
    try {
      const ris = await apiStatistiche.ottieni(partitaId);
      setStat(ris);
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi
          ? e.dettaglio
          : "Errore nel caricamento delle statistiche";
      setErrore(messaggio);
    } finally {
      setCaricamento(false);
    }
  }, [partitaId]);

  // Carica al primo mount + ogni volta che triggerRicarica cambia
  useEffect(() => {
    void richiedi();
  }, [richiedi, triggerRicarica]);

  return (
    <section className="carta p-5">
      <header className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-inchiostro-tenue" />
          <h3 className="etichetta">Statistiche partita</h3>
        </div>
        <button
          type="button"
          onClick={richiedi}
          disabled={caricamento}
          className="text-xs text-inchiostro-tenue hover:text-inchiostro flex items-center gap-1 transition disabled:opacity-50"
          aria-label="Ricarica statistiche"
        >
          <RefreshCw
            className={`w-3 h-3 ${caricamento ? "animate-spin" : ""}`}
          />
          {caricamento ? "Calcolando…" : "Aggiorna"}
        </button>
      </header>

      {errore ? <MessaggioErrore testo={errore} /> : null}

      {stat ? <ContenutoStatistiche stat={stat} /> : null}

      {!stat && !caricamento && !errore ? (
        <p className="text-sm text-inchiostro-fioco italic">
          Nessun dato (la partita non ha ancora eventi validati).
        </p>
      ) : null}
    </section>
  );
}

// === Sotto-componente principale ===

function ContenutoStatistiche({ stat }: { stat: StatistichePartita }) {
  if (stat.n_eventi_validati === 0) {
    return (
      <p className="text-sm text-inchiostro-fioco italic">
        Nessun evento validato. Accetta qualche proposta o aggiungi eventi
        manuali per vedere le statistiche.
      </p>
    );
  }

  const topAttaccante = trovaTop(
    stat.statistiche_giocatori,
    (s) => s.n_attacchi,
  );
  const topConquistatore = trovaTop(
    stat.statistiche_giocatori,
    (s) => s.n_territori_conquistati,
  );
  const topDifensore = trovaTop(
    stat.statistiche_giocatori,
    (s) => s.armate_inflitte_difendendo,
  );

  return (
    <div className="space-y-5">
      {/* Riepilogo globale */}
      <div className="grid grid-cols-3 gap-3 text-center">
        <BlockStatGlobale label="Eventi" valore={stat.n_eventi_validati} />
        <BlockStatGlobale label="Turni" valore={stat.n_turni} />
        <BlockStatGlobale label="Attacchi" valore={stat.n_attacchi_totali} />
      </div>

      {stat.durata_sec !== null ? (
        <div className="text-xs text-inchiostro-tenue text-center">
          Durata partita: {formatDurata(stat.durata_sec)}
        </div>
      ) : null}

      {/* Top performers (badge) */}
      {topAttaccante || topConquistatore || topDifensore ? (
        <div className="flex flex-wrap gap-2 justify-center">
          {topAttaccante ? (
            <BadgePremio
              etichetta="Più aggressivo"
              giocatore={topAttaccante}
              valore={`${topAttaccante.n_attacchi} attacchi`}
            />
          ) : null}
          {topConquistatore ? (
            <BadgePremio
              etichetta="Più conquiste"
              giocatore={topConquistatore}
              valore={`${topConquistatore.n_territori_conquistati} territori`}
            />
          ) : null}
          {topDifensore ? (
            <BadgePremio
              etichetta="Miglior difesa"
              giocatore={topDifensore}
              valore={`${topDifensore.armate_inflitte_difendendo} armate inflitte`}
            />
          ) : null}
        </div>
      ) : null}

      {/* Tabella per giocatore */}
      <div className="overflow-x-auto -mx-2 px-2">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-inchiostro-fioco border-b border-inchiostro/10">
              <th className="text-left py-2 pr-2 font-normal etichetta">
                Giocatore
              </th>
              <th className="text-right px-1.5 font-normal etichetta" title="Numero attacchi dichiarati">
                Att
              </th>
              <th className="text-right px-1.5 font-normal etichetta" title="Numero difese subite (calcolato dal motore)">
                Dif
              </th>
              <th className="text-right px-1.5 font-normal etichetta" title="Territori conquistati">
                Conq
              </th>
              <th className="text-right px-1.5 font-normal etichetta" title="Carte pescate">
                Carte
              </th>
              <th className="text-right px-1.5 font-normal etichetta" title="Tris giocati">
                Tris
              </th>
              <th className="text-right px-1.5 font-normal etichetta" title="Armate piazzate (totale rinforzi)">
                Rinf
              </th>
              <th className="text-right px-1.5 font-normal etichetta" title="Media valore dadi tirati">
                Med
              </th>
              <th className="text-right pl-1.5 font-normal etichetta" title="Bilancio armate: inflitte (att+dif) − perse (att+dif)">
                +/−
              </th>
            </tr>
          </thead>
          <tbody>
            {stat.statistiche_giocatori.map((sg) => (
              <RigaGiocatore key={sg.giocatore_id} sg={sg} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-[10px] text-inchiostro-fioco italic">
        Statistiche di difesa calcolate ricostruendo lo stato della partita
        evento per evento (chi possedeva il territorio attaccato in quel
        momento). Se la partita ha errori di applicazione, le difese
        successive a quel punto potrebbero essere parziali.
      </p>
    </div>
  );
}

// === Componenti di supporto ===

function BlockStatGlobale({
  label,
  valore,
}: {
  label: string;
  valore: number | string;
}) {
  return (
    <div className="border border-inchiostro/10 rounded p-2">
      <div className="text-2xl font-serif text-inchiostro tabular-nums">
        {valore}
      </div>
      <div className="text-[10px] text-inchiostro-fioco uppercase tracking-wider mt-0.5">
        {label}
      </div>
    </div>
  );
}

function BadgePremio({
  etichetta,
  giocatore,
  valore,
}: {
  etichetta: string;
  giocatore: StatisticheGiocatore;
  valore: string;
}) {
  return (
    <div className="inline-flex items-center gap-2 bg-pergamena-scura/40 border border-inchiostro/10 px-2.5 py-1 rounded-full text-xs">
      <Trophy className="w-3 h-3 text-oro" />
      <span className="text-inchiostro-fioco">{etichetta}:</span>
      <PallinoColore colore={giocatore.colore} />
      <span className="font-medium text-inchiostro">{giocatore.nome}</span>
      <span className="text-inchiostro-fioco">({valore})</span>
    </div>
  );
}

function RigaGiocatore({ sg }: { sg: StatisticheGiocatore }) {
  // Bilancio totale (attacco + difesa)
  const inflitte = sg.armate_inflitte_attaccando + sg.armate_inflitte_difendendo;
  const perse = sg.armate_perse_attaccando + sg.armate_perse_difendendo;
  const diff = inflitte - perse;
  const segnoDiff =
    diff > 0
      ? "text-bottiglia"
      : diff < 0
        ? "text-scarlatto"
        : "text-inchiostro-tenue";

  return (
    <tr className="border-b border-inchiostro/5 last:border-0">
      <td className="py-2 pr-2">
        <div className="flex items-center gap-2">
          <PallinoColore colore={sg.colore} />
          <span className="text-inchiostro">{sg.nome}</span>
        </div>
      </td>
      <td className="text-right px-1.5 tabular-nums">{sg.n_attacchi}</td>
      <td className="text-right px-1.5 tabular-nums text-inchiostro-tenue">
        {sg.n_difese}
      </td>
      <td className="text-right px-1.5 tabular-nums">
        {sg.n_territori_conquistati}
      </td>
      <td className="text-right px-1.5 tabular-nums">{sg.n_carte_pescate}</td>
      <td className="text-right px-1.5 tabular-nums">{sg.n_tris_giocati}</td>
      <td className="text-right px-1.5 tabular-nums">
        {sg.n_armate_piazzate_totali}
      </td>
      <td className="text-right px-1.5 tabular-nums">
        {sg.media_dadi_lanciati !== null ? sg.media_dadi_lanciati.toFixed(1) : "—"}
      </td>
      <td className={`text-right pl-1.5 tabular-nums font-medium ${segnoDiff}`}>
        {diff > 0 ? `+${diff}` : diff}
      </td>
    </tr>
  );
}

// === Utility ===

function trovaTop(
  giocatori: StatisticheGiocatore[],
  metrica: (sg: StatisticheGiocatore) => number,
): StatisticheGiocatore | null {
  if (giocatori.length === 0) return null;
  let top = giocatori[0]!;
  for (const g of giocatori.slice(1)) {
    if (metrica(g) > metrica(top)) top = g;
  }
  // Se il top ha 0 in quella metrica, non vale la pena mostrarlo
  return metrica(top) > 0 ? top : null;
}

function formatDurata(secondi: number): string {
  const ore = Math.floor(secondi / 3600);
  const minuti = Math.floor((secondi % 3600) / 60);
  if (ore > 0) {
    return `${ore}h ${minuti.toString().padStart(2, "0")}m`;
  }
  return `${minuti}m`;
}
