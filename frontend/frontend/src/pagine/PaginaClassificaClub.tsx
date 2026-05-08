/**
 * Pagina "Classifica club".
 *
 * Mostra una vista cross-partita aggregata per nome giocatore
 * (case-insensitive). L'utente può cambiare la metrica di ranking via
 * segmented control (bilancio armate / attacchi / conquiste / difese).
 */

import { useEffect, useMemo, useState } from "react";
import { Trophy, Users, Swords, Shield, Map, Dice5 } from "lucide-react";

import {
  apiClassificaClub,
  bilancioArmate,
  ErroreApi,
  type ClassificaClub,
  type GiocatoreClub,
} from "@/api";
import { MessaggioErrore } from "@/componenti/decorativi";

type MetricaRanking =
  | "bilancio"
  | "attacchi"
  | "conquiste"
  | "difese"
  | "armate_inflitte_difendendo";

const ETICHETTE_METRICA: Record<MetricaRanking, string> = {
  bilancio: "Bilancio",
  attacchi: "Attacchi",
  conquiste: "Conquiste",
  difese: "Difese",
  armate_inflitte_difendendo: "Difesa efficace",
};

export function PaginaClassificaClub() {
  const [classifica, setClassifica] = useState<ClassificaClub | null>(null);
  const [caricamento, setCaricamento] = useState(true);
  const [errore, setErrore] = useState<string | null>(null);
  const [metrica, setMetrica] = useState<MetricaRanking>("bilancio");

  useEffect(() => {
    let attivo = true;
    setCaricamento(true);
    setErrore(null);
    apiClassificaClub
      .ottieni()
      .then((c) => {
        if (attivo) setClassifica(c);
      })
      .catch((e) => {
        if (!attivo) return;
        const messaggio =
          e instanceof ErroreApi ? e.dettaglio : "Errore caricamento";
        setErrore(messaggio);
      })
      .finally(() => {
        if (attivo) setCaricamento(false);
      });
    return () => {
      attivo = false;
    };
  }, []);

  // Ordinamento client-side per metrica selezionata
  const giocatoriOrdinati = useMemo(() => {
    if (!classifica) return [];
    const punteggio = (g: GiocatoreClub): number => {
      switch (metrica) {
        case "bilancio":
          return bilancioArmate(g);
        case "attacchi":
          return g.n_attacchi_totali;
        case "conquiste":
          return g.n_territori_conquistati_tot;
        case "difese":
          return g.n_difese_totali;
        case "armate_inflitte_difendendo":
          return g.armate_inflitte_difendendo_tot;
      }
    };
    return [...classifica.giocatori].sort(
      (a, b) => punteggio(b) - punteggio(a),
    );
  }, [classifica, metrica]);

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h2 className="text-2xl font-display text-inchiostro">
          Classifica club
        </h2>
        {classifica ? (
          <span className="text-xs text-inchiostro-fioco">
            {classifica.n_partite_totali} partite registrate ·{" "}
            {classifica.n_giocatori_distinti} giocatori distinti
          </span>
        ) : null}
      </div>

      {errore ? <MessaggioErrore testo={errore} /> : null}

      {caricamento ? (
        <p className="text-sm text-inchiostro-fioco italic">
          Calcolando aggregazioni cross-partita…
        </p>
      ) : null}

      {classifica && classifica.n_partite_totali === 0 ? (
        <section className="carta p-8 text-center text-inchiostro-tenue">
          <Trophy className="w-8 h-8 mx-auto mb-3 text-inchiostro-fioco" />
          <p className="text-sm">
            Nessuna partita ancora registrata. La classifica si popolerà dopo
            la prima partita.
          </p>
        </section>
      ) : null}

      {classifica && classifica.n_partite_totali > 0 ? (
        <>
          <RiepilogoGlobale classifica={classifica} />

          <section className="carta p-5 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <h3 className="etichetta">Leaderboard</h3>
              <SelettoreMetrica metrica={metrica} onChange={setMetrica} />
            </div>

            {giocatoriOrdinati.length === 0 ? (
              <p className="text-sm text-inchiostro-fioco italic">
                Nessun giocatore aggregato.
              </p>
            ) : (
              <Tabella giocatori={giocatoriOrdinati} metrica={metrica} />
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}

// === Sotto-componenti ===

function RiepilogoGlobale({ classifica }: { classifica: ClassificaClub }) {
  return (
    <section className="carta p-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
        <BlockStat
          label="Partite"
          valore={classifica.n_partite_totali}
          sotto={`${classifica.n_partite_con_eventi} con eventi`}
        />
        <BlockStat
          label="Giocatori"
          valore={classifica.n_giocatori_distinti}
        />
        <BlockStat
          label="Attacchi"
          valore={classifica.n_attacchi_totali}
        />
        <BlockStat
          label="Tempo gioco"
          valore={formatDurata(classifica.durata_totale_sec)}
          sotto="totale"
        />
      </div>
    </section>
  );
}

function BlockStat({
  label,
  valore,
  sotto,
}: {
  label: string;
  valore: number | string;
  sotto?: string;
}) {
  return (
    <div className="border border-inchiostro/10 rounded p-3">
      <div className="text-2xl font-display text-inchiostro tabular-nums">
        {valore}
      </div>
      <div className="text-[10px] text-inchiostro-fioco uppercase tracking-wider mt-1">
        {label}
      </div>
      {sotto ? (
        <div className="text-[10px] text-inchiostro-fioco italic mt-0.5">
          {sotto}
        </div>
      ) : null}
    </div>
  );
}

function SelettoreMetrica({
  metrica,
  onChange,
}: {
  metrica: MetricaRanking;
  onChange: (m: MetricaRanking) => void;
}) {
  const opzioni: MetricaRanking[] = [
    "bilancio",
    "attacchi",
    "difese",
    "conquiste",
    "armate_inflitte_difendendo",
  ];
  return (
    <div className="inline-flex border border-inchiostro/15 rounded overflow-hidden text-xs">
      {opzioni.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={`px-2.5 py-1 transition ${
            metrica === opt
              ? "bg-inchiostro text-pergamena"
              : "text-inchiostro-tenue hover:bg-pergamena-scura/40"
          }`}
        >
          {ETICHETTE_METRICA[opt]}
        </button>
      ))}
    </div>
  );
}

function Tabella({
  giocatori,
  metrica,
}: {
  giocatori: GiocatoreClub[];
  metrica: MetricaRanking;
}) {
  return (
    <div className="overflow-x-auto -mx-2 px-2">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-inchiostro-fioco border-b border-inchiostro/10">
            <th className="text-left py-2 pr-2 font-normal etichetta w-10">
              #
            </th>
            <th className="text-left py-2 pr-2 font-normal etichetta">
              <span className="inline-flex items-center gap-1">
                <Users className="w-3 h-3" /> Giocatore
              </span>
            </th>
            <th className="text-right px-1.5 font-normal etichetta">
              Partite
            </th>
            <th className="text-right px-1.5 font-normal etichetta">
              <span className="inline-flex items-center gap-1">
                <Swords className="w-3 h-3" /> Att
              </span>
            </th>
            <th className="text-right px-1.5 font-normal etichetta">
              <span className="inline-flex items-center gap-1">
                <Shield className="w-3 h-3" /> Dif
              </span>
            </th>
            <th className="text-right px-1.5 font-normal etichetta">
              <span className="inline-flex items-center gap-1">
                <Map className="w-3 h-3" /> Conq
              </span>
            </th>
            <th className="text-right px-1.5 font-normal etichetta">
              <span className="inline-flex items-center gap-1">
                <Dice5 className="w-3 h-3" /> Med
              </span>
            </th>
            <th className="text-right pl-1.5 font-normal etichetta">+/-</th>
          </tr>
        </thead>
        <tbody>
          {giocatori.map((g, i) => (
            <RigaGiocatore
              key={g.nome_normalizzato}
              giocatore={g}
              posizione={i + 1}
              metrica={metrica}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RigaGiocatore({
  giocatore: g,
  posizione,
  metrica,
}: {
  giocatore: GiocatoreClub;
  posizione: number;
  metrica: MetricaRanking;
}) {
  const bilancio = bilancioArmate(g);
  const segnoBilancio =
    bilancio > 0
      ? "text-bottiglia"
      : bilancio < 0
        ? "text-scarlatto"
        : "text-inchiostro-tenue";

  // Evidenzia colonna metrica selezionata
  const isCol = (col: MetricaRanking) =>
    metrica === col ? "font-semibold text-inchiostro" : "";

  const trofeo = posizione <= 3 ? <TrofeoPiccolo posizione={posizione} /> : null;

  return (
    <tr className="border-b border-inchiostro/5 last:border-0">
      <td className="py-2 pr-2 text-inchiostro-fioco tabular-nums">
        {posizione}
      </td>
      <td className="py-2 pr-2">
        <span className="inline-flex items-center gap-2">
          {trofeo}
          <span className="text-inchiostro">{g.nome}</span>
        </span>
      </td>
      <td className="text-right px-1.5 tabular-nums text-inchiostro-tenue">
        {g.n_partite}
      </td>
      <td className={`text-right px-1.5 tabular-nums ${isCol("attacchi")}`}>
        {g.n_attacchi_totali}
      </td>
      <td className={`text-right px-1.5 tabular-nums ${isCol("difese")}`}>
        {g.n_difese_totali}
      </td>
      <td className={`text-right px-1.5 tabular-nums ${isCol("conquiste")}`}>
        {g.n_territori_conquistati_tot}
      </td>
      <td className="text-right px-1.5 tabular-nums text-inchiostro-tenue">
        {g.media_dadi_globale !== null
          ? g.media_dadi_globale.toFixed(2)
          : "—"}
      </td>
      <td
        className={`text-right pl-1.5 tabular-nums font-medium ${segnoBilancio} ${isCol("bilancio")}`}
      >
        {bilancio > 0 ? `+${bilancio}` : bilancio}
      </td>
    </tr>
  );
}

function TrofeoPiccolo({ posizione }: { posizione: number }) {
  const colore =
    posizione === 1
      ? "text-oro"
      : posizione === 2
        ? "text-inchiostro-tenue"
        : "text-scarlatto/70";
  return <Trophy className={`w-3.5 h-3.5 ${colore}`} />;
}

function formatDurata(secondi: number): string {
  if (secondi <= 0) return "—";
  const ore = Math.floor(secondi / 3600);
  const minuti = Math.floor((secondi % 3600) / 60);
  if (ore > 0) {
    return `${ore}h ${minuti.toString().padStart(2, "0")}m`;
  }
  return `${minuti}m`;
}
