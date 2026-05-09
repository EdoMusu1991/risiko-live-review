/**
 * Pannello "Discrepanze CV ↔ motore" per la review umana.
 *
 * Mostra le divergenze fra lo stato del motore (derivato dagli eventi
 * BLE/manuali) e lo stato dedotto dalle inferenze CV (raddrizzamento
 * + Roboflow). L'operatore puo' risolvere ogni divergenza:
 *
 * - **accettata_motore**: la CV ha sbagliato, ignora la sua versione
 * - **accettata_cv**: il motore ha torto, manca un evento → da aggiungere
 * - **evento_aggiunto**: ho creato manualmente l'evento mancante
 * - **aperta**: riapri (es. dopo revisione)
 *
 * Il pannello e' nascosto se la partita non ha mai avuto inferenze CV
 * (caso normale finche' non arriva il modello Roboflow). Compare quando
 * c'e' almeno un'inferenza CV nel DB per la partita.
 */

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  Check,
  Download,
  Layers,
  Loader2,
  RefreshCw,
  Scan,
  Sparkles,
  X,
} from "lucide-react";

import {
  apiInferenzeCV,
  ErroreApi,
  type AggiornamentoBulkDivergenze,
  type DivergenzaInferita,
  type RiepilogoAnalisiBatch,
  type RiepilogoDiscrepanze,
  type RisoluzioneDivergenza,
} from "@/api";
import { MessaggioErrore } from "@/componenti/decorativi";
import { ModaleEventoAggiunto } from "@/componenti/ModaleEventoAggiunto";

interface ProprietaPannelloDiscrepanze {
  partitaId: string;
}

