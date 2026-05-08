/**
 * Form dinamico per creare/modificare un evento validato.
 *
 * In base al `tipo` selezionato mostra i campi specifici:
 *   territorio_assegnato_inizio → territorio, giocatore, n_armate
 *   obiettivo_assegnato         → giocatore, obiettivo (1-16)
 *   armate_piazzate             → giocatore, territorio, n
 *   tris_giocato                → giocatore, 3 carte (territorio + simbolo)
 *   attacco_risolto             → giocatore, da, a, dadi att (1..3), dadi dif (1..3)
 *   armate_spostate             → giocatore, da, a, n
 *   turno_finito                → giocatore
 *   partita_fine                → vincitore
 *   nota                        → testo libero
 *
 * Restituisce il payload `dati` JSON pronto per l'API. La validazione
 * client-side è minima — il backend è la fonte di verità.
 */

import { useEffect, useState, type FormEvent } from "react";
import { X } from "lucide-react";

import type {
  EventoGrezzo,
  EventoValidato,
  GiocatorePartita,
  TipoEvento,
} from "@/tipi/dominio";
import {
  OBIETTIVI,
  SIMBOLI_CARTA,
  TERRITORI,
  TIPI_EVENTO,
  type SimboloCarta,
} from "@/tipi/costanti";
import { PallinoColore } from "./decorativi";

interface ProprietaFormEvento {
  giocatori: GiocatorePartita[];
  /** Se passato, modalità modifica; altrimenti creazione. */
  eventoEsistente?: EventoValidato | EventoGrezzo | null;
  /** Timestamp pre-popolato (ISO 8601). Usato in creazione. */
  tsEventoIniziale?: string;
  /** Tipo evento pre-selezionato in creazione. Default: armate_piazzate. */
  tipoIniziale?: TipoEvento;
  /** Payload pre-popolato in creazione (es. dadi da proposta aggregazione). */
  datiIniziali?: Record<string, unknown>;
  onAnnulla: () => void;
  /**
   * Chiamato a submit con i dati pronti per l'API.
   * `id` è presente solo in modalità modifica.
   */
  onSalva: (dati: {
    id?: string;
    ts_evento: string;
    tipo: TipoEvento;
    dati: Record<string, unknown>;
  }) => Promise<void>;
}

interface DatoCarta {
  territorio: string | null;
  simbolo: SimboloCarta;
}

