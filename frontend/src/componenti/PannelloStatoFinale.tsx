/**
 * Pannello che mostra lo stato finale di una partita ricostruita.
 *
 * Due viste alternative selezionabili da toggle:
 * - **Mappa** (default): plancia SVG con i 42 territori colorati per
 *   controllore, le adiacenze tracciate, i bonus continente evidenziati.
 * - **Lista**: tabella per giocatore con conteggi e dettagli espandibili.
 *
 * Mostra anche eventuali errori di applicazione eventi, per facilitare
 * la correzione durante la review.
 */

import { useState } from "react";
import { format, parseISO } from "date-fns";
import {
  AlertTriangle,
  CheckCircle2,
  LayoutGrid,
  Map as MapIcon,
  RefreshCw,
} from "lucide-react";

import type {
  GiocatorePartita,
  RisultatoRicostruzione,
} from "@/tipi/dominio";
import { PallinoColore } from "./decorativi";
import { PlanciaMappa } from "./PlanciaMappa";

type VistaStato = "mappa" | "lista";

interface ProprietaPannelloStato {
  risultato: RisultatoRicostruzione | null;
  giocatoriPartita: GiocatorePartita[];
  inRicostruzione: boolean;
  onRicostruisci: () => void;
  /** Territorio attualmente selezionato (alone scarlatto sulla mappa). */
  territorioSelezionato?: string | null;
  /** Click su un territorio della mappa. */
  onClickTerritorio?: (slug: string) => void;
}

export function PannelloStatoFinale({
  risultato,
  giocatoriPartita,
  inRicostruzione,
  onRicostruisci,
  territorioSelezionato,
  onClickTerritorio,
}: ProprietaPannelloStato) {
  const [vista, setVista] = useState<VistaStato>("mappa");

  return (
    <section>
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <h3 className="etichetta">Stato ricostruito</h3>
        <div className="flex items-center gap-2">
          {risultato?.stato_finale ? (
            <ToggleVista vista={vista} onCambia={setVista} />
          ) : null}
          <button
            type="button"
            onClick={onRicostruisci}
            disabled={inRicostruzione}
            className="btn-primario"
          >
            <RefreshCw
              size={14}
              className={inRicostruzione ? "animate-spin" : ""}
            />
            {inRicostruzione ? "Ricostruisco…" : "Ricostruisci"}
          </button>
        </div>
      </div>

      {risultato === null ? (
        <div className="border border-dashed border-inchiostro/20 p-6 text-center text-inchiostro-tenue text-sm">
          Nessuna ricostruzione disponibile. Premi "Ricostruisci" per
          applicare gli eventi validati al motore.
        </div>
      ) : (
        <RisultatoVisualizzato
          risultato={risultato}
          giocatoriPartita={giocatoriPartita}
          vista={vista}
          territorioSelezionato={territorioSelezionato}
          onClickTerritorio={onClickTerritorio}
        />
      )}
    </section>
  );
}

function ToggleVista({
  vista,
  onCambia,
}: {
  vista: VistaStato;
  onCambia: (v: VistaStato) => void;
}) {
  return (
    <div className="inline-flex border border-inchiostro/30">
      <button
        type="button"
        onClick={() => onCambia("mappa")}
        className={`px-3 py-1.5 text-xs uppercase tracking-widest transition-colors ${
          vista === "mappa"
            ? "bg-inchiostro text-pergamena"
            : "text-inchiostro-tenue hover:text-inchiostro"
        }`}
        title="Vista mappa"
      >
        <MapIcon size={12} className="inline mr-1.5" />
        Mappa
      </button>
      <button
        type="button"
        onClick={() => onCambia("lista")}
        className={`px-3 py-1.5 text-xs uppercase tracking-widest transition-colors border-l border-inchiostro/30 ${
          vista === "lista"
            ? "bg-inchiostro text-pergamena"
            : "text-inchiostro-tenue hover:text-inchiostro"
        }`}
        title="Vista lista"
      >
        <LayoutGrid size={12} className="inline mr-1.5" />
        Lista
      </button>
    </div>
  );
}

