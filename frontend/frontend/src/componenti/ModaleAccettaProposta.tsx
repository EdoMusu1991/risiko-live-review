/**
 * Modale per accettare una proposta di aggregazione dadi BLE.
 *
 * L'utente arriva qui da `PannelloProposteAggregazione` cliccando
 * "Accetta" su una proposta. Vede:
 * - Riepilogo della proposta (timestamp, dadi letti dal BLE)
 * - Form da compilare:
 *   - Giocatore attaccante (chi ha lanciato)
 *   - Territorio "da" e "a" (NON disponibili dal BLE, vanno scelti)
 *   - Dadi attaccante / difensore (pre-popolati dalla proposta,
 *     correggibili a mano se il BLE ha letto male un dado caduto)
 *
 * Alla conferma chiama `apiAggregazione.accetta(...)` che:
 * 1. Crea un EventoValidato di tipo `attacco_risolto`
 * 2. Marca tutti gli eventi grezzi citati come validati
 * 3. La proposta non comparirà più alla prossima richiesta di
 *    aggregazione.
 */

import { useMemo, useState, type FormEvent } from "react";
import { ChevronRight, Dice5, X } from "lucide-react";

import {
  apiAggregazione,
  ErroreApi,
  type PropostaAggregazioneDadi,
} from "@/api";
import { useTerritori } from "@/hooks/useRisorse";
import type { GiocatorePartita } from "@/tipi/dominio";

import { PallinoColore } from "./decorativi";

interface ProprietaModaleAccettaProposta {
  partitaId: string;
  proposta: PropostaAggregazioneDadi;
  giocatori: GiocatorePartita[];
  onAnnulla: () => void;
  onAccettata: () => void;
}