export function PannelloDiscrepanze({ partitaId }: ProprietaPannelloDiscrepanze) {
  const [riepilogo, setRiepilogo] = useState<RiepilogoDiscrepanze | null>(null);
  const [caricamento, setCaricamento] = useState(true);
  const [erroreLoad, setErroreLoad] = useState<string | null>(null);
  const [inCalcolo, setInCalcolo] = useState(false);
  const [erroreCalcolo, setErroreCalcolo] = useState<string | null>(null);
  const [filtroSoloAperte, setFiltroSoloAperte] = useState(true);
  // Modalita di calcolo: "finale" (snapshot finale) | "per_evento"
  // (snapshot intermedi). Da scegliere in base a come arrivano le inferenze.
  const [modalita, setModalita] = useState<"finale" | "per_evento">(
    "finale",
  );
  // Filtri avanzati locali (applicati lato client)
  const [filtroDeltaMin, setFiltroDeltaMin] = useState(0);
  const [filtroTerritorio, setFiltroTerritorio] = useState("");
  const [filtroColore, setFiltroColore] = useState("");

  // Stato analisi-cv (pipeline completa)
  const [inAnalisi, setInAnalisi] = useState(false);
  const [riepilogoAnalisi, setRiepilogoAnalisi] =
    useState<RiepilogoAnalisiBatch | null>(null);

  // Modale "evento aggiunto" smart
  const [modaleDivergenza, setModaleDivergenza] =
    useState<DivergenzaInferita | null>(null);

  // Stato menu bulk
  const [menuBulkAperto, setMenuBulkAperto] = useState(false);
  const [inBulk, setInBulk] = useState(false);

  // ID delle divergenze in cui e' in corso un PATCH (per disabilitare
  // i bottoni e mostrare spinner)
  const [inAggiornamento, setInAggiornamento] = useState<Set<string>>(
    () => new Set(),
  );

  async function ricarica() {
    setCaricamento(true);
    setErroreLoad(null);
    try {
      const r = await apiInferenzeCV.listaDiscrepanze(
        partitaId,
        filtroSoloAperte,
      );
      setRiepilogo(r);
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi ? e.dettaglio : "Errore caricamento";
      setErroreLoad(messaggio);
    } finally {
      setCaricamento(false);
    }
  }

  useEffect(() => {
    void ricarica();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partitaId, filtroSoloAperte]);

  async function ricalcola() {
    setInCalcolo(true);
    setErroreCalcolo(null);
    try {
      const r =
        modalita === "per_evento"
          ? await apiInferenzeCV.calcolaDiscrepanzePerEvento(partitaId)
          : await apiInferenzeCV.calcolaDiscrepanze(partitaId);
      setRiepilogo(r);
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi ? e.dettaglio : "Errore calcolo discrepanze";
      setErroreCalcolo(messaggio);
    } finally {
      setInCalcolo(false);
    }
  }

  async function eseguiBulk(body: AggiornamentoBulkDivergenze) {
    setInBulk(true);
    setErroreCalcolo(null);
    setMenuBulkAperto(false);
    try {
      const r = await apiInferenzeCV.aggiornaDivergenzeBulk(partitaId, body);
      if (r.n_aggiornate === 0) {
        setErroreCalcolo("Nessuna divergenza ha soddisfatto i filtri.");
      }
      await ricarica();
    } catch (e) {
      setErroreCalcolo(
        e instanceof ErroreApi ? e.dettaglio : "Errore azione bulk",
      );
    } finally {
      setInBulk(false);
    }
  }

  async function analizzaCv() {
    setInAnalisi(true);
    setErroreCalcolo(null);
    setRiepilogoAnalisi(null);
    try {
      const ra = await apiInferenzeCV.analizzaTuttiEventi(partitaId);
      setRiepilogoAnalisi(ra);
      // Dopo l'analisi, ricalcola le discrepanze automaticamente con la
      // modalita corrente
      const rd =
        modalita === "per_evento"
          ? await apiInferenzeCV.calcolaDiscrepanzePerEvento(partitaId)
          : await apiInferenzeCV.calcolaDiscrepanze(partitaId);
      setRiepilogo(rd);
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi ? e.dettaglio : "Errore pipeline CV";
      setErroreCalcolo(messaggio);
    } finally {
      setInAnalisi(false);
    }
  }

  async function risolvi(
    divergenza: DivergenzaInferita,
    risoluzione: RisoluzioneDivergenza,
  ) {
    // Risoluzione "evento_aggiunto" → apri modale per workflow smart
    // (chiede al backend un suggerimento + crea evento)
    if (risoluzione === "evento_aggiunto") {
      setModaleDivergenza(divergenza);
      return;
    }

    const ids = new Set(inAggiornamento);
    ids.add(divergenza.id);
    setInAggiornamento(ids);

    try {
      await apiInferenzeCV.aggiornaDivergenza(
        partitaId,
        divergenza.id,
        risoluzione,
      );
      await ricarica();
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi ? e.dettaglio : "Errore aggiornamento";
      setErroreCalcolo(messaggio);
    } finally {
      const idsFinale = new Set(inAggiornamento);
      idsFinale.delete(divergenza.id);
      setInAggiornamento(idsFinale);
    }
  }

  // Stato "vuoto": nessuna divergenza mai calcolata o nessuna inferenza CV.
  // Distinguiamo silenziosamente: se la partita e' tradizionale senza CV,
  // non mostriamo nemmeno l'errore.
  if (caricamento && riepilogo === null) {
    return (
      <section className="carta p-5">
        <header className="flex items-center justify-between mb-3">
          <h3 className="etichetta">Discrepanze CV ↔ motore</h3>
        </header>
        <div className="flex items-center gap-2 text-inchiostro-fioco py-4">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">Caricamento…</span>
        </div>
      </section>
    );
  }

  if (erroreLoad !== null) {
    return (
      <section className="carta p-5 space-y-3">
        <h3 className="etichetta">Discrepanze CV ↔ motore</h3>
        <MessaggioErrore testo={erroreLoad} />
      </section>
    );
  }

  if (riepilogo === null) {
    return null;
  }

  // Caso speciale: nessuna divergenza. Mostriamo solo il bottone calcolo,
  // utile per partita appena avviata.
  if (riepilogo.n_divergenze_totali === 0 && !inCalcolo && !inAnalisi) {
    return (
      <section className="carta p-5 space-y-3">
        <header className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="etichetta">Discrepanze CV ↔ motore</h3>
          <div className="flex items-center gap-2">
            <BottoneAnalizzaCv onClick={analizzaCv} inAnalisi={inAnalisi} />
            <BottoneRicalcola onClick={ricalcola} inCalcolo={inCalcolo} />
          </div>
        </header>
        {riepilogoAnalisi ? <RiepilogoAnalisi r={riepilogoAnalisi} /> : null}
        <p className="text-sm text-inchiostro-fioco italic">
          Nessuna divergenza calcolata. Lancia "Analizza CV" per eseguire la
          pipeline completa (estrazione frame → raddrizzamento → inferenza),
          oppure "Ricalcola" se hai gia' caricato inferenze manualmente.
        </p>
        {erroreCalcolo ? <MessaggioErrore testo={erroreCalcolo} /> : null}
      </section>
    );
  }

  // Applica filtri client-side (territorio, colore, delta minimo)
  const territoriDisponibili = Array.from(
    new Set(riepilogo.divergenze.map((d) => d.territorio)),
  ).sort();
  const coloriDisponibili = Array.from(
    new Set(riepilogo.divergenze.map((d) => d.colore)),
  ).sort();
  const divergenzeFiltrate = riepilogo.divergenze.filter((d) => {
    if (d.delta_assoluto < filtroDeltaMin) return false;
    if (filtroTerritorio && d.territorio !== filtroTerritorio) return false;
    if (filtroColore && d.colore !== filtroColore) return false;
    return true;
  });

  return (
    <section className="carta p-5 space-y-4">
      <header className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="etichetta inline-flex items-center gap-2">
          <Scan className="w-3.5 h-3.5" />
          Discrepanze CV ↔ motore
        </h3>
        <div className="flex items-center gap-2 flex-wrap">
          <SelettoreModalita modalita={modalita} onCambia={setModalita} />
          <FiltroToggle
            attivo={filtroSoloAperte}
            onToggle={() => setFiltroSoloAperte((v) => !v)}
          />
          <BottoneEsportaCsv
            partitaId={partitaId}
            soloAperte={filtroSoloAperte}
          />
          <MenuAzioniBulk
            aperto={menuBulkAperto}
            onToggle={() => setMenuBulkAperto((v) => !v)}
            onEsegui={eseguiBulk}
            inBulk={inBulk}
            filtroDeltaMin={filtroDeltaMin}
            filtroTerritorio={filtroTerritorio}
            filtroColore={filtroColore}
          />
          <BottoneAnalizzaCv onClick={analizzaCv} inAnalisi={inAnalisi} />
          <BottoneRicalcola onClick={ricalcola} inCalcolo={inCalcolo} />
        </div>
      </header>

      {riepilogoAnalisi ? <RiepilogoAnalisi r={riepilogoAnalisi} /> : null}

      <Riepilogo riepilogo={riepilogo} />

      {/* Filtri avanzati */}
      {riepilogo.divergenze.length > 0 ? (
        <FiltriAvanzati
          filtroDeltaMin={filtroDeltaMin}
          onDeltaMinCambia={setFiltroDeltaMin}
          filtroTerritorio={filtroTerritorio}
          onTerritorioCambia={setFiltroTerritorio}
          filtroColore={filtroColore}
          onColoreCambia={setFiltroColore}
          territoriDisponibili={territoriDisponibili}
          coloriDisponibili={coloriDisponibili}
          nFiltrate={divergenzeFiltrate.length}
          nTotali={riepilogo.divergenze.length}
        />
      ) : null}

      {erroreCalcolo ? <MessaggioErrore testo={erroreCalcolo} /> : null}

      {riepilogo.divergenze.length === 0 ? (
        <p className="text-sm text-inchiostro-fioco italic py-2">
          {filtroSoloAperte
            ? "Nessuna divergenza aperta. Tutte risolte 🎉"
            : "Nessuna divergenza."}
        </p>
      ) : divergenzeFiltrate.length === 0 ? (
        <p className="text-sm text-inchiostro-fioco italic py-2">
          Nessuna divergenza corrisponde ai filtri attivi.
        </p>
      ) : (
        <Tabella
          divergenze={divergenzeFiltrate}
          inAggiornamento={inAggiornamento}
          onRisolvi={risolvi}
        />
      )}

      {modaleDivergenza ? (
        <ModaleEventoAggiunto
          partitaId={partitaId}
          divergenza={modaleDivergenza}
          onChiudi={() => setModaleDivergenza(null)}
          onCompletato={() => {
            void ricarica();
          }}
        />
      ) : null}
    </section>
  );
}

