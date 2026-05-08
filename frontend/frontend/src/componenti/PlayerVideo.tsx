/**
 * Player video custom basato su HTML5 `<video>`.
 *
 * Sfrutta lo streaming HTTP Range esposto dal backend per permettere il
 * seeking senza scaricare tutto il file. Mostra timestamp corrente,
 * durata, e supporta callback `onSecondoCambia` per sincronizzare la
 * timeline degli eventi.
 *
 * Lo styling segue l'estetica cartografica: niente controlli nativi,
 * UI minimale con icone Lucide.
 */

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";
import { Pause, Play, RotateCcw, Volume2, VolumeX } from "lucide-react";

interface ProprietaPlayerVideo {
  urlStream: string;
  durataSec: number;
  onSecondoCambia?: (sec: number) => void;
}

export interface RiferimentoPlayerVideo {
  saltaA: (secondo: number) => void;
  pausa: () => void;
  riproduci: () => void;
}

export const PlayerVideo = forwardRef<RiferimentoPlayerVideo, ProprietaPlayerVideo>(
  function PlayerVideo({ urlStream, durataSec, onSecondoCambia }, ref) {
    const elementoVideo = useRef<HTMLVideoElement | null>(null);
    const [inRiproduzione, setInRiproduzione] = useState(false);
    const [secondoCorrente, setSecondoCorrente] = useState(0);
    const [muto, setMuto] = useState(true);

    useImperativeHandle(ref, () => ({
      saltaA: (secondo: number) => {
        if (elementoVideo.current) {
          elementoVideo.current.currentTime = secondo;
        }
      },
      pausa: () => elementoVideo.current?.pause(),
      riproduci: () => elementoVideo.current?.play(),
    }));

    useEffect(() => {
      const v = elementoVideo.current;
      if (!v) return;
      const onTime = () => {
        setSecondoCorrente(v.currentTime);
        onSecondoCambia?.(v.currentTime);
      };
      const onPlay = () => setInRiproduzione(true);
      const onPause = () => setInRiproduzione(false);

      v.addEventListener("timeupdate", onTime);
      v.addEventListener("play", onPlay);
      v.addEventListener("pause", onPause);
      return () => {
        v.removeEventListener("timeupdate", onTime);
        v.removeEventListener("play", onPlay);
        v.removeEventListener("pause", onPause);
      };
    }, [onSecondoCambia]);

    function alternaRiproduzione() {
      const v = elementoVideo.current;
      if (!v) return;
      if (v.paused) v.play();
      else v.pause();
    }

    function alternaMuto() {
      const v = elementoVideo.current;
      if (!v) return;
      v.muted = !v.muted;
      setMuto(v.muted);
    }

    function gestisciScrub(evento: React.ChangeEvent<HTMLInputElement>) {
      const sec = Number(evento.target.value);
      if (elementoVideo.current) {
        elementoVideo.current.currentTime = sec;
      }
    }

    return (
      <div className="bg-inchiostro relative">
        <video
          ref={elementoVideo}
          src={urlStream}
          muted={muto}
          playsInline
          preload="metadata"
          className="w-full max-h-[60vh] block bg-inchiostro"
          onClick={alternaRiproduzione}
        />

        {/* Barra controlli sotto al video */}
        <div className="bg-inchiostro text-pergamena px-4 py-3 flex items-center gap-3 border-t border-pergamena/10">
          <button
            type="button"
            onClick={alternaRiproduzione}
            className="p-1.5 hover:text-scarlatto transition-colors"
            aria-label={inRiproduzione ? "Pausa" : "Riproduci"}
          >
            {inRiproduzione ? <Pause size={18} /> : <Play size={18} />}
          </button>

          <button
            type="button"
            onClick={() => {
              if (elementoVideo.current) elementoVideo.current.currentTime = 0;
            }}
            className="p-1.5 hover:text-scarlatto transition-colors"
            aria-label="Vai all'inizio"
          >
            <RotateCcw size={16} />
          </button>

          <span className="font-mono text-xs num-tab tabular-nums whitespace-nowrap">
            {formatoTempo(secondoCorrente)}
          </span>

          <input
            type="range"
            min={0}
            max={durataSec || 1}
            step={0.1}
            value={secondoCorrente}
            onChange={gestisciScrub}
            className="flex-1 accent-scarlatto cursor-pointer"
            aria-label="Posizione video"
          />

          <span className="font-mono text-xs num-tab text-pergamena/60 whitespace-nowrap">
            {formatoTempo(durataSec)}
          </span>

          <button
            type="button"
            onClick={alternaMuto}
            className="p-1.5 hover:text-scarlatto transition-colors"
            aria-label={muto ? "Riattiva audio" : "Muta"}
          >
            {muto ? <VolumeX size={16} /> : <Volume2 size={16} />}
          </button>
        </div>
      </div>
    );
  },
);

/** "01:23:45" o "23:45" se sotto l'ora. */
function formatoTempo(secondiTotali: number): string {
  if (!Number.isFinite(secondiTotali) || secondiTotali < 0) return "00:00";
  const ore = Math.floor(secondiTotali / 3600);
  const minuti = Math.floor((secondiTotali % 3600) / 60);
  const secondi = Math.floor(secondiTotali % 60);
  const mm = String(minuti).padStart(2, "0");
  const ss = String(secondi).padStart(2, "0");
  if (ore > 0) {
    const hh = String(ore).padStart(2, "0");
    return `${hh}:${mm}:${ss}`;
  }
  return `${mm}:${ss}`;
}