export function ModaleAccettaProposta({
  partitaId,
  proposta,
  giocatori,
  onAnnulla,
  onAccettata,
}: ProprietaModaleAccettaProposta) {
  const { territori } = useTerritori();

  // Form state
  const giocatoreDefault =
    [...giocatori].sort((a, b) => a.ordine_seduta - b.ordine_seduta)[0]?.id ??
    "";
  const [giocatoreId, setGiocatoreId] = useState(giocatoreDefault);
  const [territorioDa, setTerritorioDa] = useState("");
  const [territorioA, setTerritorioA] = useState("");

  // Dadi modificabili: pre-popolati dalla proposta
  const [dadiAttaccante, setDadiAttaccante] = useState<number[]>(
    proposta.dadi_attaccante.length > 0
      ? [...proposta.dadi_attaccante]
      : [1],
  );
  const [dadiDifensore, setDadiDifensore] = useState<number[]>(
    proposta.dadi_difensore.length > 0 ? [...proposta.dadi_difensore] : [1],
  );

  const [erroreInvio, setErroreInvio] = useState<string | null>(null);
  const [inInvio, setInInvio] = useState(false);

  // Territori adiacenti al "da" (filtra dropdown "a")
  const territoriAdiacenti = useMemo(() => {
    if (!territorioDa || !territori) return null;
    const t = territori.find((x) => x.nome === territorioDa);
    return t ? t.adiacenti : null;
  }, [territorioDa, territori]);

  // Liste ordinate per UI
  const territoriOrdinati = useMemo(
    () => (territori ? [...territori].sort((a, b) => a.nome.localeCompare(b.nome)) : []),
    [territori],
  );
  const territoriPerA = useMemo(
    () =>
      territoriAdiacenti
        ? territoriOrdinati.filter((t) => territoriAdiacenti.includes(t.nome))
        : territoriOrdinati,
    [territoriAdiacenti, territoriOrdinati],
  );

  const formValido =
    giocatoreId !== "" &&
    territorioDa !== "" &&
    territorioA !== "" &&
    territorioDa !== territorioA &&
    dadiAttaccante.length >= 1 &&
    dadiDifensore.length >= 1 &&
    dadiAttaccante.every((d) => d >= 1 && d <= 6) &&
    dadiDifensore.every((d) => d >= 1 && d <= 6);

  async function inviaForm(evento: FormEvent) {
    evento.preventDefault();
    if (!formValido) return;
    setErroreInvio(null);
    setInInvio(true);
    try {
      await apiAggregazione.accetta(partitaId, {
        eventi_grezzi_id: proposta.eventi_grezzi_id,
        giocatore_id: giocatoreId,
        da: territorioDa,
        a: territorioA,
        dadi_attaccante: dadiAttaccante,
        dadi_difensore: dadiDifensore,
      });
      onAccettata();
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi
          ? e.dettaglio
          : "Errore durante l'accettazione della proposta";
      setErroreInvio(messaggio);
      setInInvio(false);
    }
  }

  const giocatoreSelezionato = giocatori.find((g) => g.id === giocatoreId);
  const tsLeggibile = new Date(proposta.ts_inizio).toLocaleTimeString(
    "it-IT",
    { hour: "2-digit", minute: "2-digit", second: "2-digit" },
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-inchiostro/40 backdrop-blur-sm p-4"
      onClick={onAnnulla}
    >
      <div
        className="carta w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-inchiostro/10">
          <div className="flex items-center gap-3">
            <Dice5 className="w-5 h-5 text-scarlatto" />
            <div>
              <h2 className="font-serif text-xl text-inchiostro">
                Accetta proposta
              </h2>
              <p className="text-xs text-inchiostro-fioco mt-0.5">
                Cluster BLE alle {tsLeggibile} ·{" "}
                {proposta.eventi_grezzi_id.length} eventi grezzi
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onAnnulla}
            className="p-2 rounded hover:bg-inchiostro/5 transition"
            aria-label="Chiudi"
          >
            <X className="w-4 h-4 text-inchiostro-tenue" />
          </button>
        </div>

        <form onSubmit={inviaForm} className="px-6 py-5 space-y-5">
          {/* Riepilogo BLE */}
          <div className="bg-pergamena-scura/40 border border-inchiostro/10 rounded p-3 text-sm">
            <div className="etichetta text-inchiostro-tenue mb-2">
              Letture BLE
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <div className="text-inchiostro-fioco">Attaccante</div>
                <div className="font-mono text-inchiostro">
                  {proposta.dadi_attaccante.length > 0
                    ? proposta.dadi_attaccante.join(" · ")
                    : "—"}
                </div>
              </div>
              <div>
                <div className="text-inchiostro-fioco">Difensore</div>
                <div className="font-mono text-inchiostro">
                  {proposta.dadi_difensore.length > 0
                    ? proposta.dadi_difensore.join(" · ")
                    : "—"}
                </div>
              </div>
            </div>
            {proposta.note.length > 0 ? (
              <ul className="mt-2 text-[11px] text-oro-scuro space-y-0.5">
                {proposta.note.map((n, i) => (
                  <li key={i}>· {n}</li>
                ))}
              </ul>
            ) : null}
          </div>

          {/* Giocatore */}
          <div>
            <label
              htmlFor="giocatore-id"
              className="etichetta text-inchiostro-tenue block mb-1.5"
            >
              Giocatore attaccante *
            </label>
            <select
              id="giocatore-id"
              value={giocatoreId}
              onChange={(e) => setGiocatoreId(e.target.value)}
              className="campo w-full"
              required
            >
              <option value="">Seleziona giocatore…</option>
              {giocatori
                .sort((a, b) => a.ordine_seduta - b.ordine_seduta)
                .map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.nome} ({g.colore})
                  </option>
                ))}
            </select>
            {giocatoreSelezionato ? (
              <div className="flex items-center gap-2 mt-2 text-xs text-inchiostro-tenue">
                <PallinoColore colore={giocatoreSelezionato.colore} />
                <span>{giocatoreSelezionato.nome}</span>
              </div>
            ) : null}
          </div>

          {/* Territori */}
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-3 items-end">
            <div>
              <label
                htmlFor="terr-da"
                className="etichetta text-inchiostro-tenue block mb-1.5"
              >
                Da *
              </label>
              <select
                id="terr-da"
                value={territorioDa}
                onChange={(e) => {
                  setTerritorioDa(e.target.value);
                  setTerritorioA(""); // reset a perché la lista cambia
                }}
                className="campo w-full"
                required
              >
                <option value="">Territorio attaccante…</option>
                {territoriOrdinati.map((t) => (
                  <option key={t.nome} value={t.nome}>
                    {t.nome}
                  </option>
                ))}
              </select>
            </div>

            <div className="hidden sm:flex items-center justify-center pb-2.5 text-inchiostro-fioco">
              <ChevronRight className="w-5 h-5" />
            </div>

            <div>
              <label
                htmlFor="terr-a"
                className="etichetta text-inchiostro-tenue block mb-1.5"
              >
                A *
              </label>
              <select
                id="terr-a"
                value={territorioA}
                onChange={(e) => setTerritorioA(e.target.value)}
                className="campo w-full"
                required
                disabled={!territorioDa}
              >
                <option value="">
                  {territorioDa
                    ? "Territorio difensore…"
                    : "Scegli prima 'Da'"}
                </option>
                {territoriPerA.map((t) => (
                  <option key={t.nome} value={t.nome}>
                    {t.nome}
                  </option>
                ))}
              </select>
              {territorioDa && territoriAdiacenti && territoriPerA.length === 0 ? (
                <p className="text-[11px] text-oro-scuro mt-1">
                  Nessun territorio adiacente trovato (anomalia regole)
                </p>
              ) : null}
            </div>
          </div>

          {/* Dadi */}
          <div className="grid grid-cols-2 gap-4">
            <EditorDadi
              etichetta="Dadi attaccante"
              valori={dadiAttaccante}
              onCambia={setDadiAttaccante}
              max={3}
            />
            <EditorDadi
              etichetta="Dadi difensore"
              valori={dadiDifensore}
              onCambia={setDadiDifensore}
              max={3}
            />
          </div>

          {erroreInvio ? (
            <div className="text-sm text-scarlatto bg-scarlatto/5 border border-scarlatto/20 rounded px-3 py-2">
              {erroreInvio}
            </div>
          ) : null}

          {/* Azioni */}
          <div className="flex justify-end gap-2 pt-2 border-t border-inchiostro/10">
            <button
              type="button"
              onClick={onAnnulla}
              className="px-4 py-2 text-sm text-inchiostro-tenue hover:bg-inchiostro/5 rounded transition"
              disabled={inInvio}
            >
              Annulla
            </button>
            <button
              type="submit"
              disabled={!formValido || inInvio}
              className="px-4 py-2 text-sm bg-scarlatto text-pergamena rounded hover:bg-scarlatto-scuro disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              {inInvio ? "Salvataggio…" : "Crea attacco risolto"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// === Sub-componente: editor di una lista di dadi 1..3 ===

