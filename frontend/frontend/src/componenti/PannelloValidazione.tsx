/**
 * Pannello "Verifica coerenza".
 *
 * Mostra i problemi rilevati dal validatore: errori bloccanti
 * (rosso scarlatto) + avvisi (giallo oro). L'utente può cliccare
 * un problema per saltare alla posizione cronologica dell'evento
 * (se nota onSeek è presente).
 *
 * Non auto-fetch: l'utente clicca "Verifica" quando vuole. Auto-fetch
 * sarebbe rumoroso e poco utile (ogni edit cambierebbe lo stato).
 */

import { useState } from "react";
import { AlertCircle, AlertTriangle, CheckCircle2, ShieldCheck } from "lucide-react";

import {
  apiValidazione,
  ErroreApi,
  type ProblemaCoerenza,
  type RisultatoValidazioneCoerenza,
} from "@/api";

import { MessaggioErrore } from "./decorativi";

interface ProprietaPannelloValidazione {
  partitaId: string;
  /** Callback per saltare a un evento nella lista (opzionale). */
  onSelezionaEvento?: (eventoId: string) => void;
}

export function PannelloValidazione({
  partitaId,
  onSelezionaEvento,
}: ProprietaPannelloValidazione) {
  const [risultato, setRisultato] =
    useState<RisultatoValidazioneCoerenza | null>(null);
  const [caricamento, setCaricamento] = useState(false);
  const [errore, setErrore] = useState<string | null>(null);

  async function verifica() {
    setErrore(null);
    setCaricamento(true);
    try {
      const ris = await apiValidazione.valida(partitaId);
      setRisultato(ris);
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi ? e.dettaglio : "Errore di validazione";
      setErrore(messaggio);
    } finally {
      setCaricamento(false);
    }
  }

  return (
    <section className="carta p-5">
      <header className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-inchiostro-tenue" />
          <h3 className="etichetta">Verifica coerenza</h3>
        </div>
        <button
          type="button"
          onClick={verifica}
          disabled={caricamento}
          className="text-xs text-scarlatto hover:text-scarlatto-scuro transition disabled:opacity-50"
        >
          {caricamento ? "Verificando…" : risultato ? "Riverifica" : "Verifica"}
        </button>
      </header>

      {errore ? <MessaggioErrore testo={errore} /> : null}

      {risultato ? (
        <ContenutoRisultato
          risultato={risultato}
          onSelezionaEvento={onSelezionaEvento}
        />
      ) : null}

      {!risultato && !caricamento && !errore ? (
        <p className="text-sm text-inchiostro-fioco italic">
          Clicca "Verifica" per controllare la coerenza degli eventi prima di
          ricostruire la partita.
        </p>
      ) : null}
    </section>
  );
}

function ContenutoRisultato({
  risultato,
  onSelezionaEvento,
}: {
  risultato: RisultatoValidazioneCoerenza;
  onSelezionaEvento?: (eventoId: string) => void;
}) {
  if (risultato.n_eventi_analizzati === 0) {
    return (
      <p className="text-sm text-inchiostro-fioco italic">
        Nessun evento da validare.
      </p>
    );
  }

  if (risultato.problemi.length === 0) {
    return (
      <div className="flex items-center gap-2 text-bottiglia bg-bottiglia/5 border border-bottiglia/20 rounded px-3 py-2 text-sm">
        <CheckCircle2 className="w-4 h-4" />
        <span>
          Nessun problema rilevato su {risultato.n_eventi_analizzati} eventi.
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Riepilogo */}
      <div className="flex gap-3 text-sm">
        {risultato.n_errori > 0 ? (
          <span className="inline-flex items-center gap-1 text-scarlatto">
            <AlertCircle className="w-4 h-4" />
            {risultato.n_errori} errori
          </span>
        ) : null}
        {risultato.n_avvisi > 0 ? (
          <span className="inline-flex items-center gap-1 text-oro">
            <AlertTriangle className="w-4 h-4" />
            {risultato.n_avvisi} avvisi
          </span>
        ) : null}
      </div>

      {/* Lista problemi */}
      <ul className="space-y-1.5">
        {risultato.problemi.map((p, i) => (
          <RigaProblema
            key={`${p.evento_id ?? "globale"}-${i}`}
            problema={p}
            onClick={
              onSelezionaEvento && p.evento_id
                ? () => onSelezionaEvento(p.evento_id!)
                : undefined
            }
          />
        ))}
      </ul>

      {risultato.n_errori > 0 ? (
        <p className="text-xs text-scarlatto italic">
          Gli errori bloccheranno la ricostruzione. Correggili prima di lanciare
          "Ricostruisci".
        </p>
      ) : (
        <p className="text-xs text-oro italic">
          Solo avvisi: la ricostruzione può procedere ma controlla che i dati
          siano corretti.
        </p>
      )}
    </div>
  );
}

function RigaProblema({
  problema,
  onClick,
}: {
  problema: ProblemaCoerenza;
  onClick?: () => void;
}) {
  const [stiliBordo, stiliTesto, Icona] =
    problema.severita === "errore"
      ? ["border-scarlatto/30 bg-scarlatto/5", "text-scarlatto", AlertCircle]
      : ["border-oro/30 bg-oro/5", "text-oro", AlertTriangle];

  const cliccabile = onClick !== undefined;
  const Wrapper = cliccabile ? "button" : "div";

  return (
    <li>
      <Wrapper
        type={cliccabile ? "button" : undefined}
        onClick={onClick}
        className={`w-full text-left flex items-start gap-2 px-3 py-2 rounded border ${stiliBordo} ${cliccabile ? "hover:opacity-80 cursor-pointer transition" : ""}`}
      >
        <Icona className={`w-4 h-4 ${stiliTesto} flex-shrink-0 mt-0.5`} />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-inchiostro">{problema.messaggio}</div>
          <div className="flex gap-2 mt-1 text-[10px] text-inchiostro-fioco font-mono">
            <span>{problema.codice}</span>
            {problema.posizione !== null ? (
              <span>· pos {problema.posizione}</span>
            ) : null}
          </div>
        </div>
      </Wrapper>
    </li>
  );
}
