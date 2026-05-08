/**
 * Modale per il setup automatico di una partita.
 *
 * Genera in transazione tutti gli eventi di setup applicando le regole
 * Risiko EG:
 * - 42 territori distribuiti round-robin tra i giocatori
 * - 40/35/30/25/20 armate iniziali secondo numero giocatori (2-6)
 * - Un obiettivo random distinto per ogni giocatore
 * - `partita_inizio` con il primo giocatore selezionato
 *
 * L'operazione è atomica e non distruttiva: fallisce con 409 se la
 * partita ha già eventi validati.
 */

import { useState, type FormEvent } from "react";
import { Sparkles, X } from "lucide-react";

import {
  apiSetupAutomatico,
  ErroreApi,
  type SetupAutomaticoRisposta,
} from "@/api";
import type { GiocatorePartita } from "@/tipi/dominio";
import { PallinoColore } from "./decorativi";

interface ProprietaModaleSetupAutomatico {
  partitaId: string;
  giocatori: GiocatorePartita[];
  onAnnulla: () => void;
  onCompletato: (risposta: SetupAutomaticoRisposta) => void;
}

// Armate iniziali per numero giocatori (regolamento EG)
const ARMATE_PER_GIOCATORI: Record<number, number> = {
  2: 40,
  3: 35,
  4: 30,
  5: 25,
  6: 20,
};

export function ModaleSetupAutomatico({
  partitaId,
  giocatori,
  onAnnulla,
  onCompletato,
}: ProprietaModaleSetupAutomatico) {
  // Default primo giocatore: ordine_seduta=1
  const giocatoriOrdinati = [...giocatori].sort(
    (a, b) => a.ordine_seduta - b.ordine_seduta,
  );
  const primoDefault = giocatoriOrdinati[0]?.id ?? "";

  const [primoGiocatoreId, setPrimoGiocatoreId] = useState(primoDefault);
  const [usaSeed, setUsaSeed] = useState(false);
  const [seed, setSeed] = useState<number>(42);

  const [erroreInvio, setErroreInvio] = useState<string | null>(null);
  const [inInvio, setInInvio] = useState(false);

  const armateAttese = ARMATE_PER_GIOCATORI[giocatori.length] ?? 0;
  const nObiettivi = giocatori.length;
  const nEventiTotali = 42 + nObiettivi + 1;

  async function inviaForm(evento: FormEvent) {
    evento.preventDefault();
    setErroreInvio(null);
    setInInvio(true);
    try {
      const risposta = await apiSetupAutomatico.esegui(partitaId, {
        primo_giocatore_id: primoGiocatoreId || null,
        seed: usaSeed ? seed : null,
      });
      onCompletato(risposta);
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi ? e.dettaglio : "Errore durante il setup";
      setErroreInvio(messaggio);
      setInInvio(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-inchiostro/40 overflow-y-auto py-8 px-4">
      <form
        onSubmit={inviaForm}
        className="bg-pergamena w-full max-w-xl border border-inchiostro shadow-cartaHover"
      >
        <header className="px-6 py-4 border-b border-inchiostro/15 flex items-center justify-between">
          <div>
            <div className="etichetta-rossa">Setup automatico</div>
            <h3 className="font-display text-2xl font-semibold tracking-crisp">
              Genera la partita iniziale
            </h3>
          </div>
          <button
            type="button"
            onClick={onAnnulla}
            className="p-1.5 hover:text-scarlatto transition-colors"
            aria-label="Chiudi"
          >
            <X size={20} />
          </button>
        </header>

        <div className="px-6 py-5 space-y-5">
          {/* Anteprima */}
          <div className="carta p-4 bg-pergamena-chiara">
            <div className="etichetta mb-2">Cosa verrà generato</div>
            <ul className="text-sm space-y-1 font-sans">
              <li>
                <strong className="font-mono num-tab">42</strong> eventi{" "}
                <span className="font-mono">territorio_assegnato_inizio</span>
              </li>
              <li>
                <strong className="font-mono num-tab">{nObiettivi}</strong>{" "}
                eventi <span className="font-mono">obiettivo_assegnato</span>{" "}
                <span className="text-inchiostro-tenue">
                  (uno distinto per giocatore)
                </span>
              </li>
              <li>
                <strong className="font-mono num-tab">1</strong> evento{" "}
                <span className="font-mono">partita_inizio</span>
              </li>
              <li className="text-inchiostro-tenue pt-1 border-t border-inchiostro/10 mt-2">
                Totale:{" "}
                <strong className="font-mono num-tab text-inchiostro">
                  {nEventiTotali}
                </strong>{" "}
                eventi · armate iniziali per giocatore:{" "}
                <strong className="font-mono num-tab text-inchiostro">
                  {armateAttese}
                </strong>
              </li>
            </ul>
          </div>

          {/* Primo giocatore */}
          <label className="block">
            <span className="etichetta block mb-1.5">
              Primo giocatore <span className="text-scarlatto">*</span>
            </span>
            <div className="flex items-center gap-2">
              <select
                required
                value={primoGiocatoreId}
                onChange={(e) => setPrimoGiocatoreId(e.target.value)}
                className="campo-testo flex-1"
              >
                {giocatoriOrdinati.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.nome} ({g.colore}) · seduta {g.ordine_seduta}
                  </option>
                ))}
              </select>
              {(() => {
                const g = giocatori.find((g) => g.id === primoGiocatoreId);
                return g ? (
                  <PallinoColore
                    colore={g.colore}
                    classeDimensione="w-4 h-4"
                  />
                ) : null;
              })()}
            </div>
          </label>

          {/* Seed (opzionale) */}
          <div>
            <label className="flex items-center gap-2 cursor-pointer mb-2">
              <input
                type="checkbox"
                checked={usaSeed}
                onChange={(e) => setUsaSeed(e.target.checked)}
                className="accent-scarlatto"
              />
              <span className="etichetta">Seed riproducibile</span>
              <span className="text-xs text-inchiostro-tenue">
                — opzionale, per debug
              </span>
            </label>
            {usaSeed ? (
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
                className="campo-testo font-mono num-tab w-32"
                min={0}
              />
            ) : null}
          </div>
        </div>

        {erroreInvio ? (
          <div className="px-6 py-3 border-t border-scarlatto/40 bg-scarlatto/5 text-sm text-inchiostro">
            <span className="etichetta-rossa">Errore:</span> {erroreInvio}
          </div>
        ) : null}

        <footer className="px-6 py-4 border-t border-inchiostro/15 flex items-center justify-end gap-3 bg-pergamena-chiara">
          <button type="button" onClick={onAnnulla} className="btn-secondario">
            Annulla
          </button>
          <button type="submit" disabled={inInvio} className="btn-primario">
            <Sparkles size={14} />
            {inInvio ? "Genero…" : "Genera setup"}
          </button>
        </footer>
      </form>
    </div>
  );
}
