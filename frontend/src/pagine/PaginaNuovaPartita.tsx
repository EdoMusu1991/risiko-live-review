/**
 * Form di creazione di una nuova partita.
 *
 * Permette di inserire data/ora, luogo, note, e l'elenco dei giocatori
 * con i loro colori. Validazione lato client minima — il backend è la
 * fonte di verità sui constraint (colori unici, ordine seduta consecutivo).
 */

import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Trash2, ArrowLeft } from "lucide-react";

import { apiPartite } from "@/api";
import { ErroreApi } from "@/api";
import { MessaggioErrore, PallinoColore } from "@/componenti/decorativi";
import type {
  ColoreGiocatore,
  GiocatorePartitaCreazione,
} from "@/tipi/dominio";

const COLORI_DISPONIBILI: ColoreGiocatore[] = [
  "rosso",
  "blu",
  "verde",
  "giallo",
  "nero",
  "viola",
];

interface RigaGiocatore {
  nome: string;
  colore: ColoreGiocatore;
}

export function PaginaNuovaPartita() {
  const navigate = useNavigate();

  const [dataLocale, setDataLocale] = useState(() => formatoDataInputLocale(new Date()));
  const [luogo, setLuogo] = useState("Il Gufo · Roma");
  const [note, setNote] = useState("");
  const [giocatori, setGiocatori] = useState<RigaGiocatore[]>([
    { nome: "", colore: "rosso" },
    { nome: "", colore: "blu" },
  ]);

  const [erroreInvio, setErroreInvio] = useState<string | null>(null);
  const [inInvio, setInInvio] = useState(false);

  // Colori già usati, per evitare duplicati nella select
  const coloriUsati = useMemo(
    () => new Set(giocatori.map((g) => g.colore)),
    [giocatori],
  );

  function aggiungiGiocatore() {
    if (giocatori.length >= 6) return;
    const coloreLibero =
      COLORI_DISPONIBILI.find((c) => !coloriUsati.has(c)) ?? "rosso";
    setGiocatori((prev) => [...prev, { nome: "", colore: coloreLibero }]);
  }

  function rimuoviGiocatore(indice: number) {
    if (giocatori.length <= 2) return;
    setGiocatori((prev) => prev.filter((_, i) => i !== indice));
  }

  function aggiornaGiocatore(
    indice: number,
    modifiche: Partial<RigaGiocatore>,
  ) {
    setGiocatori((prev) =>
      prev.map((g, i) => (i === indice ? { ...g, ...modifiche } : g)),
    );
  }

  async function inviaForm(evento: FormEvent) {
    evento.preventDefault();
    setErroreInvio(null);

    // Validazione client minima
    if (giocatori.some((g) => !g.nome.trim())) {
      setErroreInvio("Tutti i giocatori devono avere un nome");
      return;
    }
    if (coloriUsati.size !== giocatori.length) {
      setErroreInvio("Ogni giocatore deve avere un colore distinto");
      return;
    }

    const dataInizio = new Date(dataLocale).toISOString();
    const giocatoriPayload: GiocatorePartitaCreazione[] = giocatori.map(
      (g, i) => ({
        nome: g.nome.trim(),
        colore: g.colore,
        ordine_seduta: i + 1,
      }),
    );

    setInInvio(true);
    try {
      const partita = await apiPartite.crea({
        data_inizio: dataInizio,
        luogo: luogo.trim() || null,
        note: note.trim() || null,
        giocatori: giocatoriPayload,
      });
      navigate(`/partite/${partita.id}`);
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi ? e.dettaglio : "Errore durante la creazione";
      setErroreInvio(messaggio);
      setInInvio(false);
    }
  }

  return (
    <div className="max-w-[900px] mx-auto px-6 lg:px-12 py-12">
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-2 text-xs uppercase tracking-widest text-inchiostro-tenue hover:text-scarlatto mb-6 transition-colors"
      >
        <ArrowLeft size={14} /> Indietro
      </button>

      <header className="mb-10">
        <div className="etichetta-rossa mb-3">Nuova partita</div>
        <h2 className="font-display text-5xl font-black tracking-crisp leading-none">
          Apri una serata
        </h2>
      </header>

      <div className="linea-divisoria mb-8" />

      <form onSubmit={inviaForm} className="space-y-8">
        {/* Sezione: dati partita */}
        <section>
          <h3 className="etichetta mb-4">Dati partita</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Campo etichetta="Data e ora di inizio" obbligatorio>
              <input
                type="datetime-local"
                required
                value={dataLocale}
                onChange={(e) => setDataLocale(e.target.value)}
                className="campo-testo font-mono num-tab"
              />
            </Campo>
            <Campo etichetta="Luogo">
              <input
                type="text"
                value={luogo}
                onChange={(e) => setLuogo(e.target.value)}
                placeholder="es. Il Gufo · Roma"
                className="campo-testo"
              />
            </Campo>
          </div>
          <Campo etichetta="Note">
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder="Annotazioni libere sulla serata, varianti, considerazioni…"
              className="campo-testo font-sans"
            />
          </Campo>
        </section>

        <div className="linea-divisoria" />

        {/* Sezione: giocatori */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h3 className="etichetta">Giocatori ({giocatori.length}/6)</h3>
            <button
              type="button"
              onClick={aggiungiGiocatore}
              disabled={giocatori.length >= 6}
              className="btn-secondario"
            >
              <Plus size={14} /> Aggiungi
            </button>
          </div>

          <ul className="space-y-2">
            {giocatori.map((g, indice) => (
              <li
                key={indice}
                className="flex items-center gap-3 p-3 carta"
              >
                <div className="font-mono text-xs text-inchiostro-fioco w-6 num-tab">
                  {indice + 1}
                </div>
                <input
                  type="text"
                  required
                  value={g.nome}
                  onChange={(e) =>
                    aggiornaGiocatore(indice, { nome: e.target.value })
                  }
                  placeholder="Nome del giocatore"
                  className="campo-testo flex-1"
                />
                <select
                  value={g.colore}
                  onChange={(e) =>
                    aggiornaGiocatore(indice, {
                      colore: e.target.value as ColoreGiocatore,
                    })
                  }
                  className="campo-testo w-32 font-sans capitalize"
                >
                  {COLORI_DISPONIBILI.map((c) => (
                    <option
                      key={c}
                      value={c}
                      disabled={c !== g.colore && coloriUsati.has(c)}
                    >
                      {c}
                    </option>
                  ))}
                </select>
                <PallinoColore colore={g.colore} classeDimensione="w-4 h-4" />
                <button
                  type="button"
                  onClick={() => rimuoviGiocatore(indice)}
                  disabled={giocatori.length <= 2}
                  className="p-2 text-inchiostro-tenue hover:text-scarlatto disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  aria-label="Rimuovi giocatore"
                >
                  <Trash2 size={16} />
                </button>
              </li>
            ))}
          </ul>
        </section>

        {erroreInvio ? <MessaggioErrore testo={erroreInvio} /> : null}

        <div className="flex items-center justify-end gap-3 pt-4">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="btn-secondario"
          >
            Annulla
          </button>
          <button type="submit" disabled={inInvio} className="btn-primario">
            {inInvio ? "Creo…" : "Crea partita"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Campo({
  etichetta,
  obbligatorio,
  children,
}: {
  etichetta: string;
  obbligatorio?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="etichetta block mb-2">
        {etichetta}
        {obbligatorio ? <span className="text-scarlatto"> *</span> : null}
      </span>
      {children}
    </label>
  );
}

/** "2026-05-07T21:00" formato per <input type="datetime-local"> in tz locale. */
function formatoDataInputLocale(data: Date): string {
  const offset = data.getTimezoneOffset() * 60_000;
  return new Date(data.getTime() - offset).toISOString().slice(0, 16);
}
