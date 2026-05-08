/**
 * PlayerReplay — componente React di CONTROLLI replay (scrubber, play/pause,
 * step, velocità). NON disegna la mappa: il consumer (Battle Commander o
 * Risiko Live) la fornisce via render-prop `renderMappa`.
 *
 * Filosofia: lo strato "controlli" è generico. Lo strato "display dello stato"
 * è specifico di ogni app (mappa SVG di BC vs SVG di RL). Tenerli separati
 * permette ai due frontend di consumare la stessa libreria senza forzare uno
 * stile o una mappa comune.
 */

import { useReplay, type OpzioniUseReplay } from "./hooks.js";
import type { StatoPartita } from "../stato.js";
import type { BundleReplay, EventoValidato } from "@risiko/eventi-schema";

export interface PropsPlayerReplay {
  bundle: BundleReplay;
  /** Render della mappa per uno stato dato. Specifico dell'app. */
  renderMappa: (stato: StatoPartita) => JSX.Element;
  /** Render opzionale del narrative dell'evento corrente. */
  renderNarrative?: (evento: EventoValidato | null, stato: StatoPartita) => JSX.Element;
  /** Render opzionale dell'header (es. data partita, vincitore). */
  renderHeader?: (stato: StatoPartita, bundle: BundleReplay) => JSX.Element;
  /** Opzioni passate al hook useReplay. */
  opzioni?: OpzioniUseReplay;
}

/**
 * Componente di controllo replay. Render-prop based: il consumer rende la
 * mappa nel suo proprio stile (BC con foto fisica + SVG, RL con il proprio
 * SVG, etc.).
 */
export function PlayerReplay({
  bundle,
  renderMappa,
  renderNarrative,
  renderHeader,
  opzioni,
}: PropsPlayerReplay): JSX.Element {
  const r = useReplay(bundle, opzioni);

  // Indici slider: -1 → 0 nello slider per non avere tick negativi nella UI.
  const valoreSlider = r.idx + 1;
  const massimoSlider = r.lunghezza; // 0..lunghezza, 0 = pre-eventi

  return (
    <div style={stiliContenitore}>
      {renderHeader && (
        <div style={stiliHeader}>{renderHeader(r.stato, bundle)}</div>
      )}

      <div style={stiliMappa}>{renderMappa(r.stato)}</div>

      {renderNarrative && (
        <div style={stiliNarrative}>
          {renderNarrative(r.eventoCorrente, r.stato)}
        </div>
      )}

      <div style={stiliControlli}>
        <input
          type="range"
          min={0}
          max={massimoSlider}
          value={valoreSlider}
          onChange={(e) => {
            r.pausa();
            r.vai(parseInt(e.target.value, 10) - 1);
          }}
          style={stiliSlider}
          aria-label="Posizione nel replay"
        />

        <div style={stiliPulsantiera}>
          <button
            onClick={r.vaiInizio}
            disabled={!r.puoIndietro}
            style={stiliPulsante(!r.puoIndietro)}
            aria-label="Vai all'inizio"
          >
            ⏮
          </button>
          <button
            onClick={r.indietro}
            disabled={!r.puoIndietro}
            style={stiliPulsante(!r.puoIndietro)}
            aria-label="Indietro di 1 evento"
          >
            ◀
          </button>
          <button
            onClick={r.togglePlay}
            disabled={!r.puoAvanti && !r.inPlay}
            style={{
              ...stiliPulsante(!r.puoAvanti && !r.inPlay),
              flex: 1,
              fontWeight: "bold",
              background: r.inPlay
                ? "rgba(201,168,76,0.15)"
                : "transparent",
            }}
            aria-label={r.inPlay ? "Pausa" : "Play"}
          >
            {r.inPlay ? "⏸ PAUSA" : "▶ PLAY"}
          </button>
          <button
            onClick={r.avanti}
            disabled={!r.puoAvanti}
            style={stiliPulsante(!r.puoAvanti)}
            aria-label="Avanti di 1 evento"
          >
            ▶
          </button>
          <button
            onClick={r.vaiFine}
            disabled={!r.puoAvanti}
            style={stiliPulsante(!r.puoAvanti)}
            aria-label="Vai alla fine"
          >
            ⏭
          </button>
        </div>

        <div style={stiliVelocita}>
          <span style={stiliVelocitaLabel}>VELOCITÀ</span>
          {VELOCITA_PRESET.map((v) => (
            <button
              key={v.ms}
              onClick={() => r.setVelocitaMs(v.ms)}
              style={stiliPulsanteVelocita(r.velocitaMs === v.ms)}
            >
              {v.label}
            </button>
          ))}
        </div>

        <div style={stiliPosizione}>
          {r.idx + 1} / {r.lunghezza}
        </div>
      </div>
    </div>
  );
}