export function FormEvento({
  giocatori,
  eventoEsistente,
  tsEventoIniziale,
  tipoIniziale,
  datiIniziali,
  onAnnulla,
  onSalva,
}: ProprietaFormEvento) {
  const inModifica = !!eventoEsistente;

  const [tsEvento, setTsEvento] = useState(() => {
    const ts = eventoEsistente?.ts_evento ?? tsEventoIniziale ?? new Date().toISOString();
    return formattaPerInputDatetime(ts);
  });
  const [tipo, setTipo] = useState<TipoEvento>(
    eventoEsistente?.tipo ?? tipoIniziale ?? "armate_piazzate",
  );
  const [dati, setDati] = useState<Record<string, unknown>>(
    eventoEsistente?.dati ?? datiIniziali ?? {},
  );

  const [erroreInvio, setErroreInvio] = useState<string | null>(null);
  const [inInvio, setInInvio] = useState(false);

  // Quando cambia tipo, resetta `dati` con la struttura vuota corretta
  // (solo se non siamo in modifica e il tipo è cambiato dall'iniziale).
  useEffect(() => {
    if (inModifica) return;
    setDati(strutturaVuotaPerTipo(tipo, giocatori));
  }, [tipo, giocatori, inModifica]);

  async function inviaForm(evento: FormEvent) {
    evento.preventDefault();
    setErroreInvio(null);

    const tsIso = new Date(tsEvento).toISOString();

    setInInvio(true);
    try {
      await onSalva({
        id: eventoEsistente?.id,
        ts_evento: tsIso,
        tipo,
        dati,
      });
    } catch (e) {
      setErroreInvio(e instanceof Error ? e.message : "Errore");
      setInInvio(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-inchiostro/40 overflow-y-auto py-8 px-4">
      <form
        onSubmit={inviaForm}
        className="bg-pergamena w-full max-w-2xl border border-inchiostro shadow-cartaHover"
      >
        {/* Header */}
        <header className="px-6 py-4 border-b border-inchiostro/15 flex items-center justify-between">
          <div>
            <div className="etichetta-rossa">
              {inModifica ? "Modifica evento" : "Nuovo evento"}
            </div>
            <h3 className="font-display text-2xl font-semibold tracking-crisp">
              {TIPI_EVENTO.find((t) => t.tipo === tipo)?.etichetta ?? tipo}
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

        {/* Corpo: timestamp + tipo + campi dinamici */}
        <div className="px-6 py-5 space-y-5 max-h-[70vh] overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Etichetta testo="Timestamp evento" obbligatorio>
              <input
                type="datetime-local"
                step="1"
                required
                value={tsEvento}
                onChange={(e) => setTsEvento(e.target.value)}
                className="campo-testo font-mono num-tab"
              />
            </Etichetta>
            <Etichetta testo="Tipo evento" obbligatorio>
              <select
                value={tipo}
                onChange={(e) => setTipo(e.target.value as TipoEvento)}
                className="campo-testo"
                disabled={inModifica}
              >
                {TIPI_EVENTO.map((t) => (
                  <option key={t.tipo} value={t.tipo}>
                    {t.etichetta}
                  </option>
                ))}
              </select>
            </Etichetta>
          </div>

          <div className="linea-divisoria" />

          <CampiDinamici
            tipo={tipo}
            dati={dati}
            giocatori={giocatori}
            onCambia={setDati}
          />
        </div>

        {/* Footer */}
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
            {inInvio ? "Salvo…" : inModifica ? "Salva modifiche" : "Crea evento"}
          </button>
        </footer>
      </form>
    </div>
  );
}

// === Campi dinamici ===

function CampiDinamici({
  tipo,
  dati,
  giocatori,
  onCambia,
}: {
  tipo: TipoEvento;
  dati: Record<string, unknown>;
  giocatori: GiocatorePartita[];
  onCambia: (dati: Record<string, unknown>) => void;
}) {
  function aggiorna(modifiche: Record<string, unknown>) {
    onCambia({ ...dati, ...modifiche });
  }

  switch (tipo) {
    case "territorio_assegnato_inizio":
      return (
        <>
          <SelectGiocatore
            etichetta="Giocatore"
            valore={(dati.giocatore_id as string) ?? ""}
            onCambia={(v) => aggiorna({ giocatore_id: v })}
            giocatori={giocatori}
          />
          <SelectTerritorio
            etichetta="Territorio"
            valore={(dati.territorio as string) ?? ""}
            onCambia={(v) => aggiorna({ territorio: v })}
          />
          <CampoNumero
            etichetta="Armate iniziali"
            valore={(dati.n_armate as number) ?? 1}
            min={1}
            onCambia={(n) => aggiorna({ n_armate: n })}
          />
        </>
      );

    case "obiettivo_assegnato":
      return (
        <>
          <SelectGiocatore
            etichetta="Giocatore"
            valore={(dati.giocatore_id as string) ?? ""}
            onCambia={(v) => aggiorna({ giocatore_id: v })}
            giocatori={giocatori}
          />
          <Etichetta testo="Obiettivo" obbligatorio>
            <select
              required
              value={String(dati.obiettivo_id ?? "")}
              onChange={(e) =>
                aggiorna({ obiettivo_id: Number(e.target.value) })
              }
              className="campo-testo"
            >
              <option value="" disabled>
                — seleziona obiettivo —
              </option>
              {OBIETTIVI.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.id}. {o.nome}
                </option>
              ))}
            </select>
          </Etichetta>
        </>
      );

    case "partita_inizio":
      return (
        <SelectGiocatore
          etichetta="Primo giocatore"
          valore={(dati.primo_giocatore_id as string) ?? ""}
          onCambia={(v) => aggiorna({ primo_giocatore_id: v })}
          giocatori={giocatori}
        />
      );

    case "armate_piazzate":
      return (
        <>
          <SelectGiocatore
            etichetta="Giocatore"
            valore={(dati.giocatore_id as string) ?? ""}
            onCambia={(v) => aggiorna({ giocatore_id: v })}
            giocatori={giocatori}
          />
          <SelectTerritorio
            etichetta="Territorio"
            valore={(dati.territorio as string) ?? ""}
            onCambia={(v) => aggiorna({ territorio: v })}
          />
          <CampoNumero
            etichetta="Armate da piazzare"
            valore={(dati.n as number) ?? 1}
            min={1}
            onCambia={(n) => aggiorna({ n })}
          />
        </>
      );

    case "tris_giocato": {
      const carte = (dati.carte as DatoCarta[]) ?? [
        { territorio: null, simbolo: "fante" },
        { territorio: null, simbolo: "fante" },
        { territorio: null, simbolo: "fante" },
      ];
      function aggiornaCarta(indice: number, mod: Partial<DatoCarta>) {
        const nuove = carte.map((c, i) => (i === indice ? { ...c, ...mod } : c));
        aggiorna({ carte: nuove });
      }
      return (
        <>
          <SelectGiocatore
            etichetta="Giocatore"
            valore={(dati.giocatore_id as string) ?? ""}
            onCambia={(v) => aggiorna({ giocatore_id: v })}
            giocatori={giocatori}
          />
          <div>
            <div className="etichetta mb-2">Le 3 carte del tris</div>
            <div className="space-y-2">
              {carte.map((c, i) => (
                <div key={i} className="grid grid-cols-[2fr_1fr] gap-2">
                  <select
                    value={c.territorio ?? ""}
                    onChange={(e) =>
                      aggiornaCarta(i, {
                        territorio: e.target.value || null,
                      })
                    }
                    className="campo-testo"
                  >
                    <option value="">— jolly o territorio —</option>
                    {TERRITORI.map((t) => (
                      <option key={t} value={t}>
                        {nominaTerritorio(t)}
                      </option>
                    ))}
                  </select>
                  <select
                    value={c.simbolo}
                    onChange={(e) =>
                      aggiornaCarta(i, {
                        simbolo: e.target.value as SimboloCarta,
                      })
                    }
                    className="campo-testo"
                  >
                    {SIMBOLI_CARTA.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </div>
        </>
      );
    }

    case "attacco_risolto": {
      const dadiAtt = (dati.dadi_attaccante as number[]) ?? [6];
      const dadiDif = (dati.dadi_difensore as number[]) ?? [1];
      return (
        <>
          <SelectGiocatore
            etichetta="Attaccante"
            valore={(dati.giocatore_id as string) ?? ""}
            onCambia={(v) => aggiorna({ giocatore_id: v })}
            giocatori={giocatori}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SelectTerritorio
              etichetta="Da (territorio attaccante)"
              valore={(dati.da as string) ?? ""}
              onCambia={(v) => aggiorna({ da: v })}
            />
            <SelectTerritorio
              etichetta="A (territorio difensore)"
              valore={(dati.a as string) ?? ""}
              onCambia={(v) => aggiorna({ a: v })}
            />
          </div>
          <GruppoDadi
            etichetta="Dadi attaccante (1-3)"
            dadi={dadiAtt}
            onCambia={(d) => aggiorna({ dadi_attaccante: d })}
          />
          <GruppoDadi
            etichetta="Dadi difensore (1-3)"
            dadi={dadiDif}
            onCambia={(d) => aggiorna({ dadi_difensore: d })}
          />
        </>
      );
    }

    case "armate_spostate":
      return (
        <>
          <SelectGiocatore
            etichetta="Giocatore"
            valore={(dati.giocatore_id as string) ?? ""}
            onCambia={(v) => aggiorna({ giocatore_id: v })}
            giocatori={giocatori}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SelectTerritorio
              etichetta="Da"
              valore={(dati.da as string) ?? ""}
              onCambia={(v) => aggiorna({ da: v })}
            />
            <SelectTerritorio
              etichetta="A"
              valore={(dati.a as string) ?? ""}
              onCambia={(v) => aggiorna({ a: v })}
            />
          </div>
          <CampoNumero
            etichetta="Numero armate"
            valore={(dati.n as number) ?? 1}
            min={1}
            onCambia={(n) => aggiorna({ n })}
          />
        </>
      );

    case "turno_finito":
      return (
        <SelectGiocatore
          etichetta="Giocatore (di cui finisce il turno)"
          valore={(dati.giocatore_id as string) ?? ""}
          onCambia={(v) => aggiorna({ giocatore_id: v })}
          giocatori={giocatori}
        />
      );

    case "partita_fine":
      return (
        <SelectGiocatore
          etichetta="Vincitore"
          valore={(dati.vincitore_id as string) ?? ""}
          onCambia={(v) => aggiorna({ vincitore_id: v })}
          giocatori={giocatori}
        />
      );

    default:
      // Editor JSON libero per tipi senza form dedicato
      return (
        <Etichetta testo="Payload JSON">
          <textarea
            rows={8}
            value={JSON.stringify(dati, null, 2)}
            onChange={(e) => {
              try {
                onCambia(JSON.parse(e.target.value || "{}"));
              } catch {
                // ignora errori parse: l'utente sta digitando
              }
            }}
            className="campo-testo font-mono text-xs"
            placeholder='{ "messaggio": "..." }'
          />
        </Etichetta>
      );
  }
}

// === Sub-componenti riusabili ===

function Etichetta({
  testo,
  obbligatorio,
  children,
}: {
  testo: string;
  obbligatorio?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="etichetta block mb-1.5">
        {testo}
        {obbligatorio ? <span className="text-scarlatto"> *</span> : null}
      </span>
      {children}
    </label>
  );
}

function SelectGiocatore({
  etichetta,
  valore,
  onCambia,
  giocatori,
}: {
  etichetta: string;
  valore: string;
  onCambia: (v: string) => void;
  giocatori: GiocatorePartita[];
}) {
  return (
    <Etichetta testo={etichetta} obbligatorio>
      <div className="flex items-center gap-2">
        <select
          required
          value={valore}
          onChange={(e) => onCambia(e.target.value)}
          className="campo-testo flex-1"
        >
          <option value="" disabled>
            — seleziona giocatore —
          </option>
          {giocatori.map((g) => (
            <option key={g.id} value={g.id}>
              {g.nome} ({g.colore})
            </option>
          ))}
        </select>
        {(() => {
          const g = giocatori.find((g) => g.id === valore);
          return g ? (
            <PallinoColore colore={g.colore} classeDimensione="w-4 h-4" />
          ) : null;
        })()}
      </div>
    </Etichetta>
  );
}

function SelectTerritorio({
  etichetta,
  valore,
  onCambia,
}: {
  etichetta: string;
  valore: string;
  onCambia: (v: string) => void;
}) {
  return (
    <Etichetta testo={etichetta} obbligatorio>
      <select
        required
        value={valore}
        onChange={(e) => onCambia(e.target.value)}
        className="campo-testo"
      >
        <option value="" disabled>
          — seleziona territorio —
        </option>
        {TERRITORI.map((t) => (
          <option key={t} value={t}>
            {nominaTerritorio(t)}
          </option>
        ))}
      </select>
    </Etichetta>
  );
}

function CampoNumero({
  etichetta,
  valore,
  min,
  max,
  onCambia,
}: {
  etichetta: string;
  valore: number;
  min?: number;
  max?: number;
  onCambia: (n: number) => void;
}) {
  return (
    <Etichetta testo={etichetta} obbligatorio>
      <input
        type="number"
        required
        min={min}
        max={max}
        value={valore}
        onChange={(e) => onCambia(Number(e.target.value))}
        className="campo-testo font-mono num-tab w-32"
      />
    </Etichetta>
  );
}

function GruppoDadi({
  etichetta,
  dadi,
  onCambia,
}: {
  etichetta: string;
  dadi: number[];
  onCambia: (d: number[]) => void;
}) {
  function impostaCount(n: number) {
    const nuovi = Array.from({ length: n }, (_, i) => dadi[i] ?? 6);
    onCambia(nuovi);
  }
  function impostaValore(indice: number, valore: number) {
    onCambia(dadi.map((d, i) => (i === indice ? valore : d)));
  }
  return (
    <div>
      <div className="etichetta mb-2">{etichetta}</div>
      <div className="flex items-center gap-2">
        <select
          value={dadi.length}
          onChange={(e) => impostaCount(Number(e.target.value))}
          className="campo-testo w-28 font-mono num-tab"
        >
          <option value={1}>1 dado</option>
          <option value={2}>2 dadi</option>
          <option value={3}>3 dadi</option>
        </select>
        {dadi.map((d, i) => (
          <input
            key={i}
            type="number"
            min={1}
            max={6}
            value={d}
            onChange={(e) => impostaValore(i, Number(e.target.value))}
            className="campo-testo w-16 font-mono num-tab text-center"
          />
        ))}
      </div>
    </div>
  );
}

// === Helper ===

function strutturaVuotaPerTipo(
  tipo: TipoEvento,
  giocatori: GiocatorePartita[],
): Record<string, unknown> {
  const idPrimo = giocatori[0]?.id ?? "";
  switch (tipo) {
    case "territorio_assegnato_inizio":
      return { giocatore_id: idPrimo, territorio: "", n_armate: 1 };
    case "obiettivo_assegnato":
      return { giocatore_id: idPrimo, obiettivo_id: 1 };
    case "partita_inizio":
      return { primo_giocatore_id: idPrimo };
    case "armate_piazzate":
      return { giocatore_id: idPrimo, territorio: "", n: 1 };
    case "tris_giocato":
      return {
        giocatore_id: idPrimo,
        carte: [
          { territorio: null, simbolo: "fante" },
          { territorio: null, simbolo: "fante" },
          { territorio: null, simbolo: "fante" },
        ],
      };
    case "attacco_risolto":
      return {
        giocatore_id: idPrimo,
        da: "",
        a: "",
        dadi_attaccante: [6],
        dadi_difensore: [1],
      };
    case "armate_spostate":
      return { giocatore_id: idPrimo, da: "", a: "", n: 1 };
    case "turno_finito":
      return { giocatore_id: idPrimo };
    case "partita_fine":
      return { vincitore_id: idPrimo };
    default:
      return {};
  }
}

function formattaPerInputDatetime(iso: string): string {
  const d = new Date(iso);
  const offset = d.getTimezoneOffset() * 60_000;
  return new Date(d.getTime() - offset).toISOString().slice(0, 19);
}

function nominaTerritorio(slug: string): string {
  return slug.replace(/_/g, " ");
}
