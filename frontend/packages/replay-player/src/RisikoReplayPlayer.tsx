/**
 * RisikoReplayPlayer — viewer replay completo "out of the box".
 *
 * Combina `@risiko/replay-lib` + `@risiko/map-classico` per un componente
 * autoportante: dato un `BundleReplay`, mostra mappa + scrubber + narrative
 * + autoplay.
 *
 * API hooks pensati per integrazioni successive (sync video, panel laterali):
 *   - onCursorChange(ts_evento, idx, evento): chiamato ad ogni cambio indice
 *   - onStatoCambia(stato): chiamato ad ogni cambio stato derivato
 *   - onTerritorioClick(nome): per filtri eventi
 *   - controllerRef: riferimento imperativo allo state (vai/play/pausa) per
 *     controllo esterno (es. il video drives il replay)
 */

import { forwardRef, useEffect, useMemo, useRef } from "react";

import { useReplay, type ReplayController } from "@risiko/replay-lib/react";
import type {
  BundleReplay,
  EventoValidato,
  GiocatorePartita,
} from "@risiko/eventi-schema";
import type { StatoPartita } from "@risiko/replay-lib";
import {
  MappaRisikoClassico,
  type InfoTerritorio,
} from "@risiko/map-classico";

import { narrativeEvento } from "./narrative.js";

// === Props ==================================================================

export interface PropsRisikoReplayPlayer {
  /** Bundle validato dallo schema. Cambia bundle = reset del player. */
  bundle: BundleReplay;

  /**
   * Chiamato ogni volta che l'indice della timeline cambia.
   *
   * - `ts_evento` è la stringa ISO 8601 dell'evento corrente, o `null` se
   *   `idx === -1` (pre-eventi).
   * - `idx` è l'indice corrente nella timeline (-1..lunghezza-1).
   * - `evento` è il riferimento all'evento corrente (null se idx === -1).
   *
   * Usato dal consumer per sincronizzare elementi esterni (es. video player
   * via offset rispetto a `bundle.partita.data_inizio`).
   */
  onCursorChange?: (
    ts_evento: string | null,
    idx: number,
    evento: EventoValidato | null,
  ) => void;

  /**
   * Chiamato ogni volta che lo stato derivato cambia. Utile per pannelli
   * laterali che mostrano statistiche, classifica, mano carte ecc.
   */
  onStatoCambia?: (stato: StatoPartita) => void;

  /** Click su territorio nella mappa (es. per filtri eventi). */
  onTerritorioClick?: (nome: string) => void;

  /**
   * Indice di partenza. Default -1 (stato iniziale, pre-eventi).
   */
  idxIniziale?: number;

  /** Velocità autoplay in ms. Default 1500. */
  velocitaInizialeMs?: number;

  /** Mostra il pannello narrative. Default true. */
  mostraNarrative?: boolean;

  /** Mostra la legenda della mappa. Default true. */
  mostraLegenda?: boolean;

  /** Mostra l'header con metadati partita. Default true. */
  mostraHeader?: boolean;

  /** Slug territorio da evidenziare con alone scarlatto. */
  territorioSelezionato?: string | null;
}

/**
 * Riferimento imperativo per il controllo esterno del player.
 *
 * Esposto via `forwardRef` — il consumer (es. RL frontend) può chiamare
 * `vai`, `play`, `pausa` ecc. dall'esterno per sincronizzare il replay con
 * il video.
 */
export type RiferimentoRisikoReplayPlayer = Pick<
  ReplayController,
  | "vai"
  | "avanti"
  | "indietro"
  | "vaiInizio"
  | "vaiFine"
  | "play"
  | "pausa"
  | "togglePlay"
  | "setVelocitaMs"
>;

// === Componente =============================================================

export const RisikoReplayPlayer = forwardRef<
  RiferimentoRisikoReplayPlayer,
  PropsRisikoReplayPlayer
