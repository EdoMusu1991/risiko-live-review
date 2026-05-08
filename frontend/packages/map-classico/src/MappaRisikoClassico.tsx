/**
 * MappaRisikoClassico — plancia visuale dello stato della partita.
 *
 * Renderizza una mappa SVG schematica con:
 * - I 6 continenti come riquadri colorati di sfondo (con nome + bonus)
 * - Le 65+ adiacenze come linee sottili
 * - I 42 territori come dischi colorati per controllore con il numero
 *   armate al centro
 * - Etichette territoriali in piccolo sotto ogni disco
 * - Indicatori di "continente conquistato" che evidenziano i bonus attivi
 *
 * Estratto da `PlanciaMappa` di Risiko Live Review v0.1, promosso a libreria
 * condivisa fra Risiko Live e Battle Commander. Lo stile è coerente con la
 * cartografia editoriale: pergamena come base, inchiostro per i contorni,
 * accenti scarlatto, niente colori sgargianti.
 *
 * Lo stile è inline (no Tailwind, no CSS esterni): il componente è
 * autoportante e funziona in qualsiasi consumer.
 */

import { useMemo, useState } from "react";

import {
  ADIACENZE,
  CONTINENTI,
  CONTINENTE_DI,
  POSIZIONI,
} from "./layout.js";
import type { GiocatorePartita, InfoTerritorio } from "./tipi.js";
import type { ColoreGiocatore } from "@risiko/eventi-schema";

// === Palette ================================================================

/** Mappa colore giocatore → fill SVG. Coerente con i nomi enum dello schema. */
const FILL_COLORE: Record<ColoreGiocatore, string> = {
  rosso: "#b8332a",
  blu: "#1f3552",
  verde: "#2c4a36",
  giallo: "#c8902b",
  nero: "#1a1614",
  viola: "#5e2d56",
};

/** Sfondo continente: tinta tenue, "geografica" più che politica. */
const SFONDO_CONTINENTE: Record<string, string> = {
  nord_america: "#e8d8b8",
  sud_america: "#dcc89c",
  europa: "#e0d2c0",
  asia: "#e6cfa8",
  africa: "#d8c290",
  oceania: "#dab690",
};

const COLORE_PERGAMENA = "#f4ede0";
const COLORE_INCHIOSTRO = "#1a1614";
const COLORE_INCHIOSTRO_TENUE = "#5c5147";
const COLORE_SCARLATTO = "#b8332a";

// === Props ==================================================================

export interface PropsMappaRisikoClassico {
  /** Mappa territorio → InfoTerritorio (controllore + armate). */
  territori: Record<string, InfoTerritorio>;
  /** Lista giocatori della partita (per resolution colore via id). */
  giocatori: ReadonlyArray<GiocatorePartita>;
  /** Slug del territorio attualmente filtrato/selezionato (alone scarlatto). */
  territorioSelezionato?: string | null;
  /** Callback opzionale per click su territorio. */
  onClickTerritorio?: (nome: string) => void;
  /** Mostra la legenda giocatori sotto la mappa. Default true. */
  mostraLegenda?: boolean;
}

// === Componente principale ==================================================