// === Preset velocità =======================================================

const VELOCITA_PRESET = [
  { ms: 2500, label: "0.5×" },
  { ms: 1500, label: "1×" },
  { ms: 800, label: "2×" },
  { ms: 400, label: "4×" },
];

// === Stili ==================================================================
// Inline styles deliberatamente minimi: il consumer può sovrascriverli tutti
// passando un wrapper esterno con CSS proprio. Evitiamo dipendenze CSS qui
// per non vincolare BC e RL a una libreria di stili comune.

const stiliContenitore: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  height: "100%",
};
const stiliHeader: React.CSSProperties = {
  padding: "10px 14px",
  borderBottom: "1px solid rgba(255,255,255,0.08)",
};
const stiliMappa: React.CSSProperties = {
  flex: 1,
  position: "relative",
  minHeight: 200,
};
const stiliNarrative: React.CSSProperties = {
  maxHeight: 140,
  overflowY: "auto",
  padding: "10px 14px",
  borderTop: "1px solid rgba(255,255,255,0.08)",
  fontSize: 12,
};
const stiliControlli: React.CSSProperties = {
  padding: "12px 14px",
  borderTop: "1px solid rgba(255,255,255,0.08)",
  display: "flex",
  flexDirection: "column",
  gap: 8,
};
const stiliSlider: React.CSSProperties = {
  width: "100%",
  cursor: "pointer",
};
const stiliPulsantiera: React.CSSProperties = {
  display: "flex",
  gap: 6,
  alignItems: "center",
  justifyContent: "space-between",
};
const stiliVelocita: React.CSSProperties = {
  display: "flex",
  gap: 4,
  alignItems: "center",
  justifyContent: "center",
};
const stiliVelocitaLabel: React.CSSProperties = {
  fontSize: 9,
  marginRight: 6,
  letterSpacing: ".1em",
  opacity: 0.6,
};
const stiliPosizione: React.CSSProperties = {
  fontSize: 11,
  fontFamily: "monospace",
  textAlign: "center",
  opacity: 0.7,
};

const stiliPulsante = (disabled: boolean): React.CSSProperties => ({
  padding: "8px 12px",
  fontSize: 14,
  background: "transparent",
  border: "1px solid rgba(255,255,255,0.15)",
  color: disabled ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.7)",
  borderRadius: 4,
  cursor: disabled ? "default" : "pointer",
  opacity: disabled ? 0.4 : 1,
  fontFamily: "monospace",
});
const stiliPulsanteVelocita = (selezionato: boolean): React.CSSProperties => ({
  padding: "3px 8px",
  fontSize: 9,
  background: selezionato ? "rgba(201,168,76,0.25)" : "transparent",
  border: `1px solid ${
    selezionato ? "rgba(201,168,76,1)" : "rgba(255,255,255,0.15)"
  }`,
  color: selezionato ? "rgba(201,168,76,1)" : "rgba(255,255,255,0.6)",
  borderRadius: 3,
  cursor: "pointer",
  fontFamily: "monospace",
  letterSpacing: ".05em",
});