>(function RisikoReplayPlayer(
  {
    bundle,
    onCursorChange,
    onStatoCambia,
    onTerritorioClick,
    idxIniziale,
    velocitaInizialeMs,
    mostraNarrative = true,
    mostraLegenda = true,
    mostraHeader = true,
    territorioSelezionato,
  },
  ref,
) {
  const controller = useReplay(bundle, {
    idxIniziale,
    velocitaInizialeMs,
  });

  // Espone i metodi imperativi per il consumer
  useEffect(() => {
    if (!ref) return;
    const api: RiferimentoRisikoReplayPlayer = {
      vai: controller.vai,
      avanti: controller.avanti,
      indietro: controller.indietro,
      vaiInizio: controller.vaiInizio,
      vaiFine: controller.vaiFine,
      play: controller.play,
      pausa: controller.pausa,
      togglePlay: controller.togglePlay,
      setVelocitaMs: controller.setVelocitaMs,
    };
    if (typeof ref === "function") {
      ref(api);
    } else {
      ref.current = api;
    }
  }, [
    ref,
    controller.vai,
    controller.avanti,
    controller.indietro,
    controller.vaiInizio,
    controller.vaiFine,
    controller.play,
    controller.pausa,
    controller.togglePlay,
    controller.setVelocitaMs,
  ]);

  // Notifica callback al consumer
  const ultimoIdxNotificato = useRef<number>(Number.NaN);
  useEffect(() => {
    if (controller.idx === ultimoIdxNotificato.current) return;
    ultimoIdxNotificato.current = controller.idx;
    onCursorChange?.(
      controller.eventoCorrente?.ts_evento ?? null,
      controller.idx,
      controller.eventoCorrente,
    );
  }, [controller.idx, controller.eventoCorrente, onCursorChange]);

  useEffect(() => {
    onStatoCambia?.(controller.stato);
  }, [controller.stato, onStatoCambia]);

  // Adatta StatoPartita (replay-lib) → InfoTerritorio (map-classico)
  const territoriPerMappa = useMemo(
    () => statoAInfoTerritorio(controller.stato),
    [controller.stato],
  );
  const giocatoriPerMappa = useMemo(
    () => statoAGiocatoriPartita(controller.stato),
    [controller.stato],
  );

  // Slider position: -1 → 0 nello slider per non avere tick negativi
  const valoreSlider = controller.idx + 1;
  const massimoSlider = controller.lunghezza;

  return (
    <div style={stiliContenitore}>
      {mostraHeader ? (
        <HeaderPartita bundle={bundle} stato={controller.stato} />
      ) : null}

      <div style={stiliMappa}>
        <MappaRisikoClassico
          territori={territoriPerMappa}
          giocatori={giocatoriPerMappa}
          territorioSelezionato={territorioSelezionato ?? null}
          onClickTerritorio={onTerritorioClick}
          mostraLegenda={mostraLegenda}
        />
      </div>

      {mostraNarrative ? (
        <Narrative
          evento={controller.eventoCorrente}
          stato={controller.stato}
        />
      ) : null}

      <div style={stiliControlli}>
        <input
          type="range"
          min={0}
          max={massimoSlider}
          value={valoreSlider}
          onChange={(e) => {
            controller.pausa();
            controller.vai(parseInt(e.target.value, 10) - 1);
          }}
          style={stiliSlider}
          aria-label="Posizione nel replay"
        />

        <div style={stiliPulsantiera}>
          <button
            onClick={controller.vaiInizio}
            disabled={!controller.puoIndietro}
            style={stiliPulsante(!controller.puoIndietro)}
            aria-label="Vai all'inizio"
          >
            ⏮
          </button>
          <button
            onClick={controller.indietro}
            disabled={!controller.puoIndietro}
            style={stiliPulsante(!controller.puoIndietro)}
            aria-label="Indietro"
          >
            ◀
          </button>
          <button
            onClick={controller.togglePlay}
            disabled={!controller.puoAvanti && !controller.inPlay}
            style={{
              ...stiliPulsante(!controller.puoAvanti && !controller.inPlay),
              flex: 1,
              fontWeight: "bold",
              backgroundColor: controller.inPlay
                ? "rgba(184,51,42,0.12)"
                : "transparent",
            }}
            aria-label={controller.inPlay ? "Pausa" : "Play"}
          >
            {controller.inPlay ? "⏸ PAUSA" : "▶ PLAY"}
          </button>
          <button
            onClick={controller.avanti}
            disabled={!controller.puoAvanti}
            style={stiliPulsante(!controller.puoAvanti)}
            aria-label="Avanti"
          >
            ▶
          </button>
          <button
            onClick={controller.vaiFine}
            disabled={!controller.puoAvanti}
            style={stiliPulsante(!controller.puoAvanti)}
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
              onClick={() => controller.setVelocitaMs(v.ms)}
              style={stiliPulsanteVelocita(controller.velocitaMs === v.ms)}
            >
              {v.label}
            </button>
          ))}
        </div>

        <div style={stiliPosizione}>
          {controller.idx + 1} / {controller.lunghezza}
        </div>
      </div>
    </div>
  );
});