// === Sotto-componenti ===

function Riepilogo({ riepilogo }: { riepilogo: RiepilogoDiscrepanze }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
      <BlockStat
        label="Totali"
        valore={riepilogo.n_divergenze_totali}
      />
      <BlockStat
        label="Aperte"
        valore={riepilogo.n_aperte}
        evidenza={riepilogo.n_aperte > 0 ? "scarlatto" : undefined}
      />
      <BlockStat label="Risolte" valore={riepilogo.n_risolte} />
      <BlockStat
        label="Delta max"
        valore={riepilogo.delta_max}
        evidenza={riepilogo.delta_max >= 3 ? "scarlatto" : undefined}
      />
    </div>
  );
}

function BlockStat({
  label,
  valore,
  evidenza,
}: {
  label: string;
  valore: number;
  evidenza?: "scarlatto";
}) {
  const colore =
    evidenza === "scarlatto"
      ? "text-scarlatto"
      : "text-inchiostro";
  return (
    <div className="border border-inchiostro/10 rounded p-2">
      <div className={`text-xl font-display tabular-nums ${colore}`}>
        {valore}
      </div>
      <div className="text-[10px] text-inchiostro-fioco uppercase tracking-wider mt-0.5">
        {label}
      </div>
    </div>
  );
}

function FiltroToggle({
  attivo,
  onToggle,
}: {
  attivo: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`text-xs px-2.5 py-1 rounded border transition ${
        attivo
          ? "bg-inchiostro text-pergamena border-inchiostro"
          : "border-inchiostro/20 text-inchiostro-tenue hover:bg-pergamena-scura/40"
      }`}
    >
      {attivo ? "Solo aperte" : "Tutte"}
    </button>
  );
}

