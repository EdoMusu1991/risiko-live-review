/**
 * Widget compatto che mostra lo stato della pipeline CV (ffmpeg,
 * opencv, immagine riferimento, client CV).
 *
 * Da posizionare in alto alla pagina dettaglio partita o come tooltip
 * nel pannello calibrazione/discrepanze. Aiuta l'utente a capire perche'
 * un endpoint potrebbe rispondere 503.
 */

import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, ChevronDown, Cpu } from "lucide-react";

import {
  apiDiagnostica,
  ErroreApi,
  type StatoComponente,
  type StatoPipelineCv,
} from "@/api";

export function WidgetStatoPipelineCv() {
  const [stato, setStato] = useState<StatoPipelineCv | null>(null);
  const [errore, setErrore] = useState<string | null>(null);
  const [aperto, setAperto] = useState(false);

  useEffect(() => {
    apiDiagnostica
      .statoPipelineCv()
      .then(setStato)
      .catch((e) => {
        setErrore(e instanceof ErroreApi ? e.dettaglio : "Errore");
      });
  }, []);

  if (errore !== null) {
    return (
      <div className="text-xs text-scarlatto inline-flex items-center gap-1">
        <AlertCircle className="w-3 h-3" />
        Pipeline CV: errore diagnostica
      </div>
    );
  }

  if (stato === null) {
    return null;
  }

  const config: Record<
    StatoPipelineCv["livello_pronto"],
    { etichetta: string; classe: string; icona: typeof CheckCircle2 }
  > = {
    completo: {
      etichetta: "pipeline pronta",
      classe: "text-bottiglia bg-bottiglia/10",
      icona: CheckCircle2,
    },
    parziale: {
      etichetta: "pipeline mock attiva",
      classe: "text-bronzo bg-bronzo/10",
      icona: Cpu,
    },
    non_pronto: {
      etichetta: "pipeline non pronta",
      classe: "text-scarlatto bg-scarlatto/10",
      icona: AlertCircle,
    },
  };
  const c = config[stato.livello_pronto];
  const Icona = c.icona;

  return (
    <div className="text-xs">
      <button
        type="button"
        onClick={() => setAperto((v) => !v)}
        className={`inline-flex items-center gap-1 px-2 py-1 rounded ${c.classe} hover:opacity-80 transition`}
      >
        <Icona className="w-3 h-3" />
        {c.etichetta}
        <ChevronDown
          className={`w-3 h-3 transition-transform ${
            aperto ? "rotate-180" : ""
          }`}
        />
      </button>

      {aperto ? (
        <ul className="mt-2 space-y-1 p-3 bg-pergamena-scura/30 rounded border border-inchiostro/10 max-w-md">
          <RigaComponente comp={stato.ffmpeg} />
          <RigaComponente comp={stato.opencv} />
          <RigaComponente comp={stato.immagine_riferimento} />
          <RigaComponente comp={stato.client_cv} />
        </ul>
      ) : null}
    </div>
  );
}

function RigaComponente({ comp }: { comp: StatoComponente }) {
  return (
    <li className="text-[11px]">
      <div className="flex items-start gap-1.5">
        {comp.disponibile ? (
          <CheckCircle2 className="w-3 h-3 mt-0.5 text-bottiglia flex-shrink-0" />
        ) : (
          <AlertCircle className="w-3 h-3 mt-0.5 text-scarlatto flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="font-mono text-inchiostro">{comp.nome}</div>
          {comp.dettaglio ? (
            <div className="text-inchiostro-fioco italic">
              {comp.dettaglio}
            </div>
          ) : null}
        </div>
      </div>
    </li>
  );
}
