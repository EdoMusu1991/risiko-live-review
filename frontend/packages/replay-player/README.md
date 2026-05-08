# @risiko/replay-player

Viewer replay "out of the box" per Risiko classico EG.

Combina `@risiko/replay-lib` (motore stato) + `@risiko/map-classico` (mappa
SVG) in un singolo componente React. Dato un `BundleReplay`, mostra: header
metadati + mappa + narrative + scrubber + autoplay con preset velocità.

## Uso minimo

```tsx
import { RisikoReplayPlayer, importaBundleDaUrl } from "@risiko/replay-player";

function ReplayView({ partitaId }: { partitaId: string }) {
  const [bundle, setBundle] = useState(null);

  useEffect(() => {
    importaBundleDaUrl(`/api/partite/${partitaId}/esporta?formato=replay`)
      .then((r) => setBundle(r.bundle));
  }, [partitaId]);

  if (!bundle) return <p>Caricamento…</p>;
  return <RisikoReplayPlayer bundle={bundle} />;
}
```

## API completa

```tsx
<RisikoReplayPlayer
  bundle={bundle}                           // BundleReplay obbligatorio
  
  // Hooks per integrazioni esterne
  onCursorChange={(ts_evento, idx, ev) => ...}
  onStatoCambia={(stato) => ...}
  onTerritorioClick={(nome) => ...}
  
  // Configurazione iniziale
  idxIniziale={-1}                          // default -1
  velocitaInizialeMs={1500}                 // default 1500
  
  // Visibilità sezioni
  mostraHeader={true}                       // default true
  mostraNarrative={true}                    // default true
  mostraLegenda={true}                      // default true
  
  // Selezione territorio (alone scarlatto pulsante)
  territorioSelezionato={null}
/>
```

## Sync video (scope C)

Il player espone un riferimento imperativo per il controllo esterno:

```tsx
import { useRef } from "react";
import { RisikoReplayPlayer, type RiferimentoRisikoReplayPlayer } from "@risiko/replay-player";

function ReplayConVideo({ bundle, videoRef }) {
  const replayRef = useRef<RiferimentoRisikoReplayPlayer>(null);
  
  // Quando il replay scrolla, muovi il video
  const handleCursorChange = useCallback((ts_evento: string | null) => {
    if (!ts_evento) return;
    const offsetSec = (
      new Date(ts_evento).getTime() - new Date(bundle.partita.data_inizio).getTime()
    ) / 1000;
    videoRef.current?.saltaA(offsetSec);
  }, [bundle, videoRef]);

  // Quando il video scorre, muovi il replay
  const handleSecondoVideoCambia = useCallback((sec: number) => {
    const tsTarget = new Date(bundle.partita.data_inizio).getTime() + sec * 1000;
    // trova l'evento col ts più vicino, e fai replayRef.current?.vai(idx)
    // (helper utility nella prossima fase)
  }, [bundle]);

  return (
    <>
      <PlayerVideo ref={videoRef} onSecondoCambia={handleSecondoVideoCambia} />
      <RisikoReplayPlayer
        ref={replayRef}
        bundle={bundle}
        onCursorChange={handleCursorChange}
      />
    </>
  );
}
```

## Composizione customizzata

Se vuoi i tuoi propri controlli ma riusare la mappa+motore:

```tsx
import { useReplay } from "@risiko/replay-player";
import { MappaRisikoClassico } from "@risiko/map-classico";

function CustomViewer({ bundle }) {
  const r = useReplay(bundle);
  return (
    <>
      <MappaRisikoClassico
        territori={adattaTerritori(r.stato)}
        giocatori={adattaGiocatori(r.stato)}
      />
      <MyOwnControls onPlay={r.play} onPause={r.pausa} />
    </>
  );
}
```

(Helpers `adattaTerritori` e `adattaGiocatori` sono interni al player; se ne
serve l'export, segnalalo.)

## Test

```bash
npm run test:run    # test su narrative + smoke su sync delle adattazioni
```
