/**
 * Contesto React per lo stato della partita "in corso".
 *
 * Lo stato vive in memoria mentre l'app è in foreground. Viene resettato
 * dopo l'upload o l'eliminazione esplicita.
 *
 * Cosa NON sta qui: la cronologia degli upload (vive in MMKV via
 * `storageLocale.ts`). Quel codice è già persistente.
 */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import type {
  ConfigurazioneGoDado,
  Giocatore,
  RigaEventoJsonl,
} from "@/tipi";

import type { RisultatoRegistrazione } from "@/servizi/registratore";

interface ContestoPartitaValore {
  // === Setup ===
  giocatori: Giocatore[];
  setGiocatori: (g: Giocatore[]) => void;
  luogo: string | null;
  setLuogo: (l: string | null) => void;
  note: string | null;
  setNote: (n: string | null) => void;
  configurazioniDadi: ConfigurazioneGoDado[];
  setConfigurazioniDadi: (c: ConfigurazioneGoDado[]) => void;
  partita_id_locale: string;

  // === Stato ===
  fasePartita: "setup" | "registrando" | "completata";
  setFasePartita: (f: "setup" | "registrando" | "completata") => void;

  // === Eventi raccolti ===
  /** Aggiunge un evento alla lista (operazione idempotente per ts duplicati). */
  aggiungiEvento: (evento: RigaEventoJsonl) => void;
  /** Numero corrente di eventi raccolti. */
  numeroEventi: number;
  /** Ritorna l'array completo (snapshot in quel momento). */
  ottieniEventi: () => RigaEventoJsonl[];

  // === Risultato registrazione ===
  risultatoRegistrazione: RisultatoRegistrazione | null;
  setRisultatoRegistrazione: (r: RisultatoRegistrazione | null) => void;

  // === Reset ===
  resetPartita: () => void;
}

const ContestoPartita = createContext<ContestoPartitaValore | null>(null);

export function ProvenanzaPartita({ children }: { children: ReactNode }) {
  const [giocatori, setGiocatori] = useState<Giocatore[]>([]);
  const [luogo, setLuogo] = useState<string | null>("Il Gufo · Roma");
  const [note, setNote] = useState<string | null>(null);
  const [configurazioniDadi, setConfigurazioniDadi] = useState<
    ConfigurazioneGoDado[]
  >([]);
  const [fasePartita, setFasePartita] = useState<
    "setup" | "registrando" | "completata"
  >("setup");
  const [risultatoRegistrazione, setRisultatoRegistrazione] =
    useState<RisultatoRegistrazione | null>(null);

  // Eventi: usiamo un ref per evitare re-render a ogni evento BLE
  // (potenzialmente decine al secondo se i dadi sono attivi).
  // Esponiamo un contatore reattivo separato per la UI.
  const eventiRef = useRef<RigaEventoJsonl[]>([]);
  const [numeroEventi, setNumeroEventi] = useState(0);

  const partita_id_locale = useMemo(() => generaUuid(), []);

  const aggiungiEvento = useCallback((evento: RigaEventoJsonl) => {
    eventiRef.current.push(evento);
    setNumeroEventi(eventiRef.current.length);
  }, []);

  const ottieniEventi = useCallback(() => {
    return [...eventiRef.current];
  }, []);

  const resetPartita = useCallback(() => {
    setGiocatori([]);
    setLuogo("Il Gufo · Roma");
    setNote(null);
    setConfigurazioniDadi([]);
    setFasePartita("setup");
    setRisultatoRegistrazione(null);
    eventiRef.current = [];
    setNumeroEventi(0);
  }, []);

  const valore: ContestoPartitaValore = {
    giocatori,
    setGiocatori,
    luogo,
    setLuogo,
    note,
    setNote,
    configurazioniDadi,
    setConfigurazioniDadi,
    partita_id_locale,
    fasePartita,
    setFasePartita,
    aggiungiEvento,
    numeroEventi,
    ottieniEventi,
    risultatoRegistrazione,
    setRisultatoRegistrazione,
    resetPartita,
  };

  return (
    <ContestoPartita.Provider value={valore}>
      {children}
    </ContestoPartita.Provider>
  );
}

export function usaPartita(): ContestoPartitaValore {
  const v = useContext(ContestoPartita);
  if (!v) {
    throw new Error(
      "usaPartita() deve stare dentro <ProvenanzaPartita>",
    );
  }
  return v;
}

// === Helper UUID ===

/**
 * UUID v4 minimale (compatibile RFC 4122). Non usiamo `crypto.randomUUID`
 * perché su React Native vecchio non è sempre disponibile. Per la nostra
 * unicità (partita_id_locale) basta `Math.random` + timestamp.
 */
function generaUuid(): string {
  const ts = Date.now().toString(16);
  const rand = () =>
    Math.floor(Math.random() * 0xffff)
      .toString(16)
      .padStart(4, "0");
  return `${ts}-${rand()}-4${rand().slice(1)}-${rand()}-${rand()}${rand()}${rand()}`;
}
