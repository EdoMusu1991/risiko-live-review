/**
 * Bundle in attesa — lista dei bundle caricati dall'app mobile e ancora
 * da promuovere a `Partita` SQL.
 *
 * Il flusso e':
 * 1. App mobile carica via POST /api/import/bundle-mobile (M14, v0.28)
 *    → bundle deposita in storage_partite/<id>/
 * 2. Questa pagina lista i bundle disponibili
 * 3. Click su "Promuovi" apre dialog con campi opzionali (luogo, note)
 * 4. POST /api/partite/da-bundle/<id> crea record SQL → Partita appare
 *    nella lista partite ed e' navigabile per la review
 *
 * Layout: stessa estetica editoriale di PaginaListaPartite (titolo grande,
 * lista a colonna).
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { format, parseISO } from "date-fns";
import { it } from "date-fns/locale";
import { Clock, FilmIcon, Loader2, Trash2, Upload, Zap } from "lucide-react";

import {
  apiPromozioneBundle,
  apiScheduler,
  type BundleDisponibile,
  type RispostaPromozioneBundle,
  type StatoScheduler,
} from "@/api";
import {
  IndicatoreCarico,
  MessaggioErrore,
  StatoVuoto,
} from "@/componenti/decorativi";
import { useRichiestaApi } from "@/hooks/useRichiestaApi";

export function PaginaBundleInAttesa() {
  const { dato, inCaricamento, errore, ricarica } = useRichiestaApi(
    () => apiPromozioneBundle.lista(),
    [],
  );

  const [bundleDaPromuovere, setBundleDaPromuovere] =
    useState<BundleDisponibile | null>(null);
  const [idScartoInCorso, setIdScartoInCorso] = useState<string | null>(null);
  const [erroreScarto, setErroreScarto] = useState<string | null>(null);
  const [scheduler, setScheduler] = useState<StatoScheduler | null>(null);

  const bundle = dato?.bundle ?? [];

  // Fetch stato scheduler una volta al mount + ogni 60s
  useEffect(() => {
    let attivo = true;
    const carica = (): void => {
      void apiScheduler
        .stato()
        .then((s) => {
          if (attivo) setScheduler(s);
        })
        .catch(() => {
          // se il backend e' su una versione vecchia senza /scheduler,
          // ignoriamo silenziosamente
          if (attivo) setScheduler(null);
        });
    };
    carica();
    const id = setInterval(carica, 60_000);
    return () => {
      attivo = false;
      clearInterval(id);
    };
  }, []);

  // Polling automatico ogni 30s mentre la pagina e' aperta. Util quando
  // l'app mobile carica un bundle mentre l'arbitro e' gia' sulla pagina.
  // Disattivato quando la dialog di promozione e' aperta (per non far
  // sparire l'opzione che l'arbitro sta gestendo).
  useEffect(() => {
    if (bundleDaPromuovere !== null) return;
    const id = setInterval(() => {
      void ricarica();
    }, 30_000);
    return () => clearInterval(id);
  }, [bundleDaPromuovere, ricarica]);

  async function scartaBundle(b: BundleDisponibile): Promise<void> {
    const conferma = window.confirm(
      `Vuoi davvero scartare il bundle del ${formattaPeriodo(b.ts_inizio, b.ts_fine)}?\n\n` +
        `Verranno cancellati ${b.n_segmenti} segment${
          b.n_segmenti === 1 ? "o video" : "i video"
        } e ${b.n_eventi_dichiarati} eventi.\n\nL'operazione non e' reversibile.`,
    );
    if (!conferma) return;

    setIdScartoInCorso(b.id_partita);
    setErroreScarto(null);
    try {
      await apiPromozioneBundle.scarta(b.id_partita);
      ricarica();
    } catch (e) {
      setErroreScarto(
        `Impossibile scartare ${b.id_partita}: ${
          e instanceof Error ? e.message : String(e)
        }`,
      );
    } finally {
      setIdScartoInCorso(null);
    }
  }

  return (
    <div className="max-w-[1400px] mx-auto px-6 lg:px-12 py-12">
      <header className="mb-10 max-w-3xl">
        <div className="etichetta-rossa mb-3">Da rivedere</div>
        <h2 className="font-display text-5xl md:text-6xl font-black tracking-crisp leading-none mb-6">
          Bundle <em className="text-scarlatto not-italic">in attesa</em>
        </h2>
        <p className="text-inchiostro-tenue max-w-xl text-base leading-relaxed">
          Le registrazioni caricate dall'app mobile arrivano qui. Per iniziare
          la review, promuovi il bundle a Partita: i video vengono spostati
          in archivio e gli eventi importati nel database.
        </p>
      </header>

      <div className="linea-divisoria mb-8" />

      {inCaricamento ? (
        <IndicatoreCarico etichetta="Carico i bundle disponibili" />
      ) : null}

      {errore ? (
        <MessaggioErrore
          testo={errore.message}
          azioneRipristino={{ etichetta: "Riprova", onClick: ricarica }}
        />
      ) : null}

      {erroreScarto ? (
        <div className="mb-6">
          <MessaggioErrore
            testo={erroreScarto}
            azioneRipristino={{
              etichetta: "Chiudi",
              onClick: () => setErroreScarto(null),
            }}
          />
        </div>
      ) : null}

      {!inCaricamento && !errore && bundle.length === 0 ? (
        <StatoVuoto
          titolo="Nessun bundle in attesa"
          descrizione="Quando l'app mobile caricherà una partita registrata, apparirà qui."
        />
      ) : null}

      {bundle.length > 0 ? (
        <ul className="space-y-3">
          {bundle.map((b) => (
            <li
              key={b.id_partita}
              className="border border-inchiostro/15 rounded-md p-5 bg-pergamena/40 hover:bg-pergamena/70 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-2 text-sm text-inchiostro-tenue">
                    <span className="font-mono text-xs">{b.id_partita}</span>
                  </div>
                  <h3 className="font-display text-xl font-bold leading-tight mb-2">
                    {formattaPeriodo(b.ts_inizio, b.ts_fine)}
                  </h3>
                  <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-inchiostro-tenue">
                    <span className="inline-flex items-center gap-1.5">
                      <FilmIcon className="size-3.5" />
                      {b.n_segmenti} segment{b.n_segmenti === 1 ? "o" : "i"}
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <Zap className="size-3.5" />
                      {b.n_eventi_dichiarati} evento{b.n_eventi_dichiarati === 1 ? "" : "i"} BLE
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <Clock className="size-3.5" />
                      {formattaDurata(b.ts_inizio, b.ts_fine)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2 whitespace-nowrap">
                  <button
                    type="button"
                    onClick={() => void scartaBundle(b)}
                    disabled={idScartoInCorso === b.id_partita}
                    className="btn-secondario inline-flex items-center gap-2"
                    title="Cancella questo bundle (non ancora promosso)"
                  >
                    {idScartoInCorso === b.id_partita ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Trash2 className="size-4" />
                    )}
                    Scarta
                  </button>
                  <button
                    type="button"
                    onClick={() => setBundleDaPromuovere(b)}
                    className="btn-primario inline-flex items-center gap-2"
                  >
                    <Upload className="size-4" />
                    Promuovi
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {scheduler !== null ? (
        <PannelloScheduler stato={scheduler} />
      ) : null}

      {bundleDaPromuovere !== null ? (
        <DialogPromuovi
          bundle={bundleDaPromuovere}
          onChiudi={() => setBundleDaPromuovere(null)}
          onSuccesso={() => {
            setBundleDaPromuovere(null);
            void ricarica();
          }}
        />
      ) : null}
    </div>
  );
}

function PannelloScheduler({ stato }: { stato: StatoScheduler }) {
  const formattaProssima = (iso: string | null): string => {
    if (!iso) return "—";
    try {
      return format(parseISO(iso), "EEEE d MMMM 'alle' HH:mm", { locale: it });
    } catch {
      return iso;
    }
  };

  const colorePallino = stato.in_esecuzione
    ? "bg-verde"
    : stato.abilitato
      ? "bg-oro"
      : "bg-inchiostro/30";

  return (
    <section className="mt-12 pt-8 border-t border-inchiostro/10">
      <h3 className="etichetta mb-3">Cleanup automatico</h3>
      <div className="flex items-start gap-3 text-sm text-inchiostro-tenue">
        <span
          className={`inline-block w-2 h-2 rounded-full mt-1.5 ${colorePallino}`}
          aria-hidden
        />
        <div className="flex-1">
          {stato.abilitato ? (
            stato.in_esecuzione ? (
              <>
                <span className="text-inchiostro">
                  Scheduler attivo.
                </span>{" "}
                I bundle non promossi piu' vecchi di{" "}
                <strong>{stato.giorni_cleanup} giorni</strong> verranno
                cancellati automaticamente. Prossima esecuzione:{" "}
                <strong>{formattaProssima(stato.prossima_esecuzione)}</strong>.
              </>
            ) : (
              <>
                Scheduler abilitato ma non in esecuzione (probabile errore in
                avvio).
              </>
            )
          ) : (
            <>
              Scheduler disabilitato. I bundle restano in archivio fino a
              scarto manuale. Per abilitarlo, set{" "}
              <code className="text-xs bg-inchiostro/5 px-1 rounded">
                SCHEDULER_ABILITATO=true
              </code>{" "}
              nelle env vars del backend.
            </>
          )}
        </div>
      </div>
    </section>
  );
}

interface DialogPromuoviProps {
  bundle: BundleDisponibile;
  onChiudi: () => void;
  onSuccesso: () => void;
}

function DialogPromuovi({ bundle, onChiudi, onSuccesso }: DialogPromuoviProps) {
  const navigate = useNavigate();
  const [luogo, setLuogo] = useState("Il Gufo - Roma");
  const [noteExtra, setNoteExtra] = useState("");
  const [inCorso, setInCorso] = useState(false);
  const [errore, setErrore] = useState<string | null>(null);
  const [risultato, setRisultato] = useState<RispostaPromozioneBundle | null>(
    null,
  );

  async function gestisciPromozione() {
    setInCorso(true);
    setErrore(null);
    try {
      const ris = await apiPromozioneBundle.promuovi(bundle.id_partita, {
        luogo: luogo.trim() || null,
        note_extra: noteExtra.trim() || null,
      });
      setRisultato(ris);
    } catch (e) {
      setErrore(e instanceof Error ? e.message : String(e));
    } finally {
      setInCorso(false);
    }
  }

  function vaiAlDettaglio() {
    if (risultato !== null) {
      navigate(`/partite/${risultato.id_partita}`);
    }
  }

  // === Stato successo: mostro il riepilogo + CTA ===
  if (risultato !== null) {
    return (
      <ModaleOverlay onChiudi={onSuccesso}>
        <h3 className="font-display text-2xl font-bold mb-4">
          Bundle promosso
        </h3>
        <p className="text-sm text-inchiostro-tenue mb-4">
          La partita e' stata creata nel database. Puoi iniziare la review.
        </p>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm mb-4">
          <dt className="text-inchiostro-tenue">Video importati</dt>
          <dd className="font-mono">{risultato.n_video}</dd>
          <dt className="text-inchiostro-tenue">Eventi importati</dt>
          <dd className="font-mono">{risultato.n_eventi_importati}</dd>
          {risultato.n_eventi_scartati > 0 ? (
            <>
              <dt className="text-inchiostro-tenue">Eventi scartati</dt>
              <dd className="font-mono text-scarlatto">
                {risultato.n_eventi_scartati}
              </dd>
            </>
          ) : null}
        </dl>
        {risultato.avvisi.length > 0 ? (
          <details className="mb-4">
            <summary className="text-sm cursor-pointer">
              {risultato.avvisi.length} avvisi
            </summary>
            <ul className="mt-2 space-y-1 text-xs text-inchiostro-tenue">
              {risultato.avvisi.map((a, i) => (
                <li key={i}>• {a}</li>
              ))}
            </ul>
          </details>
        ) : null}
        <div className="flex gap-2 justify-end">
          <button type="button" onClick={onSuccesso} className="btn-secondario">
            Chiudi
          </button>
          <button
            type="button"
            onClick={vaiAlDettaglio}
            className="btn-primario"
          >
            Apri dettaglio partita →
          </button>
        </div>
      </ModaleOverlay>
    );
  }

  // === Stato form: input luogo + note ===
  return (
    <ModaleOverlay onChiudi={onChiudi}>
      <h3 className="font-display text-2xl font-bold mb-2">
        Promuovi bundle a Partita
      </h3>
      <p className="text-sm text-inchiostro-tenue font-mono mb-5">
        {bundle.id_partita}
      </p>

      <div className="space-y-4 mb-5">
        <div>
          <label
            htmlFor="luogo"
            className="block text-xs font-medium text-inchiostro-tenue mb-1.5 uppercase tracking-wider"
          >
            Luogo
          </label>
          <input
            id="luogo"
            type="text"
            value={luogo}
            onChange={(e) => setLuogo(e.target.value)}
            disabled={inCorso}
            placeholder="es. Il Gufo - Roma"
            className="w-full px-3 py-2 border border-inchiostro/20 rounded-sm bg-pergamena focus:outline-none focus:ring-2 focus:ring-scarlatto/40"
          />
        </div>
        <div>
          <label
            htmlFor="note_extra"
            className="block text-xs font-medium text-inchiostro-tenue mb-1.5 uppercase tracking-wider"
          >
            Note (opzionale)
          </label>
          <textarea
            id="note_extra"
            value={noteExtra}
            onChange={(e) => setNoteExtra(e.target.value)}
            disabled={inCorso}
            rows={3}
            placeholder="es. Torneo serale, 4 giocatori, finale a quattro"
            className="w-full px-3 py-2 border border-inchiostro/20 rounded-sm bg-pergamena focus:outline-none focus:ring-2 focus:ring-scarlatto/40 resize-none"
          />
        </div>
      </div>

      {errore !== null ? (
        <p className="text-sm text-scarlatto mb-4 p-3 bg-scarlatto/5 border-l-2 border-scarlatto">
          {errore}
        </p>
      ) : null}

      <div className="flex gap-2 justify-end">
        <button
          type="button"
          onClick={onChiudi}
          disabled={inCorso}
          className="btn-secondario"
        >
          Annulla
        </button>
        <button
          type="button"
          onClick={gestisciPromozione}
          disabled={inCorso}
          className="btn-primario inline-flex items-center gap-2"
        >
          {inCorso ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Promozione in corso...
            </>
          ) : (
            <>Promuovi</>
          )}
        </button>
      </div>
    </ModaleOverlay>
  );
}

interface ModaleOverlayProps {
  children: React.ReactNode;
  onChiudi: () => void;
}

function ModaleOverlay({ children, onChiudi }: ModaleOverlayProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-inchiostro/40 p-4"
      onClick={onChiudi}
    >
      <div
        className="bg-pergamena rounded-md shadow-xl max-w-md w-full p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formattaPeriodo(tsInizio: string, tsFine: string): string {
  try {
    const inizio = parseISO(tsInizio);
    const fine = parseISO(tsFine);
    const stessaData =
      format(inizio, "yyyy-MM-dd") === format(fine, "yyyy-MM-dd");
    if (stessaData) {
      return `${format(inizio, "EEEE d MMMM yyyy 'dalle' HH:mm", { locale: it })} alle ${format(fine, "HH:mm")}`;
    }
    return `${format(inizio, "dd MMM HH:mm", { locale: it })} → ${format(fine, "dd MMM HH:mm", { locale: it })}`;
  } catch {
    return `${tsInizio} → ${tsFine}`;
  }
}

function formattaDurata(tsInizio: string, tsFine: string): string {
  try {
    const inizio = parseISO(tsInizio).getTime();
    const fine = parseISO(tsFine).getTime();
    const sec = Math.max(0, Math.round((fine - inizio) / 1000));
    const ore = Math.floor(sec / 3600);
    const min = Math.floor((sec % 3600) / 60);
    if (ore > 0) return `${ore}h ${min}min`;
    return `${min}min`;
  } catch {
    return "—";
  }
}