// === Sub-componenti =========================================================

function HeaderPartita({
  bundle,
  stato,
}: {
  bundle: BundleReplay;
  stato: StatoPartita;
}): JSX.Element {
  const dataIso = bundle.partita.data_inizio;
  const data = new Date(dataIso);
  const dataFormattata = data.toLocaleDateString("it-IT", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const vincitore = stato.vincitore_id
    ? stato.giocatori.get(stato.vincitore_id)
    : null;

  return (
    <div style={stiliHeader}>
      <div style={stiliHeaderTitolo}>
        <span style={stiliHeaderData}>{dataFormattata}</span>
        {bundle.partita.luogo ? (
          <span style={stiliHeaderLuogo}> · {bundle.partita.luogo}</span>
        ) : null}
      </div>
      <div style={stiliHeaderFase}>
        {stato.fase === "setup" ? "Pre-partita" : null}
        {stato.fase === "in_corso" && stato.giocatore_di_turno ? (
          <>
            Turno di{" "}
            <strong>
              {stato.giocatori.get(stato.giocatore_di_turno)?.nome ??
                stato.giocatore_di_turno}
            </strong>
          </>
        ) : null}
        {stato.fase === "finita" && vincitore ? (
          <>
            Vincitore: <strong>{vincitore.nome}</strong>
          </>
        ) : null}
      </div>
    </div>
  );
}

function Narrative({
  evento,
  stato,
}: {
  evento: EventoValidato | null;
  stato: StatoPartita;
}): JSX.Element {
  const testo = evento ? narrativeEvento(evento, stato) : "Inizio del replay";
  return (
    <div style={stiliNarrative}>
      <div style={stiliNarrativeBadge}>
        {evento ? evento.tipo.replace(/_/g, " ") : "stato iniziale"}
      </div>
      <div style={stiliNarrativeTesto}>{testo}</div>
    </div>
  );
}

// === Helper di adattamento ==================================================

/**
 * Converte StatoPartita (replay-lib) in Record<territorio, InfoTerritorio>
 * (map-classico). I due tipi hanno naming diverso:
 *   - replay-lib: `proprietario_id` / `n_armate`
 *   - map-classico: `controllore_id` / `armate`
 */
function statoAInfoTerritorio(
  stato: StatoPartita,
): Record<string, InfoTerritorio> {
  const out: Record<string, InfoTerritorio> = {};
  for (const [nome, t] of stato.territori) {
    out[nome] = {
      controllore_id: t.proprietario_id,
      armate: t.n_armate,
    };
  }
  return out;
}

/**
 * Converte la Map dei giocatori dello stato in array di GiocatorePartita
 * compatibile con la map-classico.
 */
function statoAGiocatoriPartita(
  stato: StatoPartita,
): ReadonlyArray<GiocatorePartita> {
  const out: GiocatorePartita[] = [];
  for (const g of stato.giocatori.values()) {
    out.push({
      id: g.id,
      nome: g.nome,
      colore: g.colore,
      ordine_seduta: g.ordine_seduta,
    });
  }
  out.sort((a, b) => a.ordine_seduta - b.ordine_seduta);
  return out;
}

// === Preset velocità ========================================================

const VELOCITA_PRESET = [
  { ms: 2500, label: "0.5×" },
  { ms: 1500, label: "1×" },
  { ms: 800, label: "2×" },
  { ms: 400, label: "4×" },
];

// === Stili (inline, no Tailwind) ============================================

const COLORE_PERGAMENA = "#f4ede0";
const COLORE_INCHIOSTRO = "#1a1614";
const COLORE_INCHIOSTRO_TENUE = "#5c5147";
const COLORE_SCARLATTO = "#b8332a";

const stiliContenitore: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  backgroundColor: COLORE_PERGAMENA,
  border: `1px solid rgba(26,22,20,0.15)`,
  fontFamily: "'Inter Tight', sans-serif",
};