export function MappaRisikoClassico({
  territori,
  giocatori,
  territorioSelezionato,
  onClickTerritorio,
  mostraLegenda = true,
}: PropsMappaRisikoClassico): JSX.Element {
  const [territorioHover, setTerritorioHover] = useState<string | null>(null);

  // Indice giocatori per id, per il colore del territorio
  const giocatorePerId = useMemo(() => {
    const m = new Map<string, GiocatorePartita>();
    for (const g of giocatori) m.set(g.id, g);
    return m;
  }, [giocatori]);

  // Stato di controllo dei continenti (per evidenziare bonus attivi)
  const continenteControllato = useMemo(() => {
    const m = new Map<string, string | null>();
    for (const c of CONTINENTI) {
      const controllori = new Set(
        c.territori
          .map((t) => territori[t]?.controllore_id ?? null)
          .filter((id): id is string => id !== null),
      );
      m.set(
        c.slug,
        controllori.size === 1 && c.territori.every((t) => territori[t])
          ? [...controllori][0]!
          : null,
      );
    }
    return m;
  }, [territori]);

  return (
    <div
      style={{
        backgroundColor: COLORE_PERGAMENA,
        border: `1px solid rgba(26,22,20,0.15)`,
        overflow: "hidden",
      }}
    >
      <svg
        viewBox="0 0 1000 680"
        style={{
          width: "100%",
          height: "auto",
          display: "block",
          aspectRatio: "1000 / 680",
        }}
      >
        <defs>
          <pattern
            id="grain-mappa"
            x="0"
            y="0"
            width="120"
            height="120"
            patternUnits="userSpaceOnUse"
          >
            <filter id="filtro-grain">
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.85"
                numOctaves="2"
                stitchTiles="stitch"
              />
              <feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.05 0" />
            </filter>
            <rect width="120" height="120" filter="url(#filtro-grain)" />
          </pattern>
          <filter id="ombra-disco" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow
              dx="0"
              dy="1"
              stdDeviation="1"
              floodColor={COLORE_INCHIOSTRO}
              floodOpacity="0.25"
            />
          </filter>
        </defs>

        {/* Sfondo pergamena con grain */}
        <rect width="1000" height="680" fill={COLORE_PERGAMENA} />
        <rect width="1000" height="680" fill="url(#grain-mappa)" />

        {/* Riquadri continenti */}
        {CONTINENTI.map((c) => {
          const controllore = continenteControllato.get(c.slug);
          const controlloreGiocatore = controllore
            ? giocatorePerId.get(controllore)
            : null;
          const sfondoBase = SFONDO_CONTINENTE[c.slug] ?? "#e8d8b8";
          return (
            <g key={c.slug}>
              <rect
                x={c.riquadro.x}
                y={c.riquadro.y}
                width={c.riquadro.larghezza}
                height={c.riquadro.altezza}
                fill={sfondoBase}
                stroke="rgba(26,22,20,0.18)"
                strokeWidth="1"
                rx="4"
              />
              {controlloreGiocatore ? (
                <rect
                  x={c.riquadro.x}
                  y={c.riquadro.y}
                  width={c.riquadro.larghezza}
                  height={c.riquadro.altezza}
                  fill="none"
                  stroke={FILL_COLORE[controlloreGiocatore.colore]}
                  strokeWidth="2.5"
                  strokeDasharray="6 3"
                  rx="4"
                />
              ) : null}
              <text
                x={c.etichetta.x}
                y={c.etichetta.y}
                fontFamily="'Fraunces', Georgia, serif"
                fontSize="14"
                fontWeight="600"
                fill={COLORE_INCHIOSTRO_TENUE}
                style={{ letterSpacing: "0.18em", textTransform: "uppercase" }}
              >
                {c.nome}
              </text>
              <text
                x={c.etichetta.x}
                y={c.etichetta.y + 16}
                fontFamily="'JetBrains Mono', monospace"
                fontSize="10"
                fill={controlloreGiocatore ? COLORE_SCARLATTO : "#8a7d70"}
                fontWeight={controlloreGiocatore ? 700 : 400}
              >
                +{c.bonus} bonus{controlloreGiocatore ? " ✓" : ""}
              </text>
            </g>
          );
        })}

        {/* Adiacenze (sotto i territori) */}
        <g opacity="0.32">
          {ADIACENZE.map(([a, b]) => {
            const pa = POSIZIONI[a];
            const pb = POSIZIONI[b];
            if (!pa || !pb) return null;
            const distanza = Math.hypot(pa.x - pb.x, pa.y - pb.y);
            const intercont = CONTINENTE_DI[a] !== CONTINENTE_DI[b];
            return (
              <line
                key={`${a}-${b}`}
                x1={pa.x}
                y1={pa.y}
                x2={pb.x}
                y2={pb.y}
                stroke={COLORE_INCHIOSTRO}
                strokeWidth={intercont ? 0.6 : 0.8}
                strokeDasharray={
                  intercont || distanza > 200 ? "3 3" : undefined
                }
              />
            );
          })}
        </g>

        {/* Territori */}
        {Object.entries(POSIZIONI).map(([nome, pos]) => {
          const info = territori[nome];
          const controllore = info?.controllore_id
            ? giocatorePerId.get(info.controllore_id)
            : null;
          const armate = info?.armate ?? 0;
          const isHover = territorioHover === nome;
          const isSelezionato = territorioSelezionato === nome;

          const fill = controllore ? FILL_COLORE[controllore.colore] : "#d4c8b6";
          const tonoTesto =
            controllore && controllore.colore !== "giallo"
              ? COLORE_PERGAMENA
              : COLORE_INCHIOSTRO;

          return (
            <g
              key={nome}
              onMouseEnter={() => setTerritorioHover(nome)}
              onMouseLeave={() => setTerritorioHover(null)}
              onClick={() => onClickTerritorio?.(nome)}
              style={{ cursor: onClickTerritorio ? "pointer" : "default" }}
            >
              {isSelezionato ? (
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={28}
                  fill="none"
                  stroke={COLORE_SCARLATTO}
                  strokeWidth="2.5"
                  strokeDasharray="4 2"
                >
                  <animate
                    attributeName="r"
                    values="28;32;28"
                    dur="1.6s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0.9;0.4;0.9"
                    dur="1.6s"
                    repeatCount="indefinite"
                  />
                </circle>
              ) : null}
              <circle
                cx={pos.x}
                cy={pos.y}
                r={isHover || isSelezionato ? 22 : 18}
                fill={fill}
                stroke={isSelezionato ? COLORE_SCARLATTO : COLORE_INCHIOSTRO}
                strokeWidth={isHover || isSelezionato ? 2 : 1.2}
                filter="url(#ombra-disco)"
                style={{ transition: "r 120ms ease, stroke-width 120ms ease" }}
              />
              <text
                x={pos.x}
                y={pos.y + 5}
                fontFamily="'JetBrains Mono', monospace"
                fontSize={armate >= 100 ? 12 : 14}
                fontWeight="700"
                fill={tonoTesto}
                textAnchor="middle"
                pointerEvents="none"
                style={{ fontVariantNumeric: "tabular-nums" }}
              >
                {armate || "·"}
              </text>
              <text
                x={pos.x}
                y={pos.y + 33}
                fontFamily="'Inter Tight', sans-serif"
                fontSize="9"
                fontWeight={isHover || isSelezionato ? 700 : 500}
                fill={COLORE_INCHIOSTRO}
                textAnchor="middle"
                pointerEvents="none"
                style={{ letterSpacing: "0.02em" }}
              >
                {abbreviaTerritorio(nome)}
              </text>
            </g>
          );
        })}

        {territorioHover ? (
          <DettaglioTooltip
            nome={territorioHover}
            info={territori[territorioHover]}
            giocatorePerId={giocatorePerId}
          />
        ) : null}
      </svg>

      {mostraLegenda ? (
        <div
          style={{
            borderTop: `1px solid rgba(26,22,20,0.10)`,
            padding: "10px 16px",
            display: "flex",
            flexWrap: "wrap",
            gap: "8px 20px",
            alignItems: "center",
            fontFamily: "'Inter Tight', sans-serif",
          }}
        >
          <span
            style={{
              fontSize: 9,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: COLORE_INCHIOSTRO_TENUE,
              fontWeight: 600,
            }}
          >
            Legenda
          </span>
          {giocatori.map((g) => {
            const conteggio = Object.values(territori).filter(
              (t) => t.controllore_id === g.id,
            ).length;
            const armateTotali = Object.values(territori)
              .filter((t) => t.controllore_id === g.id)
              .reduce((s, t) => s + t.armate, 0);
            return (
              <div
                key={g.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 14,
                }}
              >
                <span
                  style={{
                    display: "inline-block",
                    width: 12,
                    height: 12,
                    borderRadius: "50%",
                    border: "1px solid rgba(26,22,20,0.4)",
                    backgroundColor: FILL_COLORE[g.colore],
                  }}
                />
                <span
                  style={{
                    fontFamily: "'Fraunces', Georgia, serif",
                    fontWeight: 600,
                    color: COLORE_INCHIOSTRO,
                  }}
                >
                  {g.nome}
                </span>
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 11,
                    fontVariantNumeric: "tabular-nums",
                    color: COLORE_INCHIOSTRO_TENUE,
                  }}
                >
                  {conteggio} terr · {armateTotali} arm
                </span>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

// === Sub-componenti =========================================================

function DettaglioTooltip({
  nome,
  info,
  giocatorePerId,
}: {
  nome: string;
  info: InfoTerritorio | undefined;
  giocatorePerId: Map<string, GiocatorePartita>;
}): JSX.Element {
  const controllore = info?.controllore_id
    ? giocatorePerId.get(info.controllore_id)
    : null;
  return (
    <g pointerEvents="none">
      <rect x="730" y="20" width="250" height="70" fill={COLORE_INCHIOSTRO} rx="2" />
      <text
        x="745"
        y="42"
        fontFamily="'Fraunces', Georgia, serif"
        fontSize="16"
        fontWeight="700"
        fill={COLORE_PERGAMENA}
        style={{ textTransform: "capitalize" }}
      >
        {nome.replace(/_/g, " ")}
      </text>
      <text
        x="745"
        y="62"
        fontFamily="'Inter Tight', sans-serif"
        fontSize="11"
        fill={COLORE_PERGAMENA}
        opacity="0.75"
      >
        {controllore
          ? `${controllore.nome} · ${info!.armate} ${info!.armate === 1 ? "armata" : "armate"}`
          : "Senza controllore"}
      </text>
      <text
        x="745"
        y="80"
        fontFamily="'JetBrains Mono', monospace"
        fontSize="9"
        fill={COLORE_PERGAMENA}
        opacity="0.5"
        style={{ letterSpacing: "0.1em", textTransform: "uppercase" }}
      >
        Continente: {(CONTINENTE_DI[nome] ?? "—").replace("_", " ")}
      </text>
    </g>
  );
}

// === Helper =================================================================

/**
 * Abbrevia il nome del territorio per stare sotto al disco.
 * Pattern: prima parola completa, seconda abbreviata se serve.
 */
function abbreviaTerritorio(slug: string): string {
  const parole = slug.split("_");
  if (parole.length === 1) {
    return parole[0]!.length > 12
      ? parole[0]!.slice(0, 11) + "."
      : parole[0]!;
  }
  if (slug === "africa_settentrionale") return "afr. sett.";
  if (slug === "africa_meridionale") return "afr. merid.";
  if (slug === "africa_orientale") return "afr. orient.";
  if (slug === "asia_sudorientale") return "asia s.e.";
  if (slug === "australia_occidentale") return "austr. occ.";
  if (slug === "australia_orientale") return "austr. orient.";
  if (slug === "europa_settentrionale") return "eur. sett.";
  if (slug === "europa_occidentale") return "eur. occ.";
  if (slug === "europa_meridionale") return "eur. merid.";
  if (slug === "stati_occidentali") return "USA occ.";
  if (slug === "stati_orientali") return "USA orient.";
  if (slug === "america_centrale") return "am. centr.";
  if (slug === "territori_nordovest") return "terr. n.o.";
  if (slug === "nuova_guinea") return "n. guinea";
  if (slug === "medio_oriente") return "medio or.";
  return parole[0]!;
}
