/**
 * Schermata 3: Registrazione attiva.
 *
 * Una volta entrati, parte:
 * - La registrazione video (servizio registratore)
 * - L'ascolto dei lanci dei dadi (servizio GoDice già connesso)
 *
 * L'utente vede:
 * - Timer crescente della registrazione
 * - Contatore di eventi BLE catturati
 * - Stato dei 6 dadi (connessi/disconnessi)
 * - Bottone STOP rosso prominente
 *
 * Quando l'utente preme STOP:
 * - Ferma la registrazione → ottieni `RisultatoRegistrazione`
 * - Salva nel contesto
 * - Naviga a `Riepilogo`
 *
 * Edge case gestiti:
 * - Disconnessione di un dado durante la partita: mostra warning ma
 *   non blocca la registrazione (la review umana sistemerà)
 * - Errore camera: ferma BLE, mostra errore, suggerisce ripristino
 */

import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { usaPartita } from "@/contesto/partita";
import { ottieniServizioGoDice } from "@/servizi/godice";
import { ottieniRegistratore } from "@/servizi/registratore";
import { colori, raggi, spazi, tipografia } from "@/tema";
import type { ConfigurazioneGoDado, RuoloDado } from "@/tipi";

import type { ParametriRotteApp } from "../navigazione";

type Navigazione = NativeStackNavigationProp<ParametriRotteApp, "Registrazione">;