function SelettoreModalita({
  modalita,
  onCambia,
}: {
  modalita: "finale" | "per_evento";
  onCambia: (m: "finale" | "per_evento") => void;
}) {
  return (
    <div className="inline-flex border border-inchiostro/20 rounded overflow-hidden text-xs">
      <button
        type="button"
        onClick={() => onCambia("finale")}
        className={`px-2.5 py-1 transition ${
          modalita === "finale"
            ? "bg-inchiostro text-pergamena"
            : "text-inchiostro-tenue hover:bg-pergamena-scura/40"
        }`}
        title="Confronta lo stato motore finale con tutte le inferenze CV"
      >
        Finale
      </button>
      <button
        type="button"
        onClick={() => onCambia("per_evento")}
        className={`px-2.5 py-1 border-l border-inchiostro/20 transition ${
          modalita === "per_evento"
            ? "bg-inchiostro text-pergamena"
            : "text-inchiostro-tenue hover:bg-pergamena-scura/40"
        }`}
        title="Confronta evento-per-evento usando snapshot intermedi del motore"
      >
        Per evento
      </button>
    </div>
  );
}

function BottoneEsportaCsv({
  partitaId,
  soloAperte,
}: {
  partitaId: string;
  soloAperte: boolean;
}) {
  const url = apiInferenzeCV.urlEsportaCsv(partitaId, soloAperte);
  return (
    <a
      href={url}
      download
      className="btn-secondario"
      title="Scarica CSV per analisi esterna (Excel italiano)"
    >
      <Download className="w-3.5 h-3.5" />
      CSV
    </a>
  );
}

