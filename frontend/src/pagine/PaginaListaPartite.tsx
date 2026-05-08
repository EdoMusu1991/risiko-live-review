/**
 * Lista partite — homepage dell'applicazione.
 *
 * Layout editoriale: titolo grande in Fraunces, una colonna per le partite
 * stile "lista articoli". Stato vuoto chiama a creare la prima partita.
 */

import { Link } from "react-router-dom";
import { format, parseISO } from "date-fns";
import { it } from "date-fns/locale";
import { ChevronRight, MapPin } from "lucide-react";

import { apiPartite } from "@/api";
import {
  BadgeStato,
  IndicatoreCarico,
  MessaggioErrore,
  StatoVuoto,
} from "@/componenti/decorativi";
import { useRichiestaApi } from "@/hooks/useRichiestaApi";

export function PaginaListaPartite() {
  const { dato, inCaricamento, errore, ricarica } = useRichiestaApi(
    () => apiPartite.lista({ limite: 50 }),
    [],
  );

  return (
    <div className="max-w-[1400px] mx-auto px-6 lg:px-12 py-12">
      <header className="mb-10 max-w-3xl">
        <div className="etichetta-rossa mb-3">Archivio</div>
        <h2 className="font-display text-5xl md:text-6xl font-black tracking-crisp leading-none mb-6">
          Tutte le <em className="text-scarlatto not-italic">partite</em>
        </h2>
        <p className="text-inchiostro-tenue max-w-xl text-base leading-relaxed">
          Ogni serata al club genera una partita. Qui puoi rivederle, validare
          gli eventi raccolti dal tablet osservatore, e ricostruire lo stato
          finale tramite il motore regole.
        </p>
      </header>

      <div className="linea-divisoria mb-8" />

      {inCaricamento ? <IndicatoreCarico etichetta="Carico le partite" /> : null}

      {errore ? (
        <MessaggioErrore
          testo={errore.message}
          azioneRipristino={{ etichetta: "Riprova", onClick: ricarica }}
        />
      ) : null}

      {!inCaricamento && !errore && dato !== null && dato.length === 0 ? (
        <StatoVuoto
          titolo="Nessuna partita ancora"
          descrizione="Crea la prima partita per iniziare a raccogliere eventi e video."
          azione={{ etichetta: "Crea partita", href: "/partite/nuova" }}
        />
      ) : null}

      {dato !== null && dato.length > 0 ? (
        <ul className="divide-y divide-inchiostro/10 border-y border-inchiostro/15">
          {dato.map((partita, indice) => (
            <li key={partita.id}>
              <Link
                to={`/partite/${partita.id}`}
                className="group flex items-center gap-6 py-5 px-2 hover:bg-inchiostro/[0.02] transition-colors"
              >
                {/* Numero progressivo, stile rivista */}
                <div className="font-mono text-xs text-inchiostro-fioco w-10 num-tab">
                  {String(dato.length - indice).padStart(2, "0")}
                </div>

                {/* Data + luogo */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-3 flex-wrap">
                    <h3 className="font-display text-2xl font-semibold leading-tight tracking-crisp">
                      {format(parseISO(partita.data_inizio), "EEEE d LLLL yyyy", {
                        locale: it,
                      })}
                    </h3>
                    <BadgeStato stato={partita.stato_review} />
                  </div>
                  <div className="mt-1 flex items-center gap-4 text-xs text-inchiostro-tenue">
                    <span className="font-mono num-tab">
                      {format(parseISO(partita.data_inizio), "HH:mm")}
                    </span>
                    {partita.luogo ? (
                      <span className="inline-flex items-center gap-1.5">
                        <MapPin size={12} />
                        {partita.luogo}
                      </span>
                    ) : null}
                  </div>
                </div>

                <ChevronRight
                  size={18}
                  className="text-inchiostro-fioco group-hover:text-scarlatto group-hover:translate-x-0.5 transition-transform"
                />
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