export function SchermataRegistrazione() {
  const navigation = useNavigation<Navigazione>();
  const partita = usaPartita();
  const servizioGoDice = ottieniServizioGoDice();
  const registratore = ottieniRegistratore();

  const [secondiTrascorsi, setSecondiTrascorsi] = useState(0);
  const [ultimoLancio, setUltimoLancio] = useState<{
    etichetta: string;
    valore: number;
  } | null>(null);
  const [statoDadi, setStatoDadi] = useState<Map<string, "connesso" | "disconnesso">>(
    () => {
      const m = new Map<string, "connesso" | "disconnesso">();
      partita.configurazioniDadi.forEach((c) => m.set(c.ble_id, "connesso"));
      return m;
    },
  );

  const tsInizioRef = useRef<Date | null>(null);
  const fermandoRef = useRef(false);

  // 1. Avvia registrazione + sottoscrivi a lanci/stato
  useEffect(() => {
    let unsubLanci: (() => void) | null = null;
    let unsubStato: (() => void) | null = null;
    let timerSecondi: ReturnType<typeof setInterval> | null = null;

    async function avvia() {
      try {
        const okPermessi = await registratore.verificaPermessi();
        if (!okPermessi) {
          Alert.alert(
            "Permessi negati",
            "Senza accesso a camera e microfono non posso registrare.",
          );
          navigation.goBack();
          return;
        }

        await registratore.avviaRegistrazione();
        const tsInizio = new Date();
        tsInizioRef.current = tsInizio;
        partita.setFasePartita("registrando");

        // Timer secondi (UI)
        timerSecondi = setInterval(() => {
          if (tsInizioRef.current) {
            const sec = Math.floor(
              (Date.now() - tsInizioRef.current.getTime()) / 1000,
            );
            setSecondiTrascorsi(sec);
          }
        }, 500);

        // Sottoscrive ai lanci
        unsubLanci = servizioGoDice.sottoscriviLanci((lancio) => {
          partita.aggiungiEvento({
            ts: lancio.ts.toISOString(),
            tipo: "dado_lanciato",
            ble_id: lancio.ble_id,
            ruolo: lancio.ruolo,
            slot: lancio.slot,
            valore: lancio.valore,
          });
          setUltimoLancio({
            etichetta:
              lancio.ruolo === "attaccante"
                ? `Att-${lancio.slot}`
                : `Dif-${lancio.slot}`,
            valore: lancio.valore,
          });
        });

        // Sottoscrive a cambi stato
        unsubStato = servizioGoDice.sottoscriviStato((ble_id, stato) => {
          if (stato === "errore") return;
          setStatoDadi((curr) => {
            const next = new Map(curr);
            next.set(ble_id, stato);
            return next;
          });

          if (stato === "disconnesso") {
            const cfg = partita.configurazioniDadi.find(
              (c) => c.ble_id === ble_id,
            );
            if (cfg) {
              partita.aggiungiEvento({
                ts: new Date().toISOString(),
                tipo: "connessione_persa",
                ble_id,
                ruolo: cfg.ruolo,
                slot: cfg.slot,
              });
            }
          }
        });
      } catch (e) {
        Alert.alert("Errore avvio registrazione", String(e));
        navigation.goBack();
      }
    }

    avvia();

    return () => {
      if (timerSecondi) clearInterval(timerSecondi);
      if (unsubLanci) unsubLanci();
      if (unsubStato) unsubStato();
    };
    // Solo all'ingresso/uscita della schermata.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function ferma() {
    if (fermandoRef.current) return;
    fermandoRef.current = true;

    try {
      // Logga stop registrazione
      partita.aggiungiEvento({
        ts: new Date().toISOString(),
        tipo: "stop_registrazione",
        motivo: "manuale",
      });

      const risultato = await registratore.fermaRegistrazione();
      partita.setRisultatoRegistrazione(risultato);
      partita.setFasePartita("completata");
      navigation.replace("Riepilogo");
    } catch (e) {
      fermandoRef.current = false;
      Alert.alert("Errore stop", String(e));
    }
  }

  function chiediConferma() {
    Alert.alert(
      "Fermare la registrazione?",
      "Tutti i dadi resteranno connessi. Potrai ricominciare una nuova partita dopo aver inviato questa.",
      [
        { text: "Annulla", style: "cancel" },
        { text: "Ferma", style: "destructive", onPress: ferma },
      ],
    );
  }

  const dadiAttaccante = partita.configurazioniDadi.filter(
    (c) => c.ruolo === "attaccante",
  );
  const dadiDifensore = partita.configurazioniDadi.filter(
    (c) => c.ruolo === "difensore",
  );

  return (
    <SafeAreaView style={stili.contenitore} edges={["top", "bottom", "left", "right"]}>
      {/* Pallino REC + timer */}
      <View style={stili.intestazione}>
        <View style={stili.rigaRec}>
          <View style={stili.pallinoRec} />
          <Text style={stili.testoRec}>REC</Text>
        </View>
        <Text style={stili.timer}>{formattaSecondi(secondiTrascorsi)}</Text>
      </View>

      {/* Stato dadi */}
      <View style={stili.gruppoSezioni}>
        <SezioneDadi
          ruolo="attaccante"
          dadi={dadiAttaccante}
          statoMap={statoDadi}
        />
        <SezioneDadi
          ruolo="difensore"
          dadi={dadiDifensore}
          statoMap={statoDadi}
        />
      </View>

      {/* Contatori e ultimo lancio */}
      <View style={stili.metriche}>
        <View style={stili.metricaCella}>
          <Text style={stili.metricaValore}>{partita.numeroEventi}</Text>
          <Text style={stili.metricaLabel}>Eventi</Text>
        </View>
        <View style={stili.divisoreVerticale} />
        <View style={stili.metricaCella}>
          {ultimoLancio ? (
            <>
              <Text style={stili.metricaValore}>{ultimoLancio.valore}</Text>
              <Text style={stili.metricaLabel}>{ultimoLancio.etichetta}</Text>
            </>
          ) : (
            <>
              <Text style={[stili.metricaValore, { color: colori.inchiostroFioco }]}>
                —
              </Text>
              <Text style={stili.metricaLabel}>Nessun lancio</Text>
            </>
          )}
        </View>
      </View>

      <View style={{ flex: 1 }} />

      {/* Bottone stop */}
      <Pressable
        onPress={chiediConferma}
        style={({ pressed }) => [
          stili.botStop,
          pressed && { transform: [{ scale: 0.97 }] },
        ]}
      >
        <View style={stili.iconaStop} />
        <Text style={stili.testoStop}>Ferma registrazione</Text>
      </Pressable>
    </SafeAreaView>
  );
}

function SezioneDadi({
  ruolo,
  dadi,
  statoMap,
}: {
  ruolo: RuoloDado;
  dadi: ConfigurazioneGoDado[];
  statoMap: Map<string, "connesso" | "disconnesso">;
}) {
  const coloreSezione =
    ruolo === "attaccante" ? colori.scarlatto : colori.navale;
  return (
    <View style={stili.sezioneDadi}>
      <Text style={[stili.titoloSezioneDadi, { color: coloreSezione }]}>
        {ruolo === "attaccante" ? "Attaccante" : "Difensore"}
      </Text>
      <View style={stili.rigaPallini}>
        {dadi.map((d) => {
          const stato = statoMap.get(d.ble_id) ?? "connesso";
          const connesso = stato === "connesso";
          return (
            <View
              key={d.ble_id}
              style={[
                stili.pallinoDado,
                {
                  backgroundColor: connesso ? coloreSezione : colori.pergamenaScura,
                  borderColor: connesso ? coloreSezione : colori.lineaForte,
                },
              ]}
            >
              <Text
                style={[
                  stili.pallinoDadoTesto,
                  { color: connesso ? "white" : colori.inchiostroFioco },
                ]}
              >
                {d.slot}
              </Text>
            </View>
          );
        })}
      </View>
    </View>
  );
}

function formattaSecondi(s: number): string {
  const ore = Math.floor(s / 3600);
  const min = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (ore > 0) {
    return `${ore}:${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }
  return `${min}:${String(sec).padStart(2, "0")}`;
}

const stili = StyleSheet.create({
  contenitore: {
    flex: 1,
    backgroundColor: colori.pergamena,
    paddingHorizontal: spazi.l,
  },
  intestazione: {
    alignItems: "center",
    paddingTop: spazi.m,
    paddingBottom: spazi.l,
  },
  rigaRec: {
    flexDirection: "row",
    alignItems: "center",
    gap: spazi.xs,
    marginBottom: spazi.s,
  },
  pallinoRec: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: colori.scarlatto,
  },
  testoRec: {
    fontSize: 12,
    fontWeight: "700",
    color: colori.scarlatto,
    letterSpacing: 2,
  },
  timer: {
    fontFamily: tipografia.fontMono,
    fontSize: 56,
    fontWeight: "300",
    color: colori.inchiostro,
    letterSpacing: 2,
  },
  gruppoSezioni: {
    gap: spazi.m,
    marginBottom: spazi.l,
  },
  sezioneDadi: {
    backgroundColor: colori.pergamenaChiara,
    borderRadius: raggi.medio,
    borderWidth: 1,
    borderColor: colori.linea,
    padding: spazi.m,
  },
  titoloSezioneDadi: {
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 2,
    textTransform: "uppercase",
    marginBottom: spazi.s,
  },
  rigaPallini: {
    flexDirection: "row",
    gap: spazi.s,
    justifyContent: "flex-start",
  },
  pallinoDado: {
    width: 44,
    height: 44,
    borderRadius: 22,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
  },
  pallinoDadoTesto: {
    fontSize: 18,
    fontWeight: "700",
  },
  metriche: {
    flexDirection: "row",
    backgroundColor: colori.pergamenaChiara,
    borderRadius: raggi.medio,
    borderWidth: 1,
    borderColor: colori.linea,
    paddingVertical: spazi.l,
  },
  metricaCella: {
    flex: 1,
    alignItems: "center",
  },
  metricaValore: {
    fontFamily: tipografia.fontSerif,
    fontSize: 40,
    fontWeight: "700",
    color: colori.inchiostro,
  },
  metricaLabel: {
    fontSize: 11,
    color: colori.inchiostroTenue,
    letterSpacing: 1.5,
    textTransform: "uppercase",
    marginTop: spazi.xs,
  },
  divisoreVerticale: {
    width: 1,
    backgroundColor: colori.linea,
  },
  botStop: {
    backgroundColor: colori.scarlatto,
    paddingVertical: spazi.l,
    borderRadius: raggi.medio,
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "center",
    gap: spazi.s,
    marginBottom: spazi.m,
  },
  iconaStop: {
    width: 16,
    height: 16,
    backgroundColor: "white",
    borderRadius: 2,
  },
  testoStop: {
    color: "white",
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 2,
    textTransform: "uppercase",
  },
});
