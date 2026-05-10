/**
 * Player video multi-segmento.
 *
 * I bundle dell'app mobile (M14) producono N segmenti mp4 separati
 * (Vision Camera ruota ogni 10 minuti per resilienza ai crash). Il
 * modello SQL `Partita` ha `video: list[Video]`, quindi una partita
 * promossa da bundle ha N record video, non uno.
 *
 * Questo componente presenta gli N segmenti come UN UNICO video al
 * consumer:
 * - `secondoGlobale = 0` corrisponde all'inizio del primo segmento
 * - `secondoGlobale = durataTotale` corrisponde alla fine dell'ultimo
 * - autoplay del segmento successivo quando il corrente finisce
 * - `saltaA(secondoGlobale)` calcola quale segmento + offset locale
 * - `onSecondoCambia(secondoGlobale)` propaga il tempo cumulativo per
 *   sincronizzare la timeline eventi
 *
 * Funziona anche con N=1: in quel caso si comporta come `PlayerVideo`
 * legacy. Per questo si puo' usare come drop-in replacement.
 *
 * Limiti:
 * - Il "salto" tra segmenti ha una micro-pausa di ~100-300ms (loading
 *   del nuovo file mp4). Per UX migliore si potrebbe pre-caricare il
 *   segmento successivo in un secondo `<video>` nascosto, ma per ora
 *   quello che abbiamo basta.
 * - Niente MediaSource Extensions (HLS): se in futuro vorremo seek
 *   istantaneo tra segmenti, conviene generare playlist m3u8 lato
 *   backend e usare hls.js.
 */

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  ChevronLeft,
  ChevronRight,
  Pause,
  Play,
  RotateCcw,
  Volume2,
  VolumeX,
} from "lucide-react";

export interface SegmentoVideoPlayer {
  id: string;
  urlStream: string;
  durataSec: number;
  /** Etichetta opzionale per UI (es. "seg 1/4", "20:00 → 20:10"). */
  etichetta?: string;
}

interface ProprietaPlayer {
  segmenti: SegmentoVideoPlayer[];
  /** Callback con il tempo cumulativo dall'inizio del primo segmento. */
  onSecondoCambia?: (secondoGlobale: number) => void;
}

export interface RiferimentoPlayerVideoMultiSegmento {
  /** Salta a un secondo globale (cumulativo, dall'inizio del primo segmento). */
  saltaA: (secondoGlobale: number) => void;
  pausa: () => void;
  riproduci: () => void;
}

export const PlayerVideoMultiSegmento = forwardRef<
  RiferimentoPlayerVideoMultiSegmento,
  ProprietaPlayer
