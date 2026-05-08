/**
 * Hook React `useReplay` per controllare una Timeline.
 *
 * Esposizione minimale:
 *   - `idx`            indice corrente nella timeline (-1..lunghezza-1)
 *   - `stato`          stato della partita all'idx corrente
 *   - `eventoCorrente` evento all'idx (null per idx === -1)
 *   - `vai(i)`         jump a indice
 *   - `avanti()`       idx + 1 (clamp)
 *   - `indietro()`     idx - 1 (clamp)
 *   - `vaiInizio()`    idx = -1
 *   - `vaiFine()`      idx = lunghezza - 1
 *   - `inPlay`         true se autoplay attivo
 *   - `play()` / `pausa()` / `togglePlay()`
 *   - `velocitaMs`     intervallo ms tra eventi in autoplay
 *   - `setVelocitaMs(ms)`
 *
 * Niente UI qui — è agnostico al render. Il componente PlayerReplay sotto
 * ne è uno consumatore d'esempio.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { creaTimeline, type Timeline } from "../timeline.js";
import type { StatoPartita } from "../stato.js";
import type { BundleReplay, EventoValidato } from "@risiko/eventi-schema";

export interface OpzioniUseReplay {
  /** Indice di partenza. Default -1 (pre-eventi). */
  idxIniziale?: number;
  /** Velocità autoplay in ms. Default 1500. */
  velocitaInizialeMs?: number;
  /** Cache size della Timeline. Default 50. */
  cacheSize?: number;
}

export interface ReplayController {
  readonly timeline: Timeline;
  readonly idx: number;
  readonly stato: StatoPartita;
  readonly eventoCorrente: EventoValidato | null;
  readonly lunghezza: number;
  readonly inPlay: boolean;
  readonly velocitaMs: number;
  readonly puoAvanti: boolean;
  readonly puoIndietro: boolean;

  vai(i: number): void;
  avanti(): void;
  indietro(): void;
  vaiInizio(): void;
  vaiFine(): void;
  play(): void;
  pausa(): void;
  togglePlay(): void;
  setVelocitaMs(ms: number): void;
}

export function useReplay(
  bundle: BundleReplay,
  opzioni: OpzioniUseReplay = {},
): ReplayController {
  const timeline = useMemo(
    () => creaTimeline(bundle, { cacheMaxSize: opzioni.cacheSize ?? 50 }),
    [bundle, opzioni.cacheSize],
  );
  const lunghezza = timeline.lunghezza;
  const idxMin = -1;
  const idxMax = lunghezza - 1;

  const idxInitClamped = clamp(
    opzioni.idxIniziale ?? -1,
    idxMin,
    Math.max(idxMin, idxMax),
  );
  const [idx, setIdx] = useState<number>(idxInitClamped);
  const [inPlay, setInPlay] = useState<boolean>(false);
  const [velocitaMs, _setVelocitaMs] = useState<number>(
    opzioni.velocitaInizialeMs ?? 1500,
  );

  // Reset quando cambia il bundle (cambia anche timeline → memoization).
  useEffect(() => {
    setIdx(idxInitClamped);
    setInPlay(false);
    // idxInitClamped dipende solo da opzioni; non vogliamo loop, quindi lo
    // calcoliamo una sola volta al cambio bundle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bundle]);

  // Autoplay: timer che incrementa idx finché c'è dove andare.
  const idxRef = useRef(idx);
  idxRef.current = idx;
  useEffect(() => {
    if (!inPlay) return;
    if (idx >= idxMax) {
      setInPlay(false);
      return;
    }
    const timer = setTimeout(() => {
      setIdx((prev) => {
        const next = prev + 1;
        return next > idxMax ? idxMax : next;
      });
    }, velocitaMs);
    return () => clearTimeout(timer);
  }, [inPlay, idx, idxMax, velocitaMs]);

  const stato = useMemo(() => timeline.statoAlIndice(idx), [timeline, idx]);
  const eventoCorrente = useMemo(
    () => timeline.eventoAlIndice(idx),
    [timeline, idx],
  );

  const vai = useCallback(
    (i: number) => {
      const c = clamp(i, idxMin, idxMax);
      setIdx(c);
    },
    [idxMax],
  );
  const avanti = useCallback(() => setIdx((p) => Math.min(idxMax, p + 1)), [
    idxMax,
  ]);
  const indietro = useCallback(
    () => setIdx((p) => Math.max(idxMin, p - 1)),
    [],
  );
  const vaiInizio = useCallback(() => setIdx(idxMin), []);
  const vaiFine = useCallback(() => setIdx(idxMax), [idxMax]);
  const play = useCallback(() => setInPlay(true), []);
  const pausa = useCallback(() => setInPlay(false), []);
  const togglePlay = useCallback(() => setInPlay((p) => !p), []);
  const setVelocitaMs = useCallback((ms: number) => {
    _setVelocitaMs(Math.max(50, ms));
  }, []);

  return {
    timeline,
    idx,
    stato,
    eventoCorrente,
    lunghezza,
    inPlay,
    velocitaMs,
    puoAvanti: idx < idxMax,
    puoIndietro: idx > idxMin,
    vai,
    avanti,
    indietro,
    vaiInizio,
    vaiFine,
    play,
    pausa,
    togglePlay,
    setVelocitaMs,
  };
}

function clamp(n: number, min: number, max: number): number {
  if (max < min) return min;
  if (n < min) return min;
  if (n > max) return max;
  return n;
}