interface ProprietaEditorDadi {
  etichetta: string;
  valori: number[];
  onCambia: (nuovi: number[]) => void;
  max: number;
}

function EditorDadi({ etichetta, valori, onCambia, max }: ProprietaEditorDadi) {
  function cambiaDado(indice: number, nuovo: number) {
    const copia = [...valori];
    copia[indice] = Math.max(1, Math.min(6, nuovo));
    onCambia(copia);
  }

  function aggiungi() {
    if (valori.length >= max) return;
    onCambia([...valori, 1]);
  }

  function rimuovi(indice: number) {
    if (valori.length <= 1) return;
    onCambia(valori.filter((_, i) => i !== indice));
  }

  return (
    <div>
      <label className="etichetta text-inchiostro-tenue block mb-1.5">
        {etichetta} ({valori.length}/{max}) *
      </label>
      <div className="flex flex-wrap gap-2">
        {valori.map((v, i) => (
          <div key={i} className="flex items-center gap-1">
            <input
              type="number"
              min={1}
              max={6}
              value={v}
              onChange={(e) => cambiaDado(i, Number(e.target.value))}
              className="campo w-14 text-center font-mono"
            />
            {valori.length > 1 ? (
              <button
                type="button"
                onClick={() => rimuovi(i)}
                className="text-inchiostro-fioco hover:text-scarlatto p-1"
                aria-label="Rimuovi dado"
              >
                <X className="w-3 h-3" />
              </button>
            ) : null}
          </div>
        ))}
        {valori.length < max ? (
          <button
            type="button"
            onClick={aggiungi}
            className="px-2 py-1 text-xs border border-inchiostro/20 rounded hover:bg-inchiostro/5 text-inchiostro-tenue"
          >
            + dado
          </button>
        ) : null}
      </div>
    </div>
  );
}
