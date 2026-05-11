/**
 * Pagina Dashboard — sommario di stato del sistema.
 *
 * Mostra in una vista a "carte" le metriche chiave:
 * - Partite SQL (totali, ultimo mese, ultima settimana, eventi, video, ore registrate)
 * - Bundle in attesa (count, dimensione, eta del piu' vecchio)
 * - Spazio disco (video, frame, partite, totale)
 * - Servizi (scheduler, Roboflow)
 *
 * Polling ogni 30 secondi per refresh automatico.
 */

import { useEffect, useState } from "react";

import { apiDashboard, type SommarioDashboard } from "@/api";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatDurata(secondi: number): string {
  if (secondi === 0) return "0 ore";
  const ore = Math.floor(secondi / 3600);
  const minuti = Math.floor((secondi % 3600) / 60);
  if (ore > 0) {
    return `${ore}h ${minuti}m`;
  }
  return `${minuti}m`;
}

export default function PaginaDashboard() {
  const [dato, setDato] = useState<SommarioDashboard | null>(null);
  const [errore, setErrore] = useState<string | null>(null);
  const [caricamento, setCaricamento] = useState(true);

  useEffect(() => {
    let attivo = true;
    const carica = (): void => {
      void apiDashboard
        .sommario()
        .then((d) => {
          if (attivo) {
            setDato(d);
            setErrore(null);
            setCaricamento(false);
          }
        })
        .catch((e) => {
          if (attivo) {
            setErrore(e instanceof Error ? e.message : String(e));
            setCaricamento(false);
          }
        });
    };

    carica();
    const id = setInterval(carica, 30_000);
    return () => {
      attivo = false;
      clearInterval(id);
    };
  }, []);

  if (caricamento && dato === null) {
    return <div className="p-8 text-inchiostro-tenue">Caricamento…</div>;
  }

  if (errore && dato === null) {
    return (
      <div className="p-8 text-rosso">
        Errore nel caricamento del sommario: {errore}
      </div>
    );
  }

  if (!dato) return null;

  return (
    <div className="max-w-5xl mx-auto p-8">
      <header className="mb-8">
        <h1 className="text-3xl font-display mb-1">Dashboard</h1>
        <p className="text-sm text-inchiostro-tenue">
          Aggiornato:{" "}
          {new Date(dato.timestamp).toLocaleTimeString("it-IT", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })}
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card Partite */}
        <section className="border border-inchiostro/10 rounded-md p-6">
          <h2 className="etichetta mb-4">Partite</h2>
          <div className="space-y-3">
            <MetricaPrincipale
              valore={dato.partite.n_partite_totali}
              etichetta="Partite registrate"
            />
            <div className="grid grid-cols-2 gap-3 pt-3 border-t border-inchiostro/10">
              <Metrica
                valore={dato.partite.n_partite_ultimo_mese}
                etichetta="Ultimo mese"
              />
              <Metrica
                valore={dato.partite.n_partite_ultima_settimana}
                etichetta="Ultima settimana"
              />
              <Metrica
                valore={dato.partite.n_eventi_totali}
                etichetta="Eventi BLE totali"
              />
              <Metrica
                valore={formatDurata(dato.partite.durata_video_totale_sec)}
                etichetta="Ore registrate"
              />
            </div>
          </div>
        </section>

        {/* Card Bundle */}
        <section className="border border-inchiostro/10 rounded-md p-6">
          <h2 className="etichetta mb-4">Bundle in attesa</h2>
          <div className="space-y-3">
            <MetricaPrincipale
              valore={dato.bundle.n_bundle_in_attesa}
              etichetta={
                dato.bundle.n_bundle_in_attesa === 0
                  ? "Nessun bundle da promuovere"
                  : "Bundle da promuovere"
              }
            />
            {dato.bundle.n_bundle_in_attesa > 0 ? (
              <div className="grid grid-cols-2 gap-3 pt-3 border-t border-inchiostro/10">
                <Metrica
                  valore={formatBytes(dato.bundle.dimensione_totale_byte)}
                  etichetta="Spazio occupato"
                />
                <Metrica
                  valore={
                    dato.bundle.bundle_piu_vecchio_giorni !== null
                      ? `${dato.bundle.bundle_piu_vecchio_giorni}g`
                      : "—"
                  }
                  etichetta="Piu' vecchio"
                />
              </div>
            ) : null}
          </div>
        </section>

        {/* Card Spazio */}
        <section className="border border-inchiostro/10 rounded-md p-6">
          <h2 className="etichetta mb-4">Spazio disco</h2>
          <div className="space-y-3">
            <MetricaPrincipale
              valore={formatBytes(dato.spazio.totale_byte)}
              etichetta="Spazio totale"
            />
            <div className="grid grid-cols-3 gap-3 pt-3 border-t border-inchiostro/10">
              <Metrica
                valore={formatBytes(dato.spazio.storage_video_byte)}
                etichetta="Video"
              />
              <Metrica
                valore={formatBytes(dato.spazio.storage_frame_byte)}
                etichetta="Frame"
              />
              <Metrica
                valore={formatBytes(dato.spazio.storage_partite_byte)}
                etichetta="Bundle"
              />
            </div>
          </div>
        </section>

        {/* Card Servizi */}
        <section className="border border-inchiostro/10 rounded-md p-6">
          <h2 className="etichetta mb-4">Servizi</h2>
          <div className="space-y-3">
            <StatoServizio
              nome="Scheduler cleanup"
              attivo={dato.servizi.scheduler_in_esecuzione}
              tooltip={
                !dato.servizi.scheduler_abilitato
                  ? "Disabilitato — setta SCHEDULER_ABILITATO=true su Railway"
                  : dato.servizi.scheduler_in_esecuzione
                    ? "In esecuzione, cleanup giornaliero attivo"
                    : "Abilitato ma non in esecuzione"
              }
            />
            <StatoServizio
              nome="Roboflow CV"
              attivo={dato.servizi.roboflow_configurato}
              tooltip={
                dato.servizi.roboflow_configurato
                  ? "API key configurata, inferenze attive"
                  : "Non configurato — usa mock CV"
              }
            />
          </div>
        </section>
      </div>
    </div>
  );
}

function MetricaPrincipale({
  valore,
  etichetta,
}: {
  valore: string | number;
  etichetta: string;
}) {
  return (
    <div>
      <div className="text-4xl font-display text-inchiostro">{valore}</div>
      <div className="text-sm text-inchiostro-tenue">{etichetta}</div>
    </div>
  );
}

function Metrica({
  valore,
  etichetta,
}: {
  valore: string | number;
  etichetta: string;
}) {
  return (
    <div>
      <div className="text-xl font-display text-inchiostro">{valore}</div>
      <div className="text-xs text-inchiostro-tenue uppercase tracking-wider">
        {etichetta}
      </div>
    </div>
  );
}

function StatoServizio({
  nome,
  attivo,
  tooltip,
}: {
  nome: string;
  attivo: boolean;
  tooltip: string;
}) {
  return (
    <div className="flex items-start gap-3" title={tooltip}>
      <span
        className={`inline-block w-2 h-2 rounded-full mt-1.5 ${
          attivo ? "bg-verde" : "bg-inchiostro/30"
        }`}
        aria-hidden
      />
      <div className="flex-1">
        <div className="text-base text-inchiostro">{nome}</div>
        <div className="text-xs text-inchiostro-tenue">{tooltip}</div>
      </div>
    </div>
  );
}
