/**
 * Schermata 2: Configurazione GoDice.
 *
 * Flusso:
 * 1. Scan BLE → mostra dadi scoperti con RSSI
 * 2. Per ognuno dei 6 slot canonici (Att-1/2/3, Dif-1/2/3) l'utente
 *    associa un dado scoperto (selezione dal pool degli scoperti)
 * 3. Una volta tutti e 6 associati, "Test lancio" verifica che ogni
 *    dado emetta un valore correttamente
 * 4. "Conferma e torna indietro" salva la configurazione nel contesto
 *
 * NOTA: usa lo `StubGoDice` di default (scopre 6 dadi finti
 * istantaneamente). In produzione, sostituire con `GoDiceBlePlx`.
 */

import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { usaPartita } from "@/contesto/partita";
import { ottieniServizioGoDice, StubGoDice } from "@/servizi/godice";
import { colori, raggi, spazi, tipografia } from "@/tema";
import {
  etichettaDado,
  type ConfigurazioneGoDado,
  type RuoloDado,
} from "@/tipi";

import type { ParametriRotteApp } from "../navigazione";

type Navigazione = NativeStackNavigationProp<ParametriRotteApp, "Dadi">;

interface DadoScoperto {
  ble_id: string;
  nome: string;
  rssi: number;
}

interface SlotConfig {
  ruolo: RuoloDado;
  slot: 1 | 2 | 3;
  ble_id_associato: string | null;
  /** Ultimo valore letto durante test, se mai. */
  valore_test: number | null;
}

const SLOTS_CANONICI: Array<Pick<SlotConfig, "ruolo" | "slot">> = [
  { ruolo: "attaccante", slot: 1 },
  { ruolo: "attaccante", slot: 2 },
  { ruolo: "attaccante", slot: 3 },
  { ruolo: "difensore", slot: 1 },
  { ruolo: "difensore", slot: 2 },
  { ruolo: "difensore", slot: 3 },
];