const stiliHeader: React.CSSProperties = {
  padding: "12px 18px",
  borderBottom: `1px solid rgba(26,22,20,0.10)`,
  display: "flex",
  justifyContent: "space-between",
  alignItems: "baseline",
  flexWrap: "wrap",
  gap: 12,
};
const stiliHeaderTitolo: React.CSSProperties = {
  fontFamily: "'Fraunces', Georgia, serif",
  fontSize: 16,
  color: COLORE_INCHIOSTRO,
};
const stiliHeaderData: React.CSSProperties = {
  fontWeight: 600,
};
const stiliHeaderLuogo: React.CSSProperties = {
  color: COLORE_INCHIOSTRO_TENUE,
  fontWeight: 400,
};
const stiliHeaderFase: React.CSSProperties = {
  fontSize: 12,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: COLORE_INCHIOSTRO_TENUE,
};

const stiliMappa: React.CSSProperties = {
  flex: 1,
  position: "relative",
  minHeight: 240,
};

const stiliNarrative: React.CSSProperties = {
  padding: "10px 18px",
  borderTop: `1px solid rgba(26,22,20,0.10)`,
  display: "flex",
  alignItems: "center",
  gap: 12,
  fontSize: 13,
  color: COLORE_INCHIOSTRO,
  minHeight: 42,
};
const stiliNarrativeBadge: React.CSSProperties = {
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: 9,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  padding: "3px 8px",
  backgroundColor: "rgba(26,22,20,0.08)",
  color: COLORE_INCHIOSTRO_TENUE,
  borderRadius: 2,
  flexShrink: 0,
};
const stiliNarrativeTesto: React.CSSProperties = {
  fontFamily: "'Fraunces', Georgia, serif",
};

const stiliControlli: React.CSSProperties = {
  padding: "12px 18px",
  borderTop: `1px solid rgba(26,22,20,0.10)`,
  display: "flex",
  flexDirection: "column",
  gap: 8,
};
const stiliSlider: React.CSSProperties = {
  width: "100%",
  cursor: "pointer",
  accentColor: COLORE_SCARLATTO,
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
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: 9,
  marginRight: 6,
  letterSpacing: ".1em",
  color: COLORE_INCHIOSTRO_TENUE,
};
const stiliPosizione: React.CSSProperties = {
  fontFamily: "'JetBrains Mono', monospace",
  fontSize: 11,
  fontVariantNumeric: "tabular-nums",
  textAlign: "center",
  color: COLORE_INCHIOSTRO_TENUE,
};

const stiliPulsante = (disabled: boolean): React.CSSProperties => ({
  padding: "8px 12px",
  fontSize: 14,
  background: "transparent",
  border: `1px solid rgba(26,22,20,0.18)`,
  color: disabled ? "rgba(26,22,20,0.3)" : COLORE_INCHIOSTRO,
  borderRadius: 3,
  cursor: disabled ? "default" : "pointer",
  fontFamily: "'JetBrains Mono', monospace",
});
const stiliPulsanteVelocita = (selezionato: boolean): React.CSSProperties => ({
  padding: "3px 8px",
  fontSize: 9,
  background: selezionato ? "rgba(184,51,42,0.15)" : "transparent",
  border: `1px solid ${selezionato ? COLORE_SCARLATTO : "rgba(26,22,20,0.18)"}`,
  color: selezionato ? COLORE_SCARLATTO : COLORE_INCHIOSTRO_TENUE,
  borderRadius: 2,
  cursor: "pointer",
  fontFamily: "'JetBrains Mono', monospace",
  letterSpacing: ".05em",
  fontWeight: selezionato ? 700 : 400,
});
