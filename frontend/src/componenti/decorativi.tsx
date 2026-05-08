/**
 * Componenti decorativi riutilizzabili: badge stato review, pallino
 * colore giocatore, indicatore carico.
 */

import type { ColoreGiocatore, StatoReview } from "@/tipi/dominio";

// === Pallino colore giocatore ===

const COLORI_TAILWIND: Record<ColoreGiocatore, string> = {
  rosso: "bg-giocatore-rosso",
  blu: "bg-giocatore-blu",
  verde: "bg-giocatore-verde",
  giallo: "bg-giocatore-giallo",
  nero: "bg-giocatore-nero",
  viola: "bg-giocatore-viola",
};

interface ProprietaPallinoColore {
  colore: ColoreGiocatore;
  classeDimensione?: string;
}

export function PallinoColore({
  colore,
  classeDimensione = "w-3 h-3",
}: ProprietaPallinoColore) {
  return (
    <span
      className={`inline-block ${classeDimensione} ${COLORI_TAILWIND[colore]} border border-inchiostro/30 rounded-full align-middle`}
      title={colore}
      aria-label={`Colore ${colore}`}
    />
  );
}

// === Badge stato review ===

interface ProprietaBadgeStato {
  stato: StatoReview;
}

const STILI_STATO: Record<StatoReview, { etichetta: string; classe: string }> = {
  grezza: {
    etichetta: "Grezza",
    classe: "border-inchiostro/30 text-inchiostro-tenue",
  },
  in_review: {
    etichetta: "In review",
    classe: "border-oro text-oro",
  },
  validata: {
    etichetta: "Validata",
    classe: "border-bottiglia text-bottiglia",
  },
  archiviata: {
    etichetta: "Archiviata",
    classe: "border-inchiostro/20 text-inchiostro-fioco",
  },
};

export function BadgeStato({ stato }: ProprietaBadgeStato) {
  const stile = STILI_STATO[stato];
  return (
    <span
      className={`inline-block px-2 py-0.5 text-[10px] font-sans uppercase tracking-widest border ${stile.classe}`}
    >
      {stile.etichetta}
    </span>
  );
}

// === Spinner / placeholder caricamento ===

export function IndicatoreCarico({ etichetta = "Caricamento" }: { etichetta?: string }) {
  return (
    <div
      className="inline-flex items-center gap-3 etichetta animate-pulse"
      role="status"
      aria-live="polite"
    >
      <span className="inline-block w-1.5 h-1.5 bg-scarlatto rounded-full" />
      {etichetta}…
    </div>
  );
}

// === Messaggio errore ===

export function MessaggioErrore({
  testo,
  azioneRipristino,
}: {
  testo: string;
  azioneRipristino?: { etichetta: string; onClick: () => void };
}) {
  return (
    <div
      role="alert"
      className="border border-scarlatto/40 bg-scarlatto/5 p-4 my-4 flex items-start justify-between gap-4"
    >
      <div>
        <div className="etichetta-rossa mb-1">Errore</div>
        <div className="text-sm text-inchiostro">{testo}</div>
      </div>
      {azioneRipristino ? (
        <button
          type="button"
          className="btn-secondario"
          onClick={azioneRipristino.onClick}
        >
          {azioneRipristino.etichetta}
        </button>
      ) : null}
    </div>
  );
}

// === Vuoto ===

export function StatoVuoto({
  titolo,
  descrizione,
  azione,
}: {
  titolo: string;
  descrizione?: string;
  azione?: { etichetta: string; href?: string; onClick?: () => void };
}) {
  return (
    <div className="text-center py-16 px-8 border border-dashed border-inchiostro/20">
      <h3 className="font-display text-xl mb-2">{titolo}</h3>
      {descrizione ? (
        <p className="text-sm text-inchiostro-tenue max-w-md mx-auto mb-6">
          {descrizione}
        </p>
      ) : null}
      {azione ? (
        azione.href ? (
          <a href={azione.href} className="btn-primario">
            {azione.etichetta}
          </a>
        ) : (
          <button
            type="button"
            onClick={azione.onClick}
            className="btn-primario"
          >
            {azione.etichetta}
          </button>
        )
      ) : null}
    </div>
  );
}