>(function PlayerVideoMultiSegmento({ segmenti, onSecondoCambia }, ref) {
  const elementoVideo = useRef<HTMLVideoElement | null>(null);
  const [indiceCorrente, setIndiceCorrente] = useState(0);
  const [secondoLocale, setSecondoLocale] = useState(0);
  const [inRiproduzione, setInRiproduzione] = useState(false);
  const [muto, setMuto] = useState(true);

  // Offsets cumulativi: offsets[i] = somma delle durate dei segmenti 0..i-1
  const offsets = useMemo(() => {
    const acc: number[] = [0];
    for (const s of segmenti) acc.push(acc[acc.length - 1]! + s.durataSec);
    return acc;
  }, [segmenti]);

  const durataTotale = offsets[offsets.length - 1] ?? 0;
  const segmentoCorrente = segmenti[indiceCorrente];

  /** Trova il segmento che contiene un certo `secondoGlobale`. */
  const trovaSegmento = useCallback(
    (secondoGlobale: number): { indice: number; offsetLocale: number } => {
      // clamp
      const t = Math.max(0, Math.min(durataTotale, secondoGlobale));
      // binary-style scan: i segmenti sono pochi (max 15-20 per partita 2.5h)
      for (let i = segmenti.length - 1; i >= 0; i--) {
        if (t >= offsets[i]!) {
          return { indice: i, offsetLocale: t - offsets[i]! };
        }
      }
      return { indice: 0, offsetLocale: 0 };
    },
    [segmenti, offsets, durataTotale],
  );

  /** Tempo globale corrente. */
  const secondoGlobale = (offsets[indiceCorrente] ?? 0) + secondoLocale;

  // Notifica il consumer ad ogni cambio di tempo globale
  useEffect(() => {
    onSecondoCambia?.(secondoGlobale);
  }, [secondoGlobale, onSecondoCambia]);

  // Imperative handle per saltare/play/pause da fuori
  useImperativeHandle(ref, () => ({
    saltaA: (secondoGlobale: number) => {
      const { indice, offsetLocale } = trovaSegmento(secondoGlobale);
      if (indice !== indiceCorrente) {
        setIndiceCorrente(indice);
        // dopo il render, useEffect sotto applica l'offset locale
        offsetLocaleDopoSwitch.current = offsetLocale;
      } else if (elementoVideo.current) {
        elementoVideo.current.currentTime = offsetLocale;
      }
    },
    pausa: () => elementoVideo.current?.pause(),
    riproduci: () => {
      void elementoVideo.current?.play();
    },
  }));

  // Quando il segmento cambia, applichiamo l'offset locale memorizzato
  // (per gestire saltaA cross-segmento)
  const offsetLocaleDopoSwitch = useRef<number>(0);
  useEffect(() => {
    const v = elementoVideo.current;
    if (!v) return;
    const onMeta = () => {
      v.currentTime = offsetLocaleDopoSwitch.current;
      offsetLocaleDopoSwitch.current = 0;
    };
    v.addEventListener("loadedmetadata", onMeta);
    return () => v.removeEventListener("loadedmetadata", onMeta);
  }, [indiceCorrente]);

  // Listener video standard
  useEffect(() => {
    const v = elementoVideo.current;
    if (!v) return;
    const onTime = () => setSecondoLocale(v.currentTime);
    const onPlay = () => setInRiproduzione(true);
    const onPause = () => setInRiproduzione(false);
    const onEnded = () => {
      // Auto-avanza al segmento successivo, se esiste
      if (indiceCorrente < segmenti.length - 1) {
        offsetLocaleDopoSwitch.current = 0;
        setIndiceCorrente((i) => i + 1);
        // mantieni in riproduzione
        // (loadedmetadata callback farà il play se serve)
      } else {
        setInRiproduzione(false);
      }
    };
    v.addEventListener("timeupdate", onTime);
    v.addEventListener("play", onPlay);
    v.addEventListener("pause", onPause);
    v.addEventListener("ended", onEnded);
    return () => {
      v.removeEventListener("timeupdate", onTime);
      v.removeEventListener("play", onPlay);
      v.removeEventListener("pause", onPause);
      v.removeEventListener("ended", onEnded);
    };
  }, [indiceCorrente, segmenti.length]);

  // Quando passiamo a un nuovo segmento, se eravamo in play continua
  useEffect(() => {
    const v = elementoVideo.current;
    if (!v) return;
    if (inRiproduzione && indiceCorrente > 0) {
      // Auto-play del segmento successivo (richiesta browser-driven)
      void v.play().catch(() => {
        // browser potrebbe bloccare se l'utente non ha interagito
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [indiceCorrente]);

  function alternaRiproduzione() {
    const v = elementoVideo.current;
    if (!v) return;
    if (v.paused) void v.play();
    else v.pause();
  }

  function alternaMuto() {
    const v = elementoVideo.current;
    if (!v) return;
    v.muted = !v.muted;
    setMuto(v.muted);
  }

  function rewind10s() {
    const v = elementoVideo.current;
    if (!v) return;
    v.currentTime = Math.max(0, v.currentTime - 10);
  }

  function vaiSegmentoPrec() {
    if (indiceCorrente > 0) {
      offsetLocaleDopoSwitch.current = 0;
      setIndiceCorrente((i) => i - 1);
    }
  }

  function vaiSegmentoSucc() {
    if (indiceCorrente < segmenti.length - 1) {
      offsetLocaleDopoSwitch.current = 0;
      setIndiceCorrente((i) => i + 1);
    }
  }

  function gestisciClickTimeline(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const frazione = Math.max(0, Math.min(1, x / rect.width));
    const target = frazione * durataTotale;
    const { indice, offsetLocale } = trovaSegmento(target);
    if (indice !== indiceCorrente) {
      offsetLocaleDopoSwitch.current = offsetLocale;
      setIndiceCorrente(indice);
    } else if (elementoVideo.current) {
      elementoVideo.current.currentTime = offsetLocale;
    }
  }

  if (segmenti.length === 0) {
    return (
      <div className="aspect-video bg-inchiostro/5 rounded-md flex items-center justify-center text-inchiostro-tenue">
        Nessun video disponibile per questa partita.
      </div>
    );
  }

  return (
    <div className="bg-inchiostro rounded-md overflow-hidden">
      <div className="relative aspect-video">
        <video
          ref={elementoVideo}
          src={segmentoCorrente?.urlStream}
          className="w-full h-full object-contain"
          playsInline
          muted={muto}
        />
      </div>

      {/* Timeline */}
      <div className="px-4 pt-3 pb-2">
        <div
          className="h-2 bg-pergamena/20 rounded-full cursor-pointer relative overflow-hidden"
          onClick={gestisciClickTimeline}
        >
          {/* Marker dei boundary tra segmenti */}
          {segmenti.length > 1
            ? offsets.slice(1, -1).map((off, i) => (
                <div
                  key={i}
                  className="absolute top-0 bottom-0 w-px bg-pergamena/40"
                  style={{ left: `${(off / durataTotale) * 100}%` }}
                />
              ))
            : null}
          {/* Progress */}
          <div
            className="absolute top-0 left-0 bottom-0 bg-scarlatto"
            style={{ width: `${(secondoGlobale / durataTotale) * 100}%` }}
          />
        </div>
      </div>

      {/* Controlli */}
      <div className="px-4 pb-3 flex items-center gap-2 text-pergamena">
        <button
          type="button"
          onClick={alternaRiproduzione}
          className="p-1.5 hover:bg-pergamena/10 rounded transition-colors"
          aria-label={inRiproduzione ? "Pausa" : "Play"}
        >
          {inRiproduzione ? (
            <Pause className="size-5" />
          ) : (
            <Play className="size-5" />
          )}
        </button>
        <button
          type="button"
          onClick={rewind10s}
          className="p-1.5 hover:bg-pergamena/10 rounded transition-colors"
          aria-label="Indietro 10s"
        >
          <RotateCcw className="size-4" />
        </button>

        {segmenti.length > 1 ? (
          <>
            <div className="w-px h-5 bg-pergamena/20 mx-1" />
            <button
              type="button"
              onClick={vaiSegmentoPrec}
              disabled={indiceCorrente === 0}
              className="p-1.5 hover:bg-pergamena/10 rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Segmento precedente"
            >
              <ChevronLeft className="size-5" />
            </button>
            <span className="text-xs font-mono tabular-nums px-1">
              seg {indiceCorrente + 1}/{segmenti.length}
            </span>
            <button
              type="button"
              onClick={vaiSegmentoSucc}
              disabled={indiceCorrente >= segmenti.length - 1}
              className="p-1.5 hover:bg-pergamena/10 rounded transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              aria-label="Segmento successivo"
            >
              <ChevronRight className="size-5" />
            </button>
          </>
        ) : null}

        <span className="text-xs font-mono tabular-nums ml-2">
          {formattaTempo(secondoGlobale)} / {formattaTempo(durataTotale)}
        </span>

        <div className="flex-1" />

        <button
          type="button"
          onClick={alternaMuto}
          className="p-1.5 hover:bg-pergamena/10 rounded transition-colors"
          aria-label={muto ? "Riattiva audio" : "Muto"}
        >
          {muto ? <VolumeX className="size-4" /> : <Volume2 className="size-4" />}
        </button>
      </div>
    </div>
  );
});

function formattaTempo(secondi: number): string {
  const totSec = Math.floor(secondi);
  const h = Math.floor(totSec / 3600);
  const m = Math.floor((totSec % 3600) / 60);
  const s = totSec % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}