function MenuAzioniBulk({
  aperto,
  onToggle,
  onEsegui,
  inBulk,
  filtroDeltaMin,
  filtroTerritorio,
  filtroColore,
}: {
  aperto: boolean;
  onToggle: () => void;
  onEsegui: (body: AggiornamentoBulkDivergenze) => void;
  inBulk: boolean;
  filtroDeltaMin: number;
  filtroTerritorio: string;
  filtroColore: string;
}) {
  const filtriBase: Partial<AggiornamentoBulkDivergenze> = {
    solo_aperte: true,
    ...(filtroDeltaMin > 0 ? { delta_minimo: filtroDeltaMin } : {}),
    ...(filtroTerritorio ? { territorio: filtroTerritorio } : {}),
    ...(filtroColore ? { colore: filtroColore } : {}),
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={onToggle}
        disabled={inBulk}
        className="btn-secondario disabled:opacity-50"
        title="Azioni in batch sulle divergenze (rispetta i filtri attivi)"
      >
        {inBulk ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <Layers className="w-3.5 h-3.5" />
        )}
        Bulk
      </button>

      {aperto ? (
        <>
          {/* Click esterno per chiudere */}
          <div
            className="fixed inset-0 z-10"
            onClick={onToggle}
          />
          <div className="absolute right-0 mt-1 w-72 bg-pergamena border border-inchiostro/15 rounded shadow-lg z-20 text-xs">
            <div className="px-3 py-2 border-b border-inchiostro/10 text-inchiostro-fioco">
              <div className="font-semibold mb-0.5">Azioni in batch</div>
              <div className="text-[10px]">
                Rispetta i filtri attivi
                {filtroDeltaMin > 0 || filtroTerritorio || filtroColore
                  ? ` (delta≥${filtroDeltaMin}${
                      filtroTerritorio ? ", " + filtroTerritorio : ""
                    }${filtroColore ? ", " + filtroColore : ""})`
                  : ""}
              </div>
            </div>
            <ul className="py-1">
              <VoceMenu
                etichetta="Accetta motore (delta ≤ 1)"
                colore="text-bottiglia"
                onClick={() =>
                  onEsegui({
                    ...filtriBase,
                    risoluzione: "accettata_motore",
                    delta_massimo: 1,
                    note: "Bulk: micro-divergenze accettate da motore",
                  } as AggiornamentoBulkDivergenze)
                }
              />
              <VoceMenu
                etichetta="Accetta motore (tutte aperte)"
                colore="text-bottiglia"
                onClick={() =>
                  onEsegui({
                    ...filtriBase,
                    risoluzione: "accettata_motore",
                    note: "Bulk: tutte accettate da motore",
                  } as AggiornamentoBulkDivergenze)
                }
              />
              <VoceMenu
                etichetta="Accetta CV (tutte aperte)"
                colore="text-bronzo"
                onClick={() =>
                  onEsegui({
                    ...filtriBase,
                    risoluzione: "accettata_cv",
                    note: "Bulk: tutte accettate da CV",
                  } as AggiornamentoBulkDivergenze)
                }
              />
              <li className="border-t border-inchiostro/10 mt-1 pt-1">
                <VoceMenu
                  etichetta="Riapri tutte"
                  colore="text-scarlatto"
                  onClick={() =>
                    onEsegui({
                      ...filtriBase,
                      solo_aperte: false,
                      risoluzione: "aperta",
                    } as AggiornamentoBulkDivergenze)
                  }
                />
              </li>
            </ul>
          </div>
        </>
      ) : null}
    </div>
  );
}

function VoceMenu({
  etichetta,
  colore,
  onClick,
}: {
  etichetta: string;
  colore: string;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className={`w-full text-left px-3 py-1.5 hover:bg-pergamena-scura/30 transition ${colore}`}
      >
        {etichetta}
      </button>
    </li>
  );
}

