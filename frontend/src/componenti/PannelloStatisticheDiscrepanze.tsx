/**
 * Pannello statistiche aggregate sulle divergenze CV ↔ motore.
 *
 * Visualizza:
 * - Distribuzione delta_assoluto (bar chart orizzontale)
 * - Conteggio per risoluzione
 * - Top 10 territori per delta totale
 * - Distribuzione per colore (con pallini)
 * - Confidence media
 *
 * Aiuta a capire pattern macroscopici: "il modello sbaglia spesso sul
 * blu?", "delta concentrati su pochi territori?", ecc.
 */

import { useEffect, useState } from "react";
import { BarChart3 } from "lucide-react";

import {
  apiInferenzeCV,
  ErroreApi,
  type StatisticheDiscrepanze,
} from "@/api";
import { MessaggioErrore, PallinoColore } from "@/componenti/decorativi";
import type { ColoreGiocatore } from "@/tipi/dominio";

interface ProprietaPannello {
  partitaId: string;
  /** Cambio di questo trigger forza ricarica. */
  triggerRicarica?: number;
}

const COLORI_VALIDI: ColoreGiocatore[] = [
  "rosso",
  "blu",
  "verde",
  "giallo",
  "nero",
  "viola",
];

export function PannelloStatisticheDiscrepanze({
  partitaId,
  triggerRicarica = 0,
}: ProprietaPannello) {
  const [stat, setStat] = useState<StatisticheDiscrepanze | null>(null);
  const [caricamento, setCaricamento] = useState(true);
  const [errore, setErrore] = useState<string | null>(null);

  useEffect(() => {
    let attivo = true;
    setCaricamento(true);
    setErrore(null);
    apiInferenzeCV
      .statisticheDiscrepanze(partitaId)
      .then((s) => {
        if (attivo) setStat(s);
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
  }, [partitaId, triggerRicarica]);

  if (caricamento) {
    return null;  // silenziosa
  }

  if (errore !== null) {
    return (
      <section className="carta p-5 space-y-2">
        <h3 className="etichetta">Statistiche discrepanze</h3>
        <MessaggioErrore testo={errore} />
      </section>
    );
  }

  if (stat === null || stat.n_totali === 0) {
    return null;  // niente da mostrare se nessuna divergenza
  }

  return (
    <section className="carta p-5 space-y-4">
      <header className="flex items-center justify-between">
        <h3 className="etichetta inline-flex items-center gap-2">
          <BarChart3 className="w-3.5 h-3.5" />
          Statistiche discrepanze
        </h3>
        <span className="text-xs text-inchiostro-fioco tabular-nums">
          {stat.n_totali} divergenze · confidence media{" "}
          {(stat.confidence_media * 100).toFixed(0)}%
        </span>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <DistribuzioneDelta distribuzione={stat.distribuzione_delta} />
        <PerRisoluzione perRisoluzione={stat.per_risoluzione} />
        <TopTerritori top={stat.top_territori} />
        <PerColore perColore={stat.per_colore} />
      </div>
    </section>
  );
}

// === Sotto-componenti ===

function DistribuzioneDelta({
  distribuzione,
}: {
  distribuzione: Record<string, number>;
}) {
  // Ordina chiavi: 1, 2, 3, 4, 5+
  const ordine = ["1", "2", "3", "4", "5+"];
  const max = Math.max(...Object.values(distribuzione), 1);

  return (
    <div>
      <div className="etichetta mb-2">Delta assoluto</div>
      <div className="space-y-1">
        {ordine.map((bucket) => {
          const valore = distribuzione[bucket] ?? 0;
          const percentuale = (valore / max) * 100;
          return (
            <div key={bucket} className="flex items-center gap-2 text-xs">
              <span className="w-6 text-right tabular-nums text-inchiostro-fioco">
                {bucket}
              </span>
              <div className="flex-1 h-4 bg-pergamena-scura/30 rounded relative overflow-hidden">
                <div
                  className={`h-full transition-all ${
                    bucket === "5+"
                      ? "bg-scarlatto"
                      : bucket === "4" || bucket === "3"
                        ? "bg-bronzo"
                        : "bg-bottiglia/70"
                  }`}
                  style={{ width: `${percentuale}%` }}
                />
              </div>
              <span className="w-8 text-right tabular-nums text-inchiostro">
                {valore}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PerRisoluzione({
  perRisoluzione,
}: {
  perRisoluzione: Record<string, number>;
}) {
  const config: Record<string, { etichetta: string; classe: string }> = {
    aperta: { etichetta: "Aperte", classe: "text-scarlatto" },
    accettata_motore: { etichetta: "Motore ok", classe: "text-bottiglia" },
    accettata_cv: { etichetta: "CV ok", classe: "text-bronzo" },
    evento_aggiunto: { etichetta: "Evento agg.", classe: "text-inchiostro" },
  };
  const totale = Object.values(perRisoluzione).reduce((a, b) => a + b, 0);

  return (
    <div>
      <div className="etichetta mb-2">Stato review</div>
      <div className="space-y-1">
        {Object.entries(config).map(([chiave, c]) => {
          const valore = perRisoluzione[chiave] ?? 0;
          const percentuale = totale > 0 ? (valore / totale) * 100 : 0;
          return (
            <div key={chiave} className="flex items-center gap-2 text-xs">
              <span className={`w-24 ${c.classe}`}>{c.etichetta}</span>
              <div className="flex-1 h-2 bg-pergamena-scura/30 rounded overflow-hidden">
                <div
                  className={`h-full ${c.classe.replace("text-", "bg-")}`}
                  style={{ width: `${percentuale}%`, opacity: 0.6 }}
                />
              </div>
              <span className="w-8 text-right tabular-nums text-inchiostro">
                {valore}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function TopTerritori({
  top,
}: {
  top: { territorio: string; delta_totale: number }[];
}) {
  if (top.length === 0) {
    return (
      <div>
        <div className="etichetta mb-2">Top territori (delta)</div>
        <p className="text-xs text-inchiostro-fioco italic">—</p>
      </div>
    );
  }
  const max = top[0]?.delta_totale ?? 1;

  return (
    <div className="md:col-span-2">
      <div className="etichetta mb-2">Top territori (delta totale)</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {top.slice(0, 10).map((t) => {
          const percentuale = (t.delta_totale / max) * 100;
          return (
            <div
              key={t.territorio}
              className="flex items-center gap-2 text-xs"
            >
              <span className="flex-1 truncate text-inchiostro">
                {formatTerritorio(t.territorio)}
              </span>
              <div className="w-12 h-2 bg-pergamena-scura/30 rounded overflow-hidden flex-shrink-0">
                <div
                  className="h-full bg-scarlatto/70"
                  style={{ width: `${percentuale}%` }}
                />
              </div>
              <span className="w-6 text-right tabular-nums text-inchiostro-fioco">
                {t.delta_totale}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PerColore({ perColore }: { perColore: Record<string, number> }) {
  const totale = Object.values(perColore).reduce((a, b) => a + b, 0);
  const valori = COLORI_VALIDI.filter((c) => (perColore[c] ?? 0) > 0).map(
    (c) => ({
      colore: c,
      n: perColore[c] ?? 0,
      percentuale: totale > 0 ? ((perColore[c] ?? 0) / totale) * 100 : 0,
    }),
  );

  if (valori.length === 0) {
    return null;
  }

  return (
    <div>
      <div className="etichetta mb-2">Per colore</div>
      <div className="space-y-1">
        {valori.map(({ colore, n, percentuale }) => (
          <div key={colore} className="flex items-center gap-2 text-xs">
            <PallinoColore colore={colore} />
            <span className="flex-1 capitalize text-inchiostro">{colore}</span>
            <span className="text-inchiostro-fioco tabular-nums">
              {n} ({percentuale.toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatTerritorio(slug: string): string {
  return slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