function RisultatoVisualizzato({
  risultato,
  giocatoriPartita,
  vista,
  territorioSelezionato,
  onClickTerritorio,
}: {
  risultato: RisultatoRicostruzione;
  giocatoriPartita: GiocatorePartita[];
  vista: VistaStato;
  territorioSelezionato?: string | null;
  onClickTerritorio?: (slug: string) => void;
}) {
  const { successo, n_eventi_totali, n_eventi_applicati, errori, stato_finale } =
    risultato;

  return (
    <div className="space-y-6">
      {/* Riepilogo */}
      <div className="carta p-4 grid grid-cols-2 md:grid-cols-4 gap-6">
        <Statistica
          etichetta="Stato"
          valore={
            <span
              className={
                successo
                  ? "text-bottiglia inline-flex items-center gap-1.5"
                  : "text-scarlatto inline-flex items-center gap-1.5"
              }
            >
              {successo ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
              {successo ? "OK" : "Con errori"}
            </span>
          }
        />
        <Statistica
          etichetta="Eventi totali"
          valore={<span className="font-mono num-tab">{n_eventi_totali}</span>}
        />
        <Statistica
          etichetta="Applicati"
          valore={
            <span className="font-mono num-tab">{n_eventi_applicati}</span>
          }
        />
        <Statistica
          etichetta="Ultima ricostruzione"
          valore={
            <span className="text-xs font-mono num-tab">
              {format(parseISO(risultato.data_ricostruzione), "HH:mm:ss")}
            </span>
          }
        />
      </div>

      {/* Errori */}
      {errori.length > 0 ? (
        <div>
          <div className="etichetta-rossa mb-2">
            {errori.length} {errori.length === 1 ? "errore" : "errori"}
          </div>
          <ul className="space-y-2">
            {errori.map((err, i) => (
              <li
                key={`${err.evento_validato_id}-${i}`}
                className="border-l-2 border-scarlatto pl-3 py-1 text-sm"
              >
                <div className="font-mono text-xs text-inchiostro-tenue">
                  #{err.posizione_nella_sequenza} ·{" "}
                  {format(parseISO(err.ts_evento), "HH:mm:ss")} · {err.tipo_evento}
                </div>
                <div className="text-inchiostro">
                  <span className="text-scarlatto font-semibold">
                    {err.classe_errore}
                  </span>
                  : {err.messaggio}
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Header fase + turno */}
      {stato_finale ? (
        <div className="etichetta flex items-center gap-3">
          <span>Fase: {stato_finale.fase_corrente.replace("_", " ")}</span>
          <span className="font-mono">·</span>
          <span>Turno {stato_finale.turno}</span>
          {stato_finale.vincitore_id ? (
            <>
              <span className="font-mono">·</span>
              <span className="text-scarlatto font-semibold">
                Vincitore decretato
              </span>
            </>
          ) : null}
        </div>
      ) : null}

      {/* Vista alternativa: mappa o lista */}
      {stato_finale ? (
        vista === "mappa" ? (
          <PlanciaMappa
            territori={stato_finale.territori}
            giocatori={giocatoriPartita}
            territorioSelezionato={territorioSelezionato}
            onClickTerritorio={onClickTerritorio}
          />
        ) : (
          <ListaPerGiocatore
            statoFinale={stato_finale}
            giocatoriPartita={giocatoriPartita}
          />
        )
      ) : null}
    </div>
  );
}

function ListaPerGiocatore({
  statoFinale,
  giocatoriPartita,
}: {
  statoFinale: NonNullable<RisultatoRicostruzione["stato_finale"]>;
  giocatoriPartita: GiocatorePartita[];
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {statoFinale.giocatori.map((g) => {
        const meta = giocatoriPartita.find((gp) => gp.id === g.player_id);
        const territoriDelGiocatore = Object.values(statoFinale.territori)
          .filter((t) => t.controllore_id === g.player_id)
          .sort((a, b) => a.nome.localeCompare(b.nome));

        const armateTotali = territoriDelGiocatore.reduce(
          (somma, t) => somma + t.armate,
          0,
        );

        const carte = statoFinale.conteggio_mani[g.player_id] ?? 0;
        const isAttivo = statoFinale.giocatore_attivo_id === g.player_id;

        return (
          <article
            key={g.player_id}
            className={`carta p-4 ${
              isAttivo ? "border-scarlatto/60" : ""
            }`}
          >
            <header className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <PallinoColore
                  colore={g.colore}
                  classeDimensione="w-3.5 h-3.5"
                />
                <span className="font-display text-lg font-semibold">
                  {meta?.nome ?? g.nome}
                </span>
                {g.eliminato ? (
                  <span className="etichetta-rossa">Eliminato</span>
                ) : isAttivo ? (
                  <span className="etichetta-rossa">Attivo</span>
                ) : null}
              </div>
            </header>

            <dl className="grid grid-cols-3 gap-2 mb-3 text-xs">
              <Riga
                etichetta="Territori"
                valore={territoriDelGiocatore.length}
              />
              <Riga etichetta="Armate" valore={armateTotali} />
              <Riga etichetta="Carte" valore={carte} />
            </dl>

            <details className="text-xs">
              <summary className="cursor-pointer etichetta hover:text-scarlatto select-none">
                Lista territori
              </summary>
              <ul className="mt-2 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono">
                {territoriDelGiocatore.map((t) => (
                  <li
                    key={t.nome}
                    className="flex justify-between gap-2 text-inchiostro-tenue"
                  >
                    <span className="truncate">
                      {t.nome.replace(/_/g, " ")}
                    </span>
                    <span className="num-tab text-inchiostro">
                      {t.armate}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          </article>
        );
      })}
    </div>
  );
}

function Statistica({
  etichetta,
  valore,
}: {
  etichetta: string;
  valore: React.ReactNode;
}) {
  return (
    <div>
      <div className="etichetta mb-1">{etichetta}</div>
      <div className="font-display text-lg font-semibold">{valore}</div>
    </div>
  );
}

function Riga({
  etichetta,
  valore,
}: {
  etichetta: string;
  valore: React.ReactNode;
}) {
  return (
    <div>
      <div className="etichetta">{etichetta}</div>
      <div className="font-mono num-tab text-base text-inchiostro">{valore}</div>
    </div>
  );
}