function FiltriAvanzati({
  filtroDeltaMin,
  onDeltaMinCambia,
  filtroTerritorio,
  onTerritorioCambia,
  filtroColore,
  onColoreCambia,
  territoriDisponibili,
  coloriDisponibili,
  nFiltrate,
  nTotali,
}: {
  filtroDeltaMin: number;
  onDeltaMinCambia: (n: number) => void;
  filtroTerritorio: string;
  onTerritorioCambia: (t: string) => void;
  filtroColore: string;
  onColoreCambia: (c: string) => void;
  territoriDisponibili: string[];
  coloriDisponibili: string[];
  nFiltrate: number;
  nTotali: number;
}) {
  const filtriAttivi =
    filtroDeltaMin > 0 || filtroTerritorio !== "" || filtroColore !== "";
  return (
    <div className="border border-inchiostro/10 rounded p-2.5 bg-pergamena-scura/20 text-xs space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <label className="text-inchiostro-fioco">Δ min:</label>
        <input
          type="number"
          min={0}
          max={20}
          value={filtroDeltaMin}
          onChange={(e) => onDeltaMinCambia(Number(e.target.value))}
          className="w-14 px-1.5 py-0.5 border border-inchiostro/20 rounded bg-pergamena tabular-nums"
        />

        <label className="text-inchiostro-fioco ml-2">Territorio:</label>
        <select
          value={filtroTerritorio}
          onChange={(e) => onTerritorioCambia(e.target.value)}
          className="px-1.5 py-0.5 border border-inchiostro/20 rounded bg-pergamena max-w-[160px]"
        >
          <option value="">Tutti</option>
          {territoriDisponibili.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <label className="text-inchiostro-fioco ml-2">Colore:</label>
        <select
          value={filtroColore}
          onChange={(e) => onColoreCambia(e.target.value)}
          className="px-1.5 py-0.5 border border-inchiostro/20 rounded bg-pergamena"
        >
          <option value="">Tutti</option>
          {coloriDisponibili.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        {filtriAttivi ? (
          <button
            type="button"
            onClick={() => {
              onDeltaMinCambia(0);
              onTerritorioCambia("");
              onColoreCambia("");
            }}
            className="ml-auto text-inchiostro-fioco hover:text-scarlatto underline-offset-2 hover:underline"
          >
            Pulisci filtri
          </button>
        ) : null}
      </div>

      {filtriAttivi ? (
        <div className="text-[11px] text-inchiostro-fioco">
          Mostro <strong>{nFiltrate}</strong> di {nTotali} divergenze
        </div>
      ) : null}
    </div>
  );
}

function BottoneRicalcola({
  onClick,
  inCalcolo,
}: {
  onClick: () => void;
  inCalcolo: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={inCalcolo}
      className="btn-secondario disabled:opacity-50"
      title="Ricalcola le divergenze sulle inferenze gia' presenti"
    >
      {inCalcolo ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : (
        <RefreshCw className="w-3.5 h-3.5" />
      )}
      Ricalcola
    </button>
  );
}

function BottoneAnalizzaCv({
  onClick,
  inAnalisi,
}: {
  onClick: () => void;
  inAnalisi: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={inAnalisi}
      className="btn-primario disabled:opacity-50"
      title="Esegue la pipeline CV completa: estrai frame, raddrizza, inferisci, ricalcola discrepanze"
    >
      {inAnalisi ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : (
        <Sparkles className="w-3.5 h-3.5" />
      )}
      {inAnalisi ? "Analisi in corso…" : "Analizza CV"}
    </button>
  );
}

function RiepilogoAnalisi({ r }: { r: RiepilogoAnalisiBatch }) {
  const ok = r.n_falliti === 0;
  return (
    <div
      className={`text-xs rounded p-2.5 border ${
        ok
          ? "bg-bottiglia/5 border-bottiglia/20 text-bottiglia"
          : "bg-bronzo/5 border-bronzo/20 text-bronzo"
      }`}
    >
      <div className="font-semibold">
        Pipeline CV completata: {r.n_inferenze_totali} inferenze su{" "}
        {r.n_riusciti}/{r.n_eventi_totali} eventi (modello{" "}
        <code className="bg-pergamena-scura/40 px-1 rounded">
          {r.modello_versione}
        </code>
        )
      </div>
      {r.n_falliti > 0 ? (
        <details className="mt-1 cursor-pointer">
          <summary className="text-[11px]">
            {r.n_falliti} eventi falliti
          </summary>
          <ul className="mt-1 text-[11px] space-y-0.5 max-h-32 overflow-y-auto">
            {r.falliti.slice(0, 10).map((f) => (
              <li key={f.evento_id}>
                <code>{f.evento_id.slice(0, 8)}</code>: {f.errore}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function Tabella({
  divergenze,
  inAggiornamento,
  onRisolvi,
}: {
  divergenze: DivergenzaInferita[];
  inAggiornamento: Set<string>;
  onRisolvi: (
    div: DivergenzaInferita,
    risoluzione: RisoluzioneDivergenza,
  ) => void;
}) {
  return (
    <div className="overflow-x-auto -mx-2 px-2">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-inchiostro-fioco border-b border-inchiostro/10">
            <th className="text-left py-2 pr-2 font-normal etichetta">
              Territorio
            </th>
            <th className="text-left py-2 pr-2 font-normal etichetta">
              Colore
            </th>
            <th className="text-right px-1.5 font-normal etichetta">
              Motore
            </th>
            <th className="text-right px-1.5 font-normal etichetta">CV</th>
            <th className="text-right px-1.5 font-normal etichetta">Δ</th>
            <th className="text-right px-1.5 font-normal etichetta">
              Confidence
            </th>
            <th className="text-left pl-1.5 font-normal etichetta">Stato</th>
            <th className="text-right pl-2 font-normal etichetta">Azioni</th>
          </tr>
        </thead>
        <tbody>
          {divergenze.map((d) => (
            <Riga
              key={d.id}
              divergenza={d}
              inAggiornamento={inAggiornamento.has(d.id)}
              onRisolvi={onRisolvi}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Riga({
  divergenza: d,
  inAggiornamento,
  onRisolvi,
}: {
  divergenza: DivergenzaInferita;
  inAggiornamento: boolean;
  onRisolvi: (
    div: DivergenzaInferita,
    risoluzione: RisoluzioneDivergenza,
  ) => void;
}) {
  const deltaSegno = d.valore_cv > d.valore_motore ? "+" : "−";

  // Severita' visiva basata su delta + confidence
  const severita =
    d.delta_assoluto >= 3
      ? "alta"
      : d.delta_assoluto >= 2
        ? "media"
        : "bassa";
  const coloreDelta =
    severita === "alta"
      ? "text-scarlatto font-semibold"
      : severita === "media"
        ? "text-bronzo"
        : "text-inchiostro-tenue";

  return (
    <tr
      className={`border-b border-inchiostro/5 last:border-0 ${
        d.risoluzione !== "aperta" ? "opacity-50" : ""
      }`}
    >
      <td className="py-2 pr-2 text-inchiostro">
        {formatTerritorio(d.territorio)}
      </td>
      <td className="py-2 pr-2 text-inchiostro-tenue">{d.colore}</td>
      <td className="text-right px-1.5 tabular-nums text-inchiostro">
        {d.valore_motore}
      </td>
      <td className="text-right px-1.5 tabular-nums text-inchiostro">
        {d.valore_cv}
      </td>
      <td className={`text-right px-1.5 tabular-nums ${coloreDelta}`}>
        {deltaSegno}
        {d.delta_assoluto}
      </td>
      <td className="text-right px-1.5 tabular-nums text-inchiostro-fioco">
        {(d.confidence_cv * 100).toFixed(0)}%
      </td>
      <td className="pl-1.5">
        <BadgeRisoluzione risoluzione={d.risoluzione} />
      </td>
      <td className="text-right pl-2">
        {inAggiornamento ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin inline-block text-inchiostro-fioco" />
        ) : d.risoluzione === "aperta" ? (
          <AzioniAperta divergenza={d} onRisolvi={onRisolvi} />
        ) : (
          <button
            type="button"
            onClick={() => onRisolvi(d, "aperta")}
            className="text-xs text-inchiostro-fioco underline-offset-2 hover:underline"
            title="Riapri questa divergenza"
          >
            Riapri
          </button>
        )}
      </td>
    </tr>
  );
}

function AzioniAperta({
  divergenza: d,
  onRisolvi,
}: {
  divergenza: DivergenzaInferita;
  onRisolvi: (
    div: DivergenzaInferita,
    risoluzione: RisoluzioneDivergenza,
  ) => void;
}) {
  return (
    <div className="inline-flex gap-1">
      <button
        type="button"
        onClick={() => onRisolvi(d, "accettata_motore")}
        title="La CV ha sbagliato — accetta valore motore"
        className="p-1 rounded text-inchiostro-tenue hover:bg-bottiglia/10 hover:text-bottiglia transition"
      >
        <Check className="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        onClick={() => onRisolvi(d, "accettata_cv")}
        title="Manca un evento — accetta valore CV"
        className="p-1 rounded text-inchiostro-tenue hover:bg-scarlatto/10 hover:text-scarlatto transition"
      >
        <AlertTriangle className="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        onClick={() => onRisolvi(d, "evento_aggiunto")}
        title="Evento aggiunto manualmente"
        className="p-1 rounded text-inchiostro-tenue hover:bg-inchiostro/10 hover:text-inchiostro transition"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function BadgeRisoluzione({
  risoluzione,
}: {
  risoluzione: RisoluzioneDivergenza;
}) {
  const config: Record<
    RisoluzioneDivergenza,
    { etichetta: string; classe: string }
  > = {
    aperta: {
      etichetta: "aperta",
      classe: "bg-scarlatto/10 text-scarlatto",
    },
    accettata_motore: {
      etichetta: "motore ok",
      classe: "bg-bottiglia/10 text-bottiglia",
    },
    accettata_cv: {
      etichetta: "CV ok",
      classe: "bg-bronzo/10 text-bronzo",
    },
    evento_aggiunto: {
      etichetta: "evento agg.",
      classe: "bg-inchiostro/10 text-inchiostro-tenue",
    },
  };
  const { etichetta, classe } = config[risoluzione];
  return (
    <span
      className={`text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded ${classe}`}
    >
      {etichetta}
    </span>
  );
}

function formatTerritorio(slug: string): string {
  return slug.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