export function SchermataDadi() {
  const navigation = useNavigation<Navigazione>();
  const partita = usaPartita();
  const servizio = ottieniServizioGoDice();

  const [scoperti, setScoperti] = useState<DadoScoperto[]>([]);
  const [scanInCorso, setScanInCorso] = useState(false);

  const [slots, setSlots] = useState<SlotConfig[]>(() =>
    SLOTS_CANONICI.map((s) => {
      // Se la partita ha già una configurazione precedente, riprendila
      const esistente = partita.configurazioniDadi.find(
        (c) => c.ruolo === s.ruolo && c.slot === s.slot,
      );
      return {
        ruolo: s.ruolo,
        slot: s.slot,
        ble_id_associato: esistente?.ble_id ?? null,
        valore_test: null,
      };
    }),
  );

  const tuttiAssociati = slots.every((s) => s.ble_id_associato !== null);
  const idAssociati = useMemo(
    () => new Set(slots.map((s) => s.ble_id_associato).filter(Boolean) as string[]),
    [slots],
  );

  // Sottoscrive ai lanci per il test
  useEffect(() => {
    const unsubscribe = servizio.sottoscriviLanci((lancio) => {
      setSlots((curr) =>
        curr.map((s) =>
          s.ble_id_associato === lancio.ble_id
            ? { ...s, valore_test: lancio.valore }
            : s,
        ),
      );
    });
    return unsubscribe;
  }, [servizio]);

  async function avviaScan() {
    setScoperti([]);
    setScanInCorso(true);
    try {
      await servizio.avviaScan((dado) => {
        setScoperti((curr) => {
          if (curr.some((d) => d.ble_id === dado.ble_id)) return curr;
          return [
            ...curr,
            {
              ble_id: dado.ble_id,
              nome: dado.nome_advertised ?? "GoDice",
              rssi: dado.rssi,
            },
          ];
        });
      });
    } catch (e) {
      Alert.alert("Errore scan", String(e));
    } finally {
      setScanInCorso(false);
    }
  }

  async function associa(slotIdx: number, ble_id: string) {
    const slot = slots[slotIdx];
    if (!slot) return;

    // Disconnette eventuale dado precedente in questo slot
    if (slot.ble_id_associato) {
      try {
        await servizio.disconnettiDado(slot.ble_id_associato);
      } catch {
        // ignora errori di disconnect, andiamo avanti
      }
    }

    const cfg: ConfigurazioneGoDado = {
      ble_id,
      ruolo: slot.ruolo,
      slot: slot.slot,
      etichetta: etichettaDado(slot.ruolo, slot.slot),
    };

    try {
      await servizio.connettiDado(cfg);
      setSlots((curr) =>
        curr.map((s, i) =>
          i === slotIdx
            ? { ...s, ble_id_associato: ble_id, valore_test: null }
            : s,
        ),
      );
    } catch (e) {
      Alert.alert("Errore connessione", String(e));
    }
  }

  async function rimuoviAssociazione(slotIdx: number) {
    const slot = slots[slotIdx];
    if (!slot?.ble_id_associato) return;
    try {
      await servizio.disconnettiDado(slot.ble_id_associato);
    } catch {
      // ignora
    }
    setSlots((curr) =>
      curr.map((s, i) =>
        i === slotIdx
          ? { ...s, ble_id_associato: null, valore_test: null }
          : s,
      ),
    );
  }

  function testLancioTutti() {
    // Per lo stub: forza un lancio simulato su ogni dado connesso.
    if (servizio instanceof StubGoDice) {
      servizio
        .dadiCorrenti()
        .filter((d) => d.stato_connessione === "connesso")
        .forEach((d) => {
          servizio.iniettaLancioSimulato({
            ble_id: d.configurazione.ble_id,
            valore: 1 + Math.floor(Math.random() * 6),
          });
        });
    } else {
      Alert.alert(
        "Test lancio",
        "Lancia ogni dado fisico per verificare la connessione. Il valore apparirà accanto al dado.",
      );
    }
  }

  function conferma() {
    if (!tuttiAssociati) {
      Alert.alert("Mancano dadi", "Devi associare tutti e 6 i dadi.");
      return;
    }
    const cfgs: ConfigurazioneGoDado[] = slots.map((s) => ({
      ble_id: s.ble_id_associato!,
      ruolo: s.ruolo,
      slot: s.slot,
      etichetta: etichettaDado(s.ruolo, s.slot),
    }));
    partita.setConfigurazioniDadi(cfgs);
    navigation.goBack();
  }

  return (
    <SafeAreaView style={stili.contenitore} edges={["bottom", "left", "right"]}>
      <ScrollView contentContainerStyle={stili.scrollBody}>
        <View style={stili.intestazione}>
          <Text style={stili.etichetta}>Configurazione</Text>
          <Text style={stili.titolo}>
            6 <Text style={stili.titoloAccento}>GoDice</Text>
          </Text>
          <Text style={stili.descrizione}>
            3 dadi attaccante, 3 dadi difensore. I dadi stanno fissi al centro
            del tavolo: chi attacca prende gli attaccante, chi difende i
            difensore.
          </Text>
        </View>

        {/* Sezione scan */}
        <View style={stili.sezione}>
          <View style={stili.righTitoloSezione}>
            <Text style={stili.etichettaSezione}>Dadi rilevati</Text>
            <Pressable
              onPress={avviaScan}
              disabled={scanInCorso}
              style={({ pressed }) => [
                stili.botSecondario,
                scanInCorso && stili.disabilitato,
                pressed && stili.premuto,
              ]}
            >
              {scanInCorso ? (
                <ActivityIndicator size="small" color={colori.inchiostro} />
              ) : (
                <Text style={stili.testoBotSecondario}>
                  {scoperti.length === 0 ? "Avvia scan" : "Riavvia scan"}
                </Text>
              )}
            </Pressable>
          </View>

          {scoperti.length === 0 && !scanInCorso ? (
            <Text style={stili.testoVuoto}>
              Tocca "Avvia scan" per cercare i GoDice nelle vicinanze.
            </Text>
          ) : null}

          {scoperti.map((d) => (
            <View key={d.ble_id} style={stili.rigaScoperto}>
              <View style={{ flex: 1 }}>
                <Text style={stili.nomeScoperto}>{d.nome}</Text>
                <Text style={stili.idScoperto}>{d.ble_id}</Text>
              </View>
              <Text style={stili.rssi}>{d.rssi} dBm</Text>
              {idAssociati.has(d.ble_id) ? (
                <Text style={stili.giaUsato}>✓ Usato</Text>
              ) : null}
            </View>
          ))}
        </View>

        {/* Sezione slots */}
        <View style={stili.sezione}>
          <Text style={stili.etichettaSezione}>Slot dadi</Text>
          {slots.map((s, idx) => (
            <RigaSlot
              key={`${s.ruolo}-${s.slot}`}
              slot={s}
              scoperti={scoperti}
              idAssociati={idAssociati}
              onAssocia={(ble_id) => associa(idx, ble_id)}
              onRimuovi={() => rimuoviAssociazione(idx)}
            />
          ))}
        </View>

        {tuttiAssociati ? (
          <Pressable
            onPress={testLancioTutti}
            style={({ pressed }) => [
              stili.botSecondario,
              { alignSelf: "stretch", marginBottom: spazi.m },
              pressed && stili.premuto,
            ]}
          >
            <Text style={stili.testoBotSecondario}>Test lancio</Text>
          </Pressable>
        ) : null}

        <Pressable
          onPress={conferma}
          disabled={!tuttiAssociati}
          style={({ pressed }) => [
            stili.botPrimario,
            !tuttiAssociati && stili.disabilitato,
            pressed && stili.premuto,
          ]}
        >
          <Text style={stili.testoBotPrimario}>Conferma configurazione</Text>
        </Pressable>

        <View style={{ height: spazi.xxl }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function RigaSlot({
  slot,
  scoperti,
  idAssociati,
  onAssocia,
  onRimuovi,
}: {
  slot: SlotConfig;
  scoperti: DadoScoperto[];
  idAssociati: Set<string>;
  onAssocia: (ble_id: string) => void;
  onRimuovi: () => void;
}) {
  const [aperto, setAperto] = useState(false);
  const associato = slot.ble_id_associato !== null;
  const coloreSlot =
    slot.ruolo === "attaccante" ? colori.scarlatto : colori.navale;

  return (
    <View style={[stili.cartaSlot, associato && stili.cartaSlotAssociato]}>
      <View style={stili.intestazioneSlot}>
        <View style={[stili.badgeRuolo, { backgroundColor: coloreSlot }]}>
          <Text style={stili.badgeRuoloTesto}>
            {etichettaDado(slot.ruolo, slot.slot)}
          </Text>
        </View>
        <View style={{ flex: 1, marginLeft: spazi.m }}>
          {associato ? (
            <>
              <Text style={stili.idAssociato}>{slot.ble_id_associato}</Text>
              {slot.valore_test !== null ? (
                <Text style={stili.valoreTest}>
                  Ultimo valore: {slot.valore_test}
                </Text>
              ) : (
                <Text style={stili.testoNonTestato}>Non testato</Text>
              )}
            </>
          ) : (
            <Text style={stili.testoNonAssociato}>Nessun dado associato</Text>
          )}
        </View>
        {associato ? (
          <Pressable onPress={onRimuovi} style={stili.botRimuoviSlot}>
            <Text style={stili.testoRimuovi}>×</Text>
          </Pressable>
        ) : (
          <Pressable
            onPress={() => setAperto(!aperto)}
            disabled={scoperti.length === 0}
            style={[
              stili.botSecondarioMini,
              scoperti.length === 0 && stili.disabilitato,
            ]}
          >
            <Text style={stili.testoBotSecondarioMini}>
              {aperto ? "Chiudi" : "Associa"}
            </Text>
          </Pressable>
        )}
      </View>

      {aperto && !associato ? (
        <View style={stili.elencoScelte}>
          {scoperti
            .filter((d) => !idAssociati.has(d.ble_id))
            .map((d) => (
              <Pressable
                key={d.ble_id}
                onPress={() => {
                  setAperto(false);
                  onAssocia(d.ble_id);
                }}
                style={({ pressed }) => [
                  stili.scelta,
                  pressed && stili.premuto,
                ]}
              >
                <Text style={stili.sceltaNome}>{d.nome}</Text>
                <Text style={stili.sceltaId}>{d.ble_id}</Text>
              </Pressable>
            ))}
          {scoperti.filter((d) => !idAssociati.has(d.ble_id)).length === 0 ? (
            <Text style={stili.testoVuoto}>
              Nessun dado disponibile. Avvia uno scan.
            </Text>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

const stili = StyleSheet.create({
  contenitore: { flex: 1, backgroundColor: colori.pergamena },
  scrollBody: { padding: spazi.l },
  intestazione: { marginBottom: spazi.l },
  etichetta: {
    fontSize: 11,
    letterSpacing: 2.5,
    color: colori.scarlatto,
    textTransform: "uppercase",
    fontWeight: "600",
  },
  titolo: {
    fontFamily: tipografia.fontSerif,
    fontSize: 36,
    fontWeight: "900",
    color: colori.inchiostro,
    marginTop: spazi.s,
    letterSpacing: -1,
  },
  titoloAccento: { color: colori.scarlatto, fontStyle: "italic" },
  descrizione: {
    marginTop: spazi.s,
    fontSize: 13,
    color: colori.inchiostroTenue,
    lineHeight: 20,
  },
  sezione: { marginBottom: spazi.l },
  righTitoloSezione: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spazi.m,
  },
  etichettaSezione: {
    fontSize: 11,
    letterSpacing: 2.5,
    color: colori.inchiostroTenue,
    textTransform: "uppercase",
    fontWeight: "600",
  },
  testoVuoto: {
    fontSize: 13,
    color: colori.inchiostroFioco,
    fontStyle: "italic",
    paddingVertical: spazi.m,
  },
  rigaScoperto: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spazi.s,
    borderBottomWidth: 1,
    borderBottomColor: colori.linea,
    gap: spazi.s,
  },
  nomeScoperto: {
    fontSize: 14,
    color: colori.inchiostro,
    fontWeight: "600",
  },
  idScoperto: {
    fontFamily: tipografia.fontMono,
    fontSize: 11,
    color: colori.inchiostroFioco,
  },
  rssi: {
    fontFamily: tipografia.fontMono,
    fontSize: 11,
    color: colori.inchiostroTenue,
  },
  giaUsato: { fontSize: 11, color: colori.successo, fontWeight: "600" },
  cartaSlot: {
    backgroundColor: colori.pergamenaChiara,
    borderRadius: raggi.medio,
    borderWidth: 1,
    borderColor: colori.linea,
    padding: spazi.m,
    marginBottom: spazi.s,
  },
  cartaSlotAssociato: { borderColor: colori.successo },
  intestazioneSlot: { flexDirection: "row", alignItems: "center" },
  badgeRuolo: {
    paddingHorizontal: spazi.s,
    paddingVertical: spazi.xs,
    borderRadius: raggi.piccolo,
    minWidth: 56,
  },
  badgeRuoloTesto: {
    color: "white",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1,
    textAlign: "center",
  },
  idAssociato: {
    fontFamily: tipografia.fontMono,
    fontSize: 12,
    color: colori.inchiostro,
  },
  valoreTest: { fontSize: 12, color: colori.successo, marginTop: 2 },
  testoNonTestato: { fontSize: 12, color: colori.inchiostroFioco, marginTop: 2 },
  testoNonAssociato: {
    fontSize: 13,
    color: colori.inchiostroFioco,
    fontStyle: "italic",
  },
  botRimuoviSlot: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  testoRimuovi: {
    fontSize: 24,
    color: colori.inchiostroFioco,
    fontWeight: "300",
    lineHeight: 24,
  },
  botSecondarioMini: {
    paddingHorizontal: spazi.s,
    paddingVertical: spazi.xs,
    borderWidth: 1,
    borderColor: colori.linea,
    borderRadius: raggi.piccolo,
  },
  testoBotSecondarioMini: {
    fontSize: 11,
    color: colori.inchiostro,
    fontWeight: "600",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  elencoScelte: { marginTop: spazi.s, gap: 4 },
  scelta: {
    paddingHorizontal: spazi.m,
    paddingVertical: spazi.s,
    backgroundColor: colori.pergamena,
    borderRadius: raggi.piccolo,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  sceltaNome: { fontSize: 14, color: colori.inchiostro },
  sceltaId: {
    fontFamily: tipografia.fontMono,
    fontSize: 11,
    color: colori.inchiostroFioco,
  },
  botPrimario: {
    backgroundColor: colori.inchiostro,
    paddingVertical: spazi.m,
    borderRadius: raggi.medio,
    alignItems: "center",
    marginTop: spazi.l,
  },
  testoBotPrimario: {
    color: colori.pergamena,
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 2,
    textTransform: "uppercase",
  },
  botSecondario: {
    paddingHorizontal: spazi.m,
    paddingVertical: spazi.s,
    borderWidth: 1,
    borderColor: colori.linea,
    borderRadius: raggi.piccolo,
    alignItems: "center",
  },
  testoBotSecondario: {
    fontSize: 12,
    color: colori.inchiostro,
    fontWeight: "600",
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  disabilitato: { opacity: 0.4 },
  premuto: { opacity: 0.7 },
});
