/**
 * Pagina di review di una singola partita.
 *
 * Layout a due colonne:
 * - Sinistra (2/3): metadati + player video (se presente) + stato finale.
 * - Destra (1/3): pannello eventi con tab validati/grezzi + editor.
 *
 * Editor eventi:
 * - Pulsante "+ Nuovo evento" (timestamp pre-popolato dal video corrente).
 * - Su ogni riga validato: edit/elimina (on hover).
 * - Shortcut tastiera "N" per aprire il form.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { format, parseISO } from "date-fns";
import { it } from "date-fns/locale";
import { ArrowLeft, MapPin, Sparkles, Trash2 } from "lucide-react";

import { apiEventi, apiPartite, apiRicostruzione, apiVideo } from "@/api";
import { ErroreApi } from "@/api";
import type { PropostaAggregazioneDadi } from "@/api/aggregazione";
import { useRichiestaApi } from "@/hooks/useRichiestaApi";
import {
  BadgeStato,
  IndicatoreCarico,
  MessaggioErrore,
  PallinoColore,
} from "@/componenti/decorativi";
import { BottoneEsportaPartita } from "@/componenti/BottoneEsportaPartita";
import { FormEvento } from "@/componenti/FormEvento";
import { ModaleSetupAutomatico } from "@/componenti/ModaleSetupAutomatico";
import { PannelloEventi } from "@/componenti/PannelloEventi";
import { PannelloProposteAggregazione } from "@/componenti/PannelloProposteAggregazione";
import { PannelloStatistiche } from "@/componenti/PannelloStatistiche";
import { PannelloStatoFinale } from "@/componenti/PannelloStatoFinale";
import { PannelloUploadVideo } from "@/componenti/PannelloUploadVideo";
import { PannelloValidazione } from "@/componenti/PannelloValidazione";
import { ModaleAccettaProposta } from "@/componenti/ModaleAccettaProposta";
import {
  PlayerVideo,
  type RiferimentoPlayerVideo,
} from "@/componenti/PlayerVideo";
import type {
  EventoGrezzo,
  EventoValidato,
  RisultatoRicostruzione,
  TipoEvento,
} from "@/tipi/dominio";

export function PaginaDettaglioPartita() {
  const { partitaId } = useParams<{ partitaId: string }>();
  const id = partitaId ?? "";

  // Caricamenti API
  const partita = useRichiestaApi(() => apiPartite.dettaglio(id), [id]);
  const grezzi = useRichiestaApi(() => apiEventi.listaGrezzi(id), [id]);
  const validati = useRichiestaApi(() => apiEventi.listaValidati(id), [id]);

  // Ricostruzione
  const [statoFinale, setStatoFinale] =
    useState<RisultatoRicostruzione | null>(null);
  const [inRicostruzione, setInRicostruzione] = useState(false);
  const [erroreRicostruzione, setErroreRicostruzione] = useState<string | null>(
    null,
  );

  useEffect(() => {
    let annullato = false;
    apiRicostruzione
      .statoFinale(id)
      .then((r) => {
        if (!annullato) setStatoFinale(r);
      })
      .catch((e) => {
        console.error("Errore caricamento stato finale", e);
      });
    return () => {
      annullato = true;
    };
  }, [id]);

  async function ricostruisci() {
    setInRicostruzione(true);
    setErroreRicostruzione(null);
    try {
      const risultato = await apiRicostruzione.ricostruisci(id);
      setStatoFinale(risultato);
    } catch (e) {
      const messaggio =
        e instanceof ErroreApi ? e.dettaglio : "Errore ricostruzione";
      setErroreRicostruzione(messaggio);
    } finally {
      setInRicostruzione(false);
    }
  }

  // Player video + tracking secondo corrente
  const playerRef = useRef<RiferimentoPlayerVideo | null>(null);
  const [secondoCorrente, setSecondoCorrente] = useState(0);

  function saltaA(secondo: number) {
    playerRef.current?.saltaA(secondo);
  }

  // Editor eventi: stato modale unificato
  type StatoModale =
    | { aperta: false }
    | {
        aperta: true;
        tipologia: "validato" | "grezzo";
        eventoEsistente: EventoValidato | EventoGrezzo | null;
      };
  const [modale, setModale] = useState<StatoModale>({ aperta: false });

  // Proposta di aggregazione BLE in fase di accettazione (modale separato)
  const [propostaInAccettazione, setPropostaInAccettazione] =
    useState<PropostaAggregazioneDadi | null>(null);
  // Trigger di refresh per il PannelloProposteAggregazione (cambia per
  // forzare un re-render dopo accettazione/rifiuto)
  const [refreshProposte, setRefreshProposte] = useState(0);

  const videoCorrente = partita.dato?.video[0] ?? null;

  /** Calcola il timestamp ISO corrispondente al secondo corrente del video. */
  const tsEventoFromVideo = useMemo(() => {
    if (!videoCorrente) return new Date().toISOString();
    const inizio = parseISO(videoCorrente.ts_inizio).getTime();
    return new Date(inizio + secondoCorrente * 1000).toISOString();
  }, [videoCorrente, secondoCorrente]);

  const apriCreazione = useCallback(
    (tipologia: "validato" | "grezzo" = "validato") => {
      setModale({ aperta: true, tipologia, eventoEsistente: null });
      playerRef.current?.pausa();
    },
    [],
  );

  const apriModificaValidato = useCallback((evento: EventoValidato) => {
    setModale({ aperta: true, tipologia: "validato", eventoEsistente: evento });
    playerRef.current?.pausa();
  }, []);

  function chiudiModale() {
    setModale({ aperta: false });
  }

  async function salvaEvento(dati: {
    id?: string;
    ts_evento: string;
    tipo: TipoEvento;
    dati: Record<string, unknown>;
  }) {
    if (!modale.aperta) return;

    if (modale.tipologia === "validato") {
      if (dati.id) {
        await apiEventi.aggiornaValidato(id, dati.id, {
          ts_evento: dati.ts_evento,
          tipo: dati.tipo,
          dati: dati.dati,
        });
      } else {
        await apiEventi.creaValidato(id, {
          ts_evento: dati.ts_evento,
          tipo: dati.tipo,
          dati: dati.dati,
          validato_da: "edoardo",
        });
      }
      await validati.ricarica();
    } else {
      if (dati.id) {
        await apiEventi.aggiornaGrezzo(id, dati.id, {
          ts_evento: dati.ts_evento,
          tipo: dati.tipo,
          dati: dati.dati,
        });
      } else {
        await apiEventi.aggiungiGrezzo(id, {
          ts_evento: dati.ts_evento,
          tipo: dati.tipo,
          fonte: "input_manuale",
          dati: dati.dati,
        });
      }
      await grezzi.ricarica();
    }
    chiudiModale();
  }

  async function eliminaEventoValidato(evento: EventoValidato) {
    const conferma = window.confirm(
      `Eliminare l'evento validato "${evento.tipo}" del ${format(
        parseISO(evento.ts_evento),
        "dd/MM/yyyy HH:mm:ss",
      )}?`,
    );
    if (!conferma) return;

    try {
      await apiEventi.eliminaValidato(id, evento.id);
      await validati.ricarica();
    } catch (e) {
      console.error("Errore eliminazione evento", e);
      alert("Errore durante l'eliminazione");
    }
  }

  const apriModificaGrezzo = useCallback((evento: EventoGrezzo) => {
    setModale({ aperta: true, tipologia: "grezzo", eventoEsistente: evento });
    playerRef.current?.pausa();
  }, []);

  async function eliminaEventoGrezzo(evento: EventoGrezzo) {
    const conferma = window.confirm(
      `Eliminare l'evento grezzo "${evento.tipo}" del ${format(
        parseISO(evento.ts_evento),
        "dd/MM/yyyy HH:mm:ss",
      )}?`,
    );
    if (!conferma) return;

    try {
      await apiEventi.eliminaGrezzo(id, evento.id);
      await grezzi.ricarica();
    } catch (e) {
      console.error("Errore eliminazione evento", e);
      alert("Errore durante l'eliminazione");
    }
  }

  /**
   * Promuove un evento grezzo a validato (one-click). Crea un evento
   * validato copiando i campi dal grezzo, e marca il grezzo come validato
   * nel backend tramite il riferimento bidirezionale.
   */
  async function promuoviEventoGrezzo(evento: EventoGrezzo) {
    try {
      await apiEventi.creaValidato(id, {
        ts_evento: evento.ts_evento,
        tipo: evento.tipo,
        dati: evento.dati,
        evento_grezzo_id: evento.id,
        validato_da: "edoardo",
      });
      await Promise.all([validati.ricarica(), grezzi.ricarica()]);
    } catch (e) {
      console.error("Errore promozione evento", e);
      alert(
        e instanceof ErroreApi
          ? `Errore promozione: ${e.dettaglio}`
          : "Errore durante la promozione",
      );
    }
  }

  // Setup automatico: stato modale aperta/chiusa
  const [modaleSetupAperta, setModaleSetupAperta] = useState(false);

  // Filtro mappa↔eventi: territorio cliccato sulla plancia
  const [territorioSelezionato, setTerritorioSelezionato] = useState<
    string | null
  >(null);

  // Click toggle: ri-cliccando lo stesso territorio si deseleziona
  const onClickTerritorio = useCallback((slug: string) => {
    setTerritorioSelezionato((prec) => (prec === slug ? null : slug));
  }, []);

  async function onSetupCompletato() {
    // Chiudi modale, ricarica eventi e (best effort) lo stato finale
    setModaleSetupAperta(false);
    await validati.ricarica();
  }

  // Shortcut tastiera "N" per nuovo evento
  useEffect(() => {
    function gestisci(e: KeyboardEvent) {
      // Ignora se sta scrivendo in input/textarea
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (modale.aperta) return;
      if (e.key === "n" || e.key === "N") {
        e.preventDefault();
        apriCreazione();
      }
    }
    window.addEventListener("keydown", gestisci);
    return () => window.removeEventListener("keydown", gestisci);
  }, [apriCreazione, modale.aperta]);

  // Indicatore "stato obsoleto"
  const statoObsoleto =
    statoFinale !== null &&
    validati.dato !== null &&
    statoFinale.n_eventi_totali !== validati.dato.length;

  // Stato di caricamento globale
  if (partita.inCaricamento) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 py-12">
        <IndicatoreCarico etichetta="Carico la partita" />
      </div>
    );
  }

  if (partita.errore) {
    return (
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 py-12">
        <MessaggioErrore
          testo={partita.errore.message}
          azioneRipristino={{
            etichetta: "Riprova",
            onClick: partita.ricarica,
          }}
        />
      </div>
    );
  }

  if (partita.dato === null) return null;

  const p = partita.dato;

  return (
    <div className="max-w-[1400px] mx-auto px-6 lg:px-12 py-8">
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-xs uppercase tracking-widest text-inchiostro-tenue hover:text-scarlatto mb-6 transition-colors"
      >
        <ArrowLeft size={14} /> Tutte le partite
      </Link>

      <header className="mb-8 flex items-end justify-between gap-6 flex-wrap">
        <div>
          <div className="etichetta-rossa mb-2">
            Partita ·{" "}
            <span className="text-inchiostro-fioco">{p.id.slice(0, 8)}…</span>
          </div>
          <h2 className="font-display text-4xl md:text-5xl font-black tracking-crisp leading-none mb-3">
            {format(parseISO(p.data_inizio), "EEEE d LLLL yyyy", { locale: it })}
          </h2>
          <div className="flex items-center gap-4 text-sm text-inchiostro-tenue">
            <span className="font-mono num-tab">
              {format(parseISO(p.data_inizio), "HH:mm")}
            </span>
            {p.luogo ? (
              <span className="inline-flex items-center gap-1.5">
                <MapPin size={14} />
                {p.luogo}
              </span>
            ) : null}
            <BadgeStato stato={p.stato_review} />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <BottoneEsportaPartita partitaId={p.id} />
          <BottoneEliminaPartita partitaId={p.id} />
        </div>
      </header>

      <section className="mb-8">
        <h3 className="etichetta mb-3">Giocatori al tavolo</h3>
        <div className="flex flex-wrap gap-3">
          {p.giocatori.map((g) => (
            <div
              key={g.id}
              className="carta px-4 py-2 inline-flex items-center gap-2"
            >
              <PallinoColore colore={g.colore} classeDimensione="w-3 h-3" />
              <span className="font-display font-semibold">{g.nome}</span>
              <span className="text-xs text-inchiostro-fioco font-mono">
                · seduta {g.ordine_seduta}
              </span>
            </div>
          ))}
        </div>
      </section>

      <div className="linea-divisoria mb-8" />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Colonna sinistra */}
        <div className="lg:col-span-2 space-y-8">
          {/* Setup automatico: visibile solo se nessun evento validato */}
          {validati.dato !== null && validati.dato.length === 0 ? (
            <section className="border border-scarlatto/30 bg-scarlatto/[0.03] p-5 flex items-center justify-between gap-4">
              <div>
                <div className="etichetta-rossa mb-1">Setup partita</div>
                <h3 className="font-display text-xl font-semibold mb-1">
                  Distribuisci automaticamente territori, obiettivi e armate
                </h3>
                <p className="text-sm text-inchiostro-tenue">
                  Genera in un click i 45 eventi di setup applicando le regole
                  Risiko EG (40 armate a testa, distribuzione round-robin,
                  obiettivi random distinti).
                </p>
              </div>
              <button
                type="button"
                onClick={() => setModaleSetupAperta(true)}
                className="btn-primario shrink-0"
              >
                <Sparkles size={14} />
                Setup automatico
              </button>
            </section>
          ) : null}

          <section>
            <h3 className="etichetta mb-3">Video</h3>
            {videoCorrente ? (
              <div>
                <PlayerVideo
                  ref={playerRef}
                  urlStream={apiVideo.urlStream(p.id, videoCorrente.id)}
                  durataSec={videoCorrente.durata_sec}
                  onSecondoCambia={setSecondoCorrente}
                />
                <div className="mt-2 flex items-center justify-between text-xs text-inchiostro-tenue font-mono num-tab">
                  <span>{videoCorrente.nome_originale}</span>
                  <span>
                    {videoCorrente.risoluzione} · {videoCorrente.codec} ·{" "}
                    {(videoCorrente.dimensione_byte / 1e9).toFixed(2)} GB
                  </span>
                </div>
              </div>
            ) : (
              <PannelloUploadVideo
                partitaId={p.id}
                onCaricato={partita.ricarica}
              />
            )}
          </section>

          {/* Avviso stato obsoleto */}
          {statoObsoleto ? (
            <div className="border-l-4 border-oro pl-3 py-2 text-sm text-inchiostro-tenue">
              <span className="etichetta text-oro">Attenzione</span> — gli
              eventi sono cambiati dopo l'ultima ricostruzione. Premi
              "Ricostruisci" per aggiornare lo stato finale.
            </div>
          ) : null}

          {erroreRicostruzione ? (
            <MessaggioErrore testo={erroreRicostruzione} />
          ) : null}

          {/* Proposte aggregazione BLE: visibili solo se ci sono giocatori */}
          {p.giocatori.length > 0 ? (
            <PannelloProposteAggregazione
              key={refreshProposte}
              partitaId={p.id}
              onSeek={(ts) => {
                if (videoCorrente) {
                  const inizioVideo = new Date(videoCorrente.ts_inizio).getTime();
                  const tsTarget = new Date(ts).getTime();
                  const offsetSec = (tsTarget - inizioVideo) / 1000;
                  if (offsetSec >= 0) saltaA(offsetSec);
                }
              }}
              onAccetta={(proposta) => setPropostaInAccettazione(proposta)}
              onEventiCambiati={() => {
                grezzi.ricarica();
                setRefreshProposte((n) => n + 1);
              }}
            />
          ) : null}

          {/* Validazione coerenza eventi: pre-controllo manuale prima
              di lanciare la ricostruzione */}
          {validati.dato !== null && validati.dato.length > 0 ? (
            <PannelloValidazione partitaId={p.id} />
          ) : null}

          <PannelloStatoFinale
            risultato={statoFinale}
            giocatoriPartita={p.giocatori}
            inRicostruzione={inRicostruzione}
            onRicostruisci={ricostruisci}
            territorioSelezionato={territorioSelezionato}
            onClickTerritorio={onClickTerritorio}
          />

          {/* Statistiche aggregate: visibili se ci sono eventi validati */}
          {validati.dato !== null && validati.dato.length > 0 ? (
            <PannelloStatistiche
              partitaId={p.id}
              triggerRicarica={validati.dato.length}
            />
          ) : null}
        </div>

        {/* Colonna destra: eventi */}
        <aside className="lg:col-span-1">
          <div className="lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] flex flex-col carta">
            <div className="px-4 py-3 border-b border-inchiostro/10">
              <h3 className="etichetta">Eventi</h3>
              <p className="text-[10px] text-inchiostro-fioco mt-0.5">
                Premi <kbd className="font-mono px-1 border border-inchiostro/20">N</kbd> per nuovo evento
              </p>
            </div>
            <PannelloEventi
              eventiGrezzi={grezzi.dato ?? []}
              eventiValidati={validati.dato ?? []}
              giocatori={p.giocatori}
              video={videoCorrente}
              filtroTerritorio={territorioSelezionato}
              onPuliciFiltro={() => setTerritorioSelezionato(null)}
              onSaltaSecondo={saltaA}
              onAggiungi={apriCreazione}
              onModificaValidato={apriModificaValidato}
              onEliminaValidato={eliminaEventoValidato}
              onModificaGrezzo={apriModificaGrezzo}
              onEliminaGrezzo={eliminaEventoGrezzo}
              onPromuoviGrezzo={promuoviEventoGrezzo}
            />
          </div>
        </aside>
      </div>

      {/* Modale form evento */}
      {modale.aperta ? (
        <FormEvento
          giocatori={p.giocatori}
          eventoEsistente={modale.eventoEsistente}
          tsEventoIniziale={tsEventoFromVideo}
          onAnnulla={chiudiModale}
          onSalva={salvaEvento}
        />
      ) : null}

      {/* Modale setup automatico */}
      {modaleSetupAperta ? (
        <ModaleSetupAutomatico
          partitaId={p.id}
          giocatori={p.giocatori}
          onAnnulla={() => setModaleSetupAperta(false)}
          onCompletato={onSetupCompletato}
        />
      ) : null}

      {/* Modale accettazione proposta aggregazione BLE */}
      {propostaInAccettazione ? (
        <ModaleAccettaProposta
          partitaId={p.id}
          proposta={propostaInAccettazione}
          giocatori={p.giocatori}
          onAnnulla={() => setPropostaInAccettazione(null)}
          onAccettata={() => {
            setPropostaInAccettazione(null);
            // Refresha eventi grezzi (gli eventi citati ora sono validato=true)
            grezzi.ricarica();
            validati.ricarica();
            // Forza il pannello proposte a re-fetchare (la proposta sparisce)
            setRefreshProposte((n) => n + 1);
          }}
        />
      ) : null}
    </div>
  );
}

function BottoneEliminaPartita({ partitaId }: { partitaId: string }) {
  const [confermando, setConfermando] = useState(false);

  async function conferma() {
    try {
      await apiPartite.elimina(partitaId);
      window.location.href = "/";
    } catch (e) {
      console.error(e);
      setConfermando(false);
    }
  }

  if (confermando) {
    return (
      <div className="flex items-center gap-2">
        <span className="etichetta-rossa">Confermare?</span>
        <button onClick={conferma} className="btn-pericolo">
          Sì, elimina
        </button>
        <button
          onClick={() => setConfermando(false)}
          className="btn-secondario"
        >
          Annulla
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setConfermando(true)}
      className="btn-pericolo"
    >
      <Trash2 size={14} /> Elimina partita
    </button>
  );
}
